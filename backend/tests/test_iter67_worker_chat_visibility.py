"""Iter 67 — Worker customer chat inbox & project page chat panel.

Reproduces the production bug the user hit: contractors couldn't find
project-scoped customer chats because the chat panel only mounted on
specific gig pages. Fixed by:

  1. New endpoint `/api/crew/customer-threads/mine` — returns every chat
     the worker can read (project + gig) across the whole platform.
  2. CustomerChatPanel now also accepts `projectId` and mounts on the
     worker project page.
  3. New WorkerCustomerChatsInbox on the worker home feed surfaces all
     chats in one tile so workers don't have to drill into a gig to
     discover the conversation.

Backend tests below assert the `/mine` endpoint returns the right shape
and the right filtering for both project and gig threads.
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
        pytest.skip(f"login failed: {r.status_code}")
    return s


def _worker_id():
    s = _login(WORKER)
    me = s.get(f"{BASE_URL}/api/auth/me", timeout=20).json()
    return me["user_id"]


def _make_project(sa, title=None):
    payload = {
        "title": title or f"Iter67 Project {uuid.uuid4().hex[:6]}",
        "description": "x",
        "client_name": "C",
    }
    return sa.post(f"{BASE_URL}/api/projects", json=payload, timeout=20).json()


def _make_gig(sa, project_id=None):
    body = {
        "title": f"iter67 gig {uuid.uuid4().hex[:6]}",
        "description": "x",
        "category": "cleaning",
        "cleaning_type": "routine",
        "pay_amount": 100,
        "pay_type": "flat",
        "pay_rate": 100,
        "slots": 1,
        "location": "123 Main St",
        "address_line": "123 Main St",
        "scheduled_date": "Dec 1, 2026",
        "scheduled_local": "2026-12-01T09:00",
        "payment_timeline": "2_3_days",
    }
    if project_id:
        body["project_id"] = project_id
    return sa.post(f"{BASE_URL}/api/gigs", json=body, timeout=20).json()


def _assign_worker(sa, gig_id, worker_id):
    sa.post(
        f"{BASE_URL}/api/gigs/{gig_id}/assign",
        json={"worker_id": worker_id},
        timeout=20,
    )


def test_worker_inbox_endpoint_returns_project_thread_when_participant():
    sa = _login(ADMIN)
    wid = _worker_id()
    p = _make_project(sa)
    # Create project thread with worker as participant
    t = sa.post(
        f"{BASE_URL}/api/admin/projects/{p['project_id']}/customer-threads",
        json={"customer_name": "Jane", "contractor_ids": [wid]},
        timeout=20,
    ).json()
    sw = _login(WORKER)
    r = sw.get(f"{BASE_URL}/api/crew/customer-threads/mine", timeout=20)
    assert r.status_code == 200
    items = r.json()["items"]
    found = next((x for x in items if x["thread_id"] == t["thread_id"]), None)
    assert found is not None
    assert found["scope_type"] == "project"
    # PII still stripped (contractor viewer)
    assert "customer_email" not in found
    assert "token" not in found


def test_worker_inbox_excludes_project_threads_not_a_participant():
    sa = _login(ADMIN)
    p = _make_project(sa)
    # Thread with NO contractor participants
    t = sa.post(
        f"{BASE_URL}/api/admin/projects/{p['project_id']}/customer-threads",
        json={"customer_name": "Jane", "contractor_ids": []},
        timeout=20,
    ).json()
    sw = _login(WORKER)
    r = sw.get(f"{BASE_URL}/api/crew/customer-threads/mine", timeout=20)
    assert r.status_code == 200
    items = r.json()["items"]
    assert not any(x["thread_id"] == t["thread_id"] for x in items)


def test_worker_inbox_includes_gig_thread_when_approved():
    sa = _login(ADMIN)
    wid = _worker_id()
    g = _make_gig(sa)
    _assign_worker(sa, g["gig_id"], wid)
    t = sa.post(
        f"{BASE_URL}/api/admin/customer-threads",
        json={"gig_id": g["gig_id"], "customer_name": "Jane"},
        timeout=20,
    ).json()
    sw = _login(WORKER)
    r = sw.get(f"{BASE_URL}/api/crew/customer-threads/mine", timeout=20)
    assert r.status_code == 200
    items = r.json()["items"]
    found = next((x for x in items if x["thread_id"] == t["thread_id"]), None)
    assert found is not None
    # gig-scoped, scope_type='gig' (or None for legacy docs)
    assert found.get("scope_type") in ("gig", None)


def test_worker_inbox_message_visible_after_admin_sends():
    """End-to-end: admin posts in a project chat → worker sees the
    message via the standard read endpoint (this is exactly the bug
    reported in production)."""
    sa = _login(ADMIN)
    wid = _worker_id()
    p = _make_project(sa)
    t = sa.post(
        f"{BASE_URL}/api/admin/projects/{p['project_id']}/customer-threads",
        json={"customer_name": "Jane", "contractor_ids": [wid]},
        timeout=20,
    ).json()
    # Admin sends a message
    sa.post(
        f"{BASE_URL}/api/admin/customer-threads/{t['thread_id']}/messages",
        json={"text": "Hey crew — let's go"},
        timeout=20,
    )
    # Worker reads
    sw = _login(WORKER)
    r = sw.get(
        f"{BASE_URL}/api/crew/customer-threads/{t['thread_id']}/messages", timeout=20
    )
    assert r.status_code == 200
    msgs = r.json()
    admin_msg = next((m for m in msgs if m["sender_type"] == "admin"), None)
    assert admin_msg is not None, "Admin's message must surface to worker"
    assert admin_msg["text"] == "Hey crew — let's go"


def test_unauthenticated_blocked_from_inbox():
    pub = requests.Session()
    r = pub.get(f"{BASE_URL}/api/crew/customer-threads/mine", timeout=20)
    assert r.status_code in (401, 403)


def test_worker_project_page_chat_uses_project_endpoint():
    """Frontend's CustomerChatPanel(projectId=...) hits this endpoint;
    verify it returns the worker's project chats."""
    sa = _login(ADMIN)
    wid = _worker_id()
    p = _make_project(sa)
    t = sa.post(
        f"{BASE_URL}/api/admin/projects/{p['project_id']}/customer-threads",
        json={"customer_name": "Jane", "contractor_ids": [wid]},
        timeout=20,
    ).json()
    sw = _login(WORKER)
    r = sw.get(
        f"{BASE_URL}/api/crew/projects/{p['project_id']}/customer-threads", timeout=20
    )
    assert r.status_code == 200
    items = r.json()["items"]
    found = next((x for x in items if x["thread_id"] == t["thread_id"]), None)
    assert found is not None
