"""Iter 65 — Project-wide Customer Chat.

Verifies:
  - Admin creates a project-scoped thread with explicit participants
  - Idempotency per (project, customer_email)
  - Customer reads/sends via the magic-link path (reuses /c/<token>)
  - Project threads show project_title, scope_type='project'
  - Contractor on participant list can read/reply via /api/crew/customer-threads
  - Contractor NOT on participant list gets 403
  - PII privacy (contractor sees no email / token / full name)
  - Manual close blocks customer sends
  - Admin can update participants
  - Project threads do NOT auto-close (per user choice 2b)
  - Project thread shows up on /crew/gigs/:gig_id/customer-threads for gigs
    in the same project (only for workers in the participant list)
  - Worker-facing /api/crew/projects/:id/customer-threads filters correctly
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


def _create_project(admin_s, title=None):
    payload = {
        "title": title or f"Iter65 Project {uuid.uuid4().hex[:6]}",
        "description": "iter65 project chat test",
        "client_name": "Test Client",
    }
    r = admin_s.post(f"{BASE_URL}/api/projects", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()


def _create_gig_in_project(admin_s, project_id):
    title = f"iter65 gig {uuid.uuid4().hex[:6]}"
    r = admin_s.post(
        f"{BASE_URL}/api/gigs",
        json={
            "title": title,
            "description": "iter65 gig",
            "category": "cleaning",
            "cleaning_type": "routine",
            "pay_amount": 100,
            "pay_type": "flat",
            "pay_rate": 100,
            "slots": 1,
            "location": "123 Main St",
            "address_line": "123 Main St, Baltimore MD 21201",
            "scheduled_date": "Dec 1, 2026 · 9:00 AM",
            "scheduled_local": "2026-12-01T09:00",
            "payment_timeline": "2_3_days",
            "project_id": project_id,
        },
        timeout=20,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _assign_worker_to_gig(admin_s, gig_id, worker_id):
    r = admin_s.post(
        f"{BASE_URL}/api/gigs/{gig_id}/assign",
        json={"worker_id": worker_id},
        timeout=20,
    )
    assert r.status_code in (200, 400), r.text


def _worker_id():
    s = _login(WORKER)
    me = s.get(f"{BASE_URL}/api/auth/me", timeout=20).json()
    return me["user_id"]


def test_admin_create_project_thread_with_participants():
    sa = _login(ADMIN)
    project = _create_project(sa)
    wid = _worker_id()
    r = sa.post(
        f"{BASE_URL}/api/admin/projects/{project['project_id']}/customer-threads",
        json={
            "customer_name": "Jane Test",
            "customer_email": f"jane+{uuid.uuid4().hex[:6]}@example.com",
            "contractor_ids": [wid],
        },
        timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["thread_id"].startswith("cthr_")
    assert body["scope_type"] == "project"
    assert body["project_id"] == project["project_id"]
    assert body["project_title"] == project["title"]
    assert body["status"] == "active"
    assert body["token"]
    assert wid in (body["participant_contractor_ids"] or [])
    assert body["customer_link"].endswith(body["token"])


def test_project_thread_create_idempotent_per_email():
    sa = _login(ADMIN)
    project = _create_project(sa)
    wid = _worker_id()
    email = f"jane+{uuid.uuid4().hex[:6]}@example.com"
    r1 = sa.post(
        f"{BASE_URL}/api/admin/projects/{project['project_id']}/customer-threads",
        json={"customer_name": "Jane", "customer_email": email, "contractor_ids": [wid]},
        timeout=20,
    ).json()
    r2 = sa.post(
        f"{BASE_URL}/api/admin/projects/{project['project_id']}/customer-threads",
        json={"customer_name": "Jane", "customer_email": email, "contractor_ids": [wid]},
        timeout=20,
    ).json()
    assert r1["thread_id"] == r2["thread_id"]


def test_customer_reads_project_thread_via_token():
    sa = _login(ADMIN)
    project = _create_project(sa, title="Customer Renovation Project")
    wid = _worker_id()
    thread = sa.post(
        f"{BASE_URL}/api/admin/projects/{project['project_id']}/customer-threads",
        json={"customer_name": "Jane", "contractor_ids": [wid]},
        timeout=20,
    ).json()
    pub = requests.Session()
    r = pub.get(f"{BASE_URL}/api/customer/threads/{thread['token']}", timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert body["scope_type"] == "project"
    assert body["project_id"] == project["project_id"]
    # Customer should see project title as the display title
    assert body["title"] == "Customer Renovation Project"
    # No admin-only fields leaking
    assert "customer_email" not in body
    assert "token" not in body or body.get("token") is None
    # Contractors hydrated
    assert any(c["user_id"] == wid for c in (body.get("contractors") or []))


def test_customer_sends_and_contractor_replies_on_project_thread():
    sa = _login(ADMIN)
    project = _create_project(sa)
    wid = _worker_id()
    thread = sa.post(
        f"{BASE_URL}/api/admin/projects/{project['project_id']}/customer-threads",
        json={"customer_name": "Jane Doe", "contractor_ids": [wid]},
        timeout=20,
    ).json()
    # Customer posts
    pub = requests.Session()
    r = pub.post(
        f"{BASE_URL}/api/customer/threads/{thread['token']}/messages",
        json={"text": "Hi project crew, any update?"},
        timeout=20,
    )
    assert r.status_code == 200
    # Contractor (participant) reads
    sw = _login(WORKER)
    r2 = sw.get(
        f"{BASE_URL}/api/crew/customer-threads/{thread['thread_id']}/messages",
        timeout=20,
    )
    assert r2.status_code == 200
    msgs = r2.json()
    assert any("any update" in m["text"] for m in msgs)
    # Contractor replies
    r3 = sw.post(
        f"{BASE_URL}/api/crew/customer-threads/{thread['thread_id']}/messages",
        json={"text": "Hey Jane — making progress!"},
        timeout=20,
    )
    assert r3.status_code == 200
    assert r3.json()["sender_type"] == "contractor"


def test_contractor_not_in_participants_is_403():
    sa = _login(ADMIN)
    project = _create_project(sa)
    # Create thread with EMPTY contractor list — worker.demo is not in it
    thread = sa.post(
        f"{BASE_URL}/api/admin/projects/{project['project_id']}/customer-threads",
        json={"customer_name": "Jane", "contractor_ids": []},
        timeout=20,
    ).json()
    sw = _login(WORKER)
    r = sw.get(
        f"{BASE_URL}/api/crew/customer-threads/{thread['thread_id']}/messages",
        timeout=20,
    )
    assert r.status_code == 403


def test_contractor_pii_stripped_on_project_thread():
    sa = _login(ADMIN)
    project = _create_project(sa)
    wid = _worker_id()
    thread = sa.post(
        f"{BASE_URL}/api/admin/projects/{project['project_id']}/customer-threads",
        json={
            "customer_name": "Jane Smith",
            "customer_email": f"jane+{uuid.uuid4().hex[:6]}@example.com",
            "contractor_ids": [wid],
        },
        timeout=20,
    ).json()
    sw = _login(WORKER)
    r = sw.get(
        f"{BASE_URL}/api/crew/projects/{project['project_id']}/customer-threads",
        timeout=20,
    )
    assert r.status_code == 200
    items = r.json()["items"]
    found = next((t for t in items if t["thread_id"] == thread["thread_id"]), None)
    assert found is not None
    assert "token" not in found
    assert "customer_email" not in found
    assert "customer_name" not in found
    assert found["customer_first_name"] == "Jane"


def test_admin_update_participants_adds_contractor():
    sa = _login(ADMIN)
    project = _create_project(sa)
    thread = sa.post(
        f"{BASE_URL}/api/admin/projects/{project['project_id']}/customer-threads",
        json={"customer_name": "Jane", "contractor_ids": []},
        timeout=20,
    ).json()
    wid = _worker_id()
    # Worker initially not in — should 403
    sw = _login(WORKER)
    r = sw.get(
        f"{BASE_URL}/api/crew/customer-threads/{thread['thread_id']}/messages",
        timeout=20,
    )
    assert r.status_code == 403
    # Admin adds the worker
    r2 = sa.patch(
        f"{BASE_URL}/api/admin/customer-threads/{thread['thread_id']}/participants",
        json={"contractor_ids": [wid]},
        timeout=20,
    )
    assert r2.status_code == 200
    assert wid in r2.json()["participant_contractor_ids"]
    # Worker should now have access
    r3 = sw.get(
        f"{BASE_URL}/api/crew/customer-threads/{thread['thread_id']}/messages",
        timeout=20,
    )
    assert r3.status_code == 200


def test_update_participants_rejected_on_gig_thread():
    """The participant editor is project-only. Editing a gig thread
    should 400 — gigs use the gig roster automatically."""
    sa = _login(ADMIN)
    # Create a fresh gig + gig thread
    gig_r = sa.post(
        f"{BASE_URL}/api/gigs",
        json={
            "title": f"iter65 gig {uuid.uuid4().hex[:6]}",
            "description": "x",
            "category": "cleaning",
            "cleaning_type": "routine",
            "pay_amount": 100,
            "pay_type": "flat",
            "pay_rate": 100,
            "slots": 1,
            "location": "123 Main",
            "address_line": "123 Main",
            "scheduled_date": "Dec 1, 2026",
            "scheduled_local": "2026-12-01T09:00",
            "payment_timeline": "2_3_days",
        },
        timeout=20,
    )
    gig = gig_r.json()
    thread = sa.post(
        f"{BASE_URL}/api/admin/customer-threads",
        json={"gig_id": gig["gig_id"], "customer_name": "X"},
        timeout=20,
    ).json()
    r = sa.patch(
        f"{BASE_URL}/api/admin/customer-threads/{thread['thread_id']}/participants",
        json={"contractor_ids": ["fake"]},
        timeout=20,
    )
    assert r.status_code == 400


def test_project_thread_close_blocks_customer_send():
    sa = _login(ADMIN)
    project = _create_project(sa)
    thread = sa.post(
        f"{BASE_URL}/api/admin/projects/{project['project_id']}/customer-threads",
        json={"customer_name": "Jane", "contractor_ids": []},
        timeout=20,
    ).json()
    rc = sa.post(
        f"{BASE_URL}/api/admin/customer-threads/{thread['thread_id']}/close",
        json={"reason": "test"},
        timeout=20,
    )
    assert rc.status_code == 200
    pub = requests.Session()
    r = pub.post(
        f"{BASE_URL}/api/customer/threads/{thread['token']}/messages",
        json={"text": "anyone home"},
        timeout=20,
    )
    assert r.status_code == 410


def test_project_thread_does_not_auto_close_on_archive():
    """Per user spec (choice 2b), project threads do NOT auto-close.
    Even archiving the project leaves the chat alive — admin must close
    manually."""
    sa = _login(ADMIN)
    project = _create_project(sa)
    thread = sa.post(
        f"{BASE_URL}/api/admin/projects/{project['project_id']}/customer-threads",
        json={"customer_name": "Jane", "contractor_ids": []},
        timeout=20,
    ).json()
    # Archive the project
    sa.delete(f"{BASE_URL}/api/projects/{project['project_id']}", timeout=20)
    # Customer can still post
    pub = requests.Session()
    r = pub.post(
        f"{BASE_URL}/api/customer/threads/{thread['token']}/messages",
        json={"text": "follow-up question"},
        timeout=20,
    )
    assert r.status_code == 200


def test_project_thread_shows_up_in_gigs_endpoint():
    """When a contractor opens a gig that's part of a project, the
    project-wide customer thread should also surface (if they're a
    participant) — unified panel."""
    sa = _login(ADMIN)
    project = _create_project(sa)
    gig = _create_gig_in_project(sa, project["project_id"])
    wid = _worker_id()
    _assign_worker_to_gig(sa, gig["gig_id"], wid)
    # Create project thread with worker as participant
    thread = sa.post(
        f"{BASE_URL}/api/admin/projects/{project['project_id']}/customer-threads",
        json={"customer_name": "Jane", "contractor_ids": [wid]},
        timeout=20,
    ).json()
    sw = _login(WORKER)
    r = sw.get(f"{BASE_URL}/api/crew/gigs/{gig['gig_id']}/customer-threads", timeout=20)
    assert r.status_code == 200
    items = r.json()["items"]
    # Project thread should be in the list with scope_type='project'
    found = next((t for t in items if t["thread_id"] == thread["thread_id"]), None)
    assert found is not None
    assert found["scope_type"] == "project"


def test_unauthenticated_cannot_create_project_thread():
    pub = requests.Session()
    r = pub.post(
        f"{BASE_URL}/api/admin/projects/fake/customer-threads",
        json={"customer_name": "X", "contractor_ids": []},
        timeout=20,
    )
    assert r.status_code in (401, 403)


def test_admin_list_project_threads():
    sa = _login(ADMIN)
    project = _create_project(sa)
    sa.post(
        f"{BASE_URL}/api/admin/projects/{project['project_id']}/customer-threads",
        json={"customer_name": "Jane", "contractor_ids": []},
        timeout=20,
    )
    r = sa.get(
        f"{BASE_URL}/api/admin/projects/{project['project_id']}/customer-threads",
        timeout=20,
    )
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 1
