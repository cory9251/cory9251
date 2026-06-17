"""Iter44 - VA pending/approval feature gating tests.

Verifies that pending VAs are blocked from revenue-generating endpoints
while approved VAs and admins retain full access. Also ensures admin
messaging endpoints (now using block_unapproved_va) have no regression.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://work-connect-147.preview.emergentagent.com").rstrip("/")

PENDING_VA = {"email": "va.pending@hcobcleaners.com", "password": "Pending2026!"}
APPROVED_VA = {"email": "va.demo@hcobcleaners.com", "password": "VaDemo2026!"}
ADMIN = {"email": "admin@hcobcleaners.com", "password": "HcobAdmin2026!"}


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Cannot login as {creds['email']}: {r.status_code} {r.text[:120]}")
    return s


@pytest.fixture(scope="module")
def pending_session():
    return _login(PENDING_VA)


@pytest.fixture(scope="module")
def approved_session():
    return _login(APPROVED_VA)


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN)


# ---- Endpoints under test ----
LOCKED_FOR_PENDING = [
    ("GET", "/api/va/leads"),
    ("GET", "/api/va/earnings"),
    ("GET", "/api/va/commercial-accounts"),
    ("GET", "/api/messages/threads"),
    ("GET", "/api/messages/unread-count"),
]
ALLOWED_FOR_PENDING = [
    ("GET", "/api/va/dashboard"),
    ("GET", "/api/va/templates"),
    ("GET", "/api/va/leaderboard"),
    ("GET", "/api/va/me"),
]


class TestPendingVa:
    """Pending VA must be 403'd on locked endpoints, 200 on allowed."""

    @pytest.mark.parametrize("method,path", LOCKED_FOR_PENDING)
    def test_pending_locked(self, pending_session, method, path):
        r = pending_session.request(method, f"{BASE_URL}{path}", timeout=20)
        assert r.status_code == 403, f"{method} {path} expected 403 got {r.status_code} body={r.text[:200]}"

    @pytest.mark.parametrize("method,path", ALLOWED_FOR_PENDING)
    def test_pending_allowed(self, pending_session, method, path):
        r = pending_session.request(method, f"{BASE_URL}{path}", timeout=20)
        assert r.status_code == 200, f"{method} {path} expected 200 got {r.status_code} body={r.text[:200]}"

    def test_pending_get_lead_by_id_403(self, pending_session):
        # /api/va/leads/{id} should also 403 - use a dummy ID
        r = pending_session.get(f"{BASE_URL}/api/va/leads/dummy-lead-id", timeout=20)
        assert r.status_code == 403, f"expected 403 got {r.status_code}"

    def test_pending_post_lead_403(self, pending_session):
        payload = {
            "prospect_name": "Test Prospect",
            "prospect_phone": "5551234567",
            "service_type": "routine",
            "property_size": "2br",
            "source": "facebook_marketplace",
        }
        r = pending_session.post(f"{BASE_URL}/api/va/leads", json=payload, timeout=20)
        assert r.status_code == 403


class TestApprovedVaNoRegression:
    """Approved VA should retain full access (200) on all 12 endpoints."""

    @pytest.mark.parametrize("method,path", LOCKED_FOR_PENDING + ALLOWED_FOR_PENDING)
    def test_approved_full_access(self, approved_session, method, path):
        r = approved_session.request(method, f"{BASE_URL}{path}", timeout=20)
        assert r.status_code == 200, f"{method} {path} expected 200 got {r.status_code} body={r.text[:200]}"


class TestAdminMessagingNoRegression:
    """Admin messaging endpoints (now wrapped in block_unapproved_va) must still work."""

    def test_admin_threads(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/messages/threads", timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_admin_unread_count(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/messages/unread-count", timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert "count" in data or "unread" in data or isinstance(data, dict)

    def test_admin_eligible_users(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/messages/eligible-users", timeout=20)
        assert r.status_code == 200

    def test_admin_dm_create(self, admin_session):
        # Get eligible users first, then DM with one of them
        elig = admin_session.get(f"{BASE_URL}/api/messages/eligible-users", timeout=20).json()
        users = elig if isinstance(elig, list) else elig.get("users", [])
        if not users:
            pytest.skip("No eligible users for DM")
        target = users[0]
        target_id = target.get("user_id") or target.get("id")
        if not target_id:
            pytest.skip(f"No user_id in eligible-users response: {target}")
        r = admin_session.post(
            f"{BASE_URL}/api/messages/threads/dm",
            json={"user_id": target_id},
            timeout=20,
        )
        assert r.status_code in (200, 201), f"DM create failed: {r.status_code} {r.text[:200]}"
