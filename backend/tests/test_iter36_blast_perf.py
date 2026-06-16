"""Iter 36: Blast endpoint must NOT block on email/sms/push fan-out.

Reproduces the production Cloudflare 524 timeout the user hit when blasting
to ~200-1,000 workers. The /gigs/{id}/blast endpoint now fans the heavy
channels out in a FastAPI BackgroundTask and returns immediately.
"""
import os
import time
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PASSWORD = "HcobAdmin2026!"


def admin_session():
    s = requests.Session()
    r = s.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200, r.text
    return s


def make_gig(admin):
    payload = {
        "title": "iter36 blast perf",
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
    assert r.status_code == 200, r.text
    return r.json()["gig_id"]


def test_blast_returns_fast_with_all_channels():
    """Even with 1,000+ workers, blast must complete the HTTP call in well
    under Cloudflare's 100s timeout. Heavy channels (email + push) run in a
    background task."""
    admin = admin_session()
    gig_id = make_gig(admin)
    try:
        t0 = time.time()
        r = admin.post(
            f"{API}/gigs/{gig_id}/blast",
            json={"channels": ["in_app", "push", "email"]},
        )
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        # Heavy channels must be queued, not synchronous
        assert body.get("queued") is True
        assert body.get("blast_id"), "blast_id should be returned for reconciliation"
        # The request must complete in well under 10s even with thousands of
        # workers. Previously this took >100s and hit Cloudflare's 524 cap.
        assert elapsed < 10, f"blast took {elapsed:.1f}s — should be < 10s"
    finally:
        admin.delete(f"{API}/gigs/{gig_id}")


def test_blast_inapp_only_still_works():
    """In-app blasts should stay inline (fast already) and not be queued."""
    admin = admin_session()
    gig_id = make_gig(admin)
    try:
        r = admin.post(
            f"{API}/gigs/{gig_id}/blast",
            json={"channels": ["in_app"]},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        # No heavy channels → nothing queued
        assert body.get("queued") is False
        # In-app count = number of workers targeted
        assert body["counts"]["in_app"] == body["workers_targeted"]
        assert body["counts"]["in_app"] > 0
    finally:
        admin.delete(f"{API}/gigs/{gig_id}")


def test_blast_log_includes_estimates():
    """The blast log is created synchronously with estimated counts. After
    the background fan-out finishes it gets reconciled, but the log must
    exist immediately so the Reports → Blasts page shows the event."""
    admin = admin_session()
    gig_id = make_gig(admin)
    try:
        r = admin.post(
            f"{API}/gigs/{gig_id}/blast",
            json={"channels": ["in_app", "email"]},
        )
        assert r.status_code == 200
        blast_id = r.json()["blast_id"]

        # Pull the recent blasts report and confirm our blast_id is there
        r = admin.get(f"{API}/admin/reports/blasts")
        assert r.status_code == 200, r.text
        rows = r.json().get("rows", [])
        matching = [b for b in rows if b.get("blast_id") == blast_id]
        assert matching, f"blast {blast_id} not found in {len(rows)} rows"
    finally:
        admin.delete(f"{API}/gigs/{gig_id}")
