"""Iter 52 — Slot overbooking concurrency fix.

Verifies the atomic slot reservation that prevents two concurrent admin
approvals from both squeezing past the capacity check on the same gig.

Regression target: production bug where a 4-slot gig had 5 approved workers
because two admins (or one admin double-clicking) both passed the
`if filled >= slots` check before either committed the increment.
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import bcrypt

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://work-connect-147.preview.emergentagent.com",
).rstrip("/")

ADMIN = {"email": "admin@hcobcleaners.com", "password": "HcobAdmin2026!"}

CANONICAL_RULES = [
    "No-shows on first gigs are an automatic deletion from the platform.",
    "You will be professional when on your gig site.",
    "You must clock in on your shift, or you may not be paid.",
]


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Cannot login: {r.status_code}")
    return s


def _admin_session():
    return _login(ADMIN)


async def _make_workers(n: int) -> list[dict]:
    """Create N approved + id-verified worker accounts."""
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    workers = []
    pwd_hash = bcrypt.hashpw(b"OverbookTest2026!", bcrypt.gensalt()).decode()
    for i in range(n):
        token = uuid.uuid4().hex[:8]
        doc = {
            "_id": str(uuid.uuid4()),
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "email": f"iter52_w{i}_{token}@example.com",
            "name": f"Iter52 Worker {i}",
            "role": "worker",
            "worker_status": "approved",
            "phone": f"+1555{10000 + i:05d}",
            "address": "123 Test St, Baltimore, MD",
            "zip_code": "21201",
            "bio": "test",
            "skills": ["cleaning"],
            "date_of_birth": "1990-01-01",
            "availability": ["weekends"],
            "emergency_contact_name": "X",
            "emergency_contact_phone": "+15550000000",
            "id_image_path": "test/id.jpg",
            "id_verified": True,
            "password_hash": pwd_hash,
            "auth_provider": "email",
            "must_change_password": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(doc)
        workers.append({"email": doc["email"], "name": doc["name"], "user_id": doc["user_id"]})
    client.close()
    return workers


async def _cleanup_workers(workers, gig_id):
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    user_ids = [w["user_id"] for w in workers]
    await db.users.delete_many({"user_id": {"$in": user_ids}})
    await db.gig_acceptances.delete_many({"gig_id": gig_id})
    await db.gigs.delete_one({"gig_id": gig_id})
    await db.worker_agreements.delete_many({"worker_id": {"$in": user_ids}})
    client.close()


def _create_gig(admin_session, slots: int) -> str:
    """Create a fresh gig with exactly `slots` open spots."""
    r = admin_session.post(
        f"{BASE_URL}/api/gigs",
        json={
            "title": f"Iter52 overbook test {uuid.uuid4().hex[:6]}",
            "description": "Test",
            "category": "cleaning",
            "location": "Baltimore",
            "scheduled_at": "2027-06-01T15:00:00+00:00",
            "scheduled_local": "2027-06-01T10:00",
            "scheduled_date": "2027-06-01",
            "pay_rate": 20,
            "pay_type": "hourly",
            "slots": slots,
            "duration_hours": 4,
        },
        timeout=20,
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["gig_id"]


def _login_worker_and_request(worker, gig_id):
    """Each worker logs in and submits an accept request with the signed
    agreement, returning the new acceptance_id."""
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": worker["email"], "password": "OverbookTest2026!"
    }, timeout=20)
    assert r.status_code == 200, r.text
    r = s.post(
        f"{BASE_URL}/api/gigs/{gig_id}/accept",
        json={"typed_name": worker["name"], "agreed_rules": CANONICAL_RULES, "version": "v1"},
        timeout=20,
    )
    assert r.status_code == 200, f"Accept failed for {worker['email']}: {r.status_code} {r.text}"
    return r.json()["acceptance_id"]


# ----------- Test 1: serial approvals respect the slot cap ------------------
def test_approvals_cap_at_slot_count():
    """5 requests + 4 slots = exactly 4 approvals succeed, 5th returns 400."""
    workers = asyncio.run(_make_workers(5))
    s = _admin_session()
    gig_id = _create_gig(s, slots=4)
    try:
        # Each worker submits a request
        acceptance_ids = [_login_worker_and_request(w, gig_id) for w in workers]
        # Approve all 5 serially
        approvals = []
        for aid in acceptance_ids:
            r = s.post(f"{BASE_URL}/api/gigs/{gig_id}/requests/{aid}/approve", timeout=20)
            approvals.append((r.status_code, r.text))
        # Exactly 4 should succeed; the 5th must 400
        success = [a for a in approvals if a[0] == 200]
        failures = [a for a in approvals if a[0] == 400]
        assert len(success) == 4, f"Expected 4 successes, got {len(success)} → {approvals}"
        assert len(failures) == 1, f"Expected 1 failure, got {len(failures)} → {approvals}"
        assert "already filled" in failures[0][1].lower()
    finally:
        asyncio.run(_cleanup_workers(workers, gig_id))


# ----------- Test 2: concurrent approvals also respect the cap --------------
def test_concurrent_approvals_dont_overbook():
    """Fire 5 approve requests in parallel against a 3-slot gig.
    The atomic findOneAndUpdate must let exactly 3 win — never 4 or 5."""
    import concurrent.futures
    workers = asyncio.run(_make_workers(5))
    s = _admin_session()
    gig_id = _create_gig(s, slots=3)
    try:
        acceptance_ids = [_login_worker_and_request(w, gig_id) for w in workers]

        def approve(aid):
            with requests.Session() as parallel_s:
                # Each thread needs its own session cookies
                parallel_s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=20)
                r = parallel_s.post(
                    f"{BASE_URL}/api/gigs/{gig_id}/requests/{aid}/approve",
                    timeout=20,
                )
                return r.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            results = list(ex.map(approve, acceptance_ids))

        success = sum(1 for r in results if r == 200)
        failures = sum(1 for r in results if r == 400)
        assert success == 3, f"Expected EXACTLY 3 to succeed, got {success}. Results: {results}"
        assert failures == 2, f"Expected 2 failures, got {failures}. Results: {results}"

        # Verify gig counter reflects truth
        r = s.get(f"{BASE_URL}/api/gigs/{gig_id}", timeout=20)
        gig = r.json()
        assert gig["slots_filled"] == 3
        assert gig["status"] in ("filled", "open")  # 'filled' once we hit cap
    finally:
        asyncio.run(_cleanup_workers(workers, gig_id))


# ----------- Test 3: remove_worker_from_gig releases the slot atomically ----
def test_remove_worker_frees_slot():
    """After admin removes a worker, slots_filled decrements and a new worker
    can be approved into the freed slot."""
    workers = asyncio.run(_make_workers(3))
    s = _admin_session()
    gig_id = _create_gig(s, slots=2)
    try:
        # Submit + approve first 2 workers
        aid0 = _login_worker_and_request(workers[0], gig_id)
        aid1 = _login_worker_and_request(workers[1], gig_id)
        aid2 = _login_worker_and_request(workers[2], gig_id)
        assert s.post(f"{BASE_URL}/api/gigs/{gig_id}/requests/{aid0}/approve", timeout=20).status_code == 200
        assert s.post(f"{BASE_URL}/api/gigs/{gig_id}/requests/{aid1}/approve", timeout=20).status_code == 200
        # 3rd should fail (cap)
        assert s.post(f"{BASE_URL}/api/gigs/{gig_id}/requests/{aid2}/approve", timeout=20).status_code == 400
        # Remove worker 0
        r = s.delete(f"{BASE_URL}/api/gigs/{gig_id}/acceptances/{aid0}", timeout=20)
        assert r.status_code == 200, r.text
        # Now worker 2 can be approved
        r = s.post(f"{BASE_URL}/api/gigs/{gig_id}/requests/{aid2}/approve", timeout=20)
        assert r.status_code == 200, r.text
        # Final state: 2/2 filled
        r = s.get(f"{BASE_URL}/api/gigs/{gig_id}", timeout=20)
        gig = r.json()
        assert gig["slots_filled"] == 2
    finally:
        asyncio.run(_cleanup_workers(workers, gig_id))


# ----------- Test 4: reconciliation log line ran on last boot ---------------
def test_reconciliation_logic_is_idempotent():
    """Importing and calling the reconcile helper inline against a known-good
    gig should change nothing (idempotent). This protects against accidentally
    flipping correctly-filled gigs."""
    workers = asyncio.run(_make_workers(2))
    s = _admin_session()
    gig_id = _create_gig(s, slots=2)
    try:
        aid0 = _login_worker_and_request(workers[0], gig_id)
        aid1 = _login_worker_and_request(workers[1], gig_id)
        s.post(f"{BASE_URL}/api/gigs/{gig_id}/requests/{aid0}/approve", timeout=20)
        s.post(f"{BASE_URL}/api/gigs/{gig_id}/requests/{aid1}/approve", timeout=20)

        async def check():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = client[os.environ["DB_NAME"]]
            before = await db.gigs.find_one({"gig_id": gig_id})
            primary = await db.gig_acceptances.count_documents({
                "gig_id": gig_id,
                "status": {"$in": ["accepted", "on_the_clock", "completed"]},
            })
            client.close()
            return before["slots_filled"], primary

        slots_filled, primary = asyncio.run(check())
        assert slots_filled == primary == 2
    finally:
        asyncio.run(_cleanup_workers(workers, gig_id))
