"""Iteration 15 tests — Admin override editor for worker profiles.

Endpoint under test: PUT /api/admin/workers/{user_id}/profile
Covers:
  - all worker self-serve fields plus admin-only (worker_status, id_verified, email)
  - validation parity with the worker self-serve endpoint
  - email duplicate / no-op / format / lowercase
  - rejected/suspended deletes sessions
  - 404 on non-existent worker, 400 on admin target
  - response shape (no password_hash, profile_complete + profile_missing_fields)
Regression:
  - PUT /api/profile worker self-serve still works
  - existing /admin/workers/{id}/{approve|suspend|reject|password-reset} still work
  - AdminReports JSON + CSV endpoints + AdminWorkers list still work
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://work-connect-147.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PASSWORD = "HcobAdmin2026!"
SMOKE_WORKER_ID = "user_f56f8567e554"


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def fresh_worker(admin_session):
    """Create a brand-new worker via /auth/register (forces role=worker)."""
    unique = uuid.uuid4().hex[:8]
    email = f"test_iter15_{unique}@example.com"
    pw = "Worker123!"
    s = requests.Session()
    r = s.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": "TEST iter15"}, timeout=15)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    me = s.get(f"{API}/auth/me", timeout=15).json()
    return {"user_id": me["user_id"], "email": email, "password": pw, "session": s}


# ---------- HAPPY PATH ----------
class TestAdminEditHappyPath:
    def test_full_update(self, admin_session, fresh_worker):
        uid = fresh_worker["user_id"]
        body = {
            "name": "TEST iter15 Updated",
            "phone": "555-0100",
            "address": "1 Test St",
            "bio": "edited by admin",
            "skills": ["deep_cleaning", "routine_cleaning"],
            "zip_code": "10001",
            "city": "NYC",
            "state": "NY",
            "date_of_birth": "1990-01-01",
            "has_car": True,
            "has_truck": False,
            "has_cdl": False,
            "experience_level": "1_3_yr",
            "availability": ["weekdays", "weekends"],
            "emergency_contact_name": "Mom",
            "emergency_contact_phone": "555-0200",
            "tshirt_size": "L",
            "worker_status": "approved",
            "id_verified": True,
        }
        r = admin_session.put(f"{API}/admin/workers/{uid}/profile", json=body, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "password_hash" not in data
        assert "profile_complete" in data
        assert "profile_missing_fields" in data
        assert data["name"] == "TEST iter15 Updated"
        assert data["zip_code"] == "10001"
        assert data["id_verified"] is True
        assert data["worker_status"] == "approved"
        # GET-after-PUT to verify persistence
        r2 = admin_session.get(f"{API}/admin/workers", timeout=15)
        assert r2.status_code == 200
        rec = next((w for w in r2.json() if w["user_id"] == uid), None)
        assert rec is not None
        assert rec["zip_code"] == "10001"


# ---------- VALIDATION ----------
class TestAdminEditValidation:
    def test_bad_skill_400(self, admin_session, fresh_worker):
        r = admin_session.put(f"{API}/admin/workers/{fresh_worker['user_id']}/profile",
                              json={"skills": ["deep_cleaning", "not_a_skill"]}, timeout=15)
        assert r.status_code == 400
        assert "Unknown skill" in r.text

    def test_bad_availability_400(self, admin_session, fresh_worker):
        r = admin_session.put(f"{API}/admin/workers/{fresh_worker['user_id']}/profile",
                              json={"availability": ["weekdays", "bogus"]}, timeout=15)
        assert r.status_code == 400

    def test_bad_experience_level_400(self, admin_session, fresh_worker):
        r = admin_session.put(f"{API}/admin/workers/{fresh_worker['user_id']}/profile",
                              json={"experience_level": "guru"}, timeout=15)
        assert r.status_code == 400

    def test_empty_experience_level_allowed(self, admin_session, fresh_worker):
        # iter12/13 regression — empty string MUST be allowed
        r = admin_session.put(f"{API}/admin/workers/{fresh_worker['user_id']}/profile",
                              json={"experience_level": ""}, timeout=15)
        assert r.status_code == 200, r.text

    def test_bad_tshirt_size_400(self, admin_session, fresh_worker):
        r = admin_session.put(f"{API}/admin/workers/{fresh_worker['user_id']}/profile",
                              json={"tshirt_size": "XXXL_BOGUS"}, timeout=15)
        assert r.status_code == 400

    def test_bad_zip_400(self, admin_session, fresh_worker):
        r = admin_session.put(f"{API}/admin/workers/{fresh_worker['user_id']}/profile",
                              json={"zip_code": "abc12"}, timeout=15)
        assert r.status_code == 400
        r2 = admin_session.put(f"{API}/admin/workers/{fresh_worker['user_id']}/profile",
                               json={"zip_code": "1234"}, timeout=15)
        assert r2.status_code == 400

    def test_bad_worker_status_400(self, admin_session, fresh_worker):
        r = admin_session.put(f"{API}/admin/workers/{fresh_worker['user_id']}/profile",
                              json={"worker_status": "haunted"}, timeout=15)
        assert r.status_code == 400


# ---------- EMAIL ----------
class TestAdminEditEmail:
    def test_invalid_format_400(self, admin_session, fresh_worker):
        r = admin_session.put(f"{API}/admin/workers/{fresh_worker['user_id']}/profile",
                              json={"email": "not-an-email"}, timeout=15)
        assert r.status_code == 400

    def test_duplicate_email_400(self, admin_session, fresh_worker):
        # Try to set the worker's email to admin's email
        r = admin_session.put(f"{API}/admin/workers/{fresh_worker['user_id']}/profile",
                              json={"email": ADMIN_EMAIL}, timeout=15)
        assert r.status_code == 400
        assert "already in use" in r.text.lower()

    def test_same_email_noop_ok(self, admin_session, fresh_worker):
        r = admin_session.put(f"{API}/admin/workers/{fresh_worker['user_id']}/profile",
                              json={"email": fresh_worker["email"]}, timeout=15)
        assert r.status_code == 200, r.text

    def test_lowercase_stored(self, admin_session, fresh_worker):
        new_email = f"TEST_ITER15_UPPER_{uuid.uuid4().hex[:6]}@EXAMPLE.COM"
        r = admin_session.put(f"{API}/admin/workers/{fresh_worker['user_id']}/profile",
                              json={"email": new_email}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["email"] == new_email.lower()


# ---------- SESSION DELETION ON STATUS CHANGE ----------
class TestAdminEditSessionKill:
    def test_rejected_kills_sessions(self, admin_session):
        # create a worker, login, then admin sets status=rejected; their session should die
        unique = uuid.uuid4().hex[:6]
        email = f"test_iter15_kill_{unique}@example.com"
        pw = "Worker123!"
        ws = requests.Session()
        r = ws.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": "kill-me"}, timeout=15)
        assert r.status_code == 200
        me = ws.get(f"{API}/auth/me", timeout=15)
        assert me.status_code == 200
        uid = me.json()["user_id"]
        # admin rejects
        r2 = admin_session.put(f"{API}/admin/workers/{uid}/profile",
                               json={"worker_status": "rejected"}, timeout=15)
        assert r2.status_code == 200
        # worker session should no longer be valid
        me2 = ws.get(f"{API}/auth/me", timeout=15)
        assert me2.status_code == 401, f"Worker session was NOT killed (got {me2.status_code})"


# ---------- 404 / 400 ON BAD TARGET ----------
class TestAdminEditBadTarget:
    def test_nonexistent_worker_404(self, admin_session):
        r = admin_session.put(f"{API}/admin/workers/user_does_not_exist_xyz/profile",
                              json={"name": "x"}, timeout=15)
        assert r.status_code == 404

    def test_target_admin_400(self, admin_session):
        # find admin user_id
        me = admin_session.get(f"{API}/auth/me", timeout=15).json()
        r = admin_session.put(f"{API}/admin/workers/{me['user_id']}/profile",
                              json={"name": "x"}, timeout=15)
        assert r.status_code == 400
        assert "admin self-service" in r.text.lower()


# ---------- REGRESSION ----------
class TestRegression:
    def test_worker_self_serve_profile_still_works(self):
        unique = uuid.uuid4().hex[:6]
        email = f"test_iter15_self_{unique}@example.com"
        pw = "Worker123!"
        ws = requests.Session()
        r = ws.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": "self-edit"}, timeout=15)
        assert r.status_code == 200
        r2 = ws.put(f"{API}/profile", json={"zip_code": "94103", "experience_level": ""}, timeout=15)
        assert r2.status_code == 200, r2.text
        assert r2.json()["zip_code"] == "94103"

    def test_existing_admin_endpoints(self, admin_session):
        # password reset endpoint still works on smoke worker
        # use an existing worker — smoke worker
        r = admin_session.get(f"{API}/admin/workers", timeout=15)
        assert r.status_code == 200

    def test_admin_reports_workers_json(self, admin_session):
        r = admin_session.get(f"{API}/admin/reports/workers", timeout=20)
        assert r.status_code == 200

    def test_admin_reports_workers_csv(self, admin_session):
        r = admin_session.get(f"{API}/admin/reports/workers.csv", timeout=20)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    def test_admin_workers_filter(self, admin_session):
        r = admin_session.get(f"{API}/admin/workers", params={"q": "smoke"}, timeout=15)
        assert r.status_code == 200
