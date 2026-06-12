"""Backend tests for the in-app messenger (DMs + gig group chats)."""
import os
import uuid
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://work-connect-147.preview.emergentagent.com"
).rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

OWNER_EMAIL = "admin@hcobcleaners.com"
OWNER_PASSWORD = "HcobAdmin2026!"
MECHIE_EMAIL = "mechiebadlong77@gmail.com"
MECHIE_PASSWORD = "Mechie2026!"


def _login(email, password):
    s = requests.Session()
    r = s.post(
        f"{API}/auth/login",
        json={"email": email, "password": password},
        timeout=20,
    )
    assert r.status_code == 200, f"Login failed {email}: {r.text}"
    return s


def _me(s):
    return s.get(f"{API}/auth/me", timeout=20).json()


async def _seed_worker(approved=True):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    uid = f"user_{uuid.uuid4().hex[:12]}"
    email = f"msgtest_{uuid.uuid4().hex[:10]}@example.com"
    await db.users.insert_one({
        "user_id": uid,
        "email": email,
        "name": f"MsgTest {uid[-6:]}",
        "role": "worker",
        "worker_status": "approved" if approved else "pending",
        "id_verified": True,
        "auth_provider": "local",
        "password_hash": "$2b$12$dummy",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    client.close()
    return uid, email


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


async def _seed_acceptance(gig_id, worker_id, status="accepted"):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    acc_id = f"acc_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.gig_acceptances.insert_one({
        "acceptance_id": acc_id,
        "gig_id": gig_id,
        "worker_id": worker_id,
        "status": status,
        "is_backup": False,
        "requested_at": now,
        "accepted_at": now,
        "approved_by": "test",
    })
    client.close()
    return acc_id


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(scope="module")
def owner():
    return _login(OWNER_EMAIL, OWNER_PASSWORD)


@pytest.fixture(scope="module")
def mechie():
    return _login(MECHIE_EMAIL, MECHIE_PASSWORD)


def test_admin_to_admin_dm(owner, mechie):
    mechie_id = _me(mechie)["user_id"]
    owner_id = _me(owner)["user_id"]
    r = owner.post(f"{API}/messages/threads/dm", json={"user_id": mechie_id}, timeout=20)
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["type"] == "dm"
    assert sorted(t["participant_ids"]) == sorted([owner_id, mechie_id])

    # Idempotent — same call returns same thread_id
    r2 = owner.post(f"{API}/messages/threads/dm", json={"user_id": mechie_id}, timeout=20)
    assert r2.json()["thread_id"] == t["thread_id"]


def test_send_message_and_unread(owner, mechie):
    mechie_id = _me(mechie)["user_id"]
    t = owner.post(
        f"{API}/messages/threads/dm", json={"user_id": mechie_id}, timeout=20
    ).json()
    tid = t["thread_id"]

    text = f"hello {uuid.uuid4().hex[:6]}"
    r = owner.post(
        f"{API}/messages/threads/{tid}/messages", json={"text": text}, timeout=20
    )
    assert r.status_code == 200, r.text
    msg = r.json()
    assert msg["text"] == text

    # Mechie's unread for this thread should go up
    uc = mechie.get(f"{API}/messages/unread-count", timeout=20).json()["count"]
    assert uc >= 1
    # Sender's unread should NOT include their own message
    suc = owner.get(f"{API}/messages/unread-count", timeout=20).json()["count"]
    # owner has at most 0 for this thread (sender)
    assert suc == 0 or suc < uc

    # Mechie reads the thread
    mechie.post(f"{API}/messages/threads/{tid}/read", timeout=20)
    uc_after = mechie.get(f"{API}/messages/unread-count", timeout=20).json()["count"]
    assert uc_after < uc


def test_empty_message_rejected(owner, mechie):
    mechie_id = _me(mechie)["user_id"]
    t = owner.post(
        f"{API}/messages/threads/dm", json={"user_id": mechie_id}, timeout=20
    ).json()
    tid = t["thread_id"]
    r = owner.post(
        f"{API}/messages/threads/{tid}/messages",
        json={"text": "", "attachment_paths": []},
        timeout=20,
    )
    assert r.status_code == 400


def test_dm_with_self_rejected(owner):
    owner_id = _me(owner)["user_id"]
    r = owner.post(f"{API}/messages/threads/dm", json={"user_id": owner_id}, timeout=20)
    assert r.status_code == 400


def test_worker_cannot_dm_va():
    # Seed a worker and a VA, then attempt the DM
    worker_id, _ = _run(_seed_worker(approved=True))
    # Seed a VA directly
    async def _seed_va():
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        uid = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": uid,
            "email": f"va_{uid[-6:]}@example.com",
            "name": f"VA {uid[-6:]}",
            "role": "va",
            "va_status": "approved",
            "auth_provider": "local",
            "password_hash": "$2b$12$dummy",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        client.close()
        return uid
    va_id = _run(_seed_va())
    tok = _run(_inject_session(worker_id))
    s = requests.Session()
    s.cookies.set("session_token", tok)
    r = s.post(f"{API}/messages/threads/dm", json={"user_id": va_id}, timeout=20)
    # Workers can DM admins or other workers; VAs are not in that list
    assert r.status_code == 403


def test_gig_group_workers_can_access(owner):
    # Owner creates a gig
    sched = (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()
    g = owner.post(
        f"{API}/gigs",
        json={
            "title": f"MsgTest gig {uuid.uuid4().hex[:6]}",
            "description": "x",
            "category": "cleaning",
            "subcategory": "deep",
            "location": "addr",
            "scheduled_date": "Fri",
            "scheduled_at": sched,
            "pay_rate": 25.0,
            "pay_type": "hourly",
            "slots": 2,
        },
        timeout=20,
    ).json()
    gig_id = g["gig_id"]
    # Approved worker on this gig
    wid, _ = _run(_seed_worker(approved=True))
    _run(_seed_acceptance(gig_id, wid, status="accepted"))
    tok = _run(_inject_session(wid))
    s = requests.Session()
    s.cookies.set("session_token", tok)
    # Worker opens group thread
    r = s.get(f"{API}/messages/threads/gig/{gig_id}", timeout=20)
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["type"] == "gig_group"
    assert wid in t["participant_ids"]
    # Worker NOT on the gig is forbidden
    wid2, _ = _run(_seed_worker(approved=True))
    tok2 = _run(_inject_session(wid2))
    s2 = requests.Session()
    s2.cookies.set("session_token", tok2)
    r2 = s2.get(f"{API}/messages/threads/gig/{gig_id}", timeout=20)
    assert r2.status_code == 403
    # Cleanup
    owner.delete(f"{API}/gigs/{gig_id}", timeout=20)


def test_message_attachments_acl(owner, mechie):
    # Owner DMs Mechie + sends attachment; Mechie can fetch; outsider cannot
    mechie_id = _me(mechie)["user_id"]
    t = owner.post(
        f"{API}/messages/threads/dm", json={"user_id": mechie_id}, timeout=20
    ).json()
    tid = t["thread_id"]
    # Upload 1x1 PNG
    import base64, io
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    )
    files = {"file": ("p.png", io.BytesIO(png_bytes), "image/png")}
    up = owner.post(f"{API}/messages/attachments", files=files, timeout=30)
    assert up.status_code == 200, up.text
    path = up.json()["path"]
    # Send message with attachment
    r = owner.post(
        f"{API}/messages/threads/{tid}/messages",
        json={"text": "", "attachment_paths": [path]},
        timeout=20,
    )
    assert r.status_code == 200, r.text

    # Owner can fetch the file (owner)
    f1 = owner.get(f"{API}/files/{path}", timeout=30)
    assert f1.status_code == 200
    # Mechie (admin) can fetch it too
    f2 = mechie.get(f"{API}/files/{path}", timeout=30)
    assert f2.status_code == 200
    # An outsider worker who is NOT in the thread should be blocked
    wid_outsider, _ = _run(_seed_worker(approved=True))
    tok = _run(_inject_session(wid_outsider))
    s = requests.Session()
    s.cookies.set("session_token", tok)
    # Outsiders without admin role: admin role currently auto-allows. Since this
    # is a non-admin worker who didn't upload and isn't in the thread, expect 403.
    f3 = s.get(f"{API}/files/{path}", timeout=30)
    assert f3.status_code == 403


def test_eligible_users_filters(owner, mechie):
    # Owner (admin) sees everyone (excl. self)
    owner_id = _me(owner)["user_id"]
    r = owner.get(f"{API}/messages/eligible-users", timeout=20)
    assert r.status_code == 200
    data = r.json()
    assert all(u["user_id"] != owner_id for u in data)
    assert len(data) > 0

    # Worker with no coworkers can only see admins.
    wid, _ = _run(_seed_worker(approved=True))
    tok = _run(_inject_session(wid))
    s = requests.Session()
    s.cookies.set("session_token", tok)
    r2 = s.get(f"{API}/messages/eligible-users", timeout=20)
    assert r2.status_code == 200
    roles = {u["role"] for u in r2.json()}
    assert roles == {"admin"}, f"Expected only admins, got {roles}"


# --- New coworker-only DM rules (iter25) ----------------------------------

def test_worker_cannot_dm_stranger_worker():
    """Two workers with no shared gig should not be able to DM."""
    w1, _ = _run(_seed_worker(approved=True))
    w2, _ = _run(_seed_worker(approved=True))
    tok = _run(_inject_session(w1))
    s = requests.Session()
    s.cookies.set("session_token", tok)
    r = s.post(f"{API}/messages/threads/dm", json={"user_id": w2}, timeout=20)
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
    assert "shared" in r.text.lower() or "coworker" in r.text.lower()


def test_worker_can_dm_coworker(owner):
    """Two workers who shared a gig can DM each other."""
    # Owner creates a gig
    sched = (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()
    g = owner.post(
        f"{API}/gigs",
        json={
            "title": f"Coworker test {uuid.uuid4().hex[:6]}",
            "description": "x",
            "category": "cleaning",
            "subcategory": "deep",
            "location": "addr",
            "scheduled_date": "Fri",
            "scheduled_at": sched,
            "pay_rate": 25.0,
            "pay_type": "hourly",
            "slots": 3,
        },
        timeout=20,
    ).json()
    gig_id = g["gig_id"]
    # Seed two workers, both approved on this gig
    w1, _ = _run(_seed_worker(approved=True))
    w2, _ = _run(_seed_worker(approved=True))
    _run(_seed_acceptance(gig_id, w1, status="accepted"))
    _run(_seed_acceptance(gig_id, w2, status="accepted"))
    # w1 DMs w2 — should work
    tok = _run(_inject_session(w1))
    s = requests.Session()
    s.cookies.set("session_token", tok)
    r = s.post(f"{API}/messages/threads/dm", json={"user_id": w2}, timeout=20)
    assert r.status_code == 200, f"Expected coworker DM to succeed: {r.text}"
    t = r.json()
    assert sorted(t["participant_ids"]) == sorted([w1, w2])
    owner.delete(f"{API}/gigs/{gig_id}", timeout=20)


def test_worker_can_dm_past_coworker(owner):
    """Completed gigs still count as 'shared' — workers stay connected."""
    sched = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    g = owner.post(
        f"{API}/gigs",
        json={
            "title": f"Past coworker test {uuid.uuid4().hex[:6]}",
            "description": "x",
            "category": "cleaning",
            "subcategory": "deep",
            "location": "addr",
            "scheduled_date": "Fri",
            "scheduled_at": sched,
            "pay_rate": 25.0,
            "pay_type": "hourly",
            "slots": 3,
        },
        timeout=20,
    ).json()
    gig_id = g["gig_id"]
    w1, _ = _run(_seed_worker(approved=True))
    w2, _ = _run(_seed_worker(approved=True))
    _run(_seed_acceptance(gig_id, w1, status="completed"))
    _run(_seed_acceptance(gig_id, w2, status="completed"))
    tok = _run(_inject_session(w1))
    s = requests.Session()
    s.cookies.set("session_token", tok)
    r = s.post(f"{API}/messages/threads/dm", json={"user_id": w2}, timeout=20)
    assert r.status_code == 200, r.text
    owner.delete(f"{API}/gigs/{gig_id}", timeout=20)


def test_worker_can_always_dm_admin(owner):
    """Workers must always be able to reach an admin (the 'Message admin' button)."""
    owner_id = _me(owner)["user_id"]
    w1, _ = _run(_seed_worker(approved=True))
    tok = _run(_inject_session(w1))
    s = requests.Session()
    s.cookies.set("session_token", tok)
    r = s.post(f"{API}/messages/threads/dm", json={"user_id": owner_id}, timeout=20)
    assert r.status_code == 200, r.text


def test_eligible_users_worker_with_coworkers(owner):
    """A worker with coworkers should see admins + those coworkers (not strangers)."""
    sched = (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()
    g = owner.post(
        f"{API}/gigs",
        json={
            "title": f"Eligible-users coworker test {uuid.uuid4().hex[:6]}",
            "description": "x",
            "category": "cleaning",
            "subcategory": "deep",
            "location": "addr",
            "scheduled_date": "Fri",
            "scheduled_at": sched,
            "pay_rate": 25.0,
            "pay_type": "hourly",
            "slots": 3,
        },
        timeout=20,
    ).json()
    gig_id = g["gig_id"]
    w1, _ = _run(_seed_worker(approved=True))
    w2, _ = _run(_seed_worker(approved=True))
    w3_stranger, _ = _run(_seed_worker(approved=True))  # not on the gig
    _run(_seed_acceptance(gig_id, w1, status="accepted"))
    _run(_seed_acceptance(gig_id, w2, status="accepted"))
    tok = _run(_inject_session(w1))
    s = requests.Session()
    s.cookies.set("session_token", tok)
    r = s.get(f"{API}/messages/eligible-users", timeout=20)
    assert r.status_code == 200
    data = r.json()
    user_ids = {u["user_id"] for u in data}
    roles = {u["role"] for u in data}
    assert "admin" in roles
    assert w2 in user_ids, "Coworker should be visible"
    assert w3_stranger not in user_ids, "Stranger worker must NOT be visible"
    owner.delete(f"{API}/gigs/{gig_id}", timeout=20)
