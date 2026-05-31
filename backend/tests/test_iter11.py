"""ITER-11 tests: pay rates, timesheet approval, earnings, reports.

New endpoints:
- PUT  /api/admin/workers/{id}/pay
- PUT  /api/gigs/{gig_id}/acceptances/{acceptance_id}/pay
- POST /api/gigs/{gig_id}/acceptances/{acceptance_id}/approve-timesheet
- POST /api/gigs/{gig_id}/acceptances/{acceptance_id}/unapprove-timesheet
- GET  /api/admin/reports/timesheets
- GET  /api/admin/reports/timesheets.csv
- POST /api/admin/reports/export-google-sheets (only error-path tested)
- GET  /api/me/earnings
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient


def _load_backend_url() -> str:
    env_path = "/app/frontend/.env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")


def _load_mongo_url() -> tuple[str, str]:
    mongo_url = None
    db_name = None
    env_path = "/app/backend/.env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("MONGO_URL="):
                    mongo_url = line.split("=", 1)[1].strip().strip('"')
                if line.startswith("DB_NAME="):
                    db_name = line.split("=", 1)[1].strip().strip('"')
    if not mongo_url or not db_name:
        raise RuntimeError("MONGO_URL / DB_NAME not configured")
    return mongo_url, db_name


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PASSWORD = "HcobAdmin2026!"
MONGO_URL, DB_NAME = _load_mongo_url()


def _db():
    return MongoClient(MONGO_URL)[DB_NAME]


# --------------------------- helpers ---------------------------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


def _register_worker(prefix="iter11"):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"TEST_{prefix}_{uuid.uuid4().hex[:8]}@ex.com"
    r = s.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": "Worker123!",
            "name": f"Iter11 {prefix}",
            "phone": "+15550001111",
            "role": "worker",
        },
    )
    assert r.status_code == 200, r.text
    me = s.get(f"{API}/auth/me").json()
    return s, email, me["user_id"]


def _create_gig(admin_sess, slots=2, pay_rate=20, pay_type="hourly", title_suffix=""):
    payload = {
        "title": f"TEST_iter11_{title_suffix or uuid.uuid4().hex[:6]}",
        "description": "iter11 gig",
        "category": "cleaning",
        "location": "Pay St, 94110",
        "address_line": "1 Pay Ave, SF CA 94110",
        "scheduled_date": "2026-12-05",
        "pay_rate": pay_rate,
        "pay_type": pay_type,
        "slots": slots,
    }
    r = admin_sess.post(f"{API}/gigs", json=payload)
    assert r.status_code == 200, r.text
    return r.json()["gig_id"]


def _assign(admin_sess, gid, uid):
    r = admin_sess.post(f"{API}/gigs/{gid}/assign", json={"worker_id": uid})
    assert r.status_code == 200, r.text
    return r.json()["acceptance_id"]


def _force_clock(acceptance_id, hours=2.0):
    """Bypass real clock-in waiting by writing both timestamps directly.
    clock_out_at is set so server-side recompute works on subsequent endpoints.
    """
    now = datetime.now(timezone.utc)
    cin = (now - timedelta(hours=hours)).isoformat()
    cout = now.isoformat()
    _db().gig_acceptances.update_one(
        {"acceptance_id": acceptance_id},
        {
            "$set": {
                "clock_in_at": cin,
                "clock_out_at": cout,
                "hours_worked": hours,
                "status": "completed",
                "timesheet_approved": False,
            }
        },
    )
    return cin, cout


def _get_acc(gid, aid, admin_sess):
    g = admin_sess.get(f"{API}/gigs/{gid}").json()
    for a in g.get("acceptances", []):
        if a["acceptance_id"] == aid:
            return a
    return None


# --------------------------- Tests ---------------------------
class TestWorkerDefaultPay:
    def test_set_and_clear_default_pay(self, admin_session):
        _, _, uid = _register_worker("dp")
        # set
        r = admin_session.put(
            f"{API}/admin/workers/{uid}/pay",
            json={"default_pay_rate": 22.5, "default_pay_type": "hourly"},
        )
        assert r.status_code == 200, r.text
        w = admin_session.get(f"{API}/admin/workers/{uid}").json()
        assert w["default_pay_rate"] == 22.5
        assert w["default_pay_type"] == "hourly"

        # clear
        r = admin_session.put(
            f"{API}/admin/workers/{uid}/pay",
            json={"clear_rate": True, "clear_type": True},
        )
        assert r.status_code == 200
        w = admin_session.get(f"{API}/admin/workers/{uid}").json()
        assert w.get("default_pay_rate") is None
        assert w.get("default_pay_type") is None

    def test_pay_negative_rejected(self, admin_session):
        _, _, uid = _register_worker("neg")
        r = admin_session.put(
            f"{API}/admin/workers/{uid}/pay",
            json={"default_pay_rate": -5},
        )
        assert r.status_code == 400

    def test_pay_unknown_worker_404(self, admin_session):
        r = admin_session.put(
            f"{API}/admin/workers/nope_xyz/pay",
            json={"default_pay_rate": 20, "default_pay_type": "hourly"},
        )
        assert r.status_code == 404


class TestResolvePayPrecedence:
    """per-gig override > worker default > gig posted."""

    def test_gig_posted_when_no_overrides(self, admin_session):
        gid = _create_gig(admin_session, slots=2, pay_rate=17, pay_type="hourly", title_suffix="posted")
        _, _, uid = _register_worker("rp1")
        aid = _assign(admin_session, gid, uid)
        _force_clock(aid, hours=2.0)
        # Trigger pay recomputation by setting clear-only override (no change → won't recompute earnings)
        # Easier: just hit approve-timesheet which uses snapshot. But snapshot was bypassed by _force_clock.
        # So instead, set an "override" then clear it to engage recompute. Simpler: use my_earnings via worker session.
        # Cleanest: call set_acceptance_pay_override no-op then check fields.
        # However recompute path only triggers when set_ops/unset_ops set. Use clear_rate=True.
        admin_session.put(f"{API}/gigs/{gid}/acceptances/{aid}/pay", json={"clear_rate": True})
        a = _get_acc(gid, aid, admin_session)
        assert a is not None
        # gig posted rate
        assert a.get("pay_rate_effective") == 17.0
        assert a.get("pay_type_effective") == "hourly"
        assert a.get("earnings") == round(17.0 * 2.0, 2)
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_worker_default_overrides_gig_posted(self, admin_session):
        gid = _create_gig(admin_session, slots=2, pay_rate=17, pay_type="hourly", title_suffix="wd")
        _, _, uid = _register_worker("rp2")
        admin_session.put(
            f"{API}/admin/workers/{uid}/pay",
            json={"default_pay_rate": 25, "default_pay_type": "hourly"},
        )
        aid = _assign(admin_session, gid, uid)
        _force_clock(aid, hours=3.0)
        admin_session.put(f"{API}/gigs/{gid}/acceptances/{aid}/pay", json={"clear_rate": True})
        a = _get_acc(gid, aid, admin_session)
        assert a["pay_rate_effective"] == 25.0
        assert a["earnings"] == round(25.0 * 3.0, 2)
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_per_gig_override_wins(self, admin_session):
        gid = _create_gig(admin_session, slots=2, pay_rate=17, pay_type="hourly", title_suffix="ov")
        _, _, uid = _register_worker("rp3")
        admin_session.put(
            f"{API}/admin/workers/{uid}/pay",
            json={"default_pay_rate": 25, "default_pay_type": "hourly"},
        )
        aid = _assign(admin_session, gid, uid)
        _force_clock(aid, hours=2.5)
        r = admin_session.put(
            f"{API}/gigs/{gid}/acceptances/{aid}/pay",
            json={"pay_rate_override": 40, "pay_type_override": "hourly"},
        )
        assert r.status_code == 200, r.text
        a = _get_acc(gid, aid, admin_session)
        assert a["pay_rate_effective"] == 40.0
        # Override invalidates a prior approval and recomputes earnings
        assert a["earnings"] == round(40.0 * 2.5, 2)
        assert a.get("timesheet_approved") in (False, None)
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_flat_pay_independent_of_hours(self, admin_session):
        gid = _create_gig(admin_session, slots=1, pay_rate=100, pay_type="flat", title_suffix="flat")
        _, _, uid = _register_worker("rp4")
        aid = _assign(admin_session, gid, uid)
        _force_clock(aid, hours=7.5)
        admin_session.put(f"{API}/gigs/{gid}/acceptances/{aid}/pay", json={"clear_rate": True})
        a = _get_acc(gid, aid, admin_session)
        assert a["pay_type_effective"] == "flat"
        assert a["earnings"] == 100.0  # ignores hours
        admin_session.delete(f"{API}/gigs/{gid}")


class TestClockOutSnapshot:
    """Real clock-in + clock-out path snapshots pay & earnings."""

    def test_clock_out_snapshots_pay_and_earnings(self, admin_session):
        gid = _create_gig(admin_session, slots=1, pay_rate=18, pay_type="hourly", title_suffix="cosnap")
        ws, _, uid = _register_worker("cosnap")
        aid = _assign(admin_session, gid, uid)
        # Real clock-in via API
        r1 = ws.post(f"{API}/gigs/{gid}/clock-in")
        assert r1.status_code == 200, r1.text
        # Backdate clock_in so clock_out produces measurable hours
        _db().gig_acceptances.update_one(
            {"acceptance_id": aid},
            {"$set": {"clock_in_at": (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()}},
        )
        r2 = ws.post(f"{API}/gigs/{gid}/clock-out")
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["hours_worked"] >= 3.9
        assert body["pay_rate_applied"] == 18.0
        assert body["earnings"] == round(18.0 * body["hours_worked"], 2)
        # Verify persisted snapshot
        a = _get_acc(gid, aid, admin_session)
        assert a["pay_rate_applied"] == 18.0
        assert a["pay_type_applied"] == "hourly"
        assert a.get("timesheet_approved") in (False, None)
        admin_session.delete(f"{API}/gigs/{gid}")


class TestTimesheetApproval:
    def test_approve_unapprove_cycle(self, admin_session):
        gid = _create_gig(admin_session, slots=1, pay_rate=20, title_suffix="apr")
        ws, _, uid = _register_worker("apr")
        aid = _assign(admin_session, gid, uid)
        _force_clock(aid, hours=2.0)
        # Approve
        r = admin_session.post(
            f"{API}/gigs/{gid}/acceptances/{aid}/approve-timesheet", json={}
        )
        assert r.status_code == 200, r.text
        assert r.json()["timesheet_approved"] is True
        # Worker should receive notification
        notes = ws.get(f"{API}/notifications").json()
        assert any("Timesheet approved" in (n.get("title") or "") for n in notes)
        # Unapprove
        r = admin_session.post(
            f"{API}/gigs/{gid}/acceptances/{aid}/unapprove-timesheet"
        )
        assert r.status_code == 200
        a = _get_acc(gid, aid, admin_session)
        assert a.get("timesheet_approved") in (False, None)
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_approve_requires_clock_out(self, admin_session):
        gid = _create_gig(admin_session, slots=1, title_suffix="noco")
        _, _, uid = _register_worker("noco")
        aid = _assign(admin_session, gid, uid)
        # No clock-out
        r = admin_session.post(
            f"{API}/gigs/{gid}/acceptances/{aid}/approve-timesheet", json={}
        )
        assert r.status_code == 400
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_approve_with_hours_correction(self, admin_session):
        gid = _create_gig(admin_session, slots=1, pay_rate=20, title_suffix="hcorr")
        _, _, uid = _register_worker("hcorr")
        aid = _assign(admin_session, gid, uid)
        _force_clock(aid, hours=2.0)
        # First seed pay snapshot
        admin_session.put(f"{API}/gigs/{gid}/acceptances/{aid}/pay", json={"clear_rate": True})
        # Approve with hours correction (e.g., admin trims to 1.5h)
        r = admin_session.post(
            f"{API}/gigs/{gid}/acceptances/{aid}/approve-timesheet",
            json={"hours_worked": 1.5},
        )
        assert r.status_code == 200
        a = _get_acc(gid, aid, admin_session)
        assert a["hours_worked"] == 1.5
        # earnings recomputed using snapshot rate (20)
        assert a["earnings"] == round(20 * 1.5, 2)
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_approve_with_manual_earnings(self, admin_session):
        gid = _create_gig(admin_session, slots=1, pay_rate=20, title_suffix="manuern")
        _, _, uid = _register_worker("manuern")
        aid = _assign(admin_session, gid, uid)
        _force_clock(aid, hours=2.0)
        r = admin_session.post(
            f"{API}/gigs/{gid}/acceptances/{aid}/approve-timesheet",
            json={"earnings": 99.99},
        )
        assert r.status_code == 200
        a = _get_acc(gid, aid, admin_session)
        assert a["earnings"] == 99.99
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_override_after_approval_invalidates(self, admin_session):
        gid = _create_gig(admin_session, slots=1, pay_rate=20, title_suffix="invl")
        _, _, uid = _register_worker("invl")
        aid = _assign(admin_session, gid, uid)
        _force_clock(aid, hours=2.0)
        admin_session.put(f"{API}/gigs/{gid}/acceptances/{aid}/pay", json={"clear_rate": True})
        r = admin_session.post(
            f"{API}/gigs/{gid}/acceptances/{aid}/approve-timesheet", json={}
        )
        assert r.status_code == 200
        # Now apply override → must reset timesheet_approved
        admin_session.put(
            f"{API}/gigs/{gid}/acceptances/{aid}/pay",
            json={"pay_rate_override": 50, "pay_type_override": "hourly"},
        )
        a = _get_acc(gid, aid, admin_session)
        assert a.get("timesheet_approved") in (False, None)
        assert a["earnings"] == round(50 * 2.0, 2)
        admin_session.delete(f"{API}/gigs/{gid}")


class TestWorkerEarningsGate:
    def test_my_earnings_excludes_pending(self, admin_session):
        gid = _create_gig(admin_session, slots=1, pay_rate=30, title_suffix="meg")
        ws, _, uid = _register_worker("meg")
        aid = _assign(admin_session, gid, uid)
        _force_clock(aid, hours=2.0)
        admin_session.put(f"{API}/gigs/{gid}/acceptances/{aid}/pay", json={"clear_rate": True})
        # Pending — not approved yet
        e = ws.get(f"{API}/me/earnings").json()
        assert e["approved"]["total_earnings"] == 0
        assert e["pending"]["count"] == 1
        assert e["pending"]["hours"] == 2.0
        # Approve
        admin_session.post(f"{API}/gigs/{gid}/acceptances/{aid}/approve-timesheet", json={})
        e2 = ws.get(f"{API}/me/earnings").json()
        assert e2["approved"]["total_earnings"] == 60.0
        assert e2["pending"]["count"] == 0
        assert len(e2["approved"]["rows"]) == 1
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_my_earnings_forbidden_for_admin(self, admin_session):
        r = admin_session.get(f"{API}/me/earnings")
        assert r.status_code == 403


class TestAdminReports:
    def test_reports_filters_and_totals(self, admin_session):
        gid = _create_gig(admin_session, slots=2, pay_rate=20, title_suffix="rep")
        _, _, uid = _register_worker("rep")
        aid = _assign(admin_session, gid, uid)
        _force_clock(aid, hours=2.0)
        admin_session.put(f"{API}/gigs/{gid}/acceptances/{aid}/pay", json={"clear_rate": True})
        # Unapproved row first
        r = admin_session.get(f"{API}/admin/reports/timesheets", params={"gig_id": gid})
        assert r.status_code == 200
        body = r.json()
        assert body["totals"]["rows"] == 1
        assert body["totals"]["hours"] == 2.0
        assert body["totals"]["earnings"] == 40.0
        assert body["totals"]["approved_earnings"] == 0.0
        # only_approved excludes
        r2 = admin_session.get(
            f"{API}/admin/reports/timesheets",
            params={"gig_id": gid, "only_approved": "true"},
        )
        assert r2.json()["totals"]["rows"] == 0
        # Approve & re-check
        admin_session.post(f"{API}/gigs/{gid}/acceptances/{aid}/approve-timesheet", json={})
        r3 = admin_session.get(f"{API}/admin/reports/timesheets", params={"gig_id": gid})
        assert r3.json()["totals"]["approved_earnings"] == 40.0
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_reports_worker_filter(self, admin_session):
        gid = _create_gig(admin_session, slots=2, pay_rate=15, title_suffix="wflt")
        _, _, uid = _register_worker("wflt")
        aid = _assign(admin_session, gid, uid)
        _force_clock(aid, hours=1.0)
        admin_session.put(f"{API}/gigs/{gid}/acceptances/{aid}/pay", json={"clear_rate": True})
        r = admin_session.get(f"{API}/admin/reports/timesheets", params={"worker_id": uid})
        body = r.json()
        assert all(row["worker_id"] == uid for row in body["rows"])
        assert body["totals"]["rows"] >= 1
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_reports_csv_download(self, admin_session):
        gid = _create_gig(admin_session, slots=1, pay_rate=12, title_suffix="csv")
        _, _, uid = _register_worker("csv")
        aid = _assign(admin_session, gid, uid)
        _force_clock(aid, hours=1.5)
        admin_session.put(f"{API}/gigs/{gid}/acceptances/{aid}/pay", json={"clear_rate": True})
        r = admin_session.get(f"{API}/admin/reports/timesheets.csv", params={"gig_id": gid})
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "text/csv" in ct
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd and ".csv" in cd
        text = r.text
        # Header row
        assert "Worker" in text and "Hours" in text and "Earnings" in text and "Timesheet approved" in text
        # Data row with our earnings
        assert "18.00" in text  # 12 * 1.5
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_reports_requires_admin(self, admin_session):
        ws, _, _ = _register_worker("noadm")
        r = ws.get(f"{API}/admin/reports/timesheets")
        assert r.status_code == 403


class TestGoogleSheetsExport:
    def test_export_400_when_not_configured(self, admin_session):
        # Ensure not configured (test env)
        s = admin_session.get(f"{API}/admin/settings").json()
        if s.get("google_sheets_ready"):
            pytest.skip("Google Sheets is configured in this env — cannot test error path")
        r = admin_session.post(
            f"{API}/admin/reports/export-google-sheets",
            json={"only_approved": False},
        )
        assert r.status_code == 400
        detail = (r.json().get("detail") or "").lower()
        assert "google" in detail or "service account" in detail

    def test_settings_exposes_gs_fields(self, admin_session):
        s = admin_session.get(f"{API}/admin/settings").json()
        assert "google_sheets_ready" in s
        assert "google_sheets_service_email" in s
        assert "google_sheets_share_email" in s


class TestAcceptanceEnrichedFields:
    def test_gig_detail_includes_pay_and_effective_fields(self, admin_session):
        gid = _create_gig(admin_session, slots=1, pay_rate=22, title_suffix="enr")
        _, _, uid = _register_worker("enr")
        admin_session.put(
            f"{API}/admin/workers/{uid}/pay",
            json={"default_pay_rate": 30, "default_pay_type": "hourly"},
        )
        aid = _assign(admin_session, gid, uid)
        g = admin_session.get(f"{API}/gigs/{gid}").json()
        a = next(x for x in g["acceptances"] if x["acceptance_id"] == aid)
        assert a["pay_rate_effective"] == 30.0
        assert a["pay_type_effective"] == "hourly"
        assert a.get("worker_default_pay_rate") == 30.0
        # Not clocked out yet → no earnings snapshot but projected should exist or be None gracefully
        # timesheet_approved is only set after clock-out; OK if absent here
        assert a.get("timesheet_approved") in (False, None) or "timesheet_approved" not in a
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_worker_detail_includes_pay_fields(self, admin_session):
        gid = _create_gig(admin_session, slots=1, pay_rate=22, title_suffix="wdt")
        _, _, uid = _register_worker("wdt")
        aid = _assign(admin_session, gid, uid)
        _force_clock(aid, hours=2.0)
        admin_session.put(f"{API}/gigs/{gid}/acceptances/{aid}/pay", json={"clear_rate": True})
        w = admin_session.get(f"{API}/admin/workers/{uid}").json()
        gigs = w.get("accepted_gigs") or w.get("gigs") or []
        assert len(gigs) >= 1
        row = gigs[0]
        # The key may be pay_rate_applied or pay_rate_effective depending on impl
        assert any(k in row for k in ("pay_rate_applied", "pay_rate_effective"))
        assert "earnings" in row or "projected_earnings" in row
        assert "timesheet_approved" in row
        admin_session.delete(f"{API}/gigs/{gid}")
