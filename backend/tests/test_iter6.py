"""Iter-6: Duplicate/Edit gigs, ID verification gate, address_line privacy."""
import io
import os
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

PNG = bytes.fromhex(
    "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4"
    "890000000D49444154789C636060606000000005000150E2C53A0000000049454E44AE426082"
)


# ---- Fixtures --------------------------------------------------------------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


def _register_worker(prefix: str):
    s = requests.Session()
    email = f"TEST_iter6_{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/register",
               json={"email": email, "password": "Worker123!", "name": f"W {prefix}", "role": "worker"})
    assert r.status_code == 200, r.text
    return s, email, r.json()["user_id"]


def _upload_id(ws: requests.Session):
    files = {"file": ("id.png", io.BytesIO(PNG), "image/png")}
    r = ws.post(f"{API}/profile/id", files=files)
    assert r.status_code == 200, r.text


def _admin_verify(admin_sess: requests.Session, user_id: str):
    r = admin_sess.post(f"{API}/admin/workers/{user_id}/verify-id")
    assert r.status_code == 200, r.text
    ra = admin_sess.post(f"{API}/admin/workers/{user_id}/approve")
    assert ra.status_code == 200, ra.text


def _create_gig(admin_sess, **overrides):
    payload = {
        "title": f"TEST_iter6_{uuid.uuid4().hex[:6]}",
        "description": "iter6 test gig",
        "category": "cleaning",
        "location": "Oak Ave · 94110",
        "address_line": "1234 Oak Ave, Apt 7B, San Francisco CA 94110",
        "scheduled_date": "2026-03-15",
        "pay_rate": 30,
        "pay_type": "hourly",
        "slots": 2,
    }
    payload.update(overrides)
    r = admin_sess.post(f"{API}/gigs", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


# ---- address_line creation & privacy --------------------------------------
class TestAddressLinePrivacy:
    def test_create_persists_address_line(self, admin_session):
        gig = _create_gig(admin_session)
        gid = gig["gig_id"]
        assert gig.get("address_line") == "1234 Oak Ave, Apt 7B, San Francisco CA 94110"
        # admin re-GET sees address_line
        r = admin_session.get(f"{API}/gigs/{gid}")
        assert r.status_code == 200
        assert r.json()["address_line"] == "1234 Oak Ave, Apt 7B, San Francisco CA 94110"
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_worker_list_hides_address_line(self, admin_session):
        gig = _create_gig(admin_session)
        gid = gig["gig_id"]
        ws, _, _ = _register_worker("listhide")
        r = ws.get(f"{API}/gigs")
        assert r.status_code == 200
        found = next((g for g in r.json() if g["gig_id"] == gid), None)
        assert found is not None
        # public location must be present, sensitive address must NOT be
        assert found.get("location") == "Oak Ave · 94110"
        assert "address_line" not in found or found.get("address_line") in (None, "")
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_worker_detail_hides_then_reveals(self, admin_session):
        gig = _create_gig(admin_session, slots=2)
        gid = gig["gig_id"]
        ws, _, uid = _register_worker("reveal")
        # before accept: address_line absent
        r = ws.get(f"{API}/gigs/{gid}")
        assert r.status_code == 200
        assert "address_line" not in r.json() or r.json().get("address_line") in (None, "")

        # verify worker then accept
        _upload_id(ws)
        _admin_verify(admin_session, uid)
        ra = ws.post(f"{API}/gigs/{gid}/accept")
        assert ra.status_code == 200, ra.text

        r2 = ws.get(f"{API}/gigs/{gid}")
        assert r2.status_code == 200
        assert r2.json().get("address_line") == "1234 Oak Ave, Apt 7B, San Francisco CA 94110"
        admin_session.delete(f"{API}/gigs/{gid}")


# ---- ID verification gate --------------------------------------------------
class TestVerificationGate:
    def test_no_id_uploaded_blocks_accept(self, admin_session):
        gig = _create_gig(admin_session)
        gid = gig["gig_id"]
        ws, _, uid = _register_worker("noid")
        # Iter-7: approve first so we hit the ID gate (not the status gate)
        admin_session.post(f"{API}/admin/workers/{uid}/approve")
        r = ws.post(f"{API}/gigs/{gid}/accept")
        assert r.status_code == 403
        body = r.json()
        msg = (body.get("detail") or body.get("message") or "").lower()
        assert "upload" in msg and "id" in msg
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_uploaded_but_unverified_blocks_accept(self, admin_session):
        gig = _create_gig(admin_session)
        gid = gig["gig_id"]
        ws, _, uid = _register_worker("uploaded")
        admin_session.post(f"{API}/admin/workers/{uid}/approve")
        _upload_id(ws)
        r = ws.post(f"{API}/gigs/{gid}/accept")
        assert r.status_code == 403
        body = r.json()
        msg = (body.get("detail") or body.get("message") or "").lower()
        assert "verif" in msg or "hcob" in msg
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_verified_can_accept_and_sees_address(self, admin_session):
        gig = _create_gig(admin_session)
        gid = gig["gig_id"]
        ws, _, uid = _register_worker("verified")
        _upload_id(ws)
        _admin_verify(admin_session, uid)
        r = ws.post(f"{API}/gigs/{gid}/accept")
        assert r.status_code == 200, r.text
        # /auth/me reflects verified state
        me = ws.get(f"{API}/auth/me").json()
        assert me.get("id_verified") is True
        # gig detail now exposes the sensitive address_line
        rd = ws.get(f"{API}/gigs/{gid}")
        assert rd.json().get("address_line") == "1234 Oak Ave, Apt 7B, San Francisco CA 94110"
        admin_session.delete(f"{API}/gigs/{gid}")


# ---- PUT /gigs/{id} (edit) -------------------------------------------------
class TestEditGig:
    def test_admin_partial_update(self, admin_session):
        gig = _create_gig(admin_session)
        gid = gig["gig_id"]
        r = admin_session.put(f"{API}/gigs/{gid}", json={"title": "TEST_iter6_edited"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["title"] == "TEST_iter6_edited"
        # untouched fields preserved
        assert data["description"] == "iter6 test gig"
        assert data["address_line"] == "1234 Oak Ave, Apt 7B, San Francisco CA 94110"
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_admin_clears_address_line_with_null(self, admin_session):
        gig = _create_gig(admin_session)
        gid = gig["gig_id"]
        r = admin_session.put(f"{API}/gigs/{gid}", json={"address_line": None})
        assert r.status_code == 200, r.text
        # GET to confirm persisted
        rg = admin_session.get(f"{API}/gigs/{gid}")
        assert rg.json().get("address_line") in (None, "")
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_cannot_reduce_slots_below_filled(self, admin_session):
        gig = _create_gig(admin_session, slots=2)
        gid = gig["gig_id"]
        ws, _, uid = _register_worker("slots")
        _upload_id(ws); _admin_verify(admin_session, uid)
        ra = ws.post(f"{API}/gigs/{gid}/accept")
        assert ra.status_code == 200
        r = admin_session.put(f"{API}/gigs/{gid}", json={"slots": 0})
        assert r.status_code == 400
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_increasing_slots_on_filled_flips_to_open(self, admin_session):
        gig = _create_gig(admin_session, slots=1)
        gid = gig["gig_id"]
        ws, _, uid = _register_worker("flip")
        _upload_id(ws); _admin_verify(admin_session, uid)
        ra = ws.post(f"{API}/gigs/{gid}/accept")
        assert ra.status_code == 200
        # confirm filled
        assert admin_session.get(f"{API}/gigs/{gid}").json()["status"] == "filled"
        # increase slots -> open again
        r = admin_session.put(f"{API}/gigs/{gid}", json={"slots": 3})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "open"
        # GET to verify persisted
        assert admin_session.get(f"{API}/gigs/{gid}").json()["status"] == "open"
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_reducing_slots_to_filled_count_sets_filled(self, admin_session):
        gig = _create_gig(admin_session, slots=3)
        gid = gig["gig_id"]
        ws, _, uid = _register_worker("recompute")
        _upload_id(ws); _admin_verify(admin_session, uid)
        ws.post(f"{API}/gigs/{gid}/accept")
        # status still open (1/3 filled)
        assert admin_session.get(f"{API}/gigs/{gid}").json()["status"] == "open"
        r = admin_session.put(f"{API}/gigs/{gid}", json={"slots": 1})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "filled"
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_worker_put_forbidden(self, admin_session):
        gig = _create_gig(admin_session)
        gid = gig["gig_id"]
        ws, _, _ = _register_worker("wput")
        r = ws.put(f"{API}/gigs/{gid}", json={"title": "hack"})
        assert r.status_code == 403
        admin_session.delete(f"{API}/gigs/{gid}")


# ---- POST /gigs/{id}/duplicate --------------------------------------------
class TestDuplicateGig:
    def test_admin_duplicate_resets_state(self, admin_session):
        gig = _create_gig(admin_session, slots=3)
        gid = gig["gig_id"]
        # have 1 acceptance on source so we can check the copy resets it
        ws, _, uid = _register_worker("dupacc")
        _upload_id(ws); _admin_verify(admin_session, uid)
        ws.post(f"{API}/gigs/{gid}/accept")

        r = admin_session.post(f"{API}/gigs/{gid}/duplicate")
        assert r.status_code == 200, r.text
        new = r.json()
        assert new["gig_id"] != gid
        assert new["title"].endswith(" (copy)")
        assert new["slots_filled"] == 0
        assert new["status"] == "open"
        assert new["duplicated_from"] == gid
        # shared fields preserved
        assert new["category"] == gig["category"]
        assert new["pay_rate"] == gig["pay_rate"]
        assert new["address_line"] == gig["address_line"]
        # GET to confirm persisted
        rg = admin_session.get(f"{API}/gigs/{new['gig_id']}")
        assert rg.status_code == 200
        assert rg.json()["title"].endswith(" (copy)")
        admin_session.delete(f"{API}/gigs/{gid}")
        admin_session.delete(f"{API}/gigs/{new['gig_id']}")

    def test_duplicate_does_not_double_copy_suffix(self, admin_session):
        gig = _create_gig(admin_session, title="Already (copy)")
        gid = gig["gig_id"]
        r = admin_session.post(f"{API}/gigs/{gid}/duplicate")
        assert r.status_code == 200, r.text
        assert r.json()["title"] == "Already (copy)"
        admin_session.delete(f"{API}/gigs/{gid}")
        admin_session.delete(f"{API}/gigs/{r.json()['gig_id']}")

    def test_worker_duplicate_forbidden(self, admin_session):
        gig = _create_gig(admin_session)
        gid = gig["gig_id"]
        ws, _, _ = _register_worker("wdup")
        r = ws.post(f"{API}/gigs/{gid}/duplicate")
        assert r.status_code == 403
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_duplicate_nonexistent_returns_404(self, admin_session):
        r = admin_session.post(f"{API}/gigs/gig_doesnotexist/duplicate")
        assert r.status_code == 404
