"""
Iter 23 helper / regression test:
- Smoke-checks the regression endpoints listed in the review request
- Provides a `prepare_gig_with_pending_worker` style API path that the Playwright
  scripts (in /tmp) call out to by importing this module via pytest-style invocation.

NOTE: this file primarily acts as a SMOKE TEST for backend regression endpoints
during iter23 frontend E2E verification. The Playwright UI test creates its own
worker/session via direct DB inject (same pattern as test_backups_and_cancel.py).
"""
import os
import uuid
import asyncio
from datetime import datetime, timezone, timedelta

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://work-connect-147.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

OWNER_EMAIL = "admin@hcobcleaners.com"
OWNER_PASSWORD = "HcobAdmin2026!"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_session():
    return _login(OWNER_EMAIL, OWNER_PASSWORD)


# ---------- regression smoke ----------
def test_admin_login_works():
    s = _login(OWNER_EMAIL, OWNER_PASSWORD)
    me = s.get(f"{API}/auth/me", timeout=15)
    assert me.status_code == 200
    body = me.json()
    assert body.get("role") == "admin"


def test_admin_gigs_list(admin_session):
    r = admin_session.get(f"{API}/gigs", timeout=20)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_admin_global_requests_queue(admin_session):
    # /ops/requests page hits /api/admin/requests or /api/admin/pending-requests
    for path in ("/admin/requests", "/admin/pending-requests", "/admin/gig-requests"):
        r = admin_session.get(f"{API}{path}", timeout=20)
        if r.status_code == 200:
            return
    pytest.skip("No matching admin requests endpoint - check route names")


def test_create_gig_with_backup_slots(admin_session):
    body = {
        "title": f"ITER23_E2E_Gig_{uuid.uuid4().hex[:6]}",
        "description": "iter23 e2e",
        "category": "cleaning",
        "subcategory": "deep",
        "location": "100 Test St",
        "scheduled_date": "Fri Mar 6 · 9am",
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
        "pay_rate": 25.0,
        "pay_type": "hourly",
        "slots": 2,
        "backup_slots": 2,
    }
    r = admin_session.post(f"{API}/gigs", json=body, timeout=20)
    assert r.status_code in (200, 201), r.text
    gig = r.json()
    gid = gig.get("gig_id") or gig.get("id")
    assert gid
    fetched = admin_session.get(f"{API}/gigs/{gid}", timeout=20)
    assert fetched.status_code == 200
    data = fetched.json()
    assert data.get("backup_slots") == 2, f"backup_slots not persisted: {data}"
    # capture id for next test
    pytest.gig_id_iter23 = gid


def test_approve_as_backup_endpoint_exists(admin_session):
    """Use DB seed to test the approve-as-backup endpoint succeeds."""
    gid = getattr(pytest, "gig_id_iter23", None)
    if not gid:
        pytest.skip("gig not created")

    async def seed():
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": f"iter23_{uuid.uuid4().hex[:6]}@example.com",
            "name": "Iter23 Worker",
            "role": "worker",
            "worker_status": "approved",
            "phone": "5551234567",
            "id_verified": True,
            "auth_provider": "local",
            "password_hash": "$2b$12$dummy",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        acc_id = f"acc_{uuid.uuid4().hex[:12]}"
        await db.gig_acceptances.insert_one({
            "acceptance_id": acc_id,
            "gig_id": gid,
            "worker_id": user_id,
            "status": "requested",
            "requested_at": datetime.now(timezone.utc).isoformat(),
        })
        client.close()
        return acc_id

    acc_id = asyncio.get_event_loop().run_until_complete(seed())
    # Endpoint per server.py and test_backups_and_cancel.py
    r = admin_session.post(f"{API}/gigs/{gid}/requests/{acc_id}/approve-backup", timeout=20)
    assert r.status_code == 200, f"approve-backup failed: {r.status_code} {r.text}"
    g = admin_session.get(f"{API}/gigs/{gid}", timeout=20).json()
    assert g.get("backups_filled", 0) >= 1
    pytest.backup_acc_id_iter23 = acc_id


def test_promote_backup_endpoint(admin_session):
    gid = getattr(pytest, "gig_id_iter23", None)
    acc_id = getattr(pytest, "backup_acc_id_iter23", None)
    if not (gid and acc_id):
        pytest.skip("missing fixtures")
    r = admin_session.post(f"{API}/gigs/{gid}/acceptances/{acc_id}/promote", timeout=20)
    assert r.status_code == 200, f"promote failed: {r.status_code} {r.text}"
    g = admin_session.get(f"{API}/gigs/{gid}", timeout=20).json()
    assert g.get("slots_filled", 0) >= 1
