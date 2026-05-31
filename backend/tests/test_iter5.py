"""Iter-5: Worker management (reset/delete) + clock-in/clock-out tests."""
import os
import time
import uuid
import requests
import pytest

def _load_backend_url() -> str:
    if os.environ.get("REACT_APP_BACKEND_URL"):
        return os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
    env_path = "/app/frontend/.env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PASSWORD = "HcobAdmin2026!"


def _new_worker(prefix="iter5"):
    s = requests.Session()
    email = f"TEST_{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(
        f"{API}/auth/register",
        json={"email": email, "password": "Worker123!", "name": f"T {prefix}", "role": "worker"},
    )
    assert r.status_code == 200, r.text
    user_id = r.json()["user_id"]
    # Iter-6: workers must be ID-verified before they can /accept
    _png = bytes.fromhex(
        "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4"
        "890000000D49444154789C636060606000000005000150E2C53A0000000049454E44AE426082"
    )
    import io as _io
    files = {"file": ("id.png", _io.BytesIO(_png), "image/png")}
    ru = s.post(f"{API}/profile/id", files=files)
    assert ru.status_code == 200, ru.text
    a = requests.Session()
    a.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    rv = a.post(f"{API}/admin/workers/{user_id}/verify-id")
    assert rv.status_code == 200, rv.text
    rap = a.post(f"{API}/admin/workers/{user_id}/approve")
    assert rap.status_code == 200, rap.text
    return s, email, user_id


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def admin_user_id(admin_session):
    return admin_session.get(f"{API}/auth/me").json()["user_id"]


def _create_gig(admin_session, slots=1, title_suffix=""):
    r = admin_session.post(
        f"{API}/gigs",
        json={
            "title": f"TEST_iter5_{title_suffix}_{uuid.uuid4().hex[:6]}",
            "description": "iter5 gig",
            "category": "cleaning",
            "location": "Miami",
            "scheduled_date": "2026-02-20",
            "pay_rate": 25,
            "pay_type": "hourly",
            "slots": slots,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["gig_id"]


# ============================================================================
# Admin reset password
# ============================================================================
class TestAdminResetPassword:
    def test_reset_generates_temp_password_and_kills_sessions(self, admin_session):
        ws, email, uid = _new_worker("rp1")
        # confirm pre-reset session works
        assert ws.get(f"{API}/auth/me").status_code == 200

        r = admin_session.post(f"{API}/admin/workers/{uid}/reset-password", json={})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        new_pw = body["new_password"]
        assert isinstance(new_pw, str) and len(new_pw) >= 6
        # alphanumeric (token_urlsafe sans -/_)
        assert all(c.isalnum() for c in new_pw), f"non-alphanumeric chars in {new_pw}"

        # old session killed
        assert ws.get(f"{API}/auth/me").status_code == 401

        # login with new password works
        s2 = requests.Session()
        rl = s2.post(f"{API}/auth/login", json={"email": email, "password": new_pw})
        assert rl.status_code == 200, rl.text
        assert s2.get(f"{API}/auth/me").status_code == 200

    def test_reset_custom_password(self, admin_session):
        ws, email, uid = _new_worker("rp2")
        r = admin_session.post(
            f"{API}/admin/workers/{uid}/reset-password",
            json={"new_password": "CustomPass123"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["new_password"] == "CustomPass123"
        # login with exact password
        s2 = requests.Session()
        rl = s2.post(f"{API}/auth/login", json={"email": email, "password": "CustomPass123"})
        assert rl.status_code == 200

    def test_reset_short_password_400(self, admin_session):
        _, _, uid = _new_worker("rp3")
        r = admin_session.post(
            f"{API}/admin/workers/{uid}/reset-password",
            json={"new_password": "abc"},
        )
        assert r.status_code == 400

    def test_reset_on_admin_400(self, admin_session, admin_user_id):
        r = admin_session.post(
            f"{API}/admin/workers/{admin_user_id}/reset-password", json={}
        )
        assert r.status_code == 400

    def test_reset_on_missing_user_404(self, admin_session):
        r = admin_session.post(
            f"{API}/admin/workers/user_does_not_exist/reset-password", json={}
        )
        assert r.status_code == 404


# ============================================================================
# Delete worker
# ============================================================================
class TestDeleteWorker:
    def test_delete_releases_gig_slot_and_reopens(self, admin_session):
        gig_id = _create_gig(admin_session, slots=1, title_suffix="del_slot")
        ws, email, uid = _new_worker("del1")
        # accept fills the only slot -> status=filled
        ra = ws.post(f"{API}/gigs/{gig_id}/accept")
        assert ra.status_code == 200
        g_before = admin_session.get(f"{API}/gigs/{gig_id}").json()
        assert g_before["status"] == "filled"
        assert g_before["slots_filled"] == 1

        # delete worker
        rd = admin_session.delete(f"{API}/admin/workers/{uid}")
        assert rd.status_code == 200

        # gig slot released and reopened
        g_after = admin_session.get(f"{API}/gigs/{gig_id}").json()
        assert g_after["slots_filled"] == 0
        assert g_after["status"] == "open"
        assert g_after["acceptances"] == []

        # user gone
        r404 = admin_session.get(f"{API}/admin/workers/{uid}")
        assert r404.status_code == 404
        # sessions killed
        assert ws.get(f"{API}/auth/me").status_code == 401

    def test_delete_admin_returns_400(self, admin_session, admin_user_id):
        r = admin_session.delete(f"{API}/admin/workers/{admin_user_id}")
        assert r.status_code == 400

    def test_delete_missing_returns_404(self, admin_session):
        r = admin_session.delete(f"{API}/admin/workers/user_nope_{uuid.uuid4().hex[:6]}")
        assert r.status_code == 404


# ============================================================================
# Self-service change password
# ============================================================================
class TestChangePassword:
    def test_change_password_success_session_preserved(self, admin_session):
        ws, email, uid = _new_worker("cp1")
        r = ws.post(
            f"{API}/auth/change-password",
            json={"current_password": "Worker123!", "new_password": "NewPass456!"},
        )
        assert r.status_code == 200, r.text
        # session preserved
        assert ws.get(f"{API}/auth/me").status_code == 200
        # new password works on fresh session
        s2 = requests.Session()
        rl = s2.post(f"{API}/auth/login", json={"email": email, "password": "NewPass456!"})
        assert rl.status_code == 200

    def test_change_password_wrong_current_401(self):
        ws, _, _ = _new_worker("cp2")
        r = ws.post(
            f"{API}/auth/change-password",
            json={"current_password": "WRONG!", "new_password": "NewPass456!"},
        )
        assert r.status_code == 401

    def test_change_password_short_new_422(self):
        ws, _, _ = _new_worker("cp3")
        r = ws.post(
            f"{API}/auth/change-password",
            json={"current_password": "Worker123!", "new_password": "abc"},
        )
        assert r.status_code == 422


# ============================================================================
# Clock-in / Clock-out
# ============================================================================
class TestClockInOut:
    def test_full_clock_flow(self, admin_session):
        gig_id = _create_gig(admin_session, slots=2, title_suffix="clk")
        ws, _, uid = _new_worker("clk1")
        ra = ws.post(f"{API}/gigs/{gig_id}/accept")
        assert ra.status_code == 200

        # clock in
        rin = ws.post(f"{API}/gigs/{gig_id}/clock-in")
        assert rin.status_code == 200, rin.text
        assert "clock_in_at" in rin.json()

        # second clock-in -> 400
        rin2 = ws.post(f"{API}/gigs/{gig_id}/clock-in")
        assert rin2.status_code == 400

        # verify gig shows acceptance status=on_the_clock for admin
        g = admin_session.get(f"{API}/gigs/{gig_id}").json()
        acc = next(a for a in g["acceptances"] if a["worker_id"] == uid)
        assert acc["status"] == "on_the_clock"
        assert acc.get("clock_in_at")

        # wait so hours_worked > 0
        time.sleep(1.2)

        # clock out
        rout = ws.post(f"{API}/gigs/{gig_id}/clock-out")
        assert rout.status_code == 200, rout.text
        body = rout.json()
        assert "clock_out_at" in body
        assert body["hours_worked"] >= 0  # spec: >= 0

        # double clock-out -> 400
        rout2 = ws.post(f"{API}/gigs/{gig_id}/clock-out")
        assert rout2.status_code == 400

        # admin sees completed status with all clock fields
        g2 = admin_session.get(f"{API}/gigs/{gig_id}").json()
        acc2 = next(a for a in g2["acceptances"] if a["worker_id"] == uid)
        assert acc2["status"] == "completed"
        assert acc2.get("clock_in_at") and acc2.get("clock_out_at")
        assert "hours_worked" in acc2

    def test_clock_in_without_acceptance_400(self, admin_session):
        gig_id = _create_gig(admin_session, slots=1, title_suffix="noacc")
        ws, _, _ = _new_worker("clk2")
        r = ws.post(f"{API}/gigs/{gig_id}/clock-in")
        assert r.status_code == 400

    def test_clock_out_without_clock_in_400(self, admin_session):
        gig_id = _create_gig(admin_session, slots=1, title_suffix="noci")
        ws, _, _ = _new_worker("clk3")
        ws.post(f"{API}/gigs/{gig_id}/accept")
        r = ws.post(f"{API}/gigs/{gig_id}/clock-out")
        assert r.status_code == 400

    def test_admin_cannot_clock_in_or_out(self, admin_session):
        gig_id = _create_gig(admin_session, slots=1, title_suffix="adm")
        r1 = admin_session.post(f"{API}/gigs/{gig_id}/clock-in")
        assert r1.status_code == 403
        r2 = admin_session.post(f"{API}/gigs/{gig_id}/clock-out")
        assert r2.status_code == 403


# ============================================================================
# Enriched admin worker detail (gig_title etc + clock fields)
# ============================================================================
class TestAdminWorkerDetailEnrichment:
    def test_accepted_gigs_enriched(self, admin_session):
        gig_id = _create_gig(admin_session, slots=2, title_suffix="enrich")
        ws, _, uid = _new_worker("enr1")
        ws.post(f"{API}/gigs/{gig_id}/accept")
        ws.post(f"{API}/gigs/{gig_id}/clock-in")
        time.sleep(1.1)
        ws.post(f"{API}/gigs/{gig_id}/clock-out")

        r = admin_session.get(f"{API}/admin/workers/{uid}")
        assert r.status_code == 200
        data = r.json()
        assert "accepted_gigs" in data
        assert len(data["accepted_gigs"]) >= 1
        a = next(x for x in data["accepted_gigs"] if x["gig_id"] == gig_id)
        # joined fields
        assert a.get("gig_title")
        assert a.get("gig_category") == "cleaning"
        assert a.get("gig_scheduled_date") == "2026-02-20"
        # clock fields
        assert a.get("clock_in_at")
        assert a.get("clock_out_at")
        assert "hours_worked" in a
        assert a.get("status") == "completed"
