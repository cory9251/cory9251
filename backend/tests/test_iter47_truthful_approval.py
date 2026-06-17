"""Iter47 — Truthful Worker Approval gate.

Covers 5 backend cases:
 1. /admin/workers list response now includes `approval_blockers` and `fully_active`.
 2. /admin/workers/{id} detail response includes the same.
 3. POST /admin/workers/{id}/approve returns 400 with a descriptive message
    listing blockers for incomplete workers.
 4. PUT /admin/workers/{id}/profile with worker_status='approved' returns 400
    for the same reason — BUT also succeeds when blockers are fixed in the
    same PATCH (prospective-merge check).
 5. POST /admin/workers/{id}/reinstate routes through _set_worker_status and
    is also blocked.
 6. Fully-active worker (worker.demo) can be approved successfully.

Also asserts the migration script `migrate_downgrade_incomplete_approvals` is
idempotent — a second run downgrades 0 additional workers.
"""
import os
import uuid
import asyncio
from datetime import datetime, timezone
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PASSWORD = "HcobAdmin2026!"
WORKER_DEMO_EMAIL = "worker.demo@hcobcleaners.com"

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


# ------------- Fixtures ----------------------------------------------------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def db():
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


@pytest.fixture(scope="module")
def incomplete_worker(db):
    """Create a fresh worker that is 'pending' AND has no ID AND incomplete
    profile — guaranteed blockers. Cleaned up at end."""
    user_id = f"TEST_iter47_{uuid.uuid4().hex[:8]}"
    user = {
        "user_id": user_id,
        "email": f"{user_id}@example.test",
        "name": "TEST Iter47 Incomplete",
        "role": "worker",
        "worker_status": "pending",
        "id_image_path": None,
        "id_verified": False,
        "password_hash": "x",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    async def _setup():
        await db.users.insert_one(user)

    async def _teardown():
        await db.users.delete_one({"user_id": user_id})

    asyncio.get_event_loop().run_until_complete(_setup())
    yield user_id
    asyncio.get_event_loop().run_until_complete(_teardown())


@pytest.fixture(scope="module")
def demo_worker_id(db):
    async def _find():
        u = await db.users.find_one({"email": WORKER_DEMO_EMAIL})
        return u["user_id"] if u else None

    uid = asyncio.get_event_loop().run_until_complete(_find())
    assert uid, f"Worker demo user {WORKER_DEMO_EMAIL} missing — seed it first"
    return uid


# ------------- 1. List response enrichment ---------------------------------
def test_admin_workers_list_includes_blockers_and_fully_active(admin_session):
    r = admin_session.get(f"{API}/admin/workers")
    assert r.status_code == 200, r.text
    workers = r.json()
    assert isinstance(workers, list) and len(workers) > 0
    # Every worker entry must have both keys
    for w in workers[:30]:
        assert "approval_blockers" in w, f"missing approval_blockers in {w.get('email')}"
        assert "fully_active" in w, f"missing fully_active in {w.get('email')}"
        assert isinstance(w["approval_blockers"], list)
        assert isinstance(w["fully_active"], bool)


# ------------- 2. Detail response enrichment -------------------------------
def test_admin_worker_detail_includes_blockers_and_fully_active(admin_session, incomplete_worker):
    r = admin_session.get(f"{API}/admin/workers/{incomplete_worker}")
    assert r.status_code == 200, r.text
    w = r.json()
    assert "approval_blockers" in w
    assert "fully_active" in w
    # This worker was seeded incomplete; blockers must surface ID and profile
    blockers_txt = " | ".join(w["approval_blockers"]).lower()
    assert "id not uploaded" in blockers_txt, w["approval_blockers"]
    assert "profile incomplete" in blockers_txt, w["approval_blockers"]
    assert w["fully_active"] is False


# ------------- 3. POST /approve blocked for incomplete worker --------------
def test_approve_blocked_for_incomplete_worker(admin_session, incomplete_worker):
    r = admin_session.post(f"{API}/admin/workers/{incomplete_worker}/approve")
    assert r.status_code == 400, r.text
    detail = r.json().get("detail", "")
    assert "Cannot approve worker yet" in detail, detail
    assert "ID not uploaded" in detail, detail
    assert "Profile incomplete" in detail, detail


# ------------- 4a. PUT /profile with worker_status='approved' blocked ------
def test_put_profile_approved_blocked_when_blockers_remain(admin_session, incomplete_worker):
    r = admin_session.put(
        f"{API}/admin/workers/{incomplete_worker}/profile",
        json={"worker_status": "approved"},
    )
    assert r.status_code == 400, r.text
    detail = r.json().get("detail", "")
    assert "Cannot approve worker yet" in detail, detail


# ------------- 4b. PUT /profile fixing everything in one call -> 200 -------
def test_put_profile_fix_all_blockers_in_one_call(admin_session, db, incomplete_worker):
    # Pre-attach an id_image_path + id_verified directly in DB (simulate that
    # the admin has already uploaded + verified) — keeps the test focused on
    # the merge logic for required-profile fields.
    async def _seed_id():
        await db.users.update_one(
            {"user_id": incomplete_worker},
            {"$set": {"id_image_path": "/tmp/fake.jpg", "id_verified": True}},
        )

    asyncio.get_event_loop().run_until_complete(_seed_id())

    # Fix all required profile fields in ONE PATCH and ask to approve at the
    # same time. Prospective-merge must allow this.
    payload = {
        "phone": "+15551234567",
        "zip_code": "94016",
        "date_of_birth": "1990-01-01",
        "skills": ["routine_cleaning"],
        "availability": ["weekdays"],
        "emergency_contact_name": "Mom",
        "emergency_contact_phone": "+15559876543",
        "worker_status": "approved",
    }
    r = admin_session.put(
        f"{API}/admin/workers/{incomplete_worker}/profile",
        json=payload,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("worker_status") == "approved"
    # PUT response uses _get_user_by_id which doesn't include approval_blockers
    # / fully_active. Verify persistence + truthful flags by hitting the GET
    # detail endpoint which DOES enrich.
    detail = admin_session.get(f"{API}/admin/workers/{incomplete_worker}").json()
    assert detail.get("worker_status") == "approved"
    assert detail.get("fully_active") is True
    assert detail.get("approval_blockers") == []


# ------------- 5. /reinstate also blocked for incomplete worker ------------
def test_reinstate_blocked_for_incomplete_worker(admin_session, db):
    """Create a new incomplete worker (suspended-ish) and try /reinstate —
    must also raise 400 because it routes through _set_worker_status('approved')."""
    user_id = f"TEST_iter47_reinst_{uuid.uuid4().hex[:8]}"
    user = {
        "user_id": user_id,
        "email": f"{user_id}@example.test",
        "name": "TEST Iter47 Suspended",
        "role": "worker",
        "worker_status": "suspended",
        "id_image_path": None,
        "id_verified": False,
        "password_hash": "x",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    async def _ins():
        await db.users.insert_one(user)

    async def _del():
        await db.users.delete_one({"user_id": user_id})

    try:
        asyncio.get_event_loop().run_until_complete(_ins())
        r = admin_session.post(f"{API}/admin/workers/{user_id}/reinstate")
        assert r.status_code == 400, r.text
        detail = r.json().get("detail", "")
        assert "Cannot approve worker yet" in detail
        assert "ID not uploaded" in detail
    finally:
        asyncio.get_event_loop().run_until_complete(_del())


# ------------- 6. Fully active worker CAN be approved ----------------------
def test_fully_active_worker_can_be_approved(admin_session, demo_worker_id):
    # First confirm demo worker is fully_active in the detail response
    detail = admin_session.get(f"{API}/admin/workers/{demo_worker_id}").json()
    assert detail.get("fully_active") is True, (
        f"Worker demo isn't fully active — fix seed. blockers={detail.get('approval_blockers')}"
    )
    r = admin_session.post(f"{API}/admin/workers/{demo_worker_id}/approve")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("worker_status") == "approved"


# ------------- 7. Migration idempotency ------------------------------------
def test_migration_is_idempotent():
    """Run the migration script once more; it must downgrade 0 workers because
    every still-approved worker is already fully active."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "migr",
        "/app/backend/scripts/migrate_downgrade_incomplete_approvals.py",
    )
    mod = importlib.util.module_from_spec(spec)
    # Ensure the migration script can find auth_deps via sys.path
    import sys
    sys.path.insert(0, "/app/backend")
    spec.loader.exec_module(mod)
    n = asyncio.get_event_loop().run_until_complete(mod.migrate(dry_run=True))
    assert n == 0, f"Expected idempotent (0 downgrades), got {n}"
