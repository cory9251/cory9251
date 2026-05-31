"""HCOB Network backend regression tests (pytest)."""
import os
import io
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://work-connect-147.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

# New seeded admin (iter-4 rebrand)
ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PASSWORD = "HcobAdmin2026!"
# Legacy admin must still work (back-compat)
LEGACY_ADMIN_EMAIL = "admin@gigblast.com"
LEGACY_ADMIN_PASSWORD = "GigBlast2026!"

UNIQUE = uuid.uuid4().hex[:8]
WORKER_EMAIL = f"TEST_worker_{UNIQUE}@example.com"
WORKER2_EMAIL = f"TEST_worker2_{UNIQUE}@example.com"
WORKER_PASSWORD = "Worker123!"

# 1x1 PNG used by fixtures and tests
PNG_BYTES = bytes.fromhex(
    "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4"
    "890000000D49444154789C636060606000000005000150E2C53A0000000049454E44AE426082"
)


def _verify_worker_via_admin(worker_sess: requests.Session) -> None:
    """Iter-6: upload an ID + have admin mark verified so /accept calls succeed."""
    import io as _io
    files = {"file": ("id.png", _io.BytesIO(PNG_BYTES), "image/png")}
    r = worker_sess.post(f"{API}/profile/id", files=files)
    assert r.status_code == 200, f"upload_id failed: {r.status_code} {r.text}"
    me = worker_sess.get(f"{API}/auth/me").json()
    a = requests.Session()
    ra = a.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert ra.status_code == 200, ra.text
    rv = a.post(f"{API}/admin/workers/{me['user_id']}/verify-id")
    assert rv.status_code == 200, rv.text


# ---- Fixtures ---------------------------------------------------------------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    data = r.json()
    assert data["role"] == "admin"
    return s


@pytest.fixture(scope="module")
def worker_session():
    s = requests.Session()
    r = s.post(
        f"{API}/auth/register",
        json={"email": WORKER_EMAIL, "password": WORKER_PASSWORD, "name": "Test Worker", "role": "worker"},
    )
    assert r.status_code == 200, f"worker register failed: {r.status_code} {r.text}"
    user = r.json()
    assert user["role"] == "worker"
    assert user["email"].lower() == WORKER_EMAIL.lower()
    _verify_worker_via_admin(s)
    return s


@pytest.fixture(scope="module")
def worker2_session():
    s = requests.Session()
    r = s.post(
        f"{API}/auth/register",
        json={"email": WORKER2_EMAIL, "password": WORKER_PASSWORD, "name": "Test Worker 2", "role": "worker"},
    )
    assert r.status_code == 200, f"worker2 register failed: {r.status_code} {r.text}"
    _verify_worker_via_admin(s)
    return s


# ---- Health -----------------------------------------------------------------
def test_root_health():
    r = requests.get(f"{API}/")
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    # iter-4: service renamed
    assert data.get("service") == "hcob-network", f"expected service=hcob-network got {data}"


# ---- Auth -------------------------------------------------------------------
def test_admin_login_sets_cookie(admin_session):
    assert "session_token" in admin_session.cookies.get_dict()


def test_auth_me_with_cookie(admin_session):
    r = admin_session.get(f"{API}/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == ADMIN_EMAIL
    assert r.json()["role"] == "admin"


def test_legacy_admin_login_still_works():
    """iter-4: legacy admin@gigblast.com / GigBlast2026! must STILL return role=admin."""
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": LEGACY_ADMIN_EMAIL, "password": LEGACY_ADMIN_PASSWORD})
    assert r.status_code == 200, f"legacy admin login failed: {r.status_code} {r.text}"
    data = r.json()
    assert data["role"] == "admin"
    assert data["email"] == LEGACY_ADMIN_EMAIL
    # cookie session also good
    me = s.get(f"{API}/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "admin"


def test_register_admin_role_is_silently_downgraded_to_worker():
    """iter-4 SECURITY: client-supplied role=admin on /auth/register must be ignored.
    User is created as worker regardless. Verified both via response and /auth/me."""
    s = requests.Session()
    email = f"TEST_hijack_{UNIQUE}@example.com"
    r = s.post(
        f"{API}/auth/register",
        json={"email": email, "password": "Pwd12345!", "name": "Hijack Try", "role": "admin"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["role"] == "worker", f"SECURITY: role hijack possible — got {body['role']}"
    # also verify via /auth/me with the issued session
    me = s.get(f"{API}/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "worker", "SECURITY: /auth/me reflects admin role after register hijack"


def test_duplicate_register_fails(worker_session):
    # worker_session ensures worker is already registered
    r = requests.post(
        f"{API}/auth/register",
        json={"email": WORKER_EMAIL, "password": WORKER_PASSWORD, "name": "Dup"},
    )
    assert r.status_code == 400


def test_login_wrong_password_returns_401():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong!!"})
    assert r.status_code == 401


def test_logout(worker2_session):
    r = worker2_session.post(f"{API}/auth/logout")
    assert r.status_code == 200
    r2 = worker2_session.get(f"{API}/auth/me")
    assert r2.status_code == 401


# ---- Gigs -------------------------------------------------------------------
created_gigs = {}


def test_create_cleaning_gig(admin_session):
    payload = {
        "title": "TEST_Deep cleaning condo",
        "description": "Deep clean 2BR condo",
        "category": "cleaning",
        "subcategory": "deep",
        "location": "Miami, FL",
        "scheduled_date": "2026-02-10",
        "pay_rate": 35.0,
        "pay_type": "hourly",
        "slots": 2,
        "duration_hours": 4,
        "contact_phone": "+10000000000",
    }
    r = admin_session.post(f"{API}/gigs", json=payload)
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["category"] == "cleaning"
    assert g["subcategory"] == "deep"
    assert g["status"] == "open"
    assert g["slots_filled"] == 0
    created_gigs["cleaning"] = g["gig_id"]


def test_create_labor_gig(admin_session):
    r = admin_session.post(
        f"{API}/gigs",
        json={
            "title": "TEST_Labor moving",
            "description": "Help move boxes",
            "category": "labor",
            "subcategory": "hourly",
            "location": "Orlando",
            "scheduled_date": "2026-02-12",
            "pay_rate": 25,
            "pay_type": "hourly",
            "slots": 1,
        },
    )
    assert r.status_code == 200
    created_gigs["labor"] = r.json()["gig_id"]


def test_create_driver_gig(admin_session):
    r = admin_session.post(
        f"{API}/gigs",
        json={
            "title": "TEST_Driver ride",
            "description": "Drive client",
            "category": "driver",
            "subcategory": "ride",
            "location": "Tampa",
            "scheduled_date": "2026-02-14",
            "pay_rate": 100,
            "pay_type": "flat",
            "slots": 1,
        },
    )
    assert r.status_code == 200
    created_gigs["driver"] = r.json()["gig_id"]


def test_worker_cannot_create_gig(worker_session):
    r = worker_session.post(
        f"{API}/gigs",
        json={
            "title": "X", "description": "x", "category": "cleaning",
            "location": "x", "scheduled_date": "x", "pay_rate": 1, "pay_type": "hourly", "slots": 1,
        },
    )
    assert r.status_code == 403


def test_worker_list_gigs_only_open(worker_session):
    r = worker_session.get(f"{API}/gigs")
    assert r.status_code == 200
    gigs = r.json()
    assert all(g["status"] == "open" for g in gigs)
    # my_acceptance field present
    assert all("my_acceptance" in g for g in gigs)


def test_filter_by_category(worker_session):
    r = worker_session.get(f"{API}/gigs?category=cleaning")
    assert r.status_code == 200
    for g in r.json():
        assert g["category"] == "cleaning"


def test_get_gig_worker_has_my_acceptance(worker_session):
    gid = created_gigs["cleaning"]
    r = worker_session.get(f"{API}/gigs/{gid}")
    assert r.status_code == 200
    assert "my_acceptance" in r.json()


def test_get_gig_admin_has_acceptances(admin_session):
    gid = created_gigs["cleaning"]
    r = admin_session.get(f"{API}/gigs/{gid}")
    assert r.status_code == 200
    assert "acceptances" in r.json()


def test_accept_gig(worker_session):
    gid = created_gigs["cleaning"]
    r = worker_session.post(f"{API}/gigs/{gid}/accept")
    assert r.status_code == 200, r.text
    # verify slots_filled increased
    r2 = worker_session.get(f"{API}/gigs/{gid}")
    assert r2.json()["slots_filled"] == 1


def test_accept_duplicate_fails(worker_session):
    gid = created_gigs["cleaning"]
    r = worker_session.post(f"{API}/gigs/{gid}/accept")
    assert r.status_code == 400


def test_withdraw_gig(worker_session):
    gid = created_gigs["cleaning"]
    r = worker_session.post(f"{API}/gigs/{gid}/withdraw")
    assert r.status_code == 200
    r2 = worker_session.get(f"{API}/gigs/{gid}")
    assert r2.json()["slots_filled"] == 0
    assert r2.json()["status"] == "open"


def test_filled_status_when_slots_full(admin_session, worker_session):
    # create a 1-slot gig and accept it
    r = admin_session.post(
        f"{API}/gigs",
        json={
            "title": "TEST_one_slot", "description": "x", "category": "labor",
            "location": "x", "scheduled_date": "x", "pay_rate": 10, "pay_type": "hourly", "slots": 1,
        },
    )
    gid = r.json()["gig_id"]
    created_gigs["one_slot"] = gid
    r2 = worker_session.post(f"{API}/gigs/{gid}/accept")
    assert r2.status_code == 200
    r3 = admin_session.get(f"{API}/gigs/{gid}")
    assert r3.json()["status"] == "filled"


# ---- Blast ------------------------------------------------------------------
def test_blast_in_app(admin_session, worker_session):
    gid = created_gigs["labor"]
    r = admin_session.post(f"{API}/gigs/{gid}/blast", json={"channels": ["in_app"]})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["counts"]["in_app"] >= 1
    # verify notification created for worker
    n = worker_session.get(f"{API}/notifications")
    assert n.status_code == 200
    assert any(item["gig_id"] == gid for item in n.json())


def test_blast_email_sms_graceful(admin_session):
    gid = created_gigs["driver"]
    r = admin_session.post(f"{API}/gigs/{gid}/blast", json={"channels": ["email", "sms"]})
    assert r.status_code == 200, r.text


def test_blast_increments_count(admin_session):
    gid = created_gigs["labor"]
    r = admin_session.get(f"{API}/gigs/{gid}")
    assert r.json()["blast_count"] >= 1


# ---- Notifications ----------------------------------------------------------
def test_notifications_list(worker_session):
    r = worker_session.get(f"{API}/notifications")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---- Profile / uploads ------------------------------------------------------
# A 1x1 PNG
PNG = bytes.fromhex(
    "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4"
    "890000000D49444154789C636060606000000005000150E2C53A0000000049454E44AE426082"
)


def test_profile_update(worker_session):
    r = worker_session.put(
        f"{API}/profile",
        json={"name": "Updated W", "phone": "+15551234567", "bio": "hi", "skills": ["clean"]},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Updated W"
    assert data["phone"] == "+15551234567"
    assert data["skills"] == ["clean"]


def test_upload_avatar(worker_session):
    files = {"file": ("a.png", io.BytesIO(PNG), "image/png")}
    r = worker_session.post(f"{API}/profile/avatar", files=files)
    assert r.status_code == 200, r.text
    assert "avatar_path" in r.json()


def test_upload_id(worker_session):
    files = {"file": ("id.png", io.BytesIO(PNG), "image/png")}
    r = worker_session.post(f"{API}/profile/id", files=files)
    assert r.status_code == 200
    path = r.json()["id_image_path"]
    assert path
    # store for access tests
    created_gigs["__id_path"] = path


def test_file_access_owner(worker_session):
    path = created_gigs["__id_path"]
    r = worker_session.get(f"{API}/files/{path}")
    assert r.status_code == 200


def test_file_access_admin(admin_session):
    path = created_gigs["__id_path"]
    r = admin_session.get(f"{API}/files/{path}")
    assert r.status_code == 200


def test_file_access_other_worker_forbidden():
    # register a 3rd worker and try to access
    s = requests.Session()
    email = f"TEST_other_{UNIQUE}@example.com"
    s.post(f"{API}/auth/register", json={"email": email, "password": "Pwd12345!", "name": "Other"})
    path = created_gigs["__id_path"]
    r = s.get(f"{API}/files/{path}")
    assert r.status_code == 403


# ---- Admin endpoints --------------------------------------------------------
def test_admin_list_workers(admin_session):
    r = admin_session.get(f"{API}/admin/workers")
    assert r.status_code == 200
    workers = r.json()
    assert any(w["email"].lower() == WORKER_EMAIL.lower() for w in workers)


def test_admin_get_worker(admin_session, worker_session):
    me = worker_session.get(f"{API}/auth/me").json()
    r = admin_session.get(f"{API}/admin/workers/{me['user_id']}")
    assert r.status_code == 200
    assert "accepted_gigs" in r.json()


def test_admin_verify_id(admin_session, worker_session):
    me = worker_session.get(f"{API}/auth/me").json()
    r = admin_session.post(f"{API}/admin/workers/{me['user_id']}/verify-id")
    assert r.status_code == 200
    # verify by GET
    r2 = admin_session.get(f"{API}/admin/workers/{me['user_id']}")
    assert r2.json()["id_verified"] is True


def test_admin_stats(admin_session):
    r = admin_session.get(f"{API}/admin/stats")
    assert r.status_code == 200
    data = r.json()
    for k in ("total_workers", "open_gigs", "filled_gigs", "total_gigs", "total_acceptances", "pending_id_verification"):
        assert k in data


def test_worker_cannot_access_admin(worker_session):
    r = worker_session.get(f"{API}/admin/workers")
    assert r.status_code == 403
    r2 = worker_session.get(f"{API}/admin/stats")
    assert r2.status_code == 403


# ---- Cleanup / Delete -------------------------------------------------------
def test_delete_gig(admin_session):
    gid = created_gigs["cleaning"]
    r = admin_session.delete(f"{API}/gigs/{gid}")
    assert r.status_code == 200
    r2 = admin_session.get(f"{API}/gigs/{gid}")
    assert r2.status_code == 404
    # cleanup other gigs as well
    for k in ("labor", "driver", "one_slot"):
        if k in created_gigs:
            admin_session.delete(f"{API}/gigs/{created_gigs[k]}")
