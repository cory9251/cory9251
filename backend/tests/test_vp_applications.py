"""Backend tests for VP application endpoints (iteration 77)."""
import os
import uuid
import pytest
import requests
from pathlib import Path

# Load frontend/.env to get REACT_APP_BACKEND_URL
_env_path = Path("/app/frontend/.env")
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if _line.startswith("REACT_APP_BACKEND_URL="):
            os.environ["REACT_APP_BACKEND_URL"] = _line.split("=", 1)[1].strip()
            break

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PASSWORD = "HcobAdmin2026!"


def _uniq_payload(**overrides):
    base = {
        "full_name": f"Test User {uuid.uuid4().hex[:6]}",
        "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
        "phone": "+63 917 555 1234",
        "country": "Philippines",
        "timezone": "Asia/Manila",
        "streams": ["commission_agent"],
        "skills": ["seo"],
        "portfolio_url": "https://example.com/portfolio",
        "hours_per_day": "4-6",
        "sales_experience": "some",
        "why_join": "I want to earn commissions and grow my skills.",
        "heard_from": "facebook",
        "consent": True,
        "src": "test",
    }
    base.update(overrides)
    return base


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


class TestPublicSubmit:
    def test_honeypot_returns_ok_no_record(self):
        # Honeypot check runs AFTER pydantic validation → send valid payload with website filled
        p = _uniq_payload(website="http://spam.example")
        r = requests.post(f"{API}/public/vp-applications", json=p)
        assert r.status_code == 200
        data = r.json()
        assert data["application_id"] == "spam_ignored"

    def test_one_word_name_returns_400(self):
        p = _uniq_payload(full_name="Onlyone")
        r = requests.post(f"{API}/public/vp-applications", json=p)
        assert r.status_code == 400

    def test_consent_false_returns_400(self):
        p = _uniq_payload(consent=False)
        r = requests.post(f"{API}/public/vp-applications", json=p)
        assert r.status_code == 400

    def test_missing_streams_returns_422(self):
        p = _uniq_payload(streams=[])
        r = requests.post(f"{API}/public/vp-applications", json=p)
        assert r.status_code in (400, 422)


class TestAdminAuth:
    def test_admin_list_requires_auth(self):
        r = requests.get(f"{API}/admin/vp-applications")
        assert r.status_code == 401

    def test_admin_list_ok(self, admin_session):
        r = admin_session.get(f"{API}/admin/vp-applications")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data and "counts" in data and "total" in data
        assert isinstance(data["items"], list)

    def test_admin_patch_persists(self, admin_session):
        # find an existing app; use the seed vpa_28286a45242f if present, else pick first
        r = admin_session.get(f"{API}/admin/vp-applications")
        items = r.json()["items"]
        if not items:
            pytest.skip("No applications in DB to patch")
        app_id = items[0]["application_id"]
        new_note = f"TEST_note_{uuid.uuid4().hex[:6]}"
        p = admin_session.patch(
            f"{API}/admin/vp-applications/{app_id}",
            json={"admin_note": new_note, "status": "contacted"},
        )
        assert p.status_code == 200
        body = p.json()
        assert body["admin_note"] == new_note
        assert body["status"] == "contacted"
        # verify persistence
        r2 = admin_session.get(f"{API}/admin/vp-applications")
        found = next(x for x in r2.json()["items"] if x["application_id"] == app_id)
        assert found["admin_note"] == new_note
        assert found["status"] == "contacted"

    def test_admin_patch_404_missing(self, admin_session):
        p = admin_session.patch(
            f"{API}/admin/vp-applications/vpa_doesnotexist", json={"status": "new"}
        )
        assert p.status_code == 404
