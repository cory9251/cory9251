"""Iter 39 extra coverage — gaps the original test_iter39_blast_safety.py
does not cover (per main-agent review request).

This file adds:
  * Non-owner admin (admin@gigblast.com) → 403 on POST /admin/blast-kill-switch
  * GET /admin/blast-kill-switch returns full shape (enabled/source/toggled_at/
    toggled_by/cooldown_seconds) after a toggle round-trip
  * Kill-switch blocks BOTH /gigs/{id}/blast AND /projects/{id}/blast with 503
  * Cooldown isolation — second blast of a DIFFERENT gig in the same window
    is NOT blocked
  * Cooldown applies to /projects/{id}/blast (the original suite only covered
    gigs)
  * in_app-only blast: queued=false, counts.in_app == workers_targeted, and
    the blast surfaces in /api/admin/reports/blasts
  * Regression: full-channel blast (in_app+email+sms+push) returns fast
    (<10s) with queued=true
  * FINAL: verify the kill switch is OFF after the test suite runs

ALL real email sends are short-circuited by the intentionally-invalid Resend
API key in the preview env, so this file does NOT consume Resend quota.
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

OWNER_EMAIL = "admin@hcobcleaners.com"
OWNER_PASSWORD = "HcobAdmin2026!"
NONOWNER_EMAIL = "admin@gigblast.com"
NONOWNER_PASSWORD = "GigBlast2026!"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return s


def _make_gig(admin: requests.Session, suffix: str = "") -> str:
    payload = {
        "title": f"iter39-extra {suffix or uuid.uuid4().hex[:6]}",
        "description": "extra blast safety test",
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


def _make_project_with_gig(admin: requests.Session) -> tuple[str, str]:
    """Create a project plus one open gig linked to it (so blast has something
    to send)."""
    pr = admin.post(
        f"{API}/projects",
        json={"title": f"iter39-extra-proj-{uuid.uuid4().hex[:6]}", "description": ""},
    )
    assert pr.status_code == 200, pr.text
    project_id = pr.json()["project_id"]

    gig_payload = {
        "title": f"iter39-extra-projgig-{uuid.uuid4().hex[:6]}",
        "description": "linked",
        "category": "cleaning",
        "subcategory": "deep",
        "location": "Test · 21201",
        "scheduled_date": "Sat Jan 17 · 9:00 AM",
        "scheduled_at": "2026-01-17T14:00:00.000Z",
        "scheduled_local": "2026-01-17T09:00",
        "pay_rate": 22,
        "pay_type": "hourly",
        "slots": 2,
        "project_id": project_id,
    }
    gr = admin.post(f"{API}/gigs", json=gig_payload)
    assert gr.status_code == 200, gr.text
    return project_id, gr.json()["gig_id"]


def _set_kill_switch(admin: requests.Session, enabled: bool) -> dict:
    r = admin.post(f"{API}/admin/blast-kill-switch", json={"enabled": enabled})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# 1. Non-owner admin → 403 on POST blast-kill-switch
# ---------------------------------------------------------------------------
def test_non_owner_admin_cannot_toggle_kill_switch():
    non_owner = _login(NONOWNER_EMAIL, NONOWNER_PASSWORD)
    # GET is allowed for any admin (require_admin)
    r_get = non_owner.get(f"{API}/admin/blast-kill-switch")
    assert r_get.status_code == 200, r_get.text

    # POST is Owner-only — non-owner admin must get 403
    r = non_owner.post(f"{API}/admin/blast-kill-switch", json={"enabled": True})
    assert r.status_code == 403, f"expected 403 for non-owner POST, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# 2. GET kill-switch shape AFTER an explicit toggle
# ---------------------------------------------------------------------------
def test_kill_switch_get_returns_full_shape():
    owner = _login(OWNER_EMAIL, OWNER_PASSWORD)
    # Toggle ON then OFF so the toggled_at / toggled_by are populated
    _set_kill_switch(owner, True)
    try:
        r = owner.get(f"{API}/admin/blast-kill-switch")
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("enabled", "source", "toggled_at", "toggled_by", "cooldown_seconds"):
            assert k in body, f"missing key: {k}"
        assert body["enabled"] is True
        assert body["source"] in ("db", "env")
        assert body["toggled_by"]  # email or user_id should be present
        assert isinstance(body["cooldown_seconds"], int)
        assert body["cooldown_seconds"] >= 1
    finally:
        _set_kill_switch(owner, False)

    # After turning off, enabled should flip to False
    r2 = owner.get(f"{API}/admin/blast-kill-switch")
    assert r2.status_code == 200
    assert r2.json()["enabled"] is False


# ---------------------------------------------------------------------------
# 3. Kill switch blocks gig AND project blasts with 503
# ---------------------------------------------------------------------------
def test_kill_switch_blocks_project_blast():
    owner = _login(OWNER_EMAIL, OWNER_PASSWORD)
    project_id, gig_id = _make_project_with_gig(owner)
    try:
        _set_kill_switch(owner, True)
        try:
            r = owner.post(
                f"{API}/projects/{project_id}/blast",
                json={"channels": ["in_app"]},
            )
            assert r.status_code == 503, f"expected 503 with kill switch on, got {r.status_code}: {r.text}"
            assert "disabled" in r.text.lower()
        finally:
            _set_kill_switch(owner, False)

        # With kill switch off, project blast succeeds
        r2 = owner.post(
            f"{API}/projects/{project_id}/blast",
            json={"channels": ["in_app"]},
        )
        assert r2.status_code == 200, r2.text
    finally:
        owner.delete(f"{API}/gigs/{gig_id}")
        # Archive the project for cleanup (no hard-delete endpoint)
        owner.patch(f"{API}/projects/{project_id}", json={"archived": True})


# ---------------------------------------------------------------------------
# 4. Cooldown isolation — a DIFFERENT gig is not blocked in the same window
# ---------------------------------------------------------------------------
def test_cooldown_is_per_gig_not_global():
    owner = _login(OWNER_EMAIL, OWNER_PASSWORD)
    gig_a = _make_gig(owner, "A")
    gig_b = _make_gig(owner, "B")
    try:
        r1 = owner.post(f"{API}/gigs/{gig_a}/blast", json={"channels": ["in_app"]})
        assert r1.status_code == 200, r1.text

        # Immediate second call on a DIFFERENT gig must succeed (per-gig cooldown)
        r2 = owner.post(f"{API}/gigs/{gig_b}/blast", json={"channels": ["in_app"]})
        assert r2.status_code == 200, f"different gig should NOT be blocked: {r2.status_code} {r2.text}"

        # And the original gig is still on cooldown
        r3 = owner.post(f"{API}/gigs/{gig_a}/blast", json={"channels": ["in_app"]})
        assert r3.status_code == 429, f"same gig should be on cooldown, got {r3.status_code}: {r3.text}"
    finally:
        owner.delete(f"{API}/gigs/{gig_a}")
        owner.delete(f"{API}/gigs/{gig_b}")


# ---------------------------------------------------------------------------
# 5. Cooldown applies to /projects/{id}/blast
# ---------------------------------------------------------------------------
def test_project_blast_cooldown():
    owner = _login(OWNER_EMAIL, OWNER_PASSWORD)
    project_id, gig_id = _make_project_with_gig(owner)
    try:
        r1 = owner.post(f"{API}/projects/{project_id}/blast", json={"channels": ["in_app"]})
        assert r1.status_code == 200, r1.text

        r2 = owner.post(f"{API}/projects/{project_id}/blast", json={"channels": ["in_app"]})
        assert r2.status_code == 429, f"expected 429 on repeat project blast, got {r2.status_code}: {r2.text}"
        assert "wait" in r2.text.lower() or "cooldown" in r2.text.lower()
    finally:
        owner.delete(f"{API}/gigs/{gig_id}")
        owner.patch(f"{API}/projects/{project_id}", json={"archived": True})


# ---------------------------------------------------------------------------
# 6. in_app-only blast: queued=false, counts.in_app == workers_targeted,
#    appears in /api/admin/reports/blasts
# ---------------------------------------------------------------------------
def test_in_app_only_blast_no_background_task():
    owner = _login(OWNER_EMAIL, OWNER_PASSWORD)
    gig_id = _make_gig(owner, "inapp")
    try:
        t0 = time.time()
        r = owner.post(f"{API}/gigs/{gig_id}/blast", json={"channels": ["in_app"]})
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["queued"] is False, f"in_app-only should NOT queue background: {body}"
        assert body["blast_id"], "blast_id should be returned"
        assert body["counts"]["in_app"] == body["workers_targeted"], (
            f"in_app count {body['counts']['in_app']} must equal workers_targeted "
            f"{body['workers_targeted']}"
        )
        assert body["counts"]["email"] == 0
        assert body["counts"]["sms"] == 0
        assert elapsed < 10, f"in_app-only blast should be fast, took {elapsed:.1f}s"

        # Show up in /admin/reports/blasts
        rr = owner.get(f"{API}/admin/reports/blasts")
        assert rr.status_code == 200, rr.text
        rows = rr.json() if isinstance(rr.json(), list) else rr.json().get("rows", [])
        blast_ids = [r.get("blast_id") for r in rows]
        assert body["blast_id"] in blast_ids, (
            f"blast_id {body['blast_id']} not surfaced in /admin/reports/blasts "
            f"(found {len(rows)} rows)"
        )
    finally:
        owner.delete(f"{API}/gigs/{gig_id}")


# ---------------------------------------------------------------------------
# 7. Regression — full-channel blast still returns fast with queued=true
# ---------------------------------------------------------------------------
def test_full_channel_blast_returns_fast_and_queued():
    owner = _login(OWNER_EMAIL, OWNER_PASSWORD)
    gig_id = _make_gig(owner, "fullch")
    try:
        t0 = time.time()
        r = owner.post(
            f"{API}/gigs/{gig_id}/blast",
            json={"channels": ["in_app", "email", "sms", "push"]},
        )
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["queued"] is True, f"full-channel blast must enqueue background, got {body}"
        assert elapsed < 10, f"full-channel blast should respond in <10s, took {elapsed:.1f}s"
        assert body["blast_id"]
        assert body["counts"]["in_app"] == body["workers_targeted"]
    finally:
        owner.delete(f"{API}/gigs/{gig_id}")


# ---------------------------------------------------------------------------
# 8. FINAL — verify kill switch is OFF (run last alphabetically with "zzz")
# ---------------------------------------------------------------------------
def test_zzz_final_kill_switch_is_off():
    """Failsafe — even if an earlier test died mid-run, ensure the kill switch
    is OFF at the end of the suite so subsequent test runs aren't blocked."""
    owner = _login(OWNER_EMAIL, OWNER_PASSWORD)
    r = owner.get(f"{API}/admin/blast-kill-switch")
    assert r.status_code == 200
    if r.json().get("enabled"):
        _set_kill_switch(owner, False)
        r = owner.get(f"{API}/admin/blast-kill-switch")
    assert r.json()["enabled"] is False, f"FINAL: kill switch should be OFF, got {r.json()}"
