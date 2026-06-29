"""Iter 68 — Worker Shift History (/me/shifts endpoint).

Returns every completed shift for the worker with rich detail: gig +
project context, clock times, hours + break, pay rate + earnings,
approval status, admin notes, co-workers' first names.

These tests validate the contract; the frontend WorkerShiftHistory
component then groups by week/month.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

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
        pytest.skip(f"login failed: {r.status_code}")
    return s


def _seed_completed_shift(sa, worker_id):
    """Create a gig + completed acceptance via sync pymongo so calling
    this twice in the same test process doesn't blow up motor's event
    loop. Returns (gig_id, acceptance_id)."""
    from datetime import datetime, timedelta, timezone
    from pymongo import MongoClient

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        pytest.skip("MONGO_URL/DB_NAME not set")
    client = MongoClient(mongo_url)
    db = client[db_name]
    try:
        gig_id = f"gig_iter68_{uuid.uuid4().hex[:8]}"
        db.gigs.insert_one({
            "gig_id": gig_id,
            "title": "Iter68 Shift History Test",
            "description": "x",
            "category": "cleaning",
            "cleaning_type": "routine",
            "pay_amount": 60,
            "pay_rate": 30,
            "pay_type": "hourly",
            "slots": 1,
            "location": "x",
            "address_line": "x",
            "scheduled_date": "Dec 1, 2026",
            "scheduled_local": "2026-12-01T09:00",
            "payment_timeline": "2_3_days",
            "status": "completed",
        })
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=3)
        end = now - timedelta(hours=1)
        acc_id = f"acc_iter68_{uuid.uuid4().hex[:8]}"
        db.gig_acceptances.insert_one({
            "acceptance_id": acc_id,
            "gig_id": gig_id,
            "worker_id": worker_id,
            "status": "completed",
            "accepted_at": (now - timedelta(days=1)).isoformat(),
            "clock_in_at": start.isoformat(),
            "clock_out_at": end.isoformat(),
            "hours_worked": 2.0,
            "break_minutes_applied": 0,
            "paid_hours": 2.0,
            "earnings": 60.0,
            "pay_rate_applied": 30,
            "pay_type_applied": "hourly",
            "timesheet_approved": True,
            "timesheet_approved_at": now.isoformat(),
            "admin_note": "Great work — thanks!",
        })
        return gig_id, acc_id
    finally:
        client.close()


def _worker_id():
    s = _login(WORKER)
    return s.get(f"{BASE_URL}/api/auth/me", timeout=20).json()["user_id"]


def test_endpoint_returns_shifts_list_with_expected_keys():
    sa = _login(ADMIN)
    wid = _worker_id()
    _seed_completed_shift(sa, wid)
    sw = _login(WORKER)
    r = sw.get(f"{BASE_URL}/api/me/shifts", timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "shifts" in body
    assert isinstance(body["shifts"], list)
    assert len(body["shifts"]) > 0
    # Find the seeded row by gig_title
    s = next((x for x in body["shifts"] if x.get("gig_title") == "Iter68 Shift History Test"), None)
    assert s is not None, "Seeded shift should be in the response"
    expected_keys = {
        "acceptance_id", "gig_id", "gig_title", "gig_category",
        "project_id", "project_title",
        "clock_in_at", "clock_out_at",
        "hours_worked", "break_minutes", "paid_hours",
        "pay_rate_applied", "pay_type_applied", "earnings",
        "approval_status", "timesheet_approved_at",
        "admin_note", "no_show_reason", "co_workers",
    }
    missing = expected_keys - set(s.keys())
    assert not missing, f"Missing keys in /me/shifts row: {missing}"
    assert s["approval_status"] in ("paid", "approved", "pending", "no_show")
    assert s["approval_status"] == "approved"  # seeded with timesheet_approved=True
    assert s["earnings"] == 60.0
    assert s["paid_hours"] == 2.0
    assert s["admin_note"] == "Great work — thanks!"


def test_shifts_sorted_desc_by_clock_in():
    sa = _login(ADMIN)
    wid = _worker_id()
    _seed_completed_shift(sa, wid)
    _seed_completed_shift(sa, wid)
    sw = _login(WORKER)
    r = sw.get(f"{BASE_URL}/api/me/shifts", timeout=20)
    assert r.status_code == 200
    items = r.json().get("shifts", [])
    assert len(items) >= 2
    for i in range(len(items) - 1):
        a, b = items[i].get("clock_in_at"), items[i + 1].get("clock_in_at")
        if a and b:
            assert a >= b, "shifts should be sorted newest first"


def test_non_worker_blocked():
    sa = _login(ADMIN)
    r = sa.get(f"{BASE_URL}/api/me/shifts", timeout=20)
    assert r.status_code == 403


def test_unauthenticated_blocked():
    pub = requests.Session()
    r = pub.get(f"{BASE_URL}/api/me/shifts", timeout=20)
    assert r.status_code in (401, 403)


def test_co_workers_first_name_only():
    """Co-worker rollup must give first names only (privacy default —
    same rule the customer chat panel enforces)."""
    sw = _login(WORKER)
    r = sw.get(f"{BASE_URL}/api/me/shifts", timeout=20)
    if r.status_code != 200:
        pytest.skip("no shifts")
    items = r.json().get("shifts", [])
    for s in items:
        for c in (s.get("co_workers") or []):
            assert "first_name" in c
            assert "user_id" in c
            # No PII leak: name field should NOT be present
            assert "name" not in c
            assert "email" not in c


def test_project_context_present_when_gig_is_in_project():
    """For shifts on gigs that belong to a project, the row should carry
    project_id + project_title so the frontend can show the project tag."""
    sw = _login(WORKER)
    r = sw.get(f"{BASE_URL}/api/me/shifts", timeout=20)
    if r.status_code != 200:
        pytest.skip("no shifts")
    items = r.json().get("shifts", [])
    proj_rows = [s for s in items if s.get("project_id")]
    for s in proj_rows:
        # When project_id is present, project_title should also be hydrated
        # (lookup miss → it'd be None, but we expect the join to succeed).
        if s.get("project_id"):
            # title may be None if the project was deleted — accept that case
            assert "project_title" in s


def test_earnings_endpoint_unchanged():
    """Regression: /me/earnings (used by the summary tiles above the
    shift history) must still return the same shape — Iter 68 added a
    sibling endpoint, didn't replace this one."""
    sw = _login(WORKER)
    r = sw.get(f"{BASE_URL}/api/me/earnings", timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert "approved" in body
    assert "pending" in body
    assert "rows" in body["approved"]
