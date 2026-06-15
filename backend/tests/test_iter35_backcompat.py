"""Iter 35 regression: backward-compat for older API callers that don't
send the new scheduled_local field. Single gig POST and recurring POST
must both still succeed."""
import os, time, requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://work-connect-147.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = ("admin@hcobcleaners.com", "HcobAdmin2026!")


def _admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
    assert r.status_code == 200
    return s


def test_old_api_single_gig_without_scheduled_local():
    """Posting without scheduled_local should still succeed."""
    admin = _admin()
    payload = {
        "title": "iter35 old-api single",
        "description": "test",
        "category": "cleaning",
        "subcategory": "deep",
        "location": "Test · 21201",
        "scheduled_date": "Sat Feb 14 · 10:00 AM",
        "scheduled_at": "2026-02-14T15:00:00.000Z",
        "pay_rate": 22,
        "pay_type": "hourly",
        "slots": 1,
    }
    r = admin.post(f"{API}/gigs", json=payload)
    assert r.status_code == 200, r.text
    gid = r.json()["gig_id"]
    try:
        # Get it back
        g = admin.get(f"{API}/gigs/{gid}").json()
        assert g["title"] == payload["title"]
    finally:
        admin.delete(f"{API}/gigs/{gid}")


def test_old_api_recurring_without_scheduled_local():
    """Recurring without scheduled_local still spaces occurrences."""
    admin = _admin()
    payload = {
        "title": "iter35 old-api recurring",
        "description": "test",
        "category": "cleaning",
        "subcategory": "deep",
        "location": "Test · 21201",
        "scheduled_date": "Mon Feb 16 · 10:00 AM",
        "scheduled_at": "2026-02-16T15:00:00.000Z",
        "pay_rate": 22,
        "pay_type": "hourly",
        "slots": 1,
        "recurrence": "weekly",
        "repeat_count": 2,
    }
    r = admin.post(f"{API}/gigs", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created_count"] == 2
    sid = body.get("series_id")
    assert sid
    # Cleanup
    gigs = admin.get(f"{API}/gigs", params={"status": "all"}).json()
    occs = [g for g in gigs if g.get("series_id") == sid]
    for o in occs:
        admin.delete(f"{API}/gigs/{o['gig_id']}")


def test_workers_filter_admin_only():
    """available_now filter is admin-only (worker hitting /admin/workers gets 403)."""
    admin = _admin()
    # Register a worker
    ts = int(time.time() * 1000)
    w = requests.Session()
    r = w.post(f"{API}/auth/register", json={
        "email": f"iter35_{ts}@example.com",
        "password": "Test1234!",
        "name": "Iter35 Worker",
    })
    assert r.status_code == 200
    wid = r.json()["user_id"]
    try:
        r = w.get(f"{API}/admin/workers", params={"available_now": True})
        assert r.status_code in (401, 403), f"worker should not have access: {r.status_code}"
    finally:
        admin.delete(f"{API}/admin/workers/{wid}")
