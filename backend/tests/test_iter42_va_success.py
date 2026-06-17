"""
Iteration 42 — VA Success Batch 2 backend tests.

Covers:
  - GET /api/va/dashboard enhanced payload (conversion_rate, stale_leads_count,
    goal, shared_notes, leaderboard_rank).
  - GET /api/va/stale-leads (7-day threshold; backdated lead surfaces).
  - GET /api/va/leaderboard (period toggle, is_self only true for caller).
  - GET /api/va/templates (only active+not-deleted; non-VA gets 403).
  - GET /api/va/coaching-notes (only shared notes; private MUST NOT leak).
  - GET /api/va/goals (last N).
  - POST/GET /api/pm/va-goals/{va_user_id} (upsert; both null deletes).
  - PM templates CRUD (create, patch active=false, delete soft, include_archived).
  - PM coaching-notes CRUD (private+shared; admin sees both; VA sees only shared).
  - GET /api/pm/vas/{va_user_id}/detail (combined payload, 404 for non-VA).
  - Permission boundaries (VA cannot hit /pm/* endpoints -> 403).
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().strip('"').strip("'").rstrip("/")
                    break
    except Exception:
        pass
assert BASE_URL, "REACT_APP_BACKEND_URL missing"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PW = "HcobAdmin2026!"

def _read_backend_env(key):
    try:
        with open("/app/backend/.env") as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        return None
    return None

MONGO_URL = os.environ.get("MONGO_URL") or _read_backend_env("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or _read_backend_env("DB_NAME")


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN_EMAIL, ADMIN_PW)


@pytest.fixture(scope="module")
def va_session(admin_session):
    em = f"iter42-va-{uuid.uuid4().hex[:8]}@example.com"
    pw = "VaTest2026!"
    r = admin_session.post(
        f"{API}/pm/vas",
        json={"email": em, "name": "Iter42 VA", "password": pw, "auto_approve": True},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    return _login(em, pw), r.json()["user_id"], em


@pytest.fixture(scope="module")
def va2_session(admin_session):
    em = f"iter42-va2-{uuid.uuid4().hex[:8]}@example.com"
    pw = "VaTest2026!"
    r = admin_session.post(
        f"{API}/pm/vas",
        json={"email": em, "name": "Iter42 VA2", "password": pw, "auto_approve": True},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    return _login(em, pw), r.json()["user_id"]


# ---------------- VA DASHBOARD ENHANCED ----------------
class TestVADashboardEnhanced:
    def test_dashboard_shape(self, va_session):
        s, _, _ = va_session
        r = s.get(f"{API}/va/dashboard", timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in [
            "active_leads", "commissions_pending", "commissions_approved",
            "total_paid", "paid_count", "conversion_rate",
            "stale_leads_count", "leaderboard_rank", "leaderboard_total",
            "goal", "shared_notes",
        ]:
            assert k in d, f"missing key {k}"
        assert isinstance(d["stale_leads_count"], int)
        assert isinstance(d["shared_notes"], list)
        # goal None when no goal set yet
        # (goal could be None for a fresh VA)


# ---------------- STALE LEADS ----------------
class TestStaleLeads:
    def test_stale_leads_surfaces_backdated_lead(self, admin_session, va_session):
        va_s, va_id, _ = va_session
        # Create a lead via VA
        payload = {
            "prospect_name": f"TEST Stale {uuid.uuid4().hex[:6]}",
            "prospect_phone": f"555{uuid.uuid4().int % 10000000:07d}",
            "prospect_email": f"stale-{uuid.uuid4().hex[:8]}@example.com",
            "prospect_address": f"{uuid.uuid4().hex[:4]} Stale St",
            "service_type": "deep", "property_size": "2br", "source": "referral",
        }
        r = va_s.post(f"{API}/va/leads", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        lead_id = r.json()["lead_id"]
        # Admin moves to 'contacted' stage
        r = admin_session.put(f"{API}/pm/leads/{lead_id}/stage",
                              json={"stage": "contacted"}, timeout=20)
        assert r.status_code == 200, r.text

        # Backdate updated_at by 8 days directly in mongo
        mc = MongoClient(MONGO_URL)
        try:
            old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
            res = mc[DB_NAME].va_leads.update_one(
                {"lead_id": lead_id}, {"$set": {"updated_at": old}}
            )
            assert res.modified_count == 1
        finally:
            mc.close()

        # /va/stale-leads should now include this lead
        r = va_s.get(f"{API}/va/stale-leads", timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert body["threshold_days"] == 7
        ids = [it["lead_id"] for it in body["items"]]
        assert lead_id in ids

        # Dashboard stale_leads_count should be >= 1
        r = va_s.get(f"{API}/va/dashboard", timeout=20)
        assert r.json()["stale_leads_count"] >= 1

    def test_stale_leads_forbidden_for_admin(self, admin_session):
        r = admin_session.get(f"{API}/va/stale-leads", timeout=20)
        assert r.status_code == 403


# ---------------- LEADERBOARD ----------------
class TestLeaderboard:
    def test_leaderboard_default_month(self, va_session):
        s, va_id, _ = va_session
        r = s.get(f"{API}/va/leaderboard", timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert body.get("period") == "month"
        assert isinstance(body["items"], list)
        # is_self must be True ONLY for this VA's own row (if present)
        for it in body["items"]:
            for k in ["rank", "va_user_id", "va_name", "leads", "booked", "conversion", "is_self"]:
                assert k in it
            if it["va_user_id"] == va_id:
                assert it["is_self"] is True
            else:
                assert it["is_self"] is False

    def test_leaderboard_period_toggle(self, va_session):
        s, _, _ = va_session
        for p in ("week", "month", "all"):
            r = s.get(f"{API}/va/leaderboard?period={p}", timeout=20)
            assert r.status_code == 200, f"{p} -> {r.text}"
            assert r.json()["period"] == p

    def test_va2_is_self_only_for_va2(self, va2_session, va_session):
        s2, va2_id = va2_session
        r = s2.get(f"{API}/va/leaderboard?period=all", timeout=20)
        assert r.status_code == 200
        for it in r.json()["items"]:
            assert it["is_self"] == (it["va_user_id"] == va2_id)


# ---------------- TEMPLATES ----------------
class TestTemplates:
    def test_pm_create_list_archive_delete(self, admin_session):
        # Create
        title = f"TEST tpl {uuid.uuid4().hex[:6]}"
        r = admin_session.post(f"{API}/pm/templates", json={
            "title": title, "body": "Hello {{name}}", "category": "intro", "channel": "dm",
        }, timeout=20)
        assert r.status_code == 200, r.text
        tpl = r.json()
        tid = tpl["template_id"]
        assert tpl["title"] == title and tpl["channel"] == "dm" and tpl["active"] is True

        # GET list (default, no archived)
        r = admin_session.get(f"{API}/pm/templates", timeout=20)
        assert r.status_code == 200
        ids = [t["template_id"] for t in r.json()["items"]]
        assert tid in ids

        # Patch archive (active=false)
        r = admin_session.patch(f"{API}/pm/templates/{tid}", json={"active": False}, timeout=20)
        assert r.status_code == 200
        assert r.json()["active"] is False

        # Default list hides archived
        r = admin_session.get(f"{API}/pm/templates", timeout=20)
        ids = [t["template_id"] for t in r.json()["items"]]
        assert tid not in ids

        # include_archived=true shows it
        r = admin_session.get(f"{API}/pm/templates?include_archived=true", timeout=20)
        ids = [t["template_id"] for t in r.json()["items"]]
        assert tid in ids

        # Soft delete
        r = admin_session.delete(f"{API}/pm/templates/{tid}", timeout=20)
        assert r.status_code == 200
        # After delete, not in either list
        r = admin_session.get(f"{API}/pm/templates?include_archived=true", timeout=20)
        ids = [t["template_id"] for t in r.json()["items"]]
        assert tid not in ids

    def test_va_templates_lists_only_active(self, admin_session, va_session):
        s, _, _ = va_session
        # Create active + archived templates
        r1 = admin_session.post(f"{API}/pm/templates", json={
            "title": f"TEST active {uuid.uuid4().hex[:6]}",
            "body": "active body", "channel": "email",
        }, timeout=20)
        assert r1.status_code == 200
        active_id = r1.json()["template_id"]

        r2 = admin_session.post(f"{API}/pm/templates", json={
            "title": f"TEST archived {uuid.uuid4().hex[:6]}",
            "body": "arch body", "channel": "sms",
        }, timeout=20)
        assert r2.status_code == 200
        arch_id = r2.json()["template_id"]
        admin_session.patch(f"{API}/pm/templates/{arch_id}", json={"active": False}, timeout=20)

        r = s.get(f"{API}/va/templates", timeout=20)
        assert r.status_code == 200
        ids = [t["template_id"] for t in r.json()["items"]]
        assert active_id in ids
        assert arch_id not in ids
        # Shape contract
        sample = next(t for t in r.json()["items"] if t["template_id"] == active_id)
        for k in ["template_id", "title", "body", "category", "channel"]:
            assert k in sample

    def test_va_cannot_pm_templates(self, va_session):
        s, _, _ = va_session
        r = s.get(f"{API}/pm/templates", timeout=20)
        assert r.status_code == 403
        r = s.post(f"{API}/pm/templates", json={
            "title": "x", "body": "y", "channel": "any",
        }, timeout=20)
        assert r.status_code == 403


# ---------------- COACHING NOTES (PRIVACY!) ----------------
class TestCoachingNotes:
    def test_private_not_leaked_to_va(self, admin_session, va_session):
        s, va_id, _ = va_session
        # Create one shared + one private
        r = admin_session.post(f"{API}/pm/coaching-notes/{va_id}", json={
            "text": "TEST shared note", "is_shared": True,
        }, timeout=20)
        assert r.status_code == 200, r.text
        shared_id = r.json()["note_id"]

        r = admin_session.post(f"{API}/pm/coaching-notes/{va_id}", json={
            "text": "TEST private note", "is_shared": False,
        }, timeout=20)
        assert r.status_code == 200
        private_id = r.json()["note_id"]

        # Admin sees BOTH
        r = admin_session.get(f"{API}/pm/coaching-notes/{va_id}", timeout=20)
        assert r.status_code == 200
        admin_ids = [n["note_id"] for n in r.json()["items"]]
        assert shared_id in admin_ids and private_id in admin_ids

        # VA only sees shared
        r = s.get(f"{API}/va/coaching-notes", timeout=20)
        assert r.status_code == 200
        va_ids = [n["note_id"] for n in r.json()["items"]]
        assert shared_id in va_ids
        assert private_id not in va_ids, "PRIVACY LEAK: private note exposed to VA"

        # Admin count > VA count for this VA
        assert len(admin_ids) > len(va_ids) or (
            len([n for n in r.json()["items"]]) < len(admin_ids)
        )

        # VA Dashboard shared_notes contains the shared note
        r = s.get(f"{API}/va/dashboard", timeout=20)
        assert r.status_code == 200
        sn_ids = [n["note_id"] for n in r.json()["shared_notes"]]
        assert shared_id in sn_ids

    def test_update_and_delete_note(self, admin_session, va_session):
        _, va_id, _ = va_session
        r = admin_session.post(f"{API}/pm/coaching-notes/{va_id}", json={
            "text": "TEST edit me", "is_shared": False,
        }, timeout=20)
        nid = r.json()["note_id"]

        # PATCH text + is_shared
        r = admin_session.patch(f"{API}/pm/coaching-notes/{nid}", json={
            "text": "TEST edited", "is_shared": True,
        }, timeout=20)
        assert r.status_code == 200
        assert r.json()["text"] == "TEST edited"
        assert r.json()["is_shared"] is True

        # DELETE (soft)
        r = admin_session.delete(f"{API}/pm/coaching-notes/{nid}", timeout=20)
        assert r.status_code == 200
        # Should no longer appear in list
        r = admin_session.get(f"{API}/pm/coaching-notes/{va_id}", timeout=20)
        ids = [n["note_id"] for n in r.json()["items"]]
        assert nid not in ids

    def test_va_cannot_hit_pm_coaching_notes(self, va_session):
        s, va_id, _ = va_session
        r = s.get(f"{API}/pm/coaching-notes/{va_id}", timeout=20)
        assert r.status_code == 403
        r = s.post(f"{API}/pm/coaching-notes/{va_id}", json={"text": "x", "is_shared": False}, timeout=20)
        assert r.status_code == 403


# ---------------- GOALS ----------------
class TestVAGoals:
    def test_pm_set_get_and_delete_when_both_null(self, admin_session, va_session):
        _, va_id, _ = va_session
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        # Upsert goal
        r = admin_session.post(f"{API}/pm/va-goals/{va_id}", json={
            "month": month, "target_leads": 20, "target_commission": 1500.0,
            "note": "TEST goal",
        }, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        # Get history
        r = admin_session.get(f"{API}/pm/va-goals/{va_id}", timeout=20)
        assert r.status_code == 200
        months_found = {g["month"]: g for g in r.json()["items"]}
        assert month in months_found
        assert months_found[month]["target_leads"] == 20
        assert months_found[month]["target_commission"] == 1500.0

        # Dashboard reflects goal
        s, _, _ = va_session
        r = s.get(f"{API}/va/dashboard", timeout=20)
        goal = r.json().get("goal")
        assert goal is not None
        assert goal["target_leads"] == 20
        assert goal["target_commission"] == 1500.0
        assert "mtd_leads" in goal and "mtd_commission" in goal

        # Update to BOTH null -> deleted
        r = admin_session.post(f"{API}/pm/va-goals/{va_id}", json={
            "month": month, "target_leads": None, "target_commission": None,
        }, timeout=20)
        assert r.status_code == 200
        assert r.json().get("deleted") is True

        # GET history should not include this month anymore (or it's gone)
        r = admin_session.get(f"{API}/pm/va-goals/{va_id}", timeout=20)
        months_found = [g["month"] for g in r.json()["items"]]
        assert month not in months_found

        # Dashboard goal -> None
        r = s.get(f"{API}/va/dashboard", timeout=20)
        assert r.json().get("goal") is None

    def test_va_get_own_goals(self, admin_session, va_session):
        s, va_id, _ = va_session
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        admin_session.post(f"{API}/pm/va-goals/{va_id}", json={
            "month": month, "target_leads": 5, "target_commission": None,
        }, timeout=20)
        r = s.get(f"{API}/va/goals?months=6", timeout=20)
        assert r.status_code == 200
        assert any(g["month"] == month for g in r.json()["items"])

    def test_va_cannot_set_goal(self, va_session):
        s, va_id, _ = va_session
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        r = s.post(f"{API}/pm/va-goals/{va_id}", json={
            "month": month, "target_leads": 10, "target_commission": 100.0,
        }, timeout=20)
        assert r.status_code == 403
        r = s.get(f"{API}/pm/va-goals/{va_id}", timeout=20)
        assert r.status_code == 403


# ---------------- PM VA DETAIL ----------------
class TestPMVADetail:
    def test_detail_shape(self, admin_session, va_session):
        _, va_id, _ = va_session
        r = admin_session.get(f"{API}/pm/vas/{va_id}/detail", timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["va"]["user_id"] == va_id
        for k in ["active_leads", "total_lifetime_leads", "conversion_rate",
                  "total_paid", "paid_count"]:
            assert k in d["stats"]
        for k in ["month", "target_leads", "target_commission", "note",
                  "mtd_leads", "mtd_commission"]:
            assert k in d["month_goal"]

    def test_detail_404_for_non_va(self, admin_session):
        # Admin's own user_id is not role=va
        r = admin_session.get(f"{API}/auth/me", timeout=20)
        admin_uid = r.json()["user_id"]
        r = admin_session.get(f"{API}/pm/vas/{admin_uid}/detail", timeout=20)
        assert r.status_code == 404
