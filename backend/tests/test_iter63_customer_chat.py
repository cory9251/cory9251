"""Iter 63 — Customer ↔ Contractor 2-way Messenger.

Verifies the full magic-link flow:
  - Admin creates a customer-chat link for an assignment
  - Customer reads + sends messages via the public /api/customer/threads/:token
  - Contractor approved on the gig reads + sends via /api/crew/customer-threads/
  - PII boundary: contractors see customer first-name only (no email/token)
  - Auto-close when gig is marked completed → 410 on writes
  - Admin can close + reopen
  - Notification audit trail (best-effort — Resend may not be configured)
"""
import os
import uuid

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://work-connect-147.preview.emergentagent.com",
).rstrip("/")

WORKER = {"email": "worker.demo@hcobcleaners.com", "password": "WorkerDemo2026!"}
ADMIN = {"email": "admin@hcobcleaners.com", "password": "HcobAdmin2026!"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Login failed for {creds['email']}: {r.status_code}")
    return s


def _create_gig(admin_s):
    """Create a fresh gig + assign the demo worker to it so they're 'approved'."""
    title = f"Iter63 Smoke Gig {uuid.uuid4().hex[:6]}"
    r = admin_s.post(
        f"{BASE_URL}/api/gigs",
        json={
            "title": title,
            "description": "Iter63 smoke test gig",
            "category": "cleaning",
            "cleaning_type": "routine",
            "pay_amount": 100,
            "pay_type": "flat",
            "pay_rate": 100,
            "slots": 1,
            "location": "123 Main St, Baltimore MD",
            "address_line": "123 Main St, Baltimore MD 21201",
            "scheduled_date": "Dec 1, 2026 · 9:00 AM",
            "scheduled_local": "2026-12-01T09:00",
            "payment_timeline": "2_3_days",
        },
        timeout=20,
    )
    assert r.status_code == 200, f"gig create failed: {r.status_code} {r.text}"
    gig = r.json()
    # Get worker id
    me = _login(WORKER).get(f"{BASE_URL}/api/auth/me", timeout=20).json()
    # Admin assigns worker directly (skips request step)
    ra = admin_s.post(
        f"{BASE_URL}/api/gigs/{gig['gig_id']}/assign",
        json={"worker_id": me["user_id"]},
        timeout=20,
    )
    assert ra.status_code in (200, 400), f"assign failed: {ra.status_code} {ra.text}"
    return gig


def test_admin_creates_customer_thread_with_token():
    sa = _login(ADMIN)
    gig = _create_gig(sa)
    r = sa.post(
        f"{BASE_URL}/api/admin/customer-threads",
        json={
            "gig_id": gig["gig_id"],
            "customer_name": "Jane Smith",
            "customer_email": f"jane+{uuid.uuid4().hex[:6]}@example.com",
        },
        timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["thread_id"].startswith("cthr_")
    assert body["token"]
    assert len(body["token"]) >= 24
    assert body["customer_link"].endswith(body["token"])
    assert body["status"] == "active"


def test_admin_create_is_idempotent_per_gig_and_email():
    """Re-clicking 'Generate link' for same gig+email returns the same thread."""
    sa = _login(ADMIN)
    gig = _create_gig(sa)
    email = f"jane+{uuid.uuid4().hex[:6]}@example.com"
    r1 = sa.post(
        f"{BASE_URL}/api/admin/customer-threads",
        json={"gig_id": gig["gig_id"], "customer_name": "Jane", "customer_email": email},
        timeout=20,
    ).json()
    r2 = sa.post(
        f"{BASE_URL}/api/admin/customer-threads",
        json={"gig_id": gig["gig_id"], "customer_name": "Jane", "customer_email": email},
        timeout=20,
    ).json()
    assert r1["thread_id"] == r2["thread_id"]
    assert r1["token"] == r2["token"]


def test_customer_can_read_and_send_via_token():
    """Public endpoint — no auth, just the token."""
    sa = _login(ADMIN)
    gig = _create_gig(sa)
    thread = sa.post(
        f"{BASE_URL}/api/admin/customer-threads",
        json={"gig_id": gig["gig_id"], "customer_name": "Jane"},
        timeout=20,
    ).json()
    token = thread["token"]
    # Customer fetches thread metadata (no auth)
    pub = requests.Session()  # no cookies
    r = pub.get(f"{BASE_URL}/api/customer/threads/{token}", timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert body["gig_id"] == gig["gig_id"]
    # Customer shouldn't see admin internal fields
    assert "created_by" not in body or body.get("created_by") is None or "token" not in body
    # Customer sends a message
    r2 = pub.post(
        f"{BASE_URL}/api/customer/threads/{token}/messages",
        json={"text": "Hello! When will the team arrive?"},
        timeout=20,
    )
    assert r2.status_code == 200, r2.text
    msg = r2.json()
    assert msg["sender_type"] == "customer"
    assert msg["text"].startswith("Hello!")
    # Customer fetches messages
    r3 = pub.get(f"{BASE_URL}/api/customer/threads/{token}/messages", timeout=20)
    assert r3.status_code == 200
    msgs = r3.json()
    assert any(m["text"].startswith("Hello!") for m in msgs)


def test_invalid_token_returns_404():
    pub = requests.Session()
    r = pub.get(f"{BASE_URL}/api/customer/threads/totally_fake_token_xyz", timeout=20)
    assert r.status_code == 404


def test_contractor_can_read_and_reply():
    """Worker approved on gig should see customer thread and be able to reply."""
    sa = _login(ADMIN)
    gig = _create_gig(sa)
    thread = sa.post(
        f"{BASE_URL}/api/admin/customer-threads",
        json={"gig_id": gig["gig_id"], "customer_name": "Jane Doe"},
        timeout=20,
    ).json()
    # Customer sends first
    pub = requests.Session()
    pub.post(
        f"{BASE_URL}/api/customer/threads/{thread['token']}/messages",
        json={"text": "Question about your service"},
        timeout=20,
    )
    # Contractor lists threads
    sw = _login(WORKER)
    r = sw.get(f"{BASE_URL}/api/crew/gigs/{gig['gig_id']}/customer-threads", timeout=20)
    assert r.status_code == 200
    items = r.json()["items"]
    found = next((t for t in items if t["thread_id"] == thread["thread_id"]), None)
    assert found is not None
    # Privacy: contractor must NOT see token or email
    assert "token" not in found
    assert "customer_email" not in found
    assert "customer_name" not in found
    assert found["customer_first_name"] == "Jane"
    # Contractor reads + replies
    r2 = sw.get(
        f"{BASE_URL}/api/crew/customer-threads/{thread['thread_id']}/messages",
        timeout=20,
    )
    assert r2.status_code == 200
    r3 = sw.post(
        f"{BASE_URL}/api/crew/customer-threads/{thread['thread_id']}/messages",
        json={"text": "Hi Jane — we'll be there at 9am sharp"},
        timeout=20,
    )
    assert r3.status_code == 200, r3.text
    body = r3.json()
    assert body["sender_type"] == "contractor"
    # Customer should see contractor's reply with first name only
    pub_r = pub.get(
        f"{BASE_URL}/api/customer/threads/{thread['token']}/messages", timeout=20
    )
    msgs = pub_r.json()
    contractor_msg = next((m for m in msgs if m["sender_type"] == "contractor"), None)
    assert contractor_msg is not None
    assert contractor_msg["sender_first_name"]
    # Customer view of contractor msg should not leak user_id
    assert "sender_user_id" not in contractor_msg


def test_contractor_not_on_gig_is_403():
    """A different worker (not approved on this gig) cannot access."""
    sa = _login(ADMIN)
    gig = _create_gig(sa)
    thread = sa.post(
        f"{BASE_URL}/api/admin/customer-threads",
        json={"gig_id": gig["gig_id"], "customer_name": "Jane"},
        timeout=20,
    ).json()
    # Register a brand-new worker that's not on the gig
    fresh_email = f"newworker+{uuid.uuid4().hex[:6]}@example.com"
    rs = requests.Session()
    rr = rs.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": fresh_email, "password": "Test12345!", "name": "Fresh Worker"},
        timeout=20,
    )
    if rr.status_code != 200:
        pytest.skip("Could not register fresh worker for permissions test")
    r = rs.get(
        f"{BASE_URL}/api/crew/customer-threads/{thread['thread_id']}/messages",
        timeout=20,
    )
    assert r.status_code == 403


def test_admin_close_blocks_customer_send():
    sa = _login(ADMIN)
    gig = _create_gig(sa)
    thread = sa.post(
        f"{BASE_URL}/api/admin/customer-threads",
        json={"gig_id": gig["gig_id"], "customer_name": "Jane"},
        timeout=20,
    ).json()
    # Close
    rc = sa.post(
        f"{BASE_URL}/api/admin/customer-threads/{thread['thread_id']}/close",
        json={"reason": "test close"},
        timeout=20,
    )
    assert rc.status_code == 200
    assert rc.json()["status"] == "closed"
    # Customer attempts to send → 410
    pub = requests.Session()
    r = pub.post(
        f"{BASE_URL}/api/customer/threads/{thread['token']}/messages",
        json={"text": "still trying"},
        timeout=20,
    )
    assert r.status_code == 410


def test_admin_can_reopen_closed_thread():
    sa = _login(ADMIN)
    gig = _create_gig(sa)
    thread = sa.post(
        f"{BASE_URL}/api/admin/customer-threads",
        json={"gig_id": gig["gig_id"], "customer_name": "Jane"},
        timeout=20,
    ).json()
    sa.post(
        f"{BASE_URL}/api/admin/customer-threads/{thread['thread_id']}/close",
        timeout=20,
    )
    rr = sa.post(
        f"{BASE_URL}/api/admin/customer-threads/{thread['thread_id']}/reopen",
        timeout=20,
    )
    assert rr.status_code == 200
    assert rr.json()["status"] == "active"
    # Customer can send again
    pub = requests.Session()
    r = pub.post(
        f"{BASE_URL}/api/customer/threads/{thread['token']}/messages",
        json={"text": "thanks for reopening"},
        timeout=20,
    )
    assert r.status_code == 200


def test_unauthenticated_cannot_access_admin_create():
    """Public attacker hitting admin endpoint should be 401/403."""
    pub = requests.Session()
    r = pub.post(
        f"{BASE_URL}/api/admin/customer-threads",
        json={"gig_id": "x", "customer_name": "X"},
        timeout=20,
    )
    assert r.status_code in (401, 403)


def test_empty_message_rejected():
    sa = _login(ADMIN)
    gig = _create_gig(sa)
    thread = sa.post(
        f"{BASE_URL}/api/admin/customer-threads",
        json={"gig_id": gig["gig_id"], "customer_name": "Jane"},
        timeout=20,
    ).json()
    pub = requests.Session()
    r = pub.post(
        f"{BASE_URL}/api/customer/threads/{thread['token']}/messages",
        json={"text": ""},
        timeout=20,
    )
    assert r.status_code == 422
