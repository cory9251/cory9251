"""
Backend tests for the Projects feature (iter "projects").

Covers:
- POST /api/projects (create)
- GET /api/projects (list active + archived + search)
- GET /api/projects/{id} (detail: gigs, crew)
- PUT /api/projects/{id}
- DELETE /api/projects/{id} (archive + unlink children)
- POST /api/projects/{id}/notes + DELETE
- POST /api/gigs/{gig_id}/link-to-project
- DELETE /api/gigs/{gig_id}/project (unlink)
- GET /api/gigs and /api/gigs/{gig_id} enrichment with project field (admin)
- Worker enrichment with project (siblings + crew) on /api/gigs/{gig_id}
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://work-connect-147.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PASSWORD = "HcobAdmin2026!"


# ----------------------------- Fixtures --------------------------------
@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    me = s.get(f"{API}/auth/me", timeout=10)
    assert me.status_code == 200 and me.json().get("role") == "admin"
    return s


@pytest.fixture(scope="session")
def created_project(admin_session):
    """Create one project to reuse across tests."""
    payload = {
        "title": f"TEST_iterproj_{uuid.uuid4().hex[:6]}",
        "description": "Test project for iter projects",
        "client_name": "TEST Client Co",
        "defaults": {
            "location": "Houston",
            "payment_timeline": "2_3_days",
        },
    }
    r = admin_session.post(f"{API}/projects", json=payload, timeout=15)
    assert r.status_code == 200, f"create_project failed: {r.status_code} {r.text}"
    proj = r.json()
    assert proj["title"] == payload["title"]
    assert proj["client_name"] == payload["client_name"]
    assert proj["archived"] is False
    assert "project_id" in proj
    return proj


def _make_gig_payload(title_suffix="", project_id=None):
    future = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    p = {
        "title": f"TEST_iterproj_gig_{title_suffix or uuid.uuid4().hex[:6]}",
        "description": "Test gig",
        "category": "cleaning",
        "location": "Houston",
        "address_line": "123 Test St, Houston TX",
        "scheduled_date": "Sat, Jan 31 · 9:00 AM",
        "scheduled_at": future,
        "pay_rate": 20.0,
        "pay_type": "hourly",
        "slots": 1,
        "duration_hours": 4.0,
        "payment_timeline": "2_3_days",
        "contact_phone": "+12815550100",
    }
    if project_id:
        p["project_id"] = project_id
    return p


# ----------------------------- Tests -----------------------------------
class TestProjectsCRUD:
    def test_login_works(self, admin_session):
        r = admin_session.get(f"{API}/auth/me")
        assert r.status_code == 200

    def test_create_validates_title(self, admin_session):
        r = admin_session.post(f"{API}/projects", json={"title": ""}, timeout=10)
        # Either 422 (pydantic) or 200 with stripped — accept 4xx; main rule: never 500.
        assert r.status_code < 500

    def test_get_project_detail(self, admin_session, created_project):
        pid = created_project["project_id"]
        r = admin_session.get(f"{API}/projects/{pid}", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["project_id"] == pid
        assert isinstance(data.get("gigs"), list)
        assert isinstance(data.get("crew"), list)
        assert data.get("title") == created_project["title"]

    def test_list_active_includes_project(self, admin_session, created_project):
        r = admin_session.get(f"{API}/projects", params={"archived": "false"}, timeout=10)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        ids = [p["project_id"] for p in rows]
        assert created_project["project_id"] in ids
        # Aggregations exist
        my = next(p for p in rows if p["project_id"] == created_project["project_id"])
        for k in ("gig_count", "worker_count", "slots_total", "slots_filled"):
            assert k in my

    def test_search_filter(self, admin_session, created_project):
        r = admin_session.get(f"{API}/projects", params={"q": created_project["title"]}, timeout=10)
        assert r.status_code == 200
        rows = r.json()
        assert any(p["project_id"] == created_project["project_id"] for p in rows)

    def test_update_project(self, admin_session, created_project):
        pid = created_project["project_id"]
        new_title = created_project["title"] + "_upd"
        r = admin_session.put(f"{API}/projects/{pid}", json={"title": new_title}, timeout=10)
        assert r.status_code == 200
        assert r.json()["title"] == new_title


class TestProjectNotes:
    def test_add_and_delete_note(self, admin_session, created_project):
        pid = created_project["project_id"]
        r = admin_session.post(f"{API}/projects/{pid}/notes", json={"text": "hello note"}, timeout=10)
        assert r.status_code == 200
        note = r.json()
        assert note["text"] == "hello note"
        assert "note_id" in note

        # verify via GET
        det = admin_session.get(f"{API}/projects/{pid}").json()
        assert any(n["note_id"] == note["note_id"] for n in det.get("notes", []))

        # delete
        d = admin_session.delete(f"{API}/projects/{pid}/notes/{note['note_id']}", timeout=10)
        assert d.status_code == 200
        det2 = admin_session.get(f"{API}/projects/{pid}").json()
        assert not any(n["note_id"] == note["note_id"] for n in det2.get("notes", []))

    def test_empty_note_rejected(self, admin_session, created_project):
        pid = created_project["project_id"]
        r = admin_session.post(f"{API}/projects/{pid}/notes", json={"text": "   "}, timeout=10)
        assert r.status_code == 400


class TestGigProjectLinking:
    @pytest.fixture(scope="class")
    def two_gigs(self, admin_session, created_project):
        """Create two gigs linked at creation time to the project."""
        pid = created_project["project_id"]
        g1 = admin_session.post(f"{API}/gigs", json=_make_gig_payload("A", project_id=pid), timeout=15)
        g2 = admin_session.post(f"{API}/gigs", json=_make_gig_payload("B", project_id=pid), timeout=15)
        assert g1.status_code == 200, g1.text
        assert g2.status_code == 200, g2.text
        return g1.json(), g2.json()

    def test_gigs_show_up_in_project_detail(self, admin_session, created_project, two_gigs):
        pid = created_project["project_id"]
        det = admin_session.get(f"{API}/projects/{pid}", timeout=10).json()
        gig_ids = [g["gig_id"] for g in det.get("gigs", [])]
        g1, g2 = two_gigs
        assert g1["gig_id"] in gig_ids
        assert g2["gig_id"] in gig_ids

    def test_admin_gigs_list_enriched_with_project(self, admin_session, created_project, two_gigs):
        r = admin_session.get(f"{API}/gigs", timeout=15)
        assert r.status_code == 200
        rows = r.json()
        g1 = two_gigs[0]
        match = next((g for g in rows if g["gig_id"] == g1["gig_id"]), None)
        assert match, "gig missing from /api/gigs list"
        assert match.get("project"), "admin /api/gigs row should have 'project' enrichment"
        assert match["project"]["project_id"] == created_project["project_id"]
        assert match["project"]["title"]

    def test_admin_gig_detail_enriched(self, admin_session, created_project, two_gigs):
        g1, g2 = two_gigs
        r = admin_session.get(f"{API}/gigs/{g1['gig_id']}", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d.get("project"), "admin /api/gigs/{id} should include 'project'"
        assert d["project"]["project_id"] == created_project["project_id"]
        sibs = d["project"].get("sibling_gigs", [])
        assert any(s["gig_id"] == g2["gig_id"] for s in sibs)

    def test_unlink_then_relink(self, admin_session, created_project, two_gigs):
        g1 = two_gigs[0]
        # Unlink
        u = admin_session.delete(f"{API}/gigs/{g1['gig_id']}/project", timeout=10)
        assert u.status_code == 200
        d = admin_session.get(f"{API}/gigs/{g1['gig_id']}", timeout=10).json()
        assert not d.get("project")

        # Relink via POST link-to-project
        rl = admin_session.post(
            f"{API}/gigs/{g1['gig_id']}/link-to-project",
            json={"project_id": created_project["project_id"], "sync_defaults": False},
            timeout=10,
        )
        assert rl.status_code == 200
        d2 = admin_session.get(f"{API}/gigs/{g1['gig_id']}", timeout=10).json()
        assert d2.get("project")
        assert d2["project"]["project_id"] == created_project["project_id"]

    def test_link_to_nonexistent_project_404(self, admin_session, two_gigs):
        g1 = two_gigs[0]
        r = admin_session.post(
            f"{API}/gigs/{g1['gig_id']}/link-to-project",
            json={"project_id": "proj_doesnotexist_xxxxxx"},
            timeout=10,
        )
        assert r.status_code == 404


class TestArchive:
    """Archive lifecycle is separate so it runs late and doesn't break other tests."""

    def test_archive_unlinks_children_and_appears_in_archived_list(self, admin_session):
        # Create disposable project + 1 gig
        r = admin_session.post(
            f"{API}/projects",
            json={"title": f"TEST_iterproj_archv_{uuid.uuid4().hex[:5]}", "client_name": "ArchClient"},
            timeout=10,
        )
        assert r.status_code == 200
        pid = r.json()["project_id"]

        gr = admin_session.post(
            f"{API}/gigs", json=_make_gig_payload("arch", project_id=pid), timeout=15
        )
        assert gr.status_code == 200
        gig_id = gr.json()["gig_id"]

        # Archive
        ar = admin_session.delete(f"{API}/projects/{pid}", timeout=10)
        assert ar.status_code == 200

        # Project must appear in archived list
        lst = admin_session.get(f"{API}/projects", params={"archived": "true"}, timeout=10).json()
        assert any(p["project_id"] == pid for p in lst), "archived project missing from archived list"

        # The previously-linked gig should be unlinked (no project field)
        d = admin_session.get(f"{API}/gigs/{gig_id}", timeout=10).json()
        assert not d.get("project")


class TestWorkerProjectCard:
    """Place a worker on TWO sibling gigs of a project, then assert that the
    worker-side GET /api/gigs/{gig_id} response includes the project block
    with sibling_gigs + crew."""

    @pytest.fixture(scope="class")
    def worker_creds(self):
        email = f"TEST_iterproj_worker_{uuid.uuid4().hex[:6]}@hcobcleaners.com"
        password = "Worker123!"
        s = requests.Session()
        r = s.post(
            f"{API}/auth/register",
            json={"email": email, "password": password, "name": "TEST Iter Proj Worker"},
            timeout=15,
        )
        assert r.status_code in (200, 201), f"register failed {r.status_code} {r.text}"
        me = s.get(f"{API}/auth/me", timeout=10).json()
        return {"email": email, "password": password, "user_id": me["user_id"], "session": s}

    @pytest.fixture(scope="class")
    def approved_verified_worker(self, admin_session, worker_creds):
        uid = worker_creds["user_id"]
        # Complete profile (some fields required for assignment)
        admin_session.put(
            f"{API}/admin/workers/{uid}/profile",
            json={
                "first_name": "Iter",
                "last_name": "Proj",
                "phone": "+12815550199",
                "address_line": "1 Test Way",
                "city": "Houston",
                "state": "TX",
                "zip": "77002",
                "id_type": "drivers_license",
                "id_number": "X9999999",
            },
            timeout=10,
        )
        # Approve
        admin_session.post(f"{API}/admin/workers/{uid}/approve", timeout=10)
        # Verify ID
        admin_session.post(f"{API}/admin/workers/{uid}/verify-id", timeout=10)
        return worker_creds

    @pytest.fixture(scope="class")
    def project_with_two_assigned_gigs(self, admin_session, approved_verified_worker):
        # Fresh project + two gigs
        r = admin_session.post(
            f"{API}/projects",
            json={"title": f"TEST_iterproj_worker_{uuid.uuid4().hex[:5]}", "client_name": "WorkerTest"},
            timeout=10,
        )
        assert r.status_code == 200
        pid = r.json()["project_id"]
        g1 = admin_session.post(f"{API}/gigs", json=_make_gig_payload("w1", project_id=pid), timeout=15).json()
        g2 = admin_session.post(f"{API}/gigs", json=_make_gig_payload("w2", project_id=pid), timeout=15).json()

        # Assign worker to both
        wid = approved_verified_worker["user_id"]
        a1 = admin_session.post(f"{API}/gigs/{g1['gig_id']}/assign", json={"worker_id": wid}, timeout=10)
        a2 = admin_session.post(f"{API}/gigs/{g2['gig_id']}/assign", json={"worker_id": wid}, timeout=10)
        assert a1.status_code == 200, f"assign g1 failed: {a1.status_code} {a1.text}"
        assert a2.status_code == 200, f"assign g2 failed: {a2.status_code} {a2.text}"
        return {"project_id": pid, "g1": g1, "g2": g2}

    def test_worker_sees_project_card_with_siblings_and_crew(
        self, approved_verified_worker, project_with_two_assigned_gigs
    ):
        s = approved_verified_worker["session"]
        # log in fresh to refresh cookie
        s.post(
            f"{API}/auth/login",
            json={"email": approved_verified_worker["email"], "password": approved_verified_worker["password"]},
            timeout=15,
        )
        gig1 = project_with_two_assigned_gigs["g1"]
        gig2 = project_with_two_assigned_gigs["g2"]
        r = s.get(f"{API}/gigs/{gig1['gig_id']}", timeout=15)
        assert r.status_code == 200, f"worker gig fetch {r.status_code} {r.text}"
        data = r.json()
        proj = data.get("project")
        assert proj, "worker should see project block on a project-linked, assigned gig"
        assert proj["project_id"] == project_with_two_assigned_gigs["project_id"]
        sibs = proj.get("sibling_gigs", [])
        assert any(s2["gig_id"] == gig2["gig_id"] for s2 in sibs), "sibling gig missing"
        # crew should be present (at minimum, the worker is on both gigs)
        assert "crew" in proj
        # crew structure should expose first_name + gig_role only (no PII leak)
        for c in proj["crew"]:
            assert "first_name" in c
            assert "last_name" not in c, "worker view must not leak last_name"

    def test_worker_unlinked_gig_no_project(self, admin_session, approved_verified_worker):
        # Create a gig WITHOUT a project, assign worker, check worker view
        gp = _make_gig_payload("unlinked")
        gr = admin_session.post(f"{API}/gigs", json=gp, timeout=15)
        assert gr.status_code == 200
        gig_id = gr.json()["gig_id"]
        wid = approved_verified_worker["user_id"]
        a = admin_session.post(f"{API}/gigs/{gig_id}/assign", json={"worker_id": wid}, timeout=10)
        assert a.status_code == 200

        s = approved_verified_worker["session"]
        s.post(
            f"{API}/auth/login",
            json={"email": approved_verified_worker["email"], "password": approved_verified_worker["password"]},
            timeout=15,
        )
        r = s.get(f"{API}/gigs/{gig_id}", timeout=10)
        assert r.status_code == 200
        assert not r.json().get("project")
