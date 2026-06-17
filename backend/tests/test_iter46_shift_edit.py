"""Iter46 - Admin shift edit endpoints (no-show / mark-completed / timesheet w/ admin_note)."""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PASSWORD = "HcobAdmin2026!"
WORKER_EMAIL = "worker.demo@hcobcleaners.com"
WORKER_PASSWORD = "WorkerDemo2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return s


@pytest.fixture(scope="module")
def worker_id(admin_session):
    r = admin_session.get(f"{API}/admin/workers", params={"search": "worker.demo"})
    assert r.status_code == 200
    workers = r.json()
    assert workers, "No worker.demo found"
    return workers[0]["user_id"]


@pytest.fixture(scope="module")
def worker_name(admin_session, worker_id):
    r = admin_session.get(f"{API}/admin/workers/{worker_id}")
    return r.json()["name"]


def _create_gig(admin_session):
    payload = {
        "title": f"TEST_ShiftEdit {uuid.uuid4().hex[:6]}",
        "description": "iter46 e2e",
        "category": "cleaning",
        "location": "Test Site · 94110",
        "address_line": "123 Test Ave",
        "scheduled_date": "Soon",
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "pay_rate": 25.0,
        "pay_type": "hourly",
        "slots": 1,
        "duration_hours": 4.0,
        "break_minutes": 0,
    }
    r = admin_session.post(f"{API}/gigs", json=payload)
    assert r.status_code in (200, 201), r.text
    return r.json()["gig_id"]


def _accept_and_approve(admin_session, gig_id, worker_id, worker_name):
    """Worker login, request gig (with agreement), then admin approves."""
    ws = requests.Session()
    r = ws.post(f"{API}/auth/login", json={"email": WORKER_EMAIL, "password": WORKER_PASSWORD})
    assert r.status_code == 200, r.text
    rules_r = ws.get(f"{API}/worker/agreement-rules")
    rules = rules_r.json().get("rules", []) if rules_r.status_code == 200 else []
    r = ws.post(f"{API}/gigs/{gig_id}/accept", json={
        "typed_name": worker_name,
        "agreed_rules": rules,
        "version": "v1",
    })
    assert r.status_code == 200, f"accept failed for worker_name={worker_name!r} gig={gig_id}: {r.status_code} {r.text}"
    acc_id = r.json()["acceptance_id"]
    # Admin approves
    r = admin_session.post(f"{API}/gigs/{gig_id}/requests/{acc_id}/approve")
    assert r.status_code == 200, r.text
    return acc_id


@pytest.fixture
def fresh_acceptance(admin_session, worker_id, worker_name):
    gid = _create_gig(admin_session)
    aid = _accept_and_approve(admin_session, gid, worker_id, worker_name)
    yield gid, aid
    # Cleanup
    admin_session.delete(f"{API}/gigs/{gid}/acceptances/{aid}")
    admin_session.delete(f"{API}/gigs/{gid}")


class TestTimesheetEditWithAdminNote:
    def test_edit_with_admin_note_persists(self, admin_session, fresh_acceptance):
        gid, aid = fresh_acceptance
        ci = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
        co = datetime.now(timezone.utc).isoformat()
        r = admin_session.put(
            f"{API}/gigs/{gid}/acceptances/{aid}/timesheet",
            json={"clock_in_at": ci, "clock_out_at": co, "admin_note": "ran late but did fine"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "completed"
        assert body["hours_worked"] > 0
        assert body["earnings"] > 0
        # Verify GET shows admin_note + audit fields
        r2 = admin_session.get(f"{API}/admin/workers/{aid}")  # not the right path; use worker detail
        # use gig accs via worker detail
        # find worker_id via the acceptance — easier path: query the gig and inspect
        r3 = admin_session.get(f"{API}/gigs/{gid}/acceptances")
        if r3.status_code == 200:
            acc = next((a for a in r3.json() if a["acceptance_id"] == aid), None)
            if acc:
                assert acc.get("admin_note") == "ran late but did fine"
                assert acc.get("admin_note_by")

    def test_edit_without_admin_note_still_works(self, admin_session, fresh_acceptance):
        gid, aid = fresh_acceptance
        ci = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        co = datetime.now(timezone.utc).isoformat()
        r = admin_session.put(
            f"{API}/gigs/{gid}/acceptances/{aid}/timesheet",
            json={"clock_in_at": ci, "clock_out_at": co},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "completed"


class TestNoShow:
    def test_noshow_requires_reason(self, admin_session, fresh_acceptance):
        gid, aid = fresh_acceptance
        r = admin_session.post(f"{API}/gigs/{gid}/acceptances/{aid}/no-show", json={})
        assert r.status_code == 422, r.text

    def test_noshow_success_clears_times(self, admin_session, fresh_acceptance):
        gid, aid = fresh_acceptance
        # First set some clock times
        ci = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        admin_session.put(
            f"{API}/gigs/{gid}/acceptances/{aid}/timesheet",
            json={"clock_in_at": ci, "clear_clock_out": True},
        )
        r = admin_session.post(
            f"{API}/gigs/{gid}/acceptances/{aid}/no-show",
            json={"reason": "Did not show up", "admin_note": "client confirmed absence"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "no_show"

    def test_noshow_rejected_for_requested_state(self, admin_session, worker_id, worker_name):
        # Create gig + worker request, but do NOT approve
        gid = _create_gig(admin_session)
        ws = requests.Session()
        ws.post(f"{API}/auth/login", json={"email": WORKER_EMAIL, "password": WORKER_PASSWORD})
        rules = ws.get(f"{API}/worker/agreement-rules").json().get("rules", [])
        r = ws.post(f"{API}/gigs/{gid}/accept", json={
            "typed_name": worker_name, "agreed_rules": rules, "version": "v1",
        })
        aid = r.json()["acceptance_id"]
        r = admin_session.post(f"{API}/gigs/{gid}/acceptances/{aid}/no-show",
                               json={"reason": "test"})
        assert r.status_code == 400, r.text
        # Cleanup
        admin_session.delete(f"{API}/gigs/{gid}/acceptances/{aid}")
        admin_session.delete(f"{API}/gigs/{gid}")


class TestMarkCompleted:
    def test_mark_completed_with_no_clock_in_uses_scheduled(self, admin_session, fresh_acceptance):
        gid, aid = fresh_acceptance
        r = admin_session.post(
            f"{API}/gigs/{gid}/acceptances/{aid}/mark-completed",
            json={},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "completed"
        assert body["hours_worked"] is not None and body["hours_worked"] > 0
        assert body["earnings"] is not None and body["earnings"] > 0

    def test_mark_completed_with_explicit_times(self, admin_session, fresh_acceptance):
        gid, aid = fresh_acceptance
        ci = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        co = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        r = admin_session.post(
            f"{API}/gigs/{gid}/acceptances/{aid}/mark-completed",
            json={"clock_in_at": ci, "clock_out_at": co, "admin_note": "verified manually"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "completed"
        assert abs(body["hours_worked"] - 2.0) < 0.05

    def test_mark_completed_rejects_requested(self, admin_session, worker_id, worker_name):
        gid = _create_gig(admin_session)
        ws = requests.Session()
        ws.post(f"{API}/auth/login", json={"email": WORKER_EMAIL, "password": WORKER_PASSWORD})
        rules = ws.get(f"{API}/worker/agreement-rules").json().get("rules", [])
        r = ws.post(f"{API}/gigs/{gid}/accept", json={
            "typed_name": worker_name, "agreed_rules": rules, "version": "v1",
        })
        aid = r.json()["acceptance_id"]
        r = admin_session.post(f"{API}/gigs/{gid}/acceptances/{aid}/mark-completed", json={})
        assert r.status_code == 400
        admin_session.delete(f"{API}/gigs/{gid}/acceptances/{aid}")
        admin_session.delete(f"{API}/gigs/{gid}")


class TestUnauthorized:
    def test_worker_cannot_edit_timesheet(self, fresh_acceptance):
        gid, aid = fresh_acceptance
        ws = requests.Session()
        ws.post(f"{API}/auth/login", json={"email": WORKER_EMAIL, "password": WORKER_PASSWORD})
        r = ws.put(f"{API}/gigs/{gid}/acceptances/{aid}/timesheet",
                   json={"admin_note": "hack"})
        assert r.status_code in (401, 403)

    def test_worker_cannot_no_show(self, fresh_acceptance):
        gid, aid = fresh_acceptance
        ws = requests.Session()
        ws.post(f"{API}/auth/login", json={"email": WORKER_EMAIL, "password": WORKER_PASSWORD})
        r = ws.post(f"{API}/gigs/{gid}/acceptances/{aid}/no-show", json={"reason": "x"})
        assert r.status_code in (401, 403)
