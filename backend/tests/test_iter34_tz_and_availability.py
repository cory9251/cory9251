"""Tests for the new scheduled_local wall-clock field on gigs and the
'Available now' worker toggle (Iter 34).
"""
import os
import time
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PASSWORD = "HcobAdmin2026!"


def _login(s, email, pwd):
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pwd})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r


def admin_session():
    s = requests.Session()
    _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)
    return s


def fresh_worker():
    """Register a new worker and return (session, user_dict)."""
    ts = int(time.time() * 1000)
    s = requests.Session()
    r = s.post(
        f"{API}/auth/register",
        json={
            "email": f"iter34_{ts}@example.com",
            "password": "Test1234!",
            "name": "Iter34 Worker",
        },
    )
    assert r.status_code == 200, r.text
    return s, r.json()


# ============================================================================
# Available Now toggle
# ============================================================================
def test_availability_toggle_on_off_flow():
    admin = admin_session()
    worker_s, worker = fresh_worker()
    try:
        # ON
        r = worker_s.put(f"{API}/me/availability", json={"available": True})
        assert r.status_code == 200
        body = r.json()
        assert body["available_now"] is True
        assert body["available_until"] is not None

        # /auth/me reflects it
        me = worker_s.get(f"{API}/auth/me").json()
        assert me["available_now"] is True
        assert me["available_until"]

        # Admin filter finds it
        r = admin.get(f"{API}/admin/workers", params={"available_now": True})
        assert r.status_code == 200
        ids = [w["user_id"] for w in r.json()]
        assert worker["user_id"] in ids

        # OFF
        r = worker_s.put(f"{API}/me/availability", json={"available": False})
        assert r.status_code == 200
        assert r.json()["available_now"] is False
        assert r.json()["available_until"] is None

        # Filter no longer includes
        r = admin.get(f"{API}/admin/workers", params={"available_now": True})
        ids = [w["user_id"] for w in r.json()]
        assert worker["user_id"] not in ids
    finally:
        admin.delete(f"{API}/admin/workers/{worker['user_id']}")


def test_availability_custom_hours():
    admin = admin_session()
    worker_s, worker = fresh_worker()
    try:
        r = worker_s.put(f"{API}/me/availability", json={"available": True, "hours": 2})
        assert r.status_code == 200
        body = r.json()
        assert body["available_now"] is True
        # Should have a 2h+ future timestamp
        assert body["available_until"]
    finally:
        admin.delete(f"{API}/admin/workers/{worker['user_id']}")


def test_availability_non_worker_blocked():
    admin = admin_session()
    r = admin.put(f"{API}/me/availability", json={"available": True})
    # Admin shouldn't be able to flip the "worker available" switch.
    assert r.status_code == 403


def test_admin_stats_includes_available_now():
    admin = admin_session()
    r = admin.get(f"{API}/admin/stats")
    assert r.status_code == 200
    body = r.json()
    assert "available_now" in body
    assert isinstance(body["available_now"], int)


# ============================================================================
# scheduled_local wall-clock field
# ============================================================================
def test_gig_stores_scheduled_local():
    admin = admin_session()
    payload = {
        "title": "iter34 single TZ",
        "description": "test",
        "category": "cleaning",
        "subcategory": "deep",
        "location": "Test · 21201",
        "scheduled_date": "Sat Jan 17 · 9:00 AM",
        "scheduled_at": "2026-01-17T14:00:00.000Z",
        "scheduled_local": "2026-01-17T09:00",
        "pay_rate": 20,
        "pay_type": "hourly",
        "slots": 1,
    }
    r = admin.post(f"{API}/gigs", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["scheduled_local"] == "2026-01-17T09:00"
    gid = body["gig_id"]
    try:
        # GET preserves the field
        r = admin.get(f"{API}/gigs/{gid}")
        assert r.status_code == 200
        assert r.json()["scheduled_local"] == "2026-01-17T09:00"
    finally:
        admin.delete(f"{API}/gigs/{gid}")


def test_recurring_uses_wall_clock_for_display():
    """Bug fix: previously the recurring loop used UTC datetime to strftime
    the human display, so an admin in EST creating a 9 AM EST weekly gig
    would see the FIRST occurrence as "9:00 AM" (correct, from payload) and
    every subsequent occurrence as "2:00 PM" (UTC). Now all occurrences
    should match the admin's wall clock."""
    admin = admin_session()
    payload = {
        "title": "iter34 recurring TZ",
        "description": "test",
        "category": "cleaning",
        "subcategory": "deep",
        "location": "Test · 21201",
        "scheduled_date": "Mon Jan 19 · 9:00 AM",
        # 9 AM EST = 14:00 UTC
        "scheduled_at": "2026-01-19T14:00:00.000Z",
        "scheduled_local": "2026-01-19T09:00",
        "pay_rate": 20,
        "pay_type": "hourly",
        "slots": 1,
        "recurrence": "weekly",
        "repeat_count": 3,
    }
    r = admin.post(f"{API}/gigs", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["created_count"] == 3
    series_id = body.get("series_id")
    assert series_id

    # Find all 3 occurrences
    r = admin.get(f"{API}/gigs", params={"status": "all"})
    assert r.status_code == 200
    occs = [g for g in r.json() if g.get("series_id") == series_id]
    occs.sort(key=lambda g: g.get("series_index", 0))
    assert len(occs) == 3
    try:
        # Every occurrence should have a 9:00 AM wall-clock and a display
        # string that says "9:00 AM" (not "2:00 PM").
        for o in occs:
            assert o["scheduled_local"].endswith("T09:00"), o["scheduled_local"]
            assert "9:00 AM" in o["scheduled_date"], o["scheduled_date"]
    finally:
        for o in occs:
            admin.delete(f"{API}/gigs/{o['gig_id']}")
