"""Iteration 12 — Worker full profile + admin worker filters + gig matching.

Covers:
- GET /api/profile/options
- PUT /api/profile (all new fields, validation)
- GET /api/auth/me with profile_complete / profile_missing_fields
- POST /api/gigs/{id}/accept profile gate (403 "Complete your profile")
- GET /api/admin/workers filter combos (skills, availability, zip, prefix, vehicle, profile_complete, search)
- GET /api/admin/workers/match scoring & filters
"""
import os
from pathlib import Path

# Load /app/frontend/.env so REACT_APP_BACKEND_URL is available at import time
_env_path = Path(__file__).resolve().parents[2] / "frontend" / ".env"
if _env_path.exists() and "REACT_APP_BACKEND_URL" not in os.environ:
    for line in _env_path.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            os.environ["REACT_APP_BACKEND_URL"] = line.split("=", 1)[1].strip().strip('"')
            break

import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PASSWORD = "HcobAdmin2026!"


def _new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(session: requests.Session, email: str, password: str) -> dict:
    r = session.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return r.json()


def _register_worker(session: requests.Session, suffix: str, name: str = "Iter12 Worker") -> dict:
    email = f"TEST_iter12_{suffix}_{uuid.uuid4().hex[:6]}@hcobcleaners.com"
    r = session.post(
        f"{API}/auth/register",
        json={"email": email, "password": "Worker123!", "name": name},
    )
    assert r.status_code == 200, f"register {email} failed: {r.status_code} {r.text}"
    body = r.json()
    body["_password"] = "Worker123!"
    return body


# --------------------- Fixtures ---------------------


@pytest.fixture(scope="module")
def admin_session():
    s = _new_session()
    _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)
    return s


@pytest.fixture(scope="module")
def worker_session():
    s = _new_session()
    _register_worker(s, "main")
    return s


@pytest.fixture(scope="module")
def created_user_ids():
    """Track user_ids created for cleanup."""
    return []


# --------------------- /api/profile/options ---------------------


class TestProfileOptions:
    def test_options_shape(self, worker_session):
        r = worker_session.get(f"{API}/profile/options")
        assert r.status_code == 200, r.text
        body = r.json()
        # skills
        assert isinstance(body["skills"], list) and len(body["skills"]) >= 5
        skill_vals = {s["value"] for s in body["skills"]}
        assert {"deep_cleaning", "routine_cleaning", "moveouts", "hourly_labor", "driving"} <= skill_vals
        for s in body["skills"]:
            assert "value" in s and "label" in s
        # availability
        assert "weekdays" in body["availability"]
        assert "weekends" in body["availability"]
        # experience
        assert "0_1_yr" in body["experience_levels"]
        # tshirt
        assert "M" in body["tshirt_sizes"]
        # required
        assert "phone" in body["required_fields"]
        assert "skills" in body["required_fields"]


# --------------------- auth/me + profile gate ---------------------


class TestProfileCompletion:
    def test_register_returns_incomplete(self):
        s = _new_session()
        u = _register_worker(s, "fresh_completion")
        assert u["role"] == "worker"
        assert u.get("profile_complete") is False
        missing = set(u.get("profile_missing_fields") or [])
        expected = {
            "phone", "zip_code", "date_of_birth", "skills",
            "availability", "emergency_contact_name", "emergency_contact_phone",
        }
        assert missing == expected, f"missing={missing}"

        # /api/auth/me echoes the same
        me = s.get(f"{API}/auth/me").json()
        assert me["profile_complete"] is False
        assert set(me["profile_missing_fields"]) == expected

    def test_fill_all_required_marks_complete(self):
        s = _new_session()
        _register_worker(s, "fill_complete")
        payload = {
            "phone": "415-555-1212",
            "zip_code": "94110",
            "date_of_birth": "1990-01-15",
            "skills": ["deep_cleaning", "moveouts"],
            "availability": ["weekends", "evenings"],
            "emergency_contact_name": "Jane Doe",
            "emergency_contact_phone": "415-555-9999",
        }
        r = s.put(f"{API}/profile", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["profile_complete"] is True
        assert body["profile_missing_fields"] == []

        # verify GET /auth/me matches
        me = s.get(f"{API}/auth/me").json()
        assert me["profile_complete"] is True
        assert me["profile_missing_fields"] == []
        # verify persisted
        assert me["zip_code"] == "94110"
        assert "deep_cleaning" in me["skills"]


# --------------------- PUT /profile validations ---------------------


class TestProfileValidation:
    def test_reject_bad_zip(self, worker_session):
        r = worker_session.put(f"{API}/profile", json={"zip_code": "1234"})
        assert r.status_code == 400
        assert "zip" in r.text.lower()

    def test_reject_unknown_skill(self, worker_session):
        r = worker_session.put(
            f"{API}/profile", json={"skills": ["deep_cleaning", "bogus_skill"]}
        )
        assert r.status_code == 400
        assert "bogus_skill" in r.text or "Unknown skill" in r.text

    def test_reject_unknown_availability(self, worker_session):
        r = worker_session.put(f"{API}/profile", json={"availability": ["weekends", "noon"]})
        assert r.status_code == 400
        assert "availability" in r.text.lower()

    def test_reject_unknown_experience(self, worker_session):
        r = worker_session.put(f"{API}/profile", json={"experience_level": "expert"})
        assert r.status_code == 400

    def test_reject_unknown_tshirt(self, worker_session):
        r = worker_session.put(f"{API}/profile", json={"tshirt_size": "XXXXXL"})
        assert r.status_code == 400

    def test_accepts_full_payload(self, worker_session):
        payload = {
            "phone": "415-000-0000",
            "zip_code": "94107",
            "city": "San Francisco",
            "state": "CA",
            "date_of_birth": "1992-04-10",
            "skills": ["deep_cleaning", "hourly_labor"],
            "availability": ["weekdays", "mornings"],
            "has_car": True,
            "has_truck": False,
            "has_cdl": False,
            "experience_level": "1_3_yr",
            "emergency_contact_name": "Sam",
            "emergency_contact_phone": "415-111-2222",
            "tshirt_size": "L",
            "address": "123 Main St",
            "bio": "Hardworking",
        }
        r = worker_session.put(f"{API}/profile", json=payload)
        assert r.status_code == 200, r.text
        u = r.json()
        for k, v in payload.items():
            assert u.get(k) == v, f"{k}: {u.get(k)} != {v}"
        assert u["profile_complete"] is True


# --------------------- Gig accept profile gate ---------------------


class TestAcceptProfileGate:
    def _create_gig(self, admin_session) -> str:
        r = admin_session.post(
            f"{API}/gigs",
            json={
                "title": "TEST_iter12 Gate Gig",
                "description": "test",
                "category": "cleaning",
                "subcategory": "deep_cleaning",
                "location": "Test St · 94110",
                "scheduled_date": "2026-02-01",
                "pay_rate": 25.0,
                "pay_type": "hourly",
                "slots": 1,
            },
        )
        assert r.status_code == 200, r.text
        return r.json()["gig_id"]

    def _upload_fake_id(self, ws):
        # Tiny valid PNG (1x1)
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\x00"
            b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        files = {"file": ("id.png", png, "image/png")}
        # remove Content-Type header (must be multipart)
        prev_ct = ws.headers.pop("Content-Type", None)
        r = ws.post(f"{API}/profile/id", files=files)
        if prev_ct:
            ws.headers["Content-Type"] = prev_ct
        assert r.status_code == 200, f"upload id failed: {r.status_code} {r.text}"

    def _verify_id(self, admin_session, worker_id):
        r = admin_session.post(f"{API}/admin/workers/{worker_id}/verify-id")
        assert r.status_code == 200, r.text

    def test_403_when_profile_incomplete_even_if_id_verified(self, admin_session):
        ws = _new_session()
        wu = _register_worker(ws, "gate_incomplete")
        worker_id = wu["user_id"]
        self._upload_fake_id(ws)
        self._verify_id(admin_session, worker_id)

        gig_id = self._create_gig(admin_session)

        r = ws.post(f"{API}/gigs/{gig_id}/accept")
        assert r.status_code == 403, r.text
        assert "Complete your profile" in r.text

    def test_accept_succeeds_when_profile_complete_and_id_verified(self, admin_session):
        ws = _new_session()
        wu = _register_worker(ws, "gate_complete")
        worker_id = wu["user_id"]

        ws.put(
            f"{API}/profile",
            json={
                "phone": "415-555-3333",
                "zip_code": "94110",
                "date_of_birth": "1990-01-01",
                "skills": ["deep_cleaning"],
                "availability": ["weekends"],
                "emergency_contact_name": "Jane",
                "emergency_contact_phone": "415-555-4444",
            },
        )
        self._upload_fake_id(ws)
        self._verify_id(admin_session, worker_id)

        gig_id = self._create_gig(admin_session)
        r = ws.post(f"{API}/gigs/{gig_id}/accept")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("status") in ("requested", "approved")


# --------------------- /admin/workers filters ---------------------


@pytest.fixture(scope="module")
def seeded_workers(admin_session):
    """Create a few workers covering all filter dimensions."""
    sessions = []
    for label, profile in [
        ("alpha",  {
            "phone": "415-000-1111", "zip_code": "94110", "city": "SF", "state": "CA",
            "date_of_birth": "1990-01-01",
            "skills": ["deep_cleaning"], "availability": ["weekends"],
            "emergency_contact_name": "E1", "emergency_contact_phone": "415-111-1111",
            "has_car": True,
        }),
        ("bravo",  {
            "phone": "415-000-2222", "zip_code": "94115", "city": "SF", "state": "CA",
            "date_of_birth": "1991-01-01",
            "skills": ["driving"], "availability": ["weekdays", "mornings"],
            "emergency_contact_name": "E2", "emergency_contact_phone": "415-222-2222",
            "has_truck": True, "has_cdl": True,
        }),
        ("charlie", {
            # leave incomplete on purpose (no skills/availability/etc.)
            "phone": "415-000-3333", "zip_code": "10001",
        }),
    ]:
        s = _new_session()
        u = _register_worker(s, label, name=f"Iter12 {label.title()}")
        if profile:
            s.put(f"{API}/profile", json=profile)
        sessions.append((label, s, u["user_id"]))
    return sessions


class TestAdminWorkersFilters:
    def test_filter_by_skill_deep_cleaning(self, admin_session, seeded_workers):
        r = admin_session.get(f"{API}/admin/workers", params={"skills": "deep_cleaning"})
        assert r.status_code == 200
        ws = r.json()
        # Must include alpha (zip 94110, deep_cleaning) but NOT bravo
        emails = [w.get("email", "") for w in ws]
        # at least one TEST_iter12_alpha matches
        assert any("iter12_alpha" in e for e in emails)
        assert not any("iter12_bravo" in e for e in emails)
        # profile_complete on every record
        assert all("profile_complete" in w and "profile_missing_fields" in w for w in ws)

    def test_filter_by_skill_csv(self, admin_session, seeded_workers):
        r = admin_session.get(
            f"{API}/admin/workers", params={"skills": "deep_cleaning,driving"}
        )
        assert r.status_code == 200
        emails = [w.get("email", "") for w in r.json()]
        assert any("iter12_alpha" in e for e in emails)
        assert any("iter12_bravo" in e for e in emails)

    def test_filter_by_availability(self, admin_session, seeded_workers):
        r = admin_session.get(f"{API}/admin/workers", params={"availability": "weekends"})
        assert r.status_code == 200
        emails = [w.get("email", "") for w in r.json()]
        assert any("iter12_alpha" in e for e in emails)
        assert not any("iter12_bravo" in e for e in emails)

    def test_filter_zip_exact(self, admin_session, seeded_workers):
        r = admin_session.get(f"{API}/admin/workers", params={"zip_code": "94110"})
        assert r.status_code == 200
        for w in r.json():
            assert w.get("zip_code") == "94110"

    def test_filter_zip_prefix(self, admin_session, seeded_workers):
        r = admin_session.get(f"{API}/admin/workers", params={"zip_prefix": "941"})
        assert r.status_code == 200
        ws = r.json()
        emails = [w.get("email", "") for w in ws]
        assert any("iter12_alpha" in e for e in emails)
        assert any("iter12_bravo" in e for e in emails)
        # charlie 10001 should NOT match
        assert not any("iter12_charlie" in e for e in emails)

    def test_filter_vehicle_truck(self, admin_session, seeded_workers):
        r = admin_session.get(f"{API}/admin/workers", params={"vehicle": "truck"})
        assert r.status_code == 200
        emails = [w.get("email", "") for w in r.json()]
        assert any("iter12_bravo" in e for e in emails)
        assert not any("iter12_alpha" in e for e in emails)

    def test_filter_vehicle_cdl(self, admin_session, seeded_workers):
        r = admin_session.get(f"{API}/admin/workers", params={"vehicle": "cdl"})
        assert r.status_code == 200
        emails = [w.get("email", "") for w in r.json()]
        assert any("iter12_bravo" in e for e in emails)

    def test_filter_vehicle_any(self, admin_session, seeded_workers):
        r = admin_session.get(f"{API}/admin/workers", params={"vehicle": "any"})
        assert r.status_code == 200
        emails = [w.get("email", "") for w in r.json()]
        assert any("iter12_alpha" in e for e in emails)
        assert any("iter12_bravo" in e for e in emails)

    def test_filter_profile_complete_true(self, admin_session, seeded_workers):
        r = admin_session.get(f"{API}/admin/workers", params={"profile_complete": "true"})
        assert r.status_code == 200
        ws = r.json()
        for w in ws:
            assert w["profile_complete"] is True
        emails = [w.get("email", "") for w in ws]
        # charlie incomplete should NOT be in this list
        assert not any("iter12_charlie" in e for e in emails)

    def test_filter_profile_complete_false(self, admin_session, seeded_workers):
        r = admin_session.get(f"{API}/admin/workers", params={"profile_complete": "false"})
        assert r.status_code == 200
        ws = r.json()
        for w in ws:
            assert w["profile_complete"] is False
        emails = [w.get("email", "") for w in ws]
        assert any("iter12_charlie" in e for e in emails)

    def test_search_by_name(self, admin_session, seeded_workers):
        # Name contains "Alpha"
        r = admin_session.get(f"{API}/admin/workers", params={"search": "Iter12 Alpha"})
        assert r.status_code == 200
        emails = [w.get("email", "") for w in r.json()]
        assert any("iter12_alpha" in e for e in emails)


# --------------------- /admin/workers/match scoring ---------------------


class TestWorkerMatch:
    def test_match_cleaning_94110(self, admin_session, seeded_workers):
        r = admin_session.get(
            f"{API}/admin/workers/match",
            params={"category": "cleaning", "zip_code": "94110"},
        )
        assert r.status_code == 200, r.text
        matches = r.json()
        # alpha (deep_cleaning + 94110) MUST be top
        assert len(matches) >= 1
        top = matches[0]
        assert "score" in top and top["score"] >= 6  # +3 skills +3 zip
        # bravo (driving) should NOT be returned for cleaning
        emails = [m.get("email", "") for m in matches]
        assert not any("iter12_bravo" in e for e in emails)
        # charlie (incomplete) MUST be excluded
        assert not any("iter12_charlie" in e for e in emails)
        # Sort order
        scores = [m["score"] for m in matches]
        assert scores == sorted(scores, reverse=True)

    def test_match_cleaning_zip_prefix_only(self, admin_session, seeded_workers):
        # Different zip but same prefix → alpha gets only +1 for prefix.
        r = admin_session.get(
            f"{API}/admin/workers/match",
            params={"category": "cleaning", "zip_code": "94199"},
        )
        assert r.status_code == 200
        matches = r.json()
        # Find alpha
        alpha = next(
            (m for m in matches if "iter12_alpha" in (m.get("email") or "")), None
        )
        assert alpha is not None
        # Score = +3 (skills) +1 (prefix) [+1 if has_car]
        assert alpha["score"] >= 4

    def test_match_driver_requires_driving(self, admin_session, seeded_workers):
        r = admin_session.get(
            f"{API}/admin/workers/match",
            params={"category": "driver", "zip_code": "94115"},
        )
        assert r.status_code == 200
        matches = r.json()
        emails = [m.get("email", "") for m in matches]
        # bravo has driving — must appear
        assert any("iter12_bravo" in e for e in emails)
        # alpha cleaning — must NOT appear
        assert not any("iter12_alpha" in e for e in emails)

    def test_match_excludes_incomplete_profile(self, admin_session, seeded_workers):
        # No category — workers still must be complete to be returned
        r = admin_session.get(f"{API}/admin/workers/match")
        assert r.status_code == 200
        emails = [m.get("email", "") for m in r.json()]
        assert not any("iter12_charlie" in e for e in emails)
