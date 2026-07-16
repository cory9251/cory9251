"""Regression: duplicating a past-dated gig must not leave it stuck on
`completed`, and rescheduling an auto-completed gig to the future must
resurrect it back to `open`.

Bug report: "Some gigs stay completed even after duplicate + change date."
The auto-complete sweep flipped duplicates to `completed` because they
inherited the source's past `scheduled_at`, and the PUT never reset status
when admin picked a new future date.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _load_backend_url() -> str:
    if os.environ.get("REACT_APP_BACKEND_URL"):
        return os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
    env_path = "/app/frontend/.env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PASSWORD = "HcobAdmin2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _create_past_gig(admin_sess) -> dict:
    """Create a gig whose scheduled_at is 30 days in the past."""
    past = datetime.now(timezone.utc) - timedelta(days=30)
    payload = {
        "title": f"TEST_dup_past_{uuid.uuid4().hex[:6]}",
        "description": "past-dated gig for duplicate regression",
        "category": "cleaning",
        "location": "Curtis Bay · 21226",
        "address_line": "1501 Aspen St, Baltimore MD 21226",
        "scheduled_date": past.strftime("%Y-%m-%d"),
        "scheduled_at": _iso(past),
        "pay_rate": 20,
        "pay_type": "hourly",
        "slots": 1,
    }
    r = admin_sess.post(f"{API}/gigs", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def test_duplicate_of_past_gig_clears_schedule(admin_session):
    """Duplicating a past-dated gig must produce a copy with no schedule,
    so it doesn't immediately get auto-completed by the sweep."""
    src = _create_past_gig(admin_session)
    src_id = src["gig_id"]
    try:
        r = admin_session.post(f"{API}/gigs/{src_id}/duplicate")
        assert r.status_code == 200, r.text
        copy = r.json()
        assert copy["gig_id"] != src_id
        assert copy["status"] == "open"
        # The whole bug: past date must NOT be inherited.
        assert copy.get("scheduled_at") in (None, ""), (
            f"expected scheduled_at cleared, got {copy.get('scheduled_at')}"
        )
        assert copy.get("scheduled_date") in (None, ""), (
            f"expected scheduled_date cleared, got {copy.get('scheduled_date')}"
        )
        # Sanity: re-GET (which triggers the sweep) must still show `open`.
        rg = admin_session.get(f"{API}/gigs/{copy['gig_id']}")
        assert rg.status_code == 200
        assert rg.json()["status"] == "open", (
            "sweep incorrectly auto-completed a duplicate with no schedule"
        )
        admin_session.delete(f"{API}/gigs/{copy['gig_id']}")
    finally:
        admin_session.delete(f"{API}/gigs/{src_id}")


def test_reschedule_completed_gig_to_future_resurrects_it(admin_session):
    """If a gig was auto-completed (past date passed) and admin edits it
    to a future date, status should flip back to `open` and the auto-
    complete markers should clear."""
    import asyncio

    src = _create_past_gig(admin_session)
    gid = src["gig_id"]

    async def _force_auto_complete():
        # Bypass the 60s debounce by writing directly, mimicking what the
        # sweep would do.
        mongo_url = os.environ["MONGO_URL"]
        db_name = os.environ["DB_NAME"]
        client = AsyncIOMotorClient(mongo_url)
        try:
            await client[db_name].gigs.update_one(
                {"gig_id": gid},
                {"$set": {
                    "status": "completed",
                    "auto_completed_at": datetime.now(timezone.utc).isoformat(),
                    "auto_completed_reason": "scheduled_date_passed",
                }},
            )
        finally:
            client.close()

    try:
        asyncio.get_event_loop().run_until_complete(_force_auto_complete())
        rg = admin_session.get(f"{API}/gigs/{gid}")
        assert rg.status_code == 200
        assert rg.json().get("status") == "completed"
        assert rg.json().get("auto_completed_at")

        # Admin reschedules it to tomorrow.
        future = datetime.now(timezone.utc) + timedelta(days=1)
        r = admin_session.put(
            f"{API}/gigs/{gid}",
            json={
                "scheduled_date": future.strftime("%Y-%m-%d"),
                "scheduled_at": _iso(future),
            },
        )
        assert r.status_code == 200, r.text
        fresh = r.json()
        assert fresh["status"] == "open", (
            f"reschedule to future should flip status open, got {fresh['status']}"
        )
        assert fresh.get("auto_completed_at") in (None, "")
        assert fresh.get("auto_completed_reason") in (None, "")

        # Re-GET (sweep runs again) — must stay `open`.
        rg2 = admin_session.get(f"{API}/gigs/{gid}")
        assert rg2.status_code == 200
        assert rg2.json()["status"] == "open"
    finally:
        admin_session.delete(f"{API}/gigs/{gid}")


def test_admin_can_still_manually_set_status_on_reschedule(admin_session):
    """If admin explicitly passes a status in the PUT, the auto-reset must
    NOT clobber it (respect explicit intent)."""
    import asyncio

    src = _create_past_gig(admin_session)
    gid = src["gig_id"]

    async def _force_auto_complete():
        mongo_url = os.environ["MONGO_URL"]
        db_name = os.environ["DB_NAME"]
        client = AsyncIOMotorClient(mongo_url)
        try:
            await client[db_name].gigs.update_one(
                {"gig_id": gid},
                {"$set": {
                    "status": "completed",
                    "auto_completed_at": datetime.now(timezone.utc).isoformat(),
                    "auto_completed_reason": "scheduled_date_passed",
                }},
            )
        finally:
            client.close()

    try:
        asyncio.get_event_loop().run_until_complete(_force_auto_complete())
        future = datetime.now(timezone.utc) + timedelta(days=2)
        r = admin_session.put(
            f"{API}/gigs/{gid}",
            json={
                "scheduled_date": future.strftime("%Y-%m-%d"),
                "scheduled_at": _iso(future),
                "status": "coming_soon",
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "coming_soon"
    finally:
        admin_session.delete(f"{API}/gigs/{gid}")
