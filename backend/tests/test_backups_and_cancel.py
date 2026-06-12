"""
Backend tests for backup workers, cancel-shift, and email notifications.
Uses direct DB manipulation for setup to avoid the worker-side profile/ID gates.
"""
import os
import time
import uuid
import asyncio
from datetime import datetime, timedelta, timezone

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
    assert r.status_code == 200, f"Login failed {email}: {r.text}"
    return s


async def _seed_worker_in_db(approved=True):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    email = f"bwt_{uuid.uuid4().hex[:6]}@example.com"
    await db.users.insert_one({
        "user_id": user_id,
        "email": email,
        "name": f"Backup Test {user_id[-6:]}",
        "role": "worker",
        "worker_status": "approved" if approved else "pending",
        "phone": "5551234567",
        "address": "100 Main St",
        "zip_code": "21201",
        "city": "Baltimore", "state": "MD",
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
    })
    client.close()
    return user_id, email


async def _seed_acceptance(gig_id, worker_id, status="accepted", is_backup=False, backup_order=None):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    acc_id = f"acc_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.gig_acceptances.insert_one({
        "acceptance_id": acc_id,
        "gig_id": gig_id,
        "worker_id": worker_id,
        "status": status,
        "is_backup": is_backup,
        "backup_order": backup_order,
        "requested_at": now,
        "accepted_at": now if status in ("accepted", "backup") else None,
        "approved_by": "test",
    })
    client.close()
    return acc_id


async def _bump_gig(gig_id, slots_filled=None, backups_filled=None):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    upd = {}
    if slots_filled is not None:
        upd["slots_filled"] = slots_filled
    if backups_filled is not None:
        upd["backups_filled"] = backups_filled
    if upd:
        await db.gigs.update_one({"gig_id": gig_id}, {"$set": upd})
    client.close()


def _async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(scope="module")
def admin_session():
    return _login(OWNER_EMAIL, OWNER_PASSWORD)


def _create_gig(admin_session, *, slots=1, backup_slots=0, future_hours=72):
    sched = (datetime.now(timezone.utc) + timedelta(hours=future_hours)).isoformat()
    r = admin_session.post(
        f"{API}/gigs",
        json={
            "title": f"Backup Test {uuid.uuid4().hex[:6]}",
            "description": "automated test",
            "category": "cleaning",
            "subcategory": "deep",
            "location": "100 Test St",
            "scheduled_date": "Fri Mar 6 · 9am",
            "scheduled_at": sched,
            "pay_rate": 25.0,
            "pay_type": "hourly",
            "slots": slots,
            "backup_slots": backup_slots,
        },
        timeout=20,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _delete_gig(admin_session, gig_id):
    admin_session.delete(f"{API}/gigs/{gig_id}", timeout=20)


# ---------------------------------------------------------------------------
def test_gig_create_with_backup_slots(admin_session):
    g = _create_gig(admin_session, slots=1, backup_slots=2)
    assert g["backup_slots"] == 2
    assert g["backups_filled"] == 0
    _delete_gig(admin_session, g["gig_id"])


def test_approve_as_backup_via_endpoint(admin_session):
    g = _create_gig(admin_session, slots=1, backup_slots=2)
    worker_id, _ = _async(_seed_worker_in_db())
    acc_id = _async(_seed_acceptance(g["gig_id"], worker_id, status="requested"))
    # Approve as backup
    r = admin_session.post(f"{API}/gigs/{g['gig_id']}/requests/{acc_id}/approve-backup", timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["backup_order"] == 1
    # Re-fetch
    g_data = admin_session.get(f"{API}/gigs/{g['gig_id']}", timeout=20).json()
    assert g_data["backups_filled"] == 1
    assert len(g_data["backups"]) == 1
    _delete_gig(admin_session, g["gig_id"])


def test_cancel_shift_auto_promotes_backup(admin_session):
    g = _create_gig(admin_session, slots=1, backup_slots=1)
    # Seed: 1 primary (worker A), 1 backup (worker B)
    workerA, emailA = _async(_seed_worker_in_db())
    workerB, _ = _async(_seed_worker_in_db())
    _async(_seed_acceptance(g["gig_id"], workerA, status="accepted"))
    _async(_seed_acceptance(g["gig_id"], workerB, status="backup", is_backup=True, backup_order=1))
    _async(_bump_gig(g["gig_id"], slots_filled=1, backups_filled=1))

    # Worker A logs in & cancels
    # We need to issue a real session for worker A — bcrypt dummy passwords won't login.
    # Bypass: directly insert a session row.
    async def _inject_session(uid):
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        token = uuid.uuid4().hex
        await db.sessions.insert_one({
            "session_token": token,
            "user_id": uid,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        })
        client.close()
        return token

    tok = _async(_inject_session(workerA))
    s = requests.Session()
    s.cookies.set("session_token", tok)
    r = s.post(f"{API}/gigs/{g['gig_id']}/cancel-shift", json={"reason": "sick"}, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["backup_promoted"] is True
    assert body["promoted_worker_id"] == workerB

    # Verify gig state
    g_data = admin_session.get(f"{API}/gigs/{g['gig_id']}", timeout=20).json()
    assert g_data["slots_filled"] == 1, "B should now hold the primary slot"
    assert g_data["backups_filled"] == 0
    assert g_data["status"] == "filled"
    _delete_gig(admin_session, g["gig_id"])


def test_cancel_shift_late_flagged(admin_session):
    g = _create_gig(admin_session, slots=1, backup_slots=0, future_hours=5)
    worker_id, _ = _async(_seed_worker_in_db())
    _async(_seed_acceptance(g["gig_id"], worker_id, status="accepted"))
    _async(_bump_gig(g["gig_id"], slots_filled=1))

    async def _inject_session(uid):
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        token = uuid.uuid4().hex
        await db.sessions.insert_one({
            "session_token": token,
            "user_id": uid,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        })
        client.close()
        return token

    tok = _async(_inject_session(worker_id))
    s = requests.Session()
    s.cookies.set("session_token", tok)
    r = s.post(f"{API}/gigs/{g['gig_id']}/cancel-shift", json={"reason": "conflict"}, timeout=20)
    assert r.status_code == 200
    assert r.json()["is_late"] is True
    _delete_gig(admin_session, g["gig_id"])


def test_manual_promote_endpoint(admin_session):
    g = _create_gig(admin_session, slots=2, backup_slots=1)
    workerA, _ = _async(_seed_worker_in_db())
    workerB, _ = _async(_seed_worker_in_db())
    _async(_seed_acceptance(g["gig_id"], workerA, status="accepted"))
    backup_acc = _async(_seed_acceptance(g["gig_id"], workerB, status="backup", is_backup=True, backup_order=1))
    _async(_bump_gig(g["gig_id"], slots_filled=1, backups_filled=1))

    r = admin_session.post(f"{API}/gigs/{g['gig_id']}/acceptances/{backup_acc}/promote", timeout=20)
    assert r.status_code == 200, r.text

    g_data = admin_session.get(f"{API}/gigs/{g['gig_id']}", timeout=20).json()
    assert g_data["slots_filled"] == 2
    assert g_data["status"] == "filled"
    assert g_data["backups_filled"] == 0
    _delete_gig(admin_session, g["gig_id"])


def test_reject_endpoint_still_works(admin_session):
    g = _create_gig(admin_session, slots=1, backup_slots=0)
    worker_id, _ = _async(_seed_worker_in_db())
    acc_id = _async(_seed_acceptance(g["gig_id"], worker_id, status="requested"))
    r = admin_session.post(f"{API}/gigs/{g['gig_id']}/requests/{acc_id}/reject", timeout=20)
    assert r.status_code == 200
    _delete_gig(admin_session, g["gig_id"])
