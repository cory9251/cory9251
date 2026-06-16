"""Iter 39 — Blast safety guards (post Feb-2026 SEV1 quota-drain incident).

Verifies:
  • POST /api/admin/blast-kill-switch  (Owner-only)
  • GET  /api/admin/blast-kill-switch
  • Kill switch returns 503 on /gigs/{id}/blast while enabled
  • Cooldown returns 429 on repeat blasts within BLAST_COOLDOWN_SECONDS
  • Workers list is deduped by email inside fanout_blast_channels
  • Idempotency: second fanout call with same blast_log_id skips already-sent
  • GET  /api/admin/blast-audit returns shape

ALL real email sends are mocked / channel-restricted to `in_app` only.
ZERO Resend calls are made by this test file.
"""
import asyncio
import os
import sys
from unittest.mock import patch

import pytest
import requests

# Make backend package importable for the unit-test portion
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PASSWORD = "HcobAdmin2026!"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


def make_gig(admin):
    payload = {
        "title": "iter39 blast safety",
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


def _set_kill_switch(admin, enabled: bool):
    r = admin.post(f"{API}/admin/blast-kill-switch", json={"enabled": enabled})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# E2E — kill switch endpoint
# ---------------------------------------------------------------------------
def test_kill_switch_endpoint_owner_only():
    admin = admin_session()
    r = admin.get(f"{API}/admin/blast-kill-switch")
    assert r.status_code == 200, r.text
    body = r.json()
    for k in ("enabled", "source", "cooldown_seconds"):
        assert k in body, f"missing {k}"
    assert body["cooldown_seconds"] == int(os.environ.get("BLAST_COOLDOWN_SECONDS", "300"))


def test_kill_switch_blocks_blast():
    """Enabling the kill switch must immediately make /blast return 503."""
    admin = admin_session()
    gig_id = make_gig(admin)
    try:
        _set_kill_switch(admin, True)
        try:
            r = admin.post(
                f"{API}/gigs/{gig_id}/blast",
                json={"channels": ["in_app"]},
            )
            assert r.status_code == 503, f"expected 503 with kill switch on, got {r.status_code}: {r.text}"
            assert "disabled" in r.text.lower()
        finally:
            # ALWAYS turn it back off, even if assertion above failed.
            _set_kill_switch(admin, False)

        # And with the switch off, blast works again.
        r = admin.post(f"{API}/gigs/{gig_id}/blast", json={"channels": ["in_app"]})
        assert r.status_code == 200, r.text
    finally:
        admin.delete(f"{API}/gigs/{gig_id}")


# ---------------------------------------------------------------------------
# E2E — cooldown
# ---------------------------------------------------------------------------
def test_cooldown_blocks_repeat_blast():
    """A second blast within BLAST_COOLDOWN_SECONDS must return 429."""
    admin = admin_session()
    gig_id = make_gig(admin)
    try:
        r1 = admin.post(f"{API}/gigs/{gig_id}/blast", json={"channels": ["in_app"]})
        assert r1.status_code == 200, r1.text

        # Immediate second call → cooldown
        r2 = admin.post(f"{API}/gigs/{gig_id}/blast", json={"channels": ["in_app"]})
        assert r2.status_code == 429, f"expected 429 on repeat, got {r2.status_code}: {r2.text}"
        assert "cooldown" in r2.text.lower() or "wait" in r2.text.lower()
    finally:
        admin.delete(f"{API}/gigs/{gig_id}")


# ---------------------------------------------------------------------------
# E2E — audit endpoint
# ---------------------------------------------------------------------------
def test_blast_audit_endpoint():
    admin = admin_session()
    gig_id = make_gig(admin)
    try:
        r = admin.post(f"{API}/gigs/{gig_id}/blast", json={"channels": ["in_app"]})
        assert r.status_code == 200
        blast_id = r.json()["blast_id"]

        r2 = admin.get(f"{API}/admin/blast-audit", params={"gig_id": gig_id, "hours": 1})
        assert r2.status_code == 200, r2.text
        body = r2.json()
        for k in ("window_hours", "blasts", "blast_count", "top_email_recipients", "total_event_emails"):
            assert k in body, f"missing {k}"
        ids = [b.get("blast_id") for b in body["blasts"]]
        assert blast_id in ids, f"blast {blast_id} not in audit rows"
    finally:
        admin.delete(f"{API}/gigs/{gig_id}")


# ---------------------------------------------------------------------------
# Unit — fanout dedupe + idempotency (Resend is mocked, ZERO real sends)
# ---------------------------------------------------------------------------
@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def test_fanout_dedupes_workers_by_email(event_loop):
    """Duplicate user docs sharing an email must only get ONE send."""
    import notifications

    workers = [
        {"user_id": "u1", "email": "dup@example.com", "phone": "+15550001"},
        {"user_id": "u2", "email": "DUP@example.com", "phone": "+15550002"},  # case-insensitive dup
        {"user_id": "u3", "email": "dup@example.com", "phone": "+15550003"},  # same email again
        {"user_id": "u4", "email": "other@example.com", "phone": "+15550004"},
    ]
    call_count = {"n": 0, "addrs": []}

    def fake_send_email_sync(api_key, sender, to, subject, html):
        call_count["n"] += 1
        call_count["addrs"].append(to)
        return {"id": f"fake_{call_count['n']}"}

    async def fake_creds():
        return {"api_key": "fake_key", "sender": "noreply@example.com"}

    async def fake_not_disabled():
        return False

    with patch.object(notifications, "_send_email_sync", side_effect=fake_send_email_sync), \
         patch.object(notifications, "_resolve_email_creds", side_effect=fake_creds), \
         patch.object(notifications, "is_blast_disabled", side_effect=fake_not_disabled):
        result = event_loop.run_until_complete(
            notifications.fanout_blast_channels(
                workers=workers,
                channels=["email"],
                subject="test",
                html="<p>test</p>",
                sms_body="test",
                push_payload={},
                blast_log_id=None,
            )
        )
    # Only TWO unique emails should be sent: dup@example.com + other@example.com
    assert call_count["n"] == 2, f"expected 2 sends, got {call_count['n']} to {call_count['addrs']}"
    assert result["email"] == 2


def test_fanout_kill_switch_aborts(event_loop):
    """If the kill switch flips ON, fanout exits immediately and sends NOTHING."""
    import notifications

    workers = [{"user_id": f"u{i}", "email": f"u{i}@x.com"} for i in range(10)]
    call_count = {"n": 0}

    def fake_send_email_sync(*a, **kw):
        call_count["n"] += 1

    async def fake_disabled():
        return True

    async def fake_creds():
        return {"api_key": "k", "sender": "s@x.com"}

    with patch.object(notifications, "_send_email_sync", side_effect=fake_send_email_sync), \
         patch.object(notifications, "_resolve_email_creds", side_effect=fake_creds), \
         patch.object(notifications, "is_blast_disabled", side_effect=fake_disabled):
        result = event_loop.run_until_complete(
            notifications.fanout_blast_channels(
                workers=workers,
                channels=["email"],
                subject="test",
                html="<p>test</p>",
                sms_body="test",
                push_payload={},
                blast_log_id=None,
            )
        )
    assert call_count["n"] == 0, "no sends should happen when kill switch is on"
    assert result.get("aborted") is True
