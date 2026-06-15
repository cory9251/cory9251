"""
Iter30 — Phase 3e backend modularization regression.

Validates the extraction of ALL admin endpoints into routes/admin.py
(~1,140 lines) and ALL reports endpoints into routes/reports.py (~1,070
lines). Pure refactor — zero behavioral change expected.

Covers, per the iter30 review-request:
  * /admin/workers list + filters
  * /admin/workers/match
  * /admin/workers/{id} detail
  * /admin/requests
  * /admin/workers/{id}/verify-id
  * PUT /admin/workers/{id}/profile partial update
  * approve/reject/suspend/reinstate transitions (session-kill where applicable)
  * /admin/workers/{id}/reset-password (worker)
  * /admin/users/{id}/reset-password (Owner-only)
  * DELETE /admin/workers/{id} cascade
  * /admin/stats KPI shape
  * PUT /admin/workers/{id}/pay defaults
  * PUT /gigs/{id}/acceptances/{aid}/pay override + earnings recompute
  * approve-timesheet / unapprove-timesheet
  * PUT /gigs/{id}/acceptances/{aid}/timesheet edits
  * /admin/reports/{workers,gigs,activity,earnings,blasts} shape
  * /admin/reports/timesheets + .csv variant
  * /admin/reports/{bogus} → 404
  * /admin/reports/export-google-sheets → 400 when SA JSON not configured
  * /me/earnings worker vs admin gating
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017").strip('"').strip("'")
DB_NAME = os.environ.get("DB_NAME", "test_database").strip('"').strip("'")

OWNER_EMAIL = "admin@hcobcleaners.com"
OWNER_PASSWORD = "HcobAdmin2026!"


def _db():
    return MongoClient(MONGO_URL)[DB_NAME]


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    return s


def _seed_verified_worker(extra=None):
    """Insert an approved, ID-verified worker directly in Mongo."""
    db = _db()
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    email = f"TEST_iter30_{uuid.uuid4().hex[:6]}@example.com"
    doc = {
        "user_id": user_id,
        "email": email,
        "name": f"Iter30 Worker {user_id[-6:]}",
        "role": "worker",
        "worker_status": "approved",
        "phone": "5551234567",
        "address": "100 Main St",
        "zip_code": "21201",
        "city": "Baltimore",
        "state": "MD",
        "date_of_birth": "1990-01-01",
        "tshirt_size": "L",
        "emergency_contact_name": "Mom",
        "emergency_contact_phone": "5559999999",
        "skills": ["cleaning"],
        "availability": ["weekdays"],
        "id_image_path": "test.png",
        "id_verified": True,
        "has_car": True,
        "experience_level": "intermediate",
        "auth_provider": "local",
        "password_hash": "$2b$12$dummy",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        doc.update(extra)
    db.users.insert_one(doc)
    return user_id, email


def _seed_acceptance(gig_id, worker_id, status="accepted", clocked_out=False, hours=2.0, pay_rate=25.0):
    db = _db()
    acc_id = f"acc_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "acceptance_id": acc_id,
        "gig_id": gig_id,
        "worker_id": worker_id,
        "status": status,
        "is_backup": False,
        "requested_at": now,
        "accepted_at": now,
    }
    if clocked_out:
        doc.update({
            "clock_in_at": now,
            "clock_out_at": now,
            "hours_worked": hours,
            "earnings": round(hours * pay_rate, 2),
            "pay_rate_applied": pay_rate,
            "pay_type_applied": "hourly",
            "status": "completed",
        })
    db.gig_acceptances.insert_one(doc)
    return acc_id


def _set_session_for_worker(user_id):
    db = _db()
    token = uuid.uuid4().hex
    db.sessions.insert_one({
        "session_token": token,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
    })
    return token


def _create_gig(admin_session, slots=1, pay_rate=25.0):
    payload = {
        "title": "TEST_iter30 Gig",
        "description": "Phase 3e admin/reports regression test gig",
        "location": "Baltimore, MD",
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=4)).isoformat(),
        "scheduled_date": "Wed Jun 19 · 9:00 AM",
        "pay_rate": pay_rate,
        "pay_type": "hourly",
        "slots": slots,
        "category": "cleaning",
    }
    r = admin_session.post(f"{API}/gigs", json=payload, timeout=20)
    assert r.status_code == 200, f"create gig failed: {r.status_code} {r.text}"
    return r.json()["gig_id"]


@pytest.fixture(scope="module")
def admin_session():
    return _login(OWNER_EMAIL, OWNER_PASSWORD)


# =========================================================================
# 1) ADMIN /workers list + filters
# =========================================================================
class TestAdminWorkers:
    def test_list_returns_array(self, admin_session):
        r = admin_session.get(f"{API}/admin/workers", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        # Some routes return a list, some return {workers: [...]}; tolerate both.
        workers = body if isinstance(body, list) else body.get("workers")
        assert isinstance(workers, list)

    def test_status_filter_pending(self, admin_session):
        r = admin_session.get(f"{API}/admin/workers", params={"status": "pending"}, timeout=20)
        assert r.status_code == 200
        body = r.json()
        workers = body if isinstance(body, list) else body.get("workers", [])
        for w in workers:
            assert w.get("worker_status") == "pending"

    def test_zip_prefix_filter(self, admin_session):
        # seed a known-zip worker so we can at least be sure the filter doesn't
        # crash and that our seed is returned when matched
        wid, _ = _seed_verified_worker({"zip_code": "21209"})
        try:
            r = admin_session.get(
                f"{API}/admin/workers", params={"zip_prefix": "212"}, timeout=20
            )
            assert r.status_code == 200
            body = r.json()
            workers = body if isinstance(body, list) else body.get("workers", [])
            assert any(w.get("user_id") == wid for w in workers)
        finally:
            _db().users.delete_one({"user_id": wid})

    def test_search_filter(self, admin_session):
        wid, email = _seed_verified_worker()
        try:
            # Search by the unique part of the email
            search_term = email.split("@")[0]
            r = admin_session.get(
                f"{API}/admin/workers", params={"search": search_term}, timeout=20
            )
            assert r.status_code == 200
            body = r.json()
            workers = body if isinstance(body, list) else body.get("workers", [])
            assert any(w.get("user_id") == wid for w in workers)
        finally:
            _db().users.delete_one({"user_id": wid})


# =========================================================================
# 2) ADMIN /workers/match
# =========================================================================
def test_workers_match_returns_list(admin_session):
    gid = _create_gig(admin_session)
    try:
        r = admin_session.get(f"{API}/admin/workers/match", params={"gig_id": gid}, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        # Tolerate either {"workers": [...]} or [...]
        workers = body if isinstance(body, list) else body.get("workers")
        assert isinstance(workers, list)
    finally:
        admin_session.delete(f"{API}/gigs/{gid}", timeout=20)


# =========================================================================
# 3) ADMIN /workers/{id} detail
# =========================================================================
def test_worker_detail_has_acceptances_and_rating(admin_session):
    wid, _ = _seed_verified_worker()
    try:
        r = admin_session.get(f"{API}/admin/workers/{wid}", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("user_id") == wid
        # The route returns enriched fields. Tolerate naming variants.
        accepted_key = next(
            (k for k in ("accepted_gigs", "acceptances", "gig_acceptances") if k in body),
            None,
        )
        assert accepted_key is not None, f"missing accepted-gigs list: keys={list(body)}"
        assert isinstance(body[accepted_key], list)
    finally:
        _db().users.delete_one({"user_id": wid})


# =========================================================================
# 4) ADMIN /requests
# =========================================================================
def test_admin_requests_queue(admin_session):
    r = admin_session.get(f"{API}/admin/requests", timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    rows = body if isinstance(body, list) else body.get("requests") or body.get("rows")
    assert isinstance(rows, list)


# =========================================================================
# 5-8) verify-id + profile update + status transitions + reset-password
# =========================================================================
class TestWorkerLifecycle:
    def test_verify_id(self, admin_session):
        wid, _ = _seed_verified_worker({"id_verified": False})
        try:
            r = admin_session.post(f"{API}/admin/workers/{wid}/verify-id", timeout=20)
            assert r.status_code == 200, r.text
            user = _db().users.find_one({"user_id": wid})
            assert user.get("id_verified") is True
        finally:
            _db().users.delete_one({"user_id": wid})

    def test_profile_partial_update(self, admin_session):
        wid, _ = _seed_verified_worker()
        try:
            r = admin_session.put(
                f"{API}/admin/workers/{wid}/profile",
                json={"admin_note": "iter30 note", "tshirt_size": "M"},
                timeout=20,
            )
            assert r.status_code == 200, r.text
            user = _db().users.find_one({"user_id": wid})
            assert user.get("admin_note") == "iter30 note"
            assert user.get("tshirt_size") == "M"
        finally:
            _db().users.delete_one({"user_id": wid})

    def test_approve_reject_suspend_reinstate(self, admin_session):
        wid, _ = _seed_verified_worker({"worker_status": "pending"})
        token = _set_session_for_worker(wid)
        db = _db()
        try:
            # approve
            r = admin_session.post(f"{API}/admin/workers/{wid}/approve", timeout=20)
            assert r.status_code == 200, r.text
            assert db.users.find_one({"user_id": wid})["worker_status"] == "approved"

            # suspend → kills sessions
            r = admin_session.post(f"{API}/admin/workers/{wid}/suspend", timeout=20)
            assert r.status_code == 200, r.text
            assert db.users.find_one({"user_id": wid})["worker_status"] == "suspended"
            assert db.sessions.count_documents({"session_token": token}) == 0

            # reinstate
            r = admin_session.post(f"{API}/admin/workers/{wid}/reinstate", timeout=20)
            assert r.status_code == 200, r.text
            assert db.users.find_one({"user_id": wid})["worker_status"] == "approved"

            # reject → kills sessions (re-issue and verify)
            token2 = _set_session_for_worker(wid)
            r = admin_session.post(f"{API}/admin/workers/{wid}/reject", timeout=20)
            assert r.status_code == 200, r.text
            assert db.users.find_one({"user_id": wid})["worker_status"] == "rejected"
            assert db.sessions.count_documents({"session_token": token2}) == 0
        finally:
            db.users.delete_one({"user_id": wid})
            db.sessions.delete_many({"user_id": wid})

    def test_reset_worker_password_kills_sessions(self, admin_session):
        wid, _ = _seed_verified_worker()
        token = _set_session_for_worker(wid)
        try:
            r = admin_session.post(f"{API}/admin/workers/{wid}/reset-password", json={}, timeout=20)
            assert r.status_code == 200, r.text
            body = r.json()
            # Should return a temp password (key names vary; accept common ones)
            tmp = (
                body.get("temp_password")
                or body.get("new_password")
                or body.get("password")
            )
            assert tmp and isinstance(tmp, str) and len(tmp) >= 6, f"no temp password in {body}"
            # Sessions killed
            assert _db().sessions.count_documents({"session_token": token}) == 0
        finally:
            _db().users.delete_one({"user_id": wid})
            _db().sessions.delete_many({"user_id": wid})

    def test_owner_reset_admin_user_password(self, admin_session):
        """POST /admin/users/{id}/reset-password — requires is_owner.
        Owner admin@hcobcleaners.com should succeed against itself or any user.
        """
        # Find an admin user that's NOT the owner (program manager) to be the target
        db = _db()
        target = db.users.find_one({"email": "mechiebadlong77@gmail.com"})
        if not target:
            pytest.skip("No PM admin seed present; skip owner-reset test")
        target_id = target["user_id"]
        r = admin_session.post(
            f"{API}/admin/users/{target_id}/reset-password",
            json={"new_password": "NewPMTemp_2026_iter30!"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # Either echoes the new password or a temp one
        assert body.get("ok", True) is not False
        # Restore original password by force-reset back
        admin_session.post(
            f"{API}/admin/users/{target_id}/reset-password",
            json={"new_password": "Mechie2026!"},
            timeout=20,
        )

    def test_delete_worker_cascades(self, admin_session):
        # Seed worker + gig + acceptance
        wid, _ = _seed_verified_worker()
        gid = _create_gig(admin_session)
        aid = _seed_acceptance(gid, wid, status="completed")
        # Seed a notification + session row + dummy file ref
        db = _db()
        db.notifications.insert_one({
            "notification_id": uuid.uuid4().hex,
            "user_id": wid,
            "kind": "test",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        token = _set_session_for_worker(wid)
        try:
            r = admin_session.delete(f"{API}/admin/workers/{wid}", timeout=20)
            assert r.status_code == 200, r.text
            assert db.users.find_one({"user_id": wid}) is None
            assert db.gig_acceptances.find_one({"acceptance_id": aid}) is None
            assert db.notifications.count_documents({"user_id": wid}) == 0
            assert db.sessions.count_documents({"session_token": token}) == 0
        finally:
            admin_session.delete(f"{API}/gigs/{gid}", timeout=20)
            db.users.delete_one({"user_id": wid})


# =========================================================================
# 9) ADMIN /stats KPI shape
# =========================================================================
def test_admin_stats_shape(admin_session):
    r = admin_session.get(f"{API}/admin/stats", timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("total_workers", "open_gigs", "filled_gigs"):
        assert key in body, f"missing KPI key: {key}"
        assert isinstance(body[key], int)


# =========================================================================
# 10-13) PAY override + timesheet edit/approve/unapprove
# =========================================================================
class TestPayAndTimesheets:
    def test_set_worker_default_pay(self, admin_session):
        wid, _ = _seed_verified_worker()
        try:
            r = admin_session.put(
                f"{API}/admin/workers/{wid}/pay",
                json={"default_pay_rate": 30.5, "default_pay_type": "hourly"},
                timeout=20,
            )
            assert r.status_code == 200, r.text
            user = _db().users.find_one({"user_id": wid})
            assert float(user.get("default_pay_rate")) == 30.5
            assert user.get("default_pay_type") == "hourly"
        finally:
            _db().users.delete_one({"user_id": wid})

    def test_acceptance_pay_override_and_earnings_recompute(self, admin_session):
        wid, _ = _seed_verified_worker()
        gid = _create_gig(admin_session, pay_rate=20.0)
        aid = _seed_acceptance(gid, wid, status="completed", clocked_out=True, hours=2.0, pay_rate=20.0)
        try:
            r = admin_session.put(
                f"{API}/gigs/{gid}/acceptances/{aid}/pay",
                json={"pay_rate_override": 50.0, "pay_type_override": "hourly"},
                timeout=20,
            )
            assert r.status_code == 200, r.text
            acc = _db().gig_acceptances.find_one({"acceptance_id": aid})
            assert float(acc.get("pay_rate_applied")) == 50.0
            assert acc.get("pay_type_applied") == "hourly"
            # earnings should be recomputed for completed acceptances
            assert acc.get("earnings") is not None
            assert float(acc["earnings"]) == pytest.approx(2.0 * 50.0, rel=0.02)
        finally:
            _db().gig_acceptances.delete_many({"gig_id": gid})
            admin_session.delete(f"{API}/gigs/{gid}", timeout=20)
            _db().users.delete_one({"user_id": wid})

    def test_approve_and_unapprove_timesheet(self, admin_session):
        wid, _ = _seed_verified_worker()
        gid = _create_gig(admin_session, pay_rate=20.0)
        aid = _seed_acceptance(gid, wid, status="completed", clocked_out=True)
        try:
            r = admin_session.post(
                f"{API}/gigs/{gid}/acceptances/{aid}/approve-timesheet", json={}, timeout=20
            )
            assert r.status_code == 200, r.text
            acc = _db().gig_acceptances.find_one({"acceptance_id": aid})
            assert acc.get("timesheet_approved") is True

            r = admin_session.post(
                f"{API}/gigs/{gid}/acceptances/{aid}/unapprove-timesheet", json={}, timeout=20
            )
            assert r.status_code == 200, r.text
            acc = _db().gig_acceptances.find_one({"acceptance_id": aid})
            assert acc.get("timesheet_approved") is False
        finally:
            _db().gig_acceptances.delete_many({"gig_id": gid})
            admin_session.delete(f"{API}/gigs/{gid}", timeout=20)
            _db().users.delete_one({"user_id": wid})

    def test_edit_timesheet_clock_times(self, admin_session):
        wid, _ = _seed_verified_worker()
        gid = _create_gig(admin_session)
        aid = _seed_acceptance(gid, wid, status="completed", clocked_out=True)
        try:
            new_in = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
            new_out = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            r = admin_session.put(
                f"{API}/gigs/{gid}/acceptances/{aid}/timesheet",
                json={
                    "clock_in_at": new_in,
                    "clock_out_at": new_out,
                    "hours_worked": 3.0,
                },
                timeout=20,
            )
            assert r.status_code == 200, r.text
            acc = _db().gig_acceptances.find_one({"acceptance_id": aid})
            assert acc.get("hours_worked") == 3.0
            assert acc.get("clock_in_at") is not None
            assert acc.get("clock_out_at") is not None
        finally:
            _db().gig_acceptances.delete_many({"gig_id": gid})
            admin_session.delete(f"{API}/gigs/{gid}", timeout=20)
            _db().users.delete_one({"user_id": wid})


# =========================================================================
# 14-17) REPORTS — workers/gigs/activity/earnings/blasts + timesheets + bogus
# =========================================================================
class TestReports:
    @pytest.mark.parametrize("report_type", ["workers", "gigs", "activity", "earnings", "blasts"])
    def test_generic_report_shape(self, admin_session, report_type):
        r = admin_session.get(f"{API}/admin/reports/{report_type}", timeout=30)
        assert r.status_code == 200, f"{report_type}: {r.status_code} {r.text}"
        body = r.json()
        assert "rows" in body, f"{report_type} missing 'rows'"
        assert "columns" in body, f"{report_type} missing 'columns'"
        assert isinstance(body["rows"], list)
        assert isinstance(body["columns"], list)
        # 'totals' may be {} or None for some reports — just assert key exists
        assert "totals" in body

    def test_timesheets_report(self, admin_session):
        r = admin_session.get(f"{API}/admin/reports/timesheets", timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "rows" in body
        assert "totals" in body
        assert isinstance(body["rows"], list)

    def test_timesheets_csv(self, admin_session):
        r = admin_session.get(f"{API}/admin/reports/timesheets.csv", timeout=30)
        assert r.status_code == 200, r.text
        ct = r.headers.get("content-type", "")
        assert "text/csv" in ct or "csv" in ct, f"unexpected content-type: {ct}"
        # Body should be non-empty CSV (at minimum a header row)
        assert len(r.text.strip()) > 0

    def test_unknown_report_type_404(self, admin_session):
        r = admin_session.get(f"{API}/admin/reports/nonsense_xyz", timeout=20)
        assert r.status_code == 404, r.text
        body = r.json()
        detail = body.get("detail", "")
        assert "Unknown report_type" in detail or "unknown" in detail.lower()

    def test_export_google_sheets_unconfigured_400(self, admin_session):
        # Ensure no SA JSON exists in settings (or accept whatever current state is).
        db = _db()
        # If a service-account json IS configured, skip this test rather than nuking it.
        s = db.app_settings.find_one({"_id": "global"}) or db.app_settings.find_one()
        if s and s.get("google_service_account_json"):
            pytest.skip("Google SA JSON is configured; cannot validate 400 path without destroying real config")
        r = admin_session.post(
            f"{API}/admin/reports/export-google-sheets",
            json={"report_type": "timesheets"},
            timeout=20,
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
        body = r.json()
        detail = (body.get("detail") or "").lower()
        assert "google" in detail or "service account" in detail or "not configured" in detail


# =========================================================================
# 18) /me/earnings — worker vs admin gating
# =========================================================================
class TestMeEarnings:
    def test_admin_forbidden(self, admin_session):
        r = admin_session.get(f"{API}/me/earnings", timeout=20)
        assert r.status_code == 403, r.text

    def test_worker_returns_totals(self, admin_session):
        wid, _ = _seed_verified_worker()
        gid1 = _create_gig(admin_session, pay_rate=20.0)
        gid2 = _create_gig(admin_session, pay_rate=20.0)
        # Two acceptances on DIFFERENT gigs (unique index gig_id_1_worker_id_1)
        aid_approved = _seed_acceptance(gid1, wid, status="completed", clocked_out=True, hours=2.0, pay_rate=20.0)
        aid_pending = _seed_acceptance(gid2, wid, status="completed", clocked_out=True, hours=1.5, pay_rate=20.0)
        # Flag the approved one
        _db().gig_acceptances.update_one(
            {"acceptance_id": aid_approved},
            {"$set": {"timesheet_approved": True, "timesheet_approved_at": datetime.now(timezone.utc).isoformat()}},
        )
        token = _set_session_for_worker(wid)
        ws = requests.Session()
        ws.cookies.set("session_token", token)
        try:
            r = ws.get(f"{API}/me/earnings", timeout=20)
            assert r.status_code == 200, r.text
            body = r.json()
            assert "approved" in body and "pending" in body
            assert isinstance(body["approved"].get("rows"), list)
            # Approved totals should include the approved acceptance
            assert float(body["approved"]["total_hours"]) >= 2.0
            assert float(body["approved"]["total_earnings"]) >= 40.0
            # Pending should reflect the un-approved acceptance
            assert int(body["pending"]["count"]) >= 1
            assert float(body["pending"]["hours"]) >= 1.5
        finally:
            _db().gig_acceptances.delete_many({"worker_id": wid})
            admin_session.delete(f"{API}/gigs/{gid1}", timeout=20)
            admin_session.delete(f"{API}/gigs/{gid2}", timeout=20)
            _db().users.delete_one({"user_id": wid})
            _db().sessions.delete_many({"user_id": wid})
