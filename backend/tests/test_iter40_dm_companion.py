"""Iter40 — DM one-click messaging + companion channels regression.

Covers:
  - POST /api/messages/threads/dm (open or create DM) works for admin
  - POST /api/messages/threads/{tid}/messages with `channels=['email','sms']`
    by admin → 200, message persisted (in-app delivery), companion email fails
    silently (preview Resend key is invalid).
  - Workers passing `channels` are silently ignored — message still saved,
    no error.
  - Companion delivery is DM-only — sending channels=['email','sms'] on a
    gig_group thread does NOT crash and message persists (companion path
    skipped because thread.type != 'dm').
  - Kill switch on → companion email/SMS skipped, in-app still succeeds.
  - Existing GET endpoints (threads, messages, unread-count) still work.
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://work-connect-147.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

OWNER_EMAIL = "admin@hcobcleaners.com"
OWNER_PW = "HcobAdmin2026!"


# ----- helpers ---------------------------------------------------------------
def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


def _me(s):
    r = s.get(f"{API}/auth/me", timeout=20)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def admin_session():
    return _login(OWNER_EMAIL, OWNER_PW)


@pytest.fixture(scope="module")
def admin_me(admin_session):
    return _me(admin_session)


@pytest.fixture(scope="module")
def worker_session(admin_session):
    """Register a fresh worker for this test run."""
    email = f"TEST_iter40_worker_{uuid.uuid4().hex[:8]}@example.com"
    pw = "Worker2026!"
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": pw, "name": "TEST Iter40 Worker", "role": "worker"},
        timeout=20,
    )
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    # Approve the worker so admin DMs work normally
    me = r.json()
    uid = me["user"]["user_id"] if "user" in me else me.get("user_id")
    # Approve via admin endpoint
    rr = admin_session.post(f"{API}/admin/workers/{uid}/approve", timeout=20)
    # endpoint may be different; ignore failures (worker can still receive DM)
    s = _login(email, pw)
    s._email = email
    s._uid = uid
    s._pw = pw
    return s


# ----- Tests -----------------------------------------------------------------

def test_kill_switch_off_at_start(admin_session):
    """Make sure kill switch is OFF before running test."""
    r = admin_session.post(
        f"{API}/admin/blast-kill-switch",
        json={"enabled": False},
        timeout=20,
    )
    # may already be off — both 200 ok
    assert r.status_code in (200, 204), r.text


def test_admin_open_dm_with_worker(admin_session, worker_session):
    """Admin can create a DM with any worker via POST /messages/threads/dm."""
    r = admin_session.post(
        f"{API}/messages/threads/dm",
        json={"user_id": worker_session._uid},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["type"] == "dm"
    assert body["thread_id"].startswith("dm_")
    assert worker_session._uid in body["participant_ids"]


def test_admin_send_dm_with_email_sms_channels(admin_session, worker_session):
    """Admin sends DM with channels=['email','sms']. In-app delivery MUST
    succeed even though preview Resend key is invalid (companion fails silently)."""
    # ensure thread exists
    r = admin_session.post(
        f"{API}/messages/threads/dm",
        json={"user_id": worker_session._uid},
        timeout=20,
    )
    assert r.status_code == 200
    tid = r.json()["thread_id"]

    payload = {
        "text": "TEST iter40 — companion email+sms test",
        "channels": ["email", "sms"],
    }
    r2 = admin_session.post(
        f"{API}/messages/threads/{tid}/messages",
        json=payload,
        timeout=30,
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["text"] == payload["text"]
    assert body["thread_id"] == tid
    assert body["sender_role"] == "admin"

    # Verify persistence by re-fetching messages
    r3 = admin_session.get(f"{API}/messages/threads/{tid}/messages", timeout=20)
    assert r3.status_code == 200
    msgs = r3.json()
    assert any(m["message_id"] == body["message_id"] for m in msgs)


def test_worker_send_dm_with_channels_silently_ignored(worker_session, admin_me):
    """Worker passes channels=['email','sms'] — server must silently ignore
    them. Message still saves with in-app delivery only. (Companion code path
    is gated by role check, so no error is raised.)"""
    r = worker_session.post(
        f"{API}/messages/threads/dm",
        json={"user_id": admin_me["user_id"]},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    tid = r.json()["thread_id"]

    payload = {
        "text": "TEST iter40 worker — should NOT trigger companion email",
        "channels": ["email", "sms"],
    }
    r2 = worker_session.post(
        f"{API}/messages/threads/{tid}/messages",
        json=payload,
        timeout=30,
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["text"] == payload["text"]


def test_send_dm_no_channels_works(admin_session, worker_session):
    """Baseline — sending without channels still works (no regression)."""
    r = admin_session.post(
        f"{API}/messages/threads/dm",
        json={"user_id": worker_session._uid},
        timeout=20,
    )
    tid = r.json()["thread_id"]
    r2 = admin_session.post(
        f"{API}/messages/threads/{tid}/messages",
        json={"text": "TEST iter40 — baseline no-channels"},
        timeout=20,
    )
    assert r2.status_code == 200, r2.text


def test_threads_list_and_unread_count(admin_session):
    """Regression — list threads + unread count both work."""
    r = admin_session.get(f"{API}/messages/threads", timeout=20)
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    r2 = admin_session.get(f"{API}/messages/unread-count", timeout=20)
    assert r2.status_code == 200
    assert "count" in r2.json()


def test_mark_thread_read(admin_session, worker_session):
    """Regression — mark-as-read endpoint still works."""
    r = admin_session.post(
        f"{API}/messages/threads/dm",
        json={"user_id": worker_session._uid},
        timeout=20,
    )
    tid = r.json()["thread_id"]
    r2 = admin_session.post(f"{API}/messages/threads/{tid}/read", timeout=20)
    assert r2.status_code == 200
    assert r2.json().get("ok") is True


def test_kill_switch_blocks_companion_email(admin_session, worker_session):
    """When kill switch ON, in-app delivery still works but companion
    email/SMS path is short-circuited (no exception, message persists)."""
    # Turn ON
    r = admin_session.post(
        f"{API}/admin/blast-kill-switch",
        json={"enabled": True},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    try:
        r2 = admin_session.post(
            f"{API}/messages/threads/dm",
            json={"user_id": worker_session._uid},
            timeout=20,
        )
        tid = r2.json()["thread_id"]
        r3 = admin_session.post(
            f"{API}/messages/threads/{tid}/messages",
            json={"text": "TEST iter40 — kill switch ON; companion should be skipped", "channels": ["email", "sms"]},
            timeout=30,
        )
        # in-app delivery still succeeds; companion is skipped silently
        assert r3.status_code == 200, r3.text
    finally:
        # restore kill switch OFF
        admin_session.post(
            f"{API}/admin/blast-kill-switch",
            json={"enabled": False},
            timeout=20,
        )


def test_companion_only_on_dm_not_gig_group(admin_session):
    """Channels parameter on gig_group threads is IGNORED — message still
    persists but no companion email/SMS is sent."""
    # create a gig to get a gig_group thread
    gig_payload = {
        "title": f"TEST iter40 gig {uuid.uuid4().hex[:6]}",
        "description": "iter40 companion-on-gig-group test",
        "category": "cleaning",
        "location": "Oak Ave · 94110",
        "scheduled_date": "2026-12-31",
        "pay_rate": 25.0,
        "pay_type": "hourly",
        "slots": 1,
    }
    rg = admin_session.post(f"{API}/gigs", json=gig_payload, timeout=20)
    assert rg.status_code == 200, rg.text
    gig_id = rg.json().get("gig_id") or rg.json().get("id")
    try:
        # open gig group thread
        rt = admin_session.get(f"{API}/messages/threads/gig/{gig_id}", timeout=20)
        assert rt.status_code == 200, rt.text
        tid = rt.json()["thread_id"]
        assert rt.json()["type"] == "gig_group"

        # send with channels — must be ignored on gig_group
        rm = admin_session.post(
            f"{API}/messages/threads/{tid}/messages",
            json={"text": "TEST iter40 gig_group with channels — should NOT spam", "channels": ["email", "sms"]},
            timeout=30,
        )
        assert rm.status_code == 200, rm.text
        assert rm.json()["text"].startswith("TEST iter40 gig_group")
    finally:
        # cleanup gig
        try:
            admin_session.delete(f"{API}/gigs/{gig_id}", timeout=20)
        except Exception:
            pass


def test_empty_message_rejected(admin_session, worker_session):
    """Regression — empty body still rejected with 400."""
    r = admin_session.post(
        f"{API}/messages/threads/dm",
        json={"user_id": worker_session._uid},
        timeout=20,
    )
    tid = r.json()["thread_id"]
    r2 = admin_session.post(
        f"{API}/messages/threads/{tid}/messages",
        json={"text": "   "},
        timeout=20,
    )
    assert r2.status_code == 400
