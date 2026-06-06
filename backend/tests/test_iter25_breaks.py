"""Iteration 25 backend tests — Break Deduction.

Covers:
- gig has `break_minutes` field (default 0, settable via POST/PUT)
- acceptance has `break_minutes` override (settable via timesheet edit/approve)
- _compute_paid_hours and _compute_earnings correctly subtract break time
- worker /me/earnings exposes break_minutes + paid_hours per row + totals
- admin /reports/timesheets returns break_minutes + paid_hours
"""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PASS = "HcobAdmin2026!"


@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return s


@pytest.fixture
def worker_session():
    """Fresh worker each run; admin force-approves the profile."""
    s_admin = requests.Session()
    s_admin.headers.update({"Content-Type": "application/json"})
    s_admin.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}).raise_for_status()

    email = f"break_test_{uuid.uuid4().hex[:8]}@hcobcleaners.com"
    pw = "Break123!"
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": "Break Tester"})
    assert r.status_code == 200, r.text
    user_id = r.json()["user_id"]

    # Force-approve + verify the worker so they can be assigned to gigs
    s_admin.put(
        f"{API}/admin/workers/{user_id}/profile",
        json={
            "first_name": "Break", "last_name": "Tester", "phone": "555-000-1111",
            "address_line": "1 Test", "city": "Houston", "state": "TX", "zip_code": "77001",
            "skills": ["deep_cleaning"], "availability": ["weekdays"],
            "has_vehicle": True,
            "emergency_contact_name": "X", "emergency_contact_phone": "555-555-5555",
            "worker_status": "approved", "id_verified": True,
        },
    )
    s.user_id = user_id
    s.email = email
    yield s
    # cleanup
    s_admin.delete(f"{API}/admin/workers/{user_id}")


def _make_gig(admin_session, break_minutes=0, pay_rate=20.0):
    payload = {
        "title": f"BREAK_TEST_{uuid.uuid4().hex[:6]}",
        "description": "break test",
        "category": "cleaning",
        "subcategory": "deep_clean",
        "location": "Test",
        "scheduled_date": "Today",
        "scheduled_at": "2026-06-06T15:00:00+00:00",
        "pay_rate": pay_rate,
        "pay_type": "hourly",
        "slots": 1,
        "break_minutes": break_minutes,
    }
    r = admin_session.post(f"{API}/gigs", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def test_gig_create_with_break_minutes(admin_session):
    g = _make_gig(admin_session, break_minutes=30)
    assert g["break_minutes"] == 30, f"Expected 30, got {g.get('break_minutes')}"
    # Cleanup
    admin_session.delete(f"{API}/gigs/{g['gig_id']}")


def test_gig_create_default_break_is_zero(admin_session):
    payload = {
        "title": f"BREAK_TEST_DEF_{uuid.uuid4().hex[:6]}",
        "description": "no break",
        "category": "cleaning",
        "subcategory": "deep_clean",
        "location": "Test",
        "scheduled_date": "Today",
        "scheduled_at": "2026-06-06T15:00:00+00:00",
        "pay_rate": 20.0,
        "pay_type": "hourly",
        "slots": 1,
    }
    r = admin_session.post(f"{API}/gigs", json=payload)
    assert r.status_code == 200
    g = r.json()
    assert g["break_minutes"] == 0
    admin_session.delete(f"{API}/gigs/{g['gig_id']}")


def test_gig_update_break_minutes(admin_session):
    g = _make_gig(admin_session, break_minutes=15)
    r = admin_session.put(f"{API}/gigs/{g['gig_id']}", json={"break_minutes": 45})
    assert r.status_code == 200
    assert r.json()["break_minutes"] == 45
    admin_session.delete(f"{API}/gigs/{g['gig_id']}")


def test_clock_out_applies_gig_break(admin_session, worker_session):
    """Worker on a 1-hour gig with break_minutes=30 → 0.5h paid → $10 at $20/hr."""
    g = _make_gig(admin_session, break_minutes=30, pay_rate=20.0)
    # Assign worker
    admin_session.post(f"{API}/gigs/{g['gig_id']}/assign", json={"worker_id": worker_session.user_id})
    # Worker clocks in
    r_in = worker_session.post(f"{API}/gigs/{g['gig_id']}/clock-in")
    assert r_in.status_code == 200, r_in.text
    # Admin sets clock-in to exactly 1 hour ago for predictable hours
    # Use the timesheet edit endpoint to set both times explicitly (1.0h apart)
    a = admin_session.get(f"{API}/gigs/{g['gig_id']}").json()
    acc_id = next(a["acceptance_id"] for a in a["acceptances"])
    r_edit = admin_session.put(
        f"{API}/gigs/{g['gig_id']}/acceptances/{acc_id}/timesheet",
        json={
            "clock_in_at": "2026-06-06T14:00:00+00:00",
            "clock_out_at": "2026-06-06T15:00:00+00:00",
        },
    )
    assert r_edit.status_code == 200, r_edit.text
    body = r_edit.json()
    assert body["hours_worked"] == 1.0
    # break=30 → paid_hours=0.5 → earnings=$10
    detail = admin_session.get(f"{API}/gigs/{g['gig_id']}").json()
    acc = detail["acceptances"][0]
    assert acc.get("break_minutes_applied") == 30, f"Expected break=30, got {acc.get('break_minutes_applied')}"
    assert acc.get("paid_hours") == 0.5, f"Expected paid=0.5, got {acc.get('paid_hours')}"
    assert acc.get("earnings") == 10.0, f"Expected $10, got {acc.get('earnings')}"
    admin_session.delete(f"{API}/gigs/{g['gig_id']}")


def test_per_worker_break_override(admin_session, worker_session):
    """Gig break=15 but admin sets per-worker override=60 — uses 60."""
    g = _make_gig(admin_session, break_minutes=15, pay_rate=20.0)
    admin_session.post(f"{API}/gigs/{g['gig_id']}/assign", json={"worker_id": worker_session.user_id})
    a = admin_session.get(f"{API}/gigs/{g['gig_id']}").json()
    acc_id = next(a["acceptance_id"] for a in a["acceptances"])
    # Set 2h timesheet + override break to 60min
    r_edit = admin_session.put(
        f"{API}/gigs/{g['gig_id']}/acceptances/{acc_id}/timesheet",
        json={
            "clock_in_at": "2026-06-06T13:00:00+00:00",
            "clock_out_at": "2026-06-06T15:00:00+00:00",
            "break_minutes": 60,
        },
    )
    assert r_edit.status_code == 200, r_edit.text
    detail = admin_session.get(f"{API}/gigs/{g['gig_id']}").json()
    acc = detail["acceptances"][0]
    # break_minutes override stored on acceptance is 60
    assert acc.get("break_minutes_applied") == 60
    # 2h - 60min = 1h paid → $20
    assert acc.get("paid_hours") == 1.0
    assert acc.get("earnings") == 20.0
    admin_session.delete(f"{API}/gigs/{g['gig_id']}")


def test_zero_break_no_deduction(admin_session, worker_session):
    """break=0 → paid_hours == hours_worked, earnings = rate * hours."""
    g = _make_gig(admin_session, break_minutes=0, pay_rate=15.0)
    admin_session.post(f"{API}/gigs/{g['gig_id']}/assign", json={"worker_id": worker_session.user_id})
    a = admin_session.get(f"{API}/gigs/{g['gig_id']}").json()
    acc_id = next(a["acceptance_id"] for a in a["acceptances"])
    admin_session.put(
        f"{API}/gigs/{g['gig_id']}/acceptances/{acc_id}/timesheet",
        json={
            "clock_in_at": "2026-06-06T13:00:00+00:00",
            "clock_out_at": "2026-06-06T16:00:00+00:00",
        },
    )
    detail = admin_session.get(f"{API}/gigs/{g['gig_id']}").json()
    acc = detail["acceptances"][0]
    assert acc.get("break_minutes_applied") == 0
    assert acc.get("paid_hours") == 3.0
    assert acc.get("earnings") == 45.0  # $15 * 3h
    admin_session.delete(f"{API}/gigs/{g['gig_id']}")


def test_flat_rate_ignores_break(admin_session, worker_session):
    """Flat-rate gigs pay the posted amount regardless of break."""
    payload = {
        "title": f"BREAK_FLAT_{uuid.uuid4().hex[:6]}",
        "description": "flat", "category": "labor", "subcategory": "moving",
        "location": "Test", "scheduled_date": "Today",
        "scheduled_at": "2026-06-06T15:00:00+00:00",
        "pay_rate": 100.0, "pay_type": "flat", "slots": 1, "break_minutes": 30,
    }
    r = admin_session.post(f"{API}/gigs", json=payload)
    g = r.json()
    admin_session.post(f"{API}/gigs/{g['gig_id']}/assign", json={"worker_id": worker_session.user_id})
    a = admin_session.get(f"{API}/gigs/{g['gig_id']}").json()
    acc_id = next(a["acceptance_id"] for a in a["acceptances"])
    admin_session.put(
        f"{API}/gigs/{g['gig_id']}/acceptances/{acc_id}/timesheet",
        json={
            "clock_in_at": "2026-06-06T13:00:00+00:00",
            "clock_out_at": "2026-06-06T15:00:00+00:00",
        },
    )
    detail = admin_session.get(f"{API}/gigs/{g['gig_id']}").json()
    acc = detail["acceptances"][0]
    assert acc.get("earnings") == 100.0
    admin_session.delete(f"{API}/gigs/{g['gig_id']}")


def test_worker_me_earnings_exposes_break(admin_session, worker_session):
    """/me/earnings returns break_minutes + paid_hours per row + totals."""
    g = _make_gig(admin_session, break_minutes=30, pay_rate=20.0)
    admin_session.post(f"{API}/gigs/{g['gig_id']}/assign", json={"worker_id": worker_session.user_id})
    a = admin_session.get(f"{API}/gigs/{g['gig_id']}").json()
    acc_id = next(a["acceptance_id"] for a in a["acceptances"])
    admin_session.put(
        f"{API}/gigs/{g['gig_id']}/acceptances/{acc_id}/timesheet",
        json={
            "clock_in_at": "2026-06-06T14:00:00+00:00",
            "clock_out_at": "2026-06-06T16:00:00+00:00",
        },
    )
    # Approve so it shows in earnings (worker only sees approved)
    admin_session.post(
        f"{API}/gigs/{g['gig_id']}/acceptances/{acc_id}/approve-timesheet",
        json={},
    )
    r = worker_session.get(f"{API}/me/earnings")
    assert r.status_code == 200
    data = r.json()
    assert "total_paid_hours" in data["approved"]
    rows = data["approved"]["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row.get("break_minutes") == 30
    assert row.get("paid_hours") == 1.5  # 2h - 30min
    admin_session.delete(f"{API}/gigs/{g['gig_id']}")


def test_admin_timesheet_report_includes_break(admin_session, worker_session):
    g = _make_gig(admin_session, break_minutes=15, pay_rate=25.0)
    admin_session.post(f"{API}/gigs/{g['gig_id']}/assign", json={"worker_id": worker_session.user_id})
    a = admin_session.get(f"{API}/gigs/{g['gig_id']}").json()
    acc_id = next(a["acceptance_id"] for a in a["acceptances"])
    admin_session.put(
        f"{API}/gigs/{g['gig_id']}/acceptances/{acc_id}/timesheet",
        json={
            "clock_in_at": "2026-06-06T14:00:00+00:00",
            "clock_out_at": "2026-06-06T15:00:00+00:00",
        },
    )
    r = admin_session.get(f"{API}/admin/reports/timesheets", params={"gig_id": g["gig_id"]})
    assert r.status_code == 200
    data = r.json()
    rows = data["rows"] if isinstance(data, dict) else data
    assert len(rows) >= 1
    row = next(x for x in rows if x["gig_id"] == g["gig_id"])
    assert row.get("break_minutes") == 15
    assert row.get("paid_hours") == 0.75  # 1h - 15min
    # CSV should have the new column
    r_csv = admin_session.get(f"{API}/admin/reports/timesheets.csv", params={"gig_id": g["gig_id"]})
    assert r_csv.status_code == 200
    assert "Break (min)" in r_csv.text
    assert "Paid hours" in r_csv.text
    admin_session.delete(f"{API}/gigs/{g['gig_id']}")
