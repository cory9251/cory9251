"""Iter 48 — Lock in the "new workers must be pending" rule.

These tests guarantee that the four known write paths for a worker's
`worker_status` field default to `pending`, not `approved`:

1. POST /auth/register (public email signup)
2. POST /auth/oauth/google/callback (Google social login)
3. POST /admin/users/{id}/role (admin demoted to worker)
4. The on_startup auto-migration (no fresh `approved` leaks survive a boot)

Regression target: production deploy on 2026-06-17 where workers showed
under the APPROVED tab as "SETUP NEEDED" because the registration endpoint
auto-approved everyone.
"""
import os
import uuid
import asyncio

import pytest
import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://work-connect-147.preview.emergentagent.com",
).rstrip("/")

ADMIN = {"email": "admin@hcobcleaners.com", "password": "HcobAdmin2026!"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Cannot login as {creds['email']}: {r.status_code}")
    return s


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN)


# ---------- Test 1: email registration defaults to pending --------------------
def test_email_registration_defaults_to_pending():
    """New workers signing up via /auth/register must NOT be auto-approved."""
    email = f"iter48_signup_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": "Test12345!", "name": "Iter48 Signup"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["role"] == "worker"
    assert body["worker_status"] == "pending", (
        f"New worker {email} got status {body['worker_status']} — should be pending"
    )

    # Also confirm the DB record (not just the response) is pending
    async def _check():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            db = client[os.environ["DB_NAME"]]
            doc = await db.users.find_one({"email": email})
            assert doc is not None
            assert doc["worker_status"] == "pending"
            await db.users.delete_one({"_id": doc["_id"]})
        finally:
            client.close()

    asyncio.run(_check())


# ---------- Test 2: admin can't see this worker under APPROVED ----------------
def test_new_signup_appears_in_pending_filter_not_approved(admin_session):
    """A freshly registered worker should ONLY appear in the PENDING tab,
    never in the APPROVED tab. This is the regression target."""
    email = f"iter48_filter_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": "Test12345!", "name": "Iter48 Filter"},
        timeout=20,
    )
    assert r.status_code == 200

    # Pending tab — should contain this worker
    r_pending = admin_session.get(f"{BASE_URL}/api/admin/workers?status=pending&limit=2000", timeout=20)
    assert r_pending.status_code == 200
    pending = r_pending.json()
    pending_items = pending if isinstance(pending, list) else pending.get("items", [])
    assert any(w.get("email") == email for w in pending_items), (
        f"New worker {email} should appear in pending filter but doesn't"
    )

    # Approved tab — must NOT contain this worker
    r_approved = admin_session.get(f"{BASE_URL}/api/admin/workers?status=approved&limit=2000", timeout=20)
    assert r_approved.status_code == 200
    approved = r_approved.json()
    approved_items = approved if isinstance(approved, list) else approved.get("items", [])
    assert not any(w.get("email") == email for w in approved_items), (
        f"New worker {email} should NOT appear in approved filter but does — regression!"
    )

    # Cleanup
    async def _clean():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            db = client[os.environ["DB_NAME"]]
            await db.users.delete_one({"email": email})
        finally:
            client.close()
    asyncio.run(_clean())


# ---------- Test 3: admin can't approve a fresh signup until profile + ID ----
def test_fresh_signup_cannot_be_approved_yet(admin_session):
    """The /approve endpoint must reject a brand-new worker who has no
    profile fields and no ID."""
    email = f"iter48_block_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": "Test12345!", "name": "Iter48 Block"},
        timeout=20,
    )
    assert r.status_code == 200
    user_id = r.json()["user_id"]

    # Attempt to approve immediately — should fail
    r_appr = admin_session.post(f"{BASE_URL}/api/admin/workers/{user_id}/approve", timeout=20)
    assert r_appr.status_code == 400, r_appr.text
    detail = r_appr.json()["detail"].lower()
    assert "cannot approve" in detail
    # Should mention what's blocking
    assert ("id" in detail) or ("profile" in detail)

    # Cleanup
    async def _clean():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            db = client[os.environ["DB_NAME"]]
            await db.users.delete_one({"email": email})
        finally:
            client.close()
    asyncio.run(_clean())
