"""Iteration 3 - Admin Calendar / scheduled_at + status='all' tests."""
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests

def _load_backend_url() -> str:
    if "REACT_APP_BACKEND_URL" in os.environ:
        return os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
    env_path = "/app/frontend/.env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")


BASE_URL = _load_backend_url()
ADMIN_EMAIL = "admin@gigblast.com"
ADMIN_PASSWORD = "GigBlast2026!"


def _api(session=None):
    s = session or requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_session():
    s = _api()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def worker_session():
    s = _api()
    email = f"TEST_cal_worker_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/register",
               json={"email": email, "password": "Pass1234!",
                     "name": "Cal Worker", "role": "worker"})
    assert r.status_code == 200, r.text
    s.email = email  # type: ignore
    return s


@pytest.fixture
def created_gig_ids():
    ids = []
    yield ids
    s = _api()
    s.post(f"{BASE_URL}/api/auth/login",
           json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    for gid in ids:
        s.delete(f"{BASE_URL}/api/gigs/{gid}")


def _make_gig_payload(scheduled_at=None, title=None):
    return {
        "title": title or f"TEST_cal_gig_{uuid.uuid4().hex[:6]}",
        "description": "calendar test gig",
        "category": "cleaning",
        "subcategory": "deep",
        "location": "123 Test St",
        "scheduled_date": "Wed Mar 5 · 9:00 AM",
        "scheduled_at": scheduled_at,
        "pay_rate": 25.0,
        "pay_type": "hourly",
        "slots": 1,
        "duration_hours": 4,
        "contact_phone": "+15551234567",
    }


# 1. POST /api/gigs accepts scheduled_at and persists it
class TestScheduledAtPersistence:
    def test_create_with_scheduled_at_persists(self, admin_session, created_gig_ids):
        iso = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        payload = _make_gig_payload(scheduled_at=iso)
        r = admin_session.post(f"{BASE_URL}/api/gigs", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        gid = body["gig_id"]
        created_gig_ids.append(gid)
        assert body["scheduled_at"] == iso
        assert body["scheduled_date"] == payload["scheduled_date"]

        # GET roundtrip
        r2 = admin_session.get(f"{BASE_URL}/api/gigs/{gid}")
        assert r2.status_code == 200
        assert r2.json()["scheduled_at"] == iso

    def test_create_without_scheduled_at_succeeds(self, admin_session, created_gig_ids):
        payload = _make_gig_payload(scheduled_at=None)
        r = admin_session.post(f"{BASE_URL}/api/gigs", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        created_gig_ids.append(body["gig_id"])
        assert body["scheduled_at"] is None

    def test_list_gigs_returns_scheduled_at_unchanged(self, admin_session, created_gig_ids):
        iso = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        r = admin_session.post(f"{BASE_URL}/api/gigs", json=_make_gig_payload(scheduled_at=iso))
        gid = r.json()["gig_id"]
        created_gig_ids.append(gid)
        r2 = admin_session.get(f"{BASE_URL}/api/gigs")
        assert r2.status_code == 200
        found = [g for g in r2.json() if g["gig_id"] == gid]
        assert len(found) == 1
        assert found[0]["scheduled_at"] == iso


# 2. status='all' filter regression
class TestStatusAllFilter:
    def test_status_all_returns_open_and_filled(self, admin_session, worker_session, created_gig_ids):
        # Create an open gig (slots=2, single accept => still open)
        p_open = _make_gig_payload(
            scheduled_at=(datetime.now(timezone.utc) + timedelta(days=3)).isoformat())
        p_open["slots"] = 2
        p_open["title"] = f"TEST_open_{uuid.uuid4().hex[:6]}"
        r1 = admin_session.post(f"{BASE_URL}/api/gigs", json=p_open)
        gid_open = r1.json()["gig_id"]
        created_gig_ids.append(gid_open)

        # Create a fill-with-one-slot gig
        p_filled = _make_gig_payload(
            scheduled_at=(datetime.now(timezone.utc) + timedelta(days=4)).isoformat())
        p_filled["slots"] = 1
        p_filled["title"] = f"TEST_fill_{uuid.uuid4().hex[:6]}"
        r2 = admin_session.post(f"{BASE_URL}/api/gigs", json=p_filled)
        gid_filled = r2.json()["gig_id"]
        created_gig_ids.append(gid_filled)

        # Worker accepts the second gig => it becomes 'filled'
        ra = worker_session.post(f"{BASE_URL}/api/gigs/{gid_filled}/accept")
        assert ra.status_code == 200, ra.text

        # Verify filled status
        g = admin_session.get(f"{BASE_URL}/api/gigs/{gid_filled}").json()
        assert g["status"] == "filled"

        # status=all should include both
        r_all = admin_session.get(f"{BASE_URL}/api/gigs?status=all")
        assert r_all.status_code == 200
        ids = {g["gig_id"] for g in r_all.json()}
        assert gid_open in ids
        assert gid_filled in ids

    def test_status_open_only(self, admin_session, created_gig_ids):
        r = admin_session.get(f"{BASE_URL}/api/gigs?status=open")
        assert r.status_code == 200
        for g in r.json():
            assert g["status"] == "open"

    def test_status_filled_only(self, admin_session, created_gig_ids):
        r = admin_session.get(f"{BASE_URL}/api/gigs?status=filled")
        assert r.status_code == 200
        for g in r.json():
            assert g["status"] == "filled"

    def test_worker_no_param_returns_only_open(self, worker_session, admin_session, created_gig_ids):
        # Create one open gig to be sure
        payload = _make_gig_payload(
            scheduled_at=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat())
        r = admin_session.post(f"{BASE_URL}/api/gigs", json=payload)
        created_gig_ids.append(r.json()["gig_id"])

        r2 = worker_session.get(f"{BASE_URL}/api/gigs")
        assert r2.status_code == 200
        for g in r2.json():
            assert g["status"] == "open", f"non-open gig leaked: {g['gig_id']}={g['status']}"

    def test_worker_status_all_sees_filled_and_acceptance_attached(
            self, worker_session, admin_session, created_gig_ids):
        # Create + accept (1 slot) to ensure 'filled' visible only via status=all
        payload = _make_gig_payload(
            scheduled_at=(datetime.now(timezone.utc) + timedelta(days=6)).isoformat())
        payload["slots"] = 1
        payload["title"] = f"TEST_w_fill_{uuid.uuid4().hex[:6]}"
        r = admin_session.post(f"{BASE_URL}/api/gigs", json=payload)
        gid = r.json()["gig_id"]
        created_gig_ids.append(gid)

        ra = worker_session.post(f"{BASE_URL}/api/gigs/{gid}/accept")
        assert ra.status_code == 200

        r_all = worker_session.get(f"{BASE_URL}/api/gigs?status=all")
        assert r_all.status_code == 200
        match = [g for g in r_all.json() if g["gig_id"] == gid]
        assert len(match) == 1
        assert match[0]["status"] == "filled"
        # my_acceptance is attached for workers
        assert match[0].get("my_acceptance") is not None
        assert match[0]["my_acceptance"]["worker_id"]

        # default (no param) excludes filled gigs
        r_def = worker_session.get(f"{BASE_URL}/api/gigs")
        assert gid not in {g["gig_id"] for g in r_def.json()}
