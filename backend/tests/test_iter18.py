"""Iteration 18 backend tests:
- GET /api/public/gigs/{gig_id} (no-auth, safe fields, no address)
- PUT /api/gigs/{gig_id}/acceptances/{acceptance_id}/role
- Worker GET /api/gigs/{gig_id} crew field for APPROVED workers
- Admin user management: /api/admin/admins (list/create/update/delete)
- Read-only admin security (require_admin blocks writes)
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PASS = "HcobAdmin2026!"
RO_ADMIN_EMAIL = "ro_admin@hcobcleaners.com"
RO_ADMIN_PASS = "ReadOnly123!"


# ---------- Sessions ----------
@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return s


def _register_worker(name_suffix: str):
    uniq = uuid.uuid4().hex[:8]
    email = f"TEST_iter18_{name_suffix}_{uniq}@example.com"
    pw = "Worker123!"
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": pw, "name": f"Iter18 {name_suffix} {uniq}"},
    )
    assert r.status_code in (200, 201), r.text
    body = r.json()
    user_id = body.get("user_id") or body.get("user", {}).get("user_id")
    return email, pw, user_id


@pytest.fixture(scope="session")
def worker_a(admin_session):
    email, pw, uid = _register_worker("A")
    admin_session.put(
        f"{API}/admin/workers/{uid}/profile",
        json={
            "worker_status": "approved",
            "id_verified": True,
            "skills": ["residential_cleaning"],
            "zip_code": "94110",
            "city": "SF",
            "state": "CA",
            "phone": "4155551111",
            "address": "1 Way",
            "date_of_birth": "1990-01-01",
            "availability": ["weekday_mornings"],
        },
    )
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    return {"user_id": uid, "email": email, "session": s}


@pytest.fixture(scope="session")
def worker_b(admin_session):
    email, pw, uid = _register_worker("B")
    admin_session.put(
        f"{API}/admin/workers/{uid}/profile",
        json={
            "worker_status": "approved",
            "id_verified": True,
            "skills": ["residential_cleaning"],
            "zip_code": "94110",
            "city": "SF",
            "state": "CA",
            "phone": "4155552222",
            "address": "2 Way",
            "date_of_birth": "1990-01-01",
            "availability": ["weekday_mornings"],
        },
    )
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    return {"user_id": uid, "email": email, "session": s}


@pytest.fixture(scope="session")
def shared_gig(admin_session, worker_a, worker_b):
    """Create a gig with both workers approved."""
    gig_payload = {
        "title": f"TEST_iter18 share-gig {uuid.uuid4().hex[:6]}",
        "description": "iter18 crew test",
        "category": "cleaning",
        "subcategory": "residential_cleaning",
        "location": "San Francisco, CA",
        "zip_code": "94110",
        "scheduled_date": "2026-12-31",
        "scheduled_at": "2026-12-31T10:00:00Z",
        "pay_rate": 25,
        "pay_type": "hourly",
        "slots": 4,
        "address_line": "123 Secret St.",
        "skills_required": ["residential_cleaning"],
    }
    gr = admin_session.post(f"{API}/gigs", json=gig_payload)
    assert gr.status_code in (200, 201), gr.text
    gig_id = gr.json()["gig_id"]
    a_assign = admin_session.post(f"{API}/gigs/{gig_id}/assign", json={"worker_id": worker_a["user_id"]})
    assert a_assign.status_code in (200, 201), a_assign.text
    a_acc = a_assign.json().get("acceptance_id") or a_assign.json().get("acceptance", {}).get("acceptance_id")
    b_assign = admin_session.post(f"{API}/gigs/{gig_id}/assign", json={"worker_id": worker_b["user_id"]})
    assert b_assign.status_code in (200, 201), b_assign.text
    b_acc = b_assign.json().get("acceptance_id") or b_assign.json().get("acceptance", {}).get("acceptance_id")
    return {"gig_id": gig_id, "a_acceptance": a_acc, "b_acceptance": b_acc}


# ---------- 1. Public gig lookup ----------
class TestPublicGigLookup:
    def test_unauth_can_lookup(self, shared_gig):
        # No session/cookies — fresh requests
        r = requests.get(f"{API}/public/gigs/{shared_gig['gig_id']}")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["gig_id"] == shared_gig["gig_id"]
        assert d.get("title")
        assert d.get("pay_rate") is not None
        assert "slots" in d

    def test_address_stripped(self, shared_gig):
        r = requests.get(f"{API}/public/gigs/{shared_gig['gig_id']}")
        assert r.status_code == 200
        d = r.json()
        assert "address_line" not in d, f"address_line should be stripped! Got: {d}"

    def test_unknown_gig_404(self):
        r = requests.get(f"{API}/public/gigs/gig_does_not_exist_zzz")
        assert r.status_code == 404

    def test_cancelled_gig_404(self, admin_session):
        """Note: there is no current API endpoint to set gig.status='cancelled'
        (GigPatch doesn't include 'status', and DELETE removes the gig entirely).
        We instead verify that a DELETED gig also returns 404 via public lookup.
        The cancelled-status branch of public_gig_lookup is currently unreachable
        from the public API surface — flagged in test report."""
        gig_payload = {
            "title": f"TEST_iter18 deleted {uuid.uuid4().hex[:6]}",
            "description": "x",
            "category": "cleaning",
            "subcategory": "residential_cleaning",
            "location": "SF",
            "zip_code": "94110",
            "scheduled_date": "2026-12-31",
            "scheduled_at": "2026-12-31T10:00:00Z",
            "pay_rate": 20,
            "pay_type": "hourly",
            "slots": 1,
        }
        gr = admin_session.post(f"{API}/gigs", json=gig_payload)
        gid = gr.json()["gig_id"]
        admin_session.delete(f"{API}/gigs/{gid}")
        r = requests.get(f"{API}/public/gigs/{gid}")
        assert r.status_code == 404


# ---------- 2. Per-gig role endpoint ----------
class TestGigRole:
    def test_set_role_manager(self, admin_session, shared_gig):
        r = admin_session.put(
            f"{API}/gigs/{shared_gig['gig_id']}/acceptances/{shared_gig['a_acceptance']}/role",
            json={"role": "manager"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["gig_role"] == "manager"
        # Verify persisted
        g = admin_session.get(f"{API}/gigs/{shared_gig['gig_id']}")
        accs = g.json().get("acceptances", [])
        a = next((x for x in accs if x["acceptance_id"] == shared_gig["a_acceptance"]), None)
        assert a is not None
        assert a.get("gig_role") == "manager"

    def test_bad_role_400(self, admin_session, shared_gig):
        r = admin_session.put(
            f"{API}/gigs/{shared_gig['gig_id']}/acceptances/{shared_gig['a_acceptance']}/role",
            json={"role": "supreme_overlord"},
        )
        assert r.status_code == 400

    def test_unknown_acceptance_404(self, admin_session, shared_gig):
        r = admin_session.put(
            f"{API}/gigs/{shared_gig['gig_id']}/acceptances/acc_zzz/role",
            json={"role": "worker"},
        )
        assert r.status_code == 404


# ---------- 3. Worker GET gig — crew field ----------
class TestWorkerCrew:
    def test_approved_worker_sees_crew(self, admin_session, shared_gig, worker_a, worker_b):
        # Make sure A is manager and B is worker
        admin_session.put(
            f"{API}/gigs/{shared_gig['gig_id']}/acceptances/{shared_gig['a_acceptance']}/role",
            json={"role": "manager"},
        )
        admin_session.put(
            f"{API}/gigs/{shared_gig['gig_id']}/acceptances/{shared_gig['b_acceptance']}/role",
            json={"role": "worker"},
        )
        # Worker A views the gig
        r = worker_a["session"].get(f"{API}/gigs/{shared_gig['gig_id']}")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "crew" in d, f"APPROVED worker should see crew, got keys={list(d.keys())}"
        crew = d["crew"]
        assert isinstance(crew, list)
        assert len(crew) == 1, f"Crew should exclude self, got: {crew}"
        member = crew[0]
        assert "first_name" in member
        assert "gig_role" in member
        # No last name leakage
        assert " " not in member["first_name"]
        assert member["gig_role"] == "worker"

    def test_pending_worker_no_crew(self, admin_session, worker_a):
        # Create another gig where worker_a is just requested (pending)
        gig_payload = {
            "title": f"TEST_iter18 pending {uuid.uuid4().hex[:6]}",
            "description": "x",
            "category": "cleaning",
            "subcategory": "residential_cleaning",
            "location": "SF",
            "zip_code": "94110",
            "scheduled_date": "2026-12-31",
            "scheduled_at": "2026-12-31T10:00:00Z",
            "pay_rate": 25,
            "pay_type": "hourly",
            "slots": 2,
        }
        gr = admin_session.post(f"{API}/gigs", json=gig_payload)
        gid = gr.json()["gig_id"]
        # Worker A requests (claim) it
        cr = worker_a["session"].post(f"{API}/gigs/{gid}/claim")
        # may be 200/201/409 if claimed-only-once; just continue
        r = worker_a["session"].get(f"{API}/gigs/{gid}")
        assert r.status_code == 200
        d = r.json()
        my = d.get("my_acceptance") or {}
        if my.get("status") == "requested":
            assert "crew" not in d, f"Pending worker should NOT see crew. d.keys={list(d.keys())}"


# ---------- 4. Admin user management ----------
@pytest.fixture(scope="session")
def created_admin_id(admin_session):
    """Create a throwaway admin to use across tests."""
    uniq = uuid.uuid4().hex[:6]
    email = f"TEST_iter18_admin_{uniq}@example.com"
    r = admin_session.post(
        f"{API}/admin/admins",
        json={
            "name": f"Test Admin {uniq}",
            "email": email,
            "password": "TestAdmin123!",
            "is_read_only": False,
        },
    )
    assert r.status_code in (200, 201), r.text
    body = r.json()
    return {"user_id": body["user_id"], "email": email}


class TestAdminUserMgmt:
    def test_list_admins_includes_self_flag(self, admin_session):
        r = admin_session.get(f"{API}/admin/admins")
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        selves = [x for x in rows if x.get("is_self")]
        assert len(selves) == 1, f"Exactly one is_self=true expected, got {selves}"
        assert selves[0]["email"] == ADMIN_EMAIL
        # is_read_only present on every row
        for x in rows:
            assert "is_read_only" in x

    def test_create_admin(self, admin_session, created_admin_id):
        # Verify it shows up (server lowercases email)
        r = admin_session.get(f"{API}/admin/admins")
        emails = [x["email"] for x in r.json()]
        assert created_admin_id["email"].lower() in emails

    def test_duplicate_email_400(self, admin_session, created_admin_id):
        r = admin_session.post(
            f"{API}/admin/admins",
            json={
                "name": "Dup",
                "email": created_admin_id["email"],
                "password": "OtherPass123!",
            },
        )
        assert r.status_code == 400

    def test_short_password_400(self, admin_session):
        r = admin_session.post(
            f"{API}/admin/admins",
            json={
                "name": "Short",
                "email": f"TEST_iter18_short_{uuid.uuid4().hex[:6]}@example.com",
                "password": "abc",
            },
        )
        assert r.status_code == 400

    def test_toggle_read_only(self, admin_session, created_admin_id):
        r = admin_session.put(
            f"{API}/admin/admins/{created_admin_id['user_id']}",
            json={"is_read_only": True},
        )
        assert r.status_code == 200, r.text
        # Verify
        lst = admin_session.get(f"{API}/admin/admins").json()
        row = next(x for x in lst if x["user_id"] == created_admin_id["user_id"])
        assert row["is_read_only"] is True

    def test_self_cannot_be_read_only(self, admin_session):
        me_list = admin_session.get(f"{API}/admin/admins").json()
        my_id = next(x["user_id"] for x in me_list if x.get("is_self"))
        r = admin_session.put(
            f"{API}/admin/admins/{my_id}",
            json={"is_read_only": True},
        )
        assert r.status_code == 400

    def test_self_cannot_be_demoted(self, admin_session):
        me_list = admin_session.get(f"{API}/admin/admins").json()
        my_id = next(x["user_id"] for x in me_list if x.get("is_self"))
        r = admin_session.put(
            f"{API}/admin/admins/{my_id}",
            json={"demote_to_worker": True},
        )
        assert r.status_code == 400

    def test_cannot_delete_self(self, admin_session):
        me_list = admin_session.get(f"{API}/admin/admins").json()
        my_id = next(x["user_id"] for x in me_list if x.get("is_self"))
        r = admin_session.delete(f"{API}/admin/admins/{my_id}")
        assert r.status_code == 400

    def test_promote_worker(self, admin_session, worker_b):
        # Promote worker_b to admin
        r = admin_session.put(
            f"{API}/admin/admins/{worker_b['user_id']}",
            json={"promote_to_admin": True},
        )
        assert r.status_code == 200, r.text
        # Then demote them back to keep state clean
        d = admin_session.put(
            f"{API}/admin/admins/{worker_b['user_id']}",
            json={"demote_to_worker": True},
        )
        assert d.status_code == 200

    def test_delete_admin(self, admin_session, created_admin_id):
        # First flip back to full so delete-check uses full count
        admin_session.put(
            f"{API}/admin/admins/{created_admin_id['user_id']}",
            json={"is_read_only": False},
        )
        r = admin_session.delete(f"{API}/admin/admins/{created_admin_id['user_id']}")
        assert r.status_code == 200
        # Verify gone
        lst = admin_session.get(f"{API}/admin/admins").json()
        assert created_admin_id["email"] not in [x["email"] for x in lst]


# ---------- 5. Read-only admin security ----------
@pytest.fixture(scope="session")
def ro_admin_session(admin_session):
    """Make sure ro_admin@hcobcleaners.com exists; otherwise create."""
    # Try login first
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": RO_ADMIN_EMAIL, "password": RO_ADMIN_PASS})
    if r.status_code == 200:
        return s
    # Otherwise create
    cr = admin_session.post(
        f"{API}/admin/admins",
        json={
            "name": "Read Only Admin",
            "email": RO_ADMIN_EMAIL,
            "password": RO_ADMIN_PASS,
            "is_read_only": True,
        },
    )
    assert cr.status_code in (200, 201, 400), cr.text
    # 400 means already exists — still try login
    s2 = requests.Session()
    s2.headers.update({"Content-Type": "application/json"})
    lr = s2.post(f"{API}/auth/login", json={"email": RO_ADMIN_EMAIL, "password": RO_ADMIN_PASS})
    assert lr.status_code == 200, lr.text
    return s2


class TestReadOnlyAdminSecurity:
    def test_ro_can_get_admin_gigs(self, ro_admin_session):
        # Admin gigs list is served via /api/gigs (admin sees all)
        r = ro_admin_session.get(f"{API}/gigs")
        assert r.status_code == 200, r.text

    def test_ro_can_get_admins_list(self, ro_admin_session):
        r = ro_admin_session.get(f"{API}/admin/admins")
        assert r.status_code == 200

    def test_ro_post_gig_blocked(self, ro_admin_session):
        r = ro_admin_session.post(
            f"{API}/gigs",
            json={
                "title": "RO try",
                "description": "x",
                "category": "cleaning",
                "subcategory": "residential_cleaning",
                "location": "SF",
                "zip_code": "94110",
                "scheduled_date": "2026-12-31",
                "scheduled_at": "2026-12-31T10:00:00Z",
                "pay_rate": 20,
                "pay_type": "hourly",
                "slots": 1,
            },
        )
        assert r.status_code == 403, r.text
        assert "Read-only" in r.text or "read-only" in r.text

    def test_ro_delete_admin_blocked(self, ro_admin_session):
        r = ro_admin_session.delete(f"{API}/admin/admins/usr_anything")
        assert r.status_code == 403

    def test_ro_put_admin_blocked(self, ro_admin_session):
        r = ro_admin_session.put(
            f"{API}/admin/admins/usr_anything",
            json={"is_read_only": False},
        )
        assert r.status_code == 403
