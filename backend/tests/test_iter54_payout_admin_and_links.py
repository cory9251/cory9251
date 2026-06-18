"""Iter 54 (follow-up to Iter 53) — admin payout edit + email link fixes.

Catches the production regressions reported on the live `hcobnetwork.com`:
- email links point to preview URL because `PUBLIC_BASE_URL` env still says preview
- "Add payment method" CTA pointed to `/crew/profile` (not a route) → blank page
- Admin had no way to see/edit a worker's payout method
"""
import os
import importlib
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
WORKER = {"email": "worker.demo@hcobcleaners.com", "password": "WorkerDemo2026!"}


def _admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code}")
    return s


def _worker_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=WORKER, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Worker login failed: {r.status_code}")
    return s


# ---------- Public base URL — preview URL is ignored in favor of prod ------
def test_resolve_public_base_skips_preview_url():
    """If PUBLIC_BASE_URL is somehow set to a preview/emergent hostname (legacy
    env carry-over from preview → prod deploy), we should ignore it and use
    the canonical production fallback so emailed CTAs don't link back to
    preview."""
    os.environ["PUBLIC_BASE_URL"] = "https://work-connect-147.preview.emergentagent.com"
    import notifications
    importlib.reload(notifications)
    assert notifications._resolve_public_base() == "https://hcobnetwork.com"

    os.environ["PUBLIC_BASE_URL"] = "https://x.emergent.host"
    importlib.reload(notifications)
    assert notifications._resolve_public_base() == "https://hcobnetwork.com"

    # A real custom prod URL is honored.
    os.environ["PUBLIC_BASE_URL"] = "https://hcobnetwork.com"
    importlib.reload(notifications)
    assert notifications._resolve_public_base() == "https://hcobnetwork.com"

    # Unset → fall back to default.
    del os.environ["PUBLIC_BASE_URL"]
    importlib.reload(notifications)
    assert notifications._resolve_public_base() == "https://hcobnetwork.com"


# ---------- Welcome/reminder emails CTA points to a real route -------------
def test_email_cta_url_uses_crew_me_not_crew_profile():
    """`/crew/profile` is NOT a route → button click yields blank page.
    Worker profile lives at `/crew/me`. Search the source to confirm
    neither the reminders nor welcome email reference the bad path."""
    for path in ("/app/backend/reminders.py", "/app/backend/notifications.py"):
        with open(path) as f:
            src = f.read()
        assert "/crew/profile" not in src, (
            f"{path} still references /crew/profile (bad route). "
            "Worker profile is at /crew/me."
        )


# ---------- Admin can SET / CLEAR / INVALIDATE a worker's payout ----------
@pytest.fixture
def worker_id():
    s = _admin_session()
    r = s.get(f"{BASE_URL}/api/admin/workers?limit=1", timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    rows = body if isinstance(body, list) else body.get("workers", [])
    if not rows:
        pytest.skip("No workers available to test")
    return rows[0]["user_id"]


def test_admin_can_set_worker_payout(worker_id):
    s = _admin_session()
    r = s.put(
        f"{BASE_URL}/api/admin/workers/{worker_id}/profile",
        json={"payout_method": "chime", "payout_handle": "$AdminEdit"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["payout_method"] == "chime"
    assert body["payout_handle"] == "$AdminEdit"
    assert body.get("payout_updated_at")


def test_admin_can_clear_worker_payout(worker_id):
    s = _admin_session()
    # First set it
    s.put(
        f"{BASE_URL}/api/admin/workers/{worker_id}/profile",
        json={"payout_method": "zelle", "payout_handle": "(555) 111-2222"},
        timeout=20,
    )
    # Then clear with empty string
    r = s.put(
        f"{BASE_URL}/api/admin/workers/{worker_id}/profile",
        json={"payout_method": ""},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("payout_method") in (None, "")
    assert body.get("payout_handle") in (None, "")


def test_admin_invalid_method_rejected(worker_id):
    s = _admin_session()
    r = s.put(
        f"{BASE_URL}/api/admin/workers/{worker_id}/profile",
        json={"payout_method": "venmo", "payout_handle": "@bad"},
        timeout=20,
    )
    assert r.status_code == 400
    assert "zelle" in r.json()["detail"].lower()


def test_admin_method_without_handle_rejected(worker_id):
    s = _admin_session()
    r = s.put(
        f"{BASE_URL}/api/admin/workers/{worker_id}/profile",
        json={"payout_method": "zelle", "payout_handle": ""},
        timeout=20,
    )
    assert r.status_code == 400


def test_admin_payout_visible_in_worker_response(worker_id):
    """Setting it via admin endpoint should make it visible on
    GET /admin/workers/{id}."""
    s = _admin_session()
    s.put(
        f"{BASE_URL}/api/admin/workers/{worker_id}/profile",
        json={"payout_method": "apple_cash", "payout_handle": "+15551112222"},
        timeout=20,
    )
    r = s.get(f"{BASE_URL}/api/admin/workers/{worker_id}", timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert body.get("payout_method") == "apple_cash"
    assert body.get("payout_handle") == "+15551112222"
