"""Backend tests for VA Digital Jobs feature.

Covers admin create (open + directly assigned), VA board/claim/start/submit
(fixed + hourly), admin approve → commission pipeline, reject flow, assign
reassign, cancel, access control, and PM commission approve.
"""
import os
import time
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"

ADMIN = {"email": "admin@hcobcleaners.com", "password": "HcobAdmin2026!"}
VA = {"email": "va.demo@hcobcleaners.com", "password": "VaDemo2026!"}
WORKER = {"email": "worker.demo@hcobcleaners.com", "password": "WorkerDemo2026!"}
PENDING_VA = {"email": "va.pending@hcobcleaners.com", "password": "Pending2026!"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"Login failed for {creds['email']}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def va():
    return _login(VA)


@pytest.fixture(scope="module")
def va_user_id(va):
    r = va.get(f"{API}/auth/me")
    assert r.status_code == 200
    return r.json()["user_id"]


@pytest.fixture(scope="module")
def worker():
    return _login(WORKER)


# ---------------- Access control ----------------
class TestAccessControl:
    def test_worker_blocked_from_board(self, worker):
        r = worker.get(f"{API}/va/jobs/board")
        assert r.status_code == 403

    def test_pending_va_blocked_from_board(self):
        try:
            s = _login(PENDING_VA)
        except AssertionError:
            pytest.skip("Pending VA account not seeded")
        r = s.get(f"{API}/va/jobs/board")
        assert r.status_code == 403


# ---------------- Fixed-price happy path ----------------
class TestFixedPriceFlow:
    def test_full_flow(self, admin, va, va_user_id):
        # Admin creates OPEN fixed job
        payload = {
            "title": "TEST_fixed_job_" + str(int(time.time())),
            "description": "Automated test",
            "pay_type": "fixed",
            "pay_amount": 150,
            "due_date": None,
            "assigned_va_id": None,
        }
        r = admin.post(f"{API}/admin/va-jobs", json=payload)
        assert r.status_code == 200, r.text
        job = r.json()
        assert job["status"] == "open"
        assert job["pay_amount"] == 150.0
        job_id = job["job_id"]

        # Admin list
        r = admin.get(f"{API}/admin/va-jobs")
        assert r.status_code == 200
        data = r.json()
        assert any(j["job_id"] == job_id for j in data["items"])
        assert "counts" in data

        # VA sees on board
        r = va.get(f"{API}/va/jobs/board")
        assert r.status_code == 200
        assert any(j["job_id"] == job_id for j in r.json()["items"])

        # Claim
        r = va.post(f"{API}/va/jobs/{job_id}/claim")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "assigned"
        assert r.json()["assigned_va_id"] == va_user_id

        # Second claim → 409
        r2 = va.post(f"{API}/va/jobs/{job_id}/claim")
        assert r2.status_code == 409

        # Admin bell notification
        r = admin.get(f"{API}/notifications")
        assert r.status_code == 200
        titles = [n.get("title", "") for n in r.json()]
        assert any("Job claimed" in t for t in titles)

        # Start
        r = va.post(f"{API}/va/jobs/{job_id}/start")
        assert r.status_code == 200
        assert r.json()["status"] == "in_progress"

        # Submit
        r = va.post(f"{API}/va/jobs/{job_id}/submit", json={"note": "Done, see file"})
        assert r.status_code == 200
        assert r.json()["status"] == "submitted"
        assert r.json()["deliverable_note"] == "Done, see file"

        # Admin bell: submitted
        r = admin.get(f"{API}/notifications")
        assert any("Job submitted for review" in n.get("title", "") for n in r.json())

        # Approve on non-submitted returns 400 — first, approve legit
        r = admin.post(f"{API}/admin/va-jobs/{job_id}/approve", json={"note": "great work"})
        assert r.status_code == 200, r.text
        approved = r.json()
        assert approved["status"] == "approved"
        assert approved["payout_amount"] == 150.0
        assert approved["commission_id"]
        pytest.commission_id_fixed = approved["commission_id"]
        pytest.job_id_fixed = job_id

        # Approve again → 400
        r = admin.post(f"{API}/admin/va-jobs/{job_id}/approve", json={"note": "x"})
        assert r.status_code == 400

        # VA earnings shows commission
        r = va.get(f"{API}/va/earnings")
        assert r.status_code == 200, r.text
        data = r.json()
        items = data.get("items") or data.get("commissions") or []
        found = [x for x in items if x.get("commission_id") == approved["commission_id"]]
        assert found, f"digital_job commission not in earnings. items keys: {list(data.keys())}"
        c = found[0]
        assert c.get("service_type") == "digital_job"
        assert float(c.get("amount")) == 150.0
        assert c.get("status") == "pending_approval"

        # VA bell notification
        r = va.get(f"{API}/notifications")
        assert any("Job approved" in n.get("title", "") for n in r.json())


# ---------------- Hourly + direct assign ----------------
class TestHourlyDirectAssign:
    def test_flow(self, admin, va, va_user_id):
        payload = {
            "title": "TEST_hourly_job_" + str(int(time.time())),
            "description": "hourly",
            "pay_type": "hourly",
            "pay_amount": 25,
            "assigned_va_id": va_user_id,
        }
        r = admin.post(f"{API}/admin/va-jobs", json=payload)
        assert r.status_code == 200, r.text
        job = r.json()
        assert job["status"] == "assigned"
        assert job["assigned_va_id"] == va_user_id
        job_id = job["job_id"]

        # VA bell: New job assigned
        r = va.get(f"{API}/notifications")
        assert any("New job assigned" in n.get("title", "") for n in r.json())

        # Submit without hours → 400
        r = va.post(f"{API}/va/jobs/{job_id}/submit", json={"note": "done"})
        assert r.status_code == 400

        # Submit with hours
        r = va.post(f"{API}/va/jobs/{job_id}/submit", json={"note": "done", "hours_logged": 4})
        assert r.status_code == 200, r.text
        assert r.json()["hours_logged"] == 4.0
        assert r.json()["status"] == "submitted"

        # Approve → payout 100
        r = admin.post(f"{API}/admin/va-jobs/{job_id}/approve", json={})
        assert r.status_code == 200, r.text
        assert r.json()["payout_amount"] == 100.0
        pytest.commission_id_hourly = r.json()["commission_id"]


# ---------------- Reject flow ----------------
class TestRejectFlow:
    def test_reject(self, admin, va, va_user_id):
        # Create + directly assign a fixed job so we can quickly submit it
        r = admin.post(f"{API}/admin/va-jobs", json={
            "title": "TEST_reject_job_" + str(int(time.time())),
            "description": "",
            "pay_type": "fixed",
            "pay_amount": 50,
            "assigned_va_id": va_user_id,
        })
        assert r.status_code == 200
        job_id = r.json()["job_id"]

        # submit
        r = va.post(f"{API}/va/jobs/{job_id}/submit", json={"note": "attempt 1"})
        assert r.status_code == 200

        # reject without note → 400
        r = admin.post(f"{API}/admin/va-jobs/{job_id}/reject", json={})
        assert r.status_code == 400

        # reject with note
        r = admin.post(f"{API}/admin/va-jobs/{job_id}/reject", json={"note": "fix X"})
        assert r.status_code == 200
        assert r.json()["status"] == "in_progress"
        assert r.json()["review_note"] == "fix X"

        # VA bell: Changes requested
        r = va.get(f"{API}/notifications")
        assert any("Changes requested" in n.get("title", "") for n in r.json())


# ---------------- Assign / reassign / cancel ----------------
class TestAssignReassignCancel:
    def test_assign_and_cancel(self, admin, va_user_id):
        # Create job assigned to VA
        r = admin.post(f"{API}/admin/va-jobs", json={
            "title": "TEST_assign_" + str(int(time.time())),
            "description": "",
            "pay_type": "fixed",
            "pay_amount": 10,
            "assigned_va_id": va_user_id,
        })
        assert r.status_code == 200
        job_id = r.json()["job_id"]

        # Reassign to open (va_user_id: None)
        r = admin.post(f"{API}/admin/va-jobs/{job_id}/assign", json={"va_user_id": None})
        assert r.status_code == 200
        assert r.json()["status"] == "open"
        assert r.json()["assigned_va_id"] is None

        # Cancel non-approved
        r = admin.post(f"{API}/admin/va-jobs/{job_id}/cancel")
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"

    def test_approve_on_non_submitted_400(self, admin):
        # Create open job, immediately try to approve
        r = admin.post(f"{API}/admin/va-jobs", json={
            "title": "TEST_bad_approve_" + str(int(time.time())),
            "description": "",
            "pay_type": "fixed",
            "pay_amount": 10,
        })
        assert r.status_code == 200
        job_id = r.json()["job_id"]
        r = admin.post(f"{API}/admin/va-jobs/{job_id}/approve", json={})
        assert r.status_code == 400


# ---------------- PM commission approval on digital_job ----------------
class TestPMCommissionApprove:
    def test_pm_queue_and_approve(self, admin):
        cid = getattr(pytest, "commission_id_fixed", None)
        if not cid:
            pytest.skip("No fixed-job commission created")
        # PM queue (admin is owner and can access pm routes typically)
        r = admin.get(f"{API}/pm/commissions")
        assert r.status_code == 200, r.text
        body = r.json()
        items = body if isinstance(body, list) else (body.get("items") or body.get("commissions") or [])
        found = [c for c in items if c.get("commission_id") == cid]
        assert found, "digital_job commission missing from PM queue"
        assert found[0].get("status") == "pending_approval"

        # PM approve — must not crash on missing lead_id
        r = admin.post(f"{API}/pm/commissions/{cid}/approve", json={"note": "ok"})
        assert r.status_code in (200, 201), r.text
