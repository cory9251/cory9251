"""Iter 66 — Admin-side Customer Chat page.

Verifies the admin send/read endpoints work end-to-end, since the new
AdminCustomerChat.jsx page hits them directly. Backend endpoints already
existed (Iter 63) — these tests pin them down so future refactors don't
break the admin reply path.
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

ADMIN = {"email": "admin@hcobcleaners.com", "password": "HcobAdmin2026!"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"login failed: {r.status_code}")
    return s


def _make_project(s):
    r = s.post(
        f"{BASE_URL}/api/projects",
        json={"title": f"iter66 proj {uuid.uuid4().hex[:6]}", "description": "x", "client_name": "C"},
        timeout=20,
    )
    return r.json()


def _make_project_thread(s, project_id, name="Jane"):
    r = s.post(
        f"{BASE_URL}/api/admin/projects/{project_id}/customer-threads",
        json={"customer_name": name, "contractor_ids": []},
        timeout=20,
    )
    return r.json()


def test_admin_can_get_thread_full_details():
    """Admin GET should include token, customer_email, customer_link, and
    contractors — full PII view since admin owns the thread."""
    sa = _login(ADMIN)
    p = _make_project(sa)
    t = _make_project_thread(sa, p["project_id"])
    r = sa.get(f"{BASE_URL}/api/admin/customer-threads/{t['thread_id']}", timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert body["thread_id"] == t["thread_id"]
    assert body["scope_type"] == "project"
    assert body["customer_name"] == "Jane"
    assert body["token"]
    assert body["customer_link"]
    assert "contractors" in body  # hydrated list (may be empty for project w/ no participants)


def test_admin_can_send_and_read_messages():
    """Admin send should record sender_type='admin' + show up in list."""
    sa = _login(ADMIN)
    p = _make_project(sa)
    t = _make_project_thread(sa, p["project_id"])
    # Send
    r = sa.post(
        f"{BASE_URL}/api/admin/customer-threads/{t['thread_id']}/messages",
        json={"text": "Hello from admin"},
        timeout=20,
    )
    assert r.status_code == 200
    msg = r.json()
    assert msg["sender_type"] == "admin"
    assert msg["text"] == "Hello from admin"
    # Admin list
    r2 = sa.get(
        f"{BASE_URL}/api/admin/customer-threads/{t['thread_id']}/messages", timeout=20
    )
    assert r2.status_code == 200
    msgs = r2.json()
    assert any(m["sender_type"] == "admin" and m["text"] == "Hello from admin" for m in msgs)


def test_admin_message_visible_to_customer_via_token():
    """When admin sends, customer fetching via /api/customer/threads/<token>/messages
    sees it as sender_type='admin' (light-purple HCOB Team bubble)."""
    sa = _login(ADMIN)
    p = _make_project(sa)
    t = _make_project_thread(sa, p["project_id"])
    sa.post(
        f"{BASE_URL}/api/admin/customer-threads/{t['thread_id']}/messages",
        json={"text": "Welcome aboard!"},
        timeout=20,
    )
    pub = requests.Session()
    r = pub.get(f"{BASE_URL}/api/customer/threads/{t['token']}/messages", timeout=20)
    assert r.status_code == 200
    msgs = r.json()
    admin_msg = next((m for m in msgs if m["sender_type"] == "admin"), None)
    assert admin_msg is not None
    assert admin_msg["text"] == "Welcome aboard!"


def test_admin_cannot_send_on_closed_thread():
    sa = _login(ADMIN)
    p = _make_project(sa)
    t = _make_project_thread(sa, p["project_id"])
    sa.post(
        f"{BASE_URL}/api/admin/customer-threads/{t['thread_id']}/close",
        json={"reason": "test"}, timeout=20,
    )
    r = sa.post(
        f"{BASE_URL}/api/admin/customer-threads/{t['thread_id']}/messages",
        json={"text": "still trying"},
        timeout=20,
    )
    assert r.status_code == 410


def test_admin_empty_message_rejected():
    sa = _login(ADMIN)
    p = _make_project(sa)
    t = _make_project_thread(sa, p["project_id"])
    r = sa.post(
        f"{BASE_URL}/api/admin/customer-threads/{t['thread_id']}/messages",
        json={"text": ""},
        timeout=20,
    )
    assert r.status_code == 422


def test_non_admin_blocked_from_admin_endpoints():
    """A worker session shouldn't be able to hit /api/admin/customer-threads/* —
    enforces the role boundary."""
    rs = requests.Session()
    # Try to register a fresh worker
    email = f"w+{uuid.uuid4().hex[:6]}@example.com"
    rr = rs.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": "Test12345!", "name": "Z"},
        timeout=20,
    )
    if rr.status_code != 200:
        pytest.skip("registration failed")
    r = rs.get(f"{BASE_URL}/api/admin/customer-threads/anything/messages", timeout=20)
    assert r.status_code in (401, 403, 404)
