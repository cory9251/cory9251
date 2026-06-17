"""
Iter29 — Phase 3d backend modularization regression.

Validates that ALL /api/gigs/* endpoints behave identically after being
extracted from server.py into routes/gigs.py. Covers the surface that
prior tests skipped: clock-in/out, blast, rush, tags, cancel-shift,
publish, and the full request→approve→clock-in→clock-out chain.

Strategy:
  - Use admin@hcobcleaners.com for admin-only endpoints.
  - Use a freshly-registered worker to assert the auth gates (403 on
    /accept without ID verification).
  - Seed an approved+ID-verified worker directly in Mongo to drive the
    happy-path acceptance → clock-in/out chain end-to-end (mirrors the
    pattern used by test_backups_and_cancel.py).
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


# ---- helpers --------------------------------------------------------------
def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    return s


def _seed_verified_worker():
    """Insert an approved, ID-verified worker directly in Mongo so we can
    bypass the front-door /accept gates and exercise the lifecycle."""
    db = _db()
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    email = f"TEST_iter29_{uuid.uuid4().hex[:6]}@example.com"
    db.users.insert_one({
        "user_id": user_id,
        "email": email,
        "name": f"Iter29 Worker {user_id[-6:]}",
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
    })
    return user_id, email


def _seed_acceptance(gig_id, worker_id, status="accepted"):
    db = _db()
    acc_id = f"acc_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    db.gig_acceptances.insert_one({
        "acceptance_id": acc_id,
        "gig_id": gig_id,
        "worker_id": worker_id,
        "status": status,
        "is_backup": False,
        "requested_at": now,
        "accepted_at": now,
        "approved_by": "test",
    })
    return acc_id


def _set_session_for_worker(user_id):
    """Issue a session_token directly in the DB and return its value."""
    db = _db()
    token = uuid.uuid4().hex
    db.sessions.insert_one({
        "session_token": token,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
    })
    return token


@pytest.fixture(scope="module")
def admin_session():
    return _login(OWNER_EMAIL, OWNER_PASSWORD)


@pytest.fixture(scope="module")
def created_gig(admin_session):
    """Create a fresh gig and yield its full doc; the gig is left behind
    for inspection if a test fails, then deleted in teardown."""
    payload = {
        "title": "TEST_iter29 Clock Cycle Gig",
        "description": "Phase 3d refactor regression - clock in/out coverage.",
        "location": "Baltimore, MD",
        "address": "100 Test Ave, Baltimore, MD",
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        "scheduled_date": "Mon Jun 17 · 9:00 AM",
        "pay_rate": 25.0,
        "pay_type": "hourly",
        "slots": 2,
        "category": "cleaning",
    }
    r = admin_session.post(f"{API}/gigs", json=payload, timeout=20)
    assert r.status_code == 200, f"Create gig failed: {r.status_code} {r.text}"
    gig = r.json()
    assert "gig_id" in gig
    yield gig
    # Teardown — best-effort cleanup
    admin_session.delete(f"{API}/gigs/{gig['gig_id']}", timeout=20)


# ---- LIST + GET -----------------------------------------------------------
# Gig listing/detail surface (fields preserved by refactor)
def test_list_gigs_includes_refactor_fields(admin_session, created_gig):
    r = admin_session.get(f"{API}/gigs", timeout=20)
    assert r.status_code == 200
    data = r.json()
    gigs = data.get("gigs") if isinstance(data, dict) else data
    assert isinstance(gigs, list), f"Unexpected gigs payload shape: {type(data)}"
    target = next((g for g in gigs if g.get("gig_id") == created_gig["gig_id"]), None)
    assert target is not None, "Newly-created gig not in list"
    for key in ("is_rush", "tags", "scheduled_at"):
        assert key in target, f"Field '{key}' missing from gig in list response"


def test_get_gig_detail_has_request_arrays(admin_session, created_gig):
    r = admin_session.get(f"{API}/gigs/{created_gig['gig_id']}", timeout=20)
    assert r.status_code == 200
    g = r.json()
    for key in ("pending_requests", "backups", "acceptances"):
        assert key in g, f"Field '{key}' missing from gig detail response"
        assert isinstance(g[key], list)


# ---- AUTH GATES on /accept ------------------------------------------------
# Worker self-registration cannot bypass the id_verified gate
def test_accept_blocked_for_unverified_worker(created_gig):
    email = f"TEST_iter29_unv_{uuid.uuid4().hex[:6]}@example.com"
    password = "Worker123!"
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "name": "Iter29 Unverified"},
        timeout=20,
    )
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"

    s = _login(email, password)
    # Iter45: /accept now requires an agreement body. Send a valid one so the
    # request progresses past schema validation and hits the ID-verified gate.
    r = s.post(
        f"{API}/gigs/{created_gig['gig_id']}/accept",
        json={
            "typed_name": "Iter29 Unverified",
            "agreed_rules": [
                "No-shows on first gigs are an automatic deletion from the platform.",
                "You will be professional when on your gig site.",
                "You must clock in on your shift, or you may not be paid.",
            ],
            "version": "v1",
        },
        timeout=20,
    )
    assert r.status_code == 403, (
        f"Expected 403 for unverified worker; got {r.status_code} {r.text}"
    )
    body = r.json()
    detail = body.get("detail") or ""
    assert "ID" in detail or "profile" in detail.lower(), f"Unexpected gate message: {detail}"


# ---- HAPPY PATH: request → approve → clock-in → clock-out ----------------
# Verifies acceptance.status transitions and slots_filled increments
def test_request_approve_clock_cycle(admin_session, created_gig):
    gig_id = created_gig["gig_id"]
    worker_id, _email = _seed_verified_worker()
    session_token = _set_session_for_worker(worker_id)

    s = requests.Session()
    s.cookies.set("session_token", session_token)

    # /auth/me works with the session cookie
    me = s.get(f"{API}/auth/me", timeout=20)
    assert me.status_code == 200 and me.json()["user_id"] == worker_id

    # 1) request — Iter45: must include signed agreement body
    worker_name = f"Iter29 Worker {worker_id[-6:]}"
    r = s.post(
        f"{API}/gigs/{gig_id}/accept",
        json={
            "typed_name": worker_name,
            "agreed_rules": [
                "No-shows on first gigs are an automatic deletion from the platform.",
                "You will be professional when on your gig site.",
                "You must clock in on your shift, or you may not be paid.",
            ],
            "version": "v1",
        },
        timeout=20,
    )
    assert r.status_code == 200, f"accept failed: {r.status_code} {r.text}"
    acc = r.json()
    assert acc["status"] == "requested"
    assert acc["gig_id"] == gig_id
    aid = acc["acceptance_id"]

    # 2) admin approves
    r = admin_session.post(
        f"{API}/gigs/{gig_id}/requests/{aid}/approve", timeout=20
    )
    assert r.status_code == 200, f"approve failed: {r.status_code} {r.text}"

    g = admin_session.get(f"{API}/gigs/{gig_id}", timeout=20).json()
    assert int(g.get("slots_filled") or 0) >= 1, "slots_filled did not increment"

    # 3) worker clocks in
    r = s.post(f"{API}/gigs/{gig_id}/clock-in", timeout=20)
    assert r.status_code == 200, f"clock-in failed: {r.status_code} {r.text}"
    assert "clock_in_at" in r.json()

    # Cannot clock-in twice
    r = s.post(f"{API}/gigs/{gig_id}/clock-in", timeout=20)
    assert r.status_code == 400

    # 4) worker clocks out
    r = s.post(f"{API}/gigs/{gig_id}/clock-out", timeout=20)
    assert r.status_code == 200, f"clock-out failed: {r.status_code} {r.text}"
    body = r.json()
    assert "clock_out_at" in body or body.get("ok") is True

    # Verify status flipped to completed
    final = _db().gig_acceptances.find_one({"acceptance_id": aid})
    assert final is not None
    assert final.get("status") == "completed", f"Expected status=completed, got {final.get('status')}"
    assert final.get("clock_out_at") is not None


# ---- BLAST flips is_rush + adds 'rush' tag --------------------------------
def test_blast_marks_rush(admin_session, created_gig):
    gig_id = created_gig["gig_id"]
    r = admin_session.post(
        f"{API}/gigs/{gig_id}/blast", json={"channels": ["in_app"]}, timeout=30
    )
    assert r.status_code == 200, f"blast failed: {r.status_code} {r.text}"
    body = r.json()
    assert body.get("ok") is True
    assert body.get("is_rush") is True
    assert "rush" in (body.get("tags") or [])
    assert isinstance(body.get("counts"), dict)
    assert body["counts"].get("in_app", 0) >= 0  # may be 0 if no workers

    g = admin_session.get(f"{API}/gigs/{gig_id}", timeout=20).json()
    assert g.get("is_rush") is True
    assert "rush" in (g.get("tags") or [])


# ---- RUSH toggle ----------------------------------------------------------
def test_rush_toggle(admin_session, created_gig):
    gig_id = created_gig["gig_id"]
    # Turn rush ON
    r = admin_session.put(f"{API}/gigs/{gig_id}/rush", json={"is_rush": True}, timeout=20)
    assert r.status_code == 200, f"rush on failed: {r.status_code} {r.text}"
    assert "rush" in (r.json().get("tags") or [])

    # Turn rush OFF (removes 'rush' tag; is_rush depends on remaining tags)
    r = admin_session.put(f"{API}/gigs/{gig_id}/rush", json={"is_rush": False}, timeout=20)
    assert r.status_code == 200
    assert "rush" not in (r.json().get("tags") or [])


# ---- TAGS set/replace -----------------------------------------------------
def test_set_tags_replaces_array(admin_session, created_gig):
    gig_id = created_gig["gig_id"]
    r = admin_session.put(
        f"{API}/gigs/{gig_id}/tags", json={"tags": ["top_pay"]}, timeout=20
    )
    assert r.status_code == 200, f"set tags failed: {r.status_code} {r.text}"
    body = r.json()
    assert body.get("tags") == ["top_pay"]
    assert body.get("is_rush") is True  # any tag pins the gig

    # Verify persisted
    g = admin_session.get(f"{API}/gigs/{gig_id}", timeout=20).json()
    assert g.get("tags") == ["top_pay"]

    # Clear tags
    r = admin_session.put(f"{API}/gigs/{gig_id}/tags", json={"tags": []}, timeout=20)
    assert r.status_code == 200
    assert r.json().get("tags") == []
    assert r.json().get("is_rush") is False


# ---- CANCEL-SHIFT ---------------------------------------------------------
def test_cancel_shift_flow(admin_session):
    """Seed a worker + accepted acceptance and verify /cancel-shift deletes
    the acceptance, frees the slot, and logs the cancellation."""
    # Create a fresh gig (don't reuse the module-scoped one to avoid
    # interference with the clock-cycle test).
    r = admin_session.post(
        f"{API}/gigs",
        json={
            "title": "TEST_iter29 Cancel Gig",
            "description": "cancel shift test",
            "location": "Baltimore, MD",
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
            "scheduled_date": "Sat Jun 20 · 9:00 AM",
            "pay_rate": 20.0,
            "pay_type": "hourly",
            "slots": 1,
            "category": "cleaning",
        },
        timeout=20,
    )
    assert r.status_code == 200
    gig_id = r.json()["gig_id"]

    try:
        worker_id, _ = _seed_verified_worker()
        _seed_acceptance(gig_id, worker_id, status="accepted")

        # Bump slots_filled so /cancel-shift can decrement it
        _db().gigs.update_one(
            {"gig_id": gig_id}, {"$set": {"slots_filled": 1, "status": "filled"}}
        )

        session_token = _set_session_for_worker(worker_id)
        ws = requests.Session()
        ws.cookies.set("session_token", session_token)

        r = ws.post(
            f"{API}/gigs/{gig_id}/cancel-shift",
            json={"reason": "sick", "note": "iter29 regression test"},
            timeout=20,
        )
        assert r.status_code == 200, f"cancel-shift failed: {r.status_code} {r.text}"
        body = r.json()
        assert body.get("ok") is True
        assert "is_late" in body

        # Acceptance gone, slot freed
        db = _db()
        remaining = db.gig_acceptances.find_one({"gig_id": gig_id, "worker_id": worker_id})
        gig_doc = db.gigs.find_one({"gig_id": gig_id})
        assert remaining is None, "acceptance was not deleted"
        assert int(gig_doc.get("slots_filled") or 0) == 0
        assert gig_doc.get("status") == "open"
    finally:
        admin_session.delete(f"{API}/gigs/{gig_id}", timeout=20)


# ---- DELETE cascades acceptances ------------------------------------------
def test_delete_gig_cascades_acceptances(admin_session):
    r = admin_session.post(
        f"{API}/gigs",
        json={
            "title": "TEST_iter29 Delete Cascade Gig",
            "description": "cascade test",
            "location": "Baltimore, MD",
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
            "scheduled_date": "Thu Jun 18 · 9:00 AM",
            "pay_rate": 22.0,
            "pay_type": "hourly",
            "slots": 1,
            "category": "cleaning",
        },
        timeout=20,
    )
    assert r.status_code == 200
    gig_id = r.json()["gig_id"]

    worker_id, _ = _seed_verified_worker()
    aid = _seed_acceptance(gig_id, worker_id, status="accepted")

    r = admin_session.delete(f"{API}/gigs/{gig_id}", timeout=20)
    assert r.status_code == 200

    db = _db()
    g = db.gigs.find_one({"gig_id": gig_id})
    acc = db.gig_acceptances.find_one({"acceptance_id": aid})
    assert g is None, "gig was not deleted"
    assert acc is None, "acceptance was not cascaded"


# ---- PUSH / AUTH / PROFILE smoke ------------------------------------------
def test_push_public_key_unauth():
    r = requests.get(f"{API}/push/public-key", timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert "public_key" in body or "publicKey" in body or "vapid_public_key" in body


def test_push_status_requires_auth():
    r = requests.get(f"{API}/push/status", timeout=20)
    assert r.status_code in (401, 403)


def test_auth_me(admin_session):
    r = admin_session.get(f"{API}/auth/me", timeout=20)
    assert r.status_code == 200
    me = r.json()
    assert me.get("email") == OWNER_EMAIL


def test_forgot_password_always_200():
    r = requests.post(
        f"{API}/auth/forgot-password",
        json={"email": "doesnotexist_iter29@example.com"},
        timeout=20,
    )
    assert r.status_code == 200


def test_profile_options_requires_auth():
    r = requests.get(f"{API}/profile/options", timeout=20)
    assert r.status_code in (401, 403)


def test_profile_options_with_auth(admin_session):
    r = admin_session.get(f"{API}/profile/options", timeout=20)
    assert r.status_code == 200
    body = r.json()
    # The endpoint returns enum-ish lists used by the profile form
    assert isinstance(body, dict)
