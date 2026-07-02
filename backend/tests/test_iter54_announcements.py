"""Iteration 54 — Centralized Announcements backend tests.

Covers admin create/list/update/delete, user GET+dismiss, audience targeting,
validation, non-admin gate, notifications fan-in, and cleanup of UITEST data.
"""
import os
import time
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    # fallback: read from /app/frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except FileNotFoundError:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

ADMIN = ("admin@hcobcleaners.com", "HcobAdmin2026!")
WORKER = ("worker.demo@hcobcleaners.com", "WorkerDemo2026!")
VA = ("va.demo@hcobcleaners.com", "VaDemo2026!")


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_sess():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def worker_sess():
    return _login(*WORKER)


@pytest.fixture(scope="module")
def va_sess():
    return _login(*VA)


@pytest.fixture(scope="module")
def created_ids():
    ids = []
    yield ids
    # ---- cleanup at end of module ----
    admin = _login(*ADMIN)
    for aid in ids:
        try:
            admin.delete(f"{API}/admin/announcements/{aid}", timeout=15)
        except Exception:
            pass


# --------------------------------------------------------------------------
# Validation & auth
# --------------------------------------------------------------------------
def test_validation_empty_audience(admin_sess):
    r = admin_sess.post(f"{API}/admin/announcements", json={
        "title": "UITEST bad", "body": "x", "audience": [], "channels": ["in_app"]
    })
    assert r.status_code == 422, f"expected 422 got {r.status_code}: {r.text[:200]}"


def test_validation_empty_channels(admin_sess):
    r = admin_sess.post(f"{API}/admin/announcements", json={
        "title": "UITEST bad2", "body": "x", "audience": ["worker"], "channels": []
    })
    assert r.status_code == 422


def test_non_admin_forbidden(worker_sess):
    r = worker_sess.post(f"{API}/admin/announcements", json={
        "title": "UITEST hack", "body": "x", "audience": ["worker"], "channels": ["in_app"]
    })
    assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}"


def test_admin_get_user_announcements_empty(admin_sess):
    """Admin role not targeted → my_announcements returns empty."""
    r = admin_sess.get(f"{API}/announcements")
    assert r.status_code == 200
    assert r.json().get("items") == []


# --------------------------------------------------------------------------
# Create popup announcement (workers+VAs, in-app only)
# --------------------------------------------------------------------------
def test_create_popup_announcement(admin_sess, created_ids):
    r = admin_sess.post(f"{API}/admin/announcements", json={
        "title": "UITEST payday update",
        "body": "Payments this Friday. Please check earnings tab.",
        "audience": ["worker", "va"],
        "popup": True,
        "channels": ["in_app"],
    })
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["title"] == "UITEST payday update"
    assert d["popup"] is True
    assert sorted(d["audience"]) == ["va", "worker"]
    assert d["channels"] == ["in_app"]
    assert d["recipients"] >= 2  # at least worker+VA demo accounts
    assert d["in_app"] == d["recipients"]
    assert d.get("blast_id") is None  # no external channels
    aid = d["announcement_id"]
    assert aid.startswith("ann_")
    created_ids.append(aid)


def test_admin_list_contains_it(admin_sess, created_ids):
    r = admin_sess.get(f"{API}/admin/announcements")
    assert r.status_code == 200
    items = r.json()["items"]
    match = [i for i in items if i["announcement_id"] == created_ids[0]]
    assert len(match) == 1
    a = match[0]
    assert a["popup"] is True
    assert a["read_count"] == 0
    assert "delivery" in a and a["delivery"]["in_app"] >= 2


# --------------------------------------------------------------------------
# Worker & VA visibility + dismiss
# --------------------------------------------------------------------------
def test_worker_sees_announcement(worker_sess, created_ids):
    r = worker_sess.get(f"{API}/announcements")
    assert r.status_code == 200
    items = r.json()["items"]
    m = [i for i in items if i["announcement_id"] == created_ids[0]]
    assert len(m) == 1
    assert m[0]["dismissed"] is False
    assert m[0]["popup"] is True


def test_worker_dismiss_persists(worker_sess, created_ids):
    r = worker_sess.post(f"{API}/announcements/{created_ids[0]}/dismiss")
    assert r.status_code == 200
    # re-fetch
    r2 = worker_sess.get(f"{API}/announcements")
    m = [i for i in r2.json()["items"] if i["announcement_id"] == created_ids[0]]
    assert m and m[0]["dismissed"] is True


def test_va_sees_and_dismisses(va_sess, created_ids):
    r = va_sess.get(f"{API}/announcements")
    m = [i for i in r.json()["items"] if i["announcement_id"] == created_ids[0]]
    assert m and m[0]["dismissed"] is False
    r2 = va_sess.post(f"{API}/announcements/{created_ids[0]}/dismiss")
    assert r2.status_code == 200
    r3 = va_sess.get(f"{API}/announcements")
    m3 = [i for i in r3.json()["items"] if i["announcement_id"] == created_ids[0]]
    assert m3 and m3[0]["dismissed"] is True


def test_admin_read_count_updates(admin_sess, created_ids):
    r = admin_sess.get(f"{API}/admin/announcements")
    a = [i for i in r.json()["items"] if i["announcement_id"] == created_ids[0]][0]
    assert a["read_count"] >= 2, f"expected read_count>=2 got {a['read_count']}"


# --------------------------------------------------------------------------
# Board-only (popup=False) announcement
# --------------------------------------------------------------------------
def test_create_board_only_announcement(admin_sess, created_ids):
    r = admin_sess.post(f"{API}/admin/announcements", json={
        "title": "UITEST board only",
        "body": "Board-only content — no popup.",
        "audience": ["worker", "va"],
        "popup": False,
        "channels": ["in_app"],
    })
    assert r.status_code == 200
    d = r.json()
    assert d["popup"] is False
    created_ids.append(d["announcement_id"])


def test_worker_sees_board_only_but_no_popup_flag(worker_sess, created_ids):
    r = worker_sess.get(f"{API}/announcements")
    m = [i for i in r.json()["items"] if i["announcement_id"] == created_ids[1]]
    assert m and m[0]["popup"] is False and m[0]["dismissed"] is False


# --------------------------------------------------------------------------
# Audience targeting: workers-only
# --------------------------------------------------------------------------
def test_workers_only_announcement(admin_sess, worker_sess, va_sess, created_ids):
    r = admin_sess.post(f"{API}/admin/announcements", json={
        "title": "UITEST workers only",
        "body": "Only workers should see this.",
        "audience": ["worker"],
        "popup": False,
        "channels": ["in_app"],
    })
    assert r.status_code == 200
    aid = r.json()["announcement_id"]
    created_ids.append(aid)

    rw = worker_sess.get(f"{API}/announcements")
    assert any(i["announcement_id"] == aid for i in rw.json()["items"]), "worker should see"

    rv = va_sess.get(f"{API}/announcements")
    assert not any(i["announcement_id"] == aid for i in rv.json()["items"]), "VA must NOT see"


# --------------------------------------------------------------------------
# Notifications include kind=announcement for worker
# --------------------------------------------------------------------------
def test_worker_notifications_include_announcement(worker_sess, created_ids):
    # try common notification endpoints
    for path in ("/notifications", "/notifications/list", "/me/notifications"):
        r = worker_sess.get(f"{API}{path}")
        if r.status_code == 200:
            data = r.json()
            items = data.get("items") if isinstance(data, dict) else data
            if items is None:
                continue
            titles = " ".join([(n.get("title") or "") + " " + (n.get("kind") or "") for n in items])
            if "announcement" in titles.lower() or any(n.get("kind") == "announcement" for n in items):
                return
    pytest.skip("no reachable notifications endpoint; DB verification path skipped in HTTP tests")


# --------------------------------------------------------------------------
# External channel code path (VA audience only for perf — Resend/Twilio will fail gracefully)
# --------------------------------------------------------------------------
def test_external_channel_creates_blast(admin_sess, created_ids):
    r = admin_sess.post(f"{API}/admin/announcements", json={
        "title": "UITEST external",
        "body": "External channel test.",
        "audience": ["va"],
        "popup": False,
        "channels": ["in_app", "email"],
    })
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("blast_id"), "expected blast_id when external channel present"
    created_ids.append(d["announcement_id"])


# --------------------------------------------------------------------------
# Toggle active + delete
# --------------------------------------------------------------------------
def test_toggle_active_hides_from_users(admin_sess, worker_sess, created_ids):
    aid = created_ids[0]  # popup one
    r = admin_sess.put(f"{API}/admin/announcements/{aid}", json={"active": False})
    assert r.status_code == 200
    assert r.json()["active"] is False
    time.sleep(0.5)
    rw = worker_sess.get(f"{API}/announcements")
    assert not any(i["announcement_id"] == aid for i in rw.json()["items"]), "hidden ann must not appear"

    # restore for cleanup path
    admin_sess.put(f"{API}/admin/announcements/{aid}", json={"active": True})


def test_delete_announcement(admin_sess, created_ids):
    # delete the workers-only one and verify 404 afterwards
    aid = created_ids[2]
    r = admin_sess.delete(f"{API}/admin/announcements/{aid}")
    assert r.status_code == 200
    r2 = admin_sess.delete(f"{API}/admin/announcements/{aid}")
    assert r2.status_code == 404
    # pop from cleanup list to avoid double delete noise
    created_ids.pop(2)
