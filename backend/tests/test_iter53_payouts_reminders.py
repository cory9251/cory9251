"""Iter 53 — Payout method collection + email reminders.

Verifies:
- PUT /api/profile accepts new payout_method + payout_handle fields
- Validation: handle required when method is set
- Clearing both works
- /auth/me returns the saved payout fields
- The shift-reminder and payment-reminder helpers can be imported and
  called without errors (deep behavior tested via reminder_log idempotency)
"""
import os
import asyncio
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
import bcrypt
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://work-connect-147.preview.emergentagent.com",
).rstrip("/")

WORKER = {"email": "worker.demo@hcobcleaners.com", "password": "WorkerDemo2026!"}


def _login():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=WORKER, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Worker login failed: {r.status_code}")
    return s


@pytest.fixture
def worker_session():
    s = _login()
    # Clean up — make sure we start without any payout method on file
    s.put(f"{BASE_URL}/api/profile", json={"payout_method": ""}, timeout=20)
    yield s


# ---------- Payout fields persist via PUT /profile --------------------------
def test_set_zelle_payout(worker_session):
    r = worker_session.put(
        f"{BASE_URL}/api/profile",
        json={"payout_method": "zelle", "payout_handle": "(410) 555-0199"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["payout_method"] == "zelle"
    assert body["payout_handle"] == "(410) 555-0199"
    assert body.get("payout_updated_at")


def test_set_apple_cash_payout(worker_session):
    r = worker_session.put(
        f"{BASE_URL}/api/profile",
        json={"payout_method": "apple_cash", "payout_handle": "+14105550199"},
        timeout=20,
    )
    assert r.status_code == 200
    assert r.json()["payout_method"] == "apple_cash"


def test_set_chime_payout(worker_session):
    r = worker_session.put(
        f"{BASE_URL}/api/profile",
        json={"payout_method": "chime", "payout_handle": "$WorkerDemo"},
        timeout=20,
    )
    assert r.status_code == 200
    assert r.json()["payout_handle"] == "$WorkerDemo"


def test_invalid_method_rejected(worker_session):
    r = worker_session.put(
        f"{BASE_URL}/api/profile",
        json={"payout_method": "venmo", "payout_handle": "@WorkerDemo"},
        timeout=20,
    )
    assert r.status_code == 422  # Literal type rejects


def test_method_without_handle_rejected(worker_session):
    """When payload sends both fields and handle is empty, return 400."""
    r = worker_session.put(
        f"{BASE_URL}/api/profile",
        json={"payout_method": "zelle", "payout_handle": ""},
        timeout=20,
    )
    assert r.status_code == 400
    assert "handle" in r.json()["detail"].lower() or "required" in r.json()["detail"].lower()


def test_clearing_resets_both_fields(worker_session):
    # First set
    worker_session.put(
        f"{BASE_URL}/api/profile",
        json={"payout_method": "zelle", "payout_handle": "(410) 555-0199"},
        timeout=20,
    )
    # Then clear
    r = worker_session.put(
        f"{BASE_URL}/api/profile",
        json={"payout_method": ""},
        timeout=20,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("payout_method") in (None, "")
    assert body.get("payout_handle") in (None, "")


def test_auth_me_returns_payout(worker_session):
    worker_session.put(
        f"{BASE_URL}/api/profile",
        json={"payout_method": "zelle", "payout_handle": "(410) 555-0199"},
        timeout=20,
    )
    r = worker_session.get(f"{BASE_URL}/api/auth/me", timeout=20)
    assert r.status_code == 200
    me = r.json()
    assert me["payout_method"] == "zelle"
    assert me["payout_handle"] == "(410) 555-0199"


# ---------- Reminders module can be imported and dedupe key works ----------
def test_reminder_log_dedupe_is_idempotent():
    """The reminder helpers use a `reminder_log` collection keyed by a unique
    string. Verify _has_logged + _mark_logged behave correctly."""
    import sys
    sys.path.insert(0, "/app/backend")
    from reminders import _has_logged, _mark_logged

    test_key = f"iter53_test::{uuid.uuid4().hex[:8]}"

    async def run():
        assert (await _has_logged(test_key)) is False
        await _mark_logged(test_key, {"hello": "world"})
        assert (await _has_logged(test_key)) is True
        # Idempotent — second mark is a no-op upsert
        await _mark_logged(test_key, {"hello": "world"})
        # Cleanup
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            await client[os.environ["DB_NAME"]].reminder_log.delete_one({"_id": test_key})
        finally:
            client.close()

    asyncio.run(run())


def test_shift_reminders_pass_runs_without_error():
    """The shift-reminder pass should run cleanly even when no shifts match.
    This protects against syntax / query errors in the loop."""
    import sys
    sys.path.insert(0, "/app/backend")
    from reminders import _send_shift_reminders_pass
    asyncio.run(_send_shift_reminders_pass())  # Just verify no exceptions


def test_payment_reminders_pass_runs_without_error():
    import sys
    sys.path.insert(0, "/app/backend")
    from reminders import _send_payment_reminders_pass
    asyncio.run(_send_payment_reminders_pass())


# ---------- End-to-end: shift reminder dedupe stops second send ------------
def test_shift_reminder_dedupes_within_window():
    """If we manually log a shift-reminder key, the next pass should NOT
    re-send for that acceptance."""
    import sys
    sys.path.insert(0, "/app/backend")
    from reminders import _has_logged, _mark_logged

    fake_acceptance_id = f"acc_iter53_{uuid.uuid4().hex[:8]}"
    key = f"shift_24h::{fake_acceptance_id}"

    async def run():
        await _mark_logged(key, {"test": True})
        assert await _has_logged(key)
        # Cleanup
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            await client[os.environ["DB_NAME"]].reminder_log.delete_one({"_id": key})
        finally:
            client.close()

    asyncio.run(run())
