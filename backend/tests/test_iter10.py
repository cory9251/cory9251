"""ITER-10 tests: admin add/remove worker on a gig.

New endpoints:
- POST /api/gigs/{gig_id}/assign         {worker_id}
- DELETE /api/gigs/{gig_id}/acceptances/{acceptance_id}
"""
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


# --------------------------- helpers ---------------------------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


def _register_worker(prefix="iter10"):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"TEST_{prefix}_{uuid.uuid4().hex[:8]}@ex.com"
    r = s.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": "Worker123!",
            "name": f"Iter10 {prefix}",
            "phone": "+15550001111",
            "role": "worker",
        },
    )
    assert r.status_code == 200, r.text
    me = s.get(f"{API}/auth/me").json()
    return s, email, me["user_id"]


def _create_gig(admin_sess, slots=2, title_suffix=""):
    payload = {
        "title": f"TEST_iter10_{title_suffix or uuid.uuid4().hex[:6]}",
        "description": "iter10 gig",
        "category": "cleaning",
        "location": "Public St, 94110",
        "address_line": "1234 Oak Ave, San Francisco CA 94110",
        "scheduled_date": "2026-12-01",
        "pay_rate": 25,
        "pay_type": "hourly",
        "slots": slots,
    }
    r = admin_sess.post(f"{API}/gigs", json=payload)
    assert r.status_code == 200, r.text
    return r.json()["gig_id"]


def _upload_and_verify_id(ws, admin_sess, uid):
    old_ct = ws.headers.pop("Content-Type", None)
    files = {"file": ("id.png", b"\x89PNG\r\n\x1a\nfake", "image/png")}
    r = ws.post(f"{API}/profile/id", files=files)
    if old_ct:
        ws.headers["Content-Type"] = old_ct
    assert r.status_code == 200, r.text
    rv = admin_sess.post(f"{API}/admin/workers/{uid}/verify-id")
    assert rv.status_code == 200, rv.text


def _set_worker_status(admin_sess, uid, status):
    """Use admin endpoint to set worker_status."""
    if status == "approved":
        r = admin_sess.post(f"{API}/admin/workers/{uid}/approve")
    elif status == "rejected":
        r = admin_sess.post(f"{API}/admin/workers/{uid}/reject")
    elif status == "suspended":
        r = admin_sess.post(f"{API}/admin/workers/{uid}/suspend")
    else:
        raise ValueError(status)
    assert r.status_code == 200, r.text


# --------------------------- Tests ---------------------------
class TestAssignWorker:
    def test_assign_fresh_worker_creates_accepted(self, admin_session):
        gid = _create_gig(admin_session, slots=2, title_suffix="fresh")
        ws, email, uid = _register_worker("fresh")
        r = admin_session.post(f"{API}/gigs/{gid}/assign", json={"worker_id": uid})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["slots_filled"] == 1
        aid = body["acceptance_id"]

        g = admin_session.get(f"{API}/gigs/{gid}").json()
        assert g["slots_filled"] == 1
        assert g["status"] == "open"  # still room
        accs = g.get("acceptances", [])
        assert len(accs) == 1
        a = accs[0]
        assert a["acceptance_id"] == aid
        assert a["status"] == "accepted"
        assert a.get("accepted_at")
        assert a.get("approved_by") == ADMIN_EMAIL
        assert a.get("assigned_by_admin") is True

        # Worker received a notification
        notes = ws.get(f"{API}/notifications").json()
        assert any(n.get("gig_id") == gid for n in notes)
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_assign_fills_gig_when_last_slot(self, admin_session):
        gid = _create_gig(admin_session, slots=1, title_suffix="last")
        _, _, uid = _register_worker("last")
        r = admin_session.post(f"{API}/gigs/{gid}/assign", json={"worker_id": uid})
        assert r.status_code == 200
        g = admin_session.get(f"{API}/gigs/{gid}").json()
        assert g["slots_filled"] == 1
        assert g["status"] == "filled"
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_assign_converts_pending_request(self, admin_session):
        gid = _create_gig(admin_session, slots=2, title_suffix="convert")
        ws, _, uid = _register_worker("convert")
        _upload_and_verify_id(ws, admin_session, uid)
        # Worker requests first
        ra = ws.post(f"{API}/gigs/{gid}/accept")
        assert ra.status_code == 200
        aid_req = ra.json()["acceptance_id"]
        # Admin assigns same worker — should convert, not duplicate
        r = admin_session.post(f"{API}/gigs/{gid}/assign", json={"worker_id": uid})
        assert r.status_code == 200, r.text
        assert r.json()["acceptance_id"] == aid_req  # same row

        g = admin_session.get(f"{API}/gigs/{gid}").json()
        # Only one acceptance row for this worker
        rows = [a for a in g["acceptances"] if a["worker_id"] == uid]
        pending = [a for a in g.get("pending_requests", []) if a["worker_id"] == uid]
        assert len(rows) == 1
        assert len(pending) == 0
        assert rows[0]["status"] == "accepted"
        assert g["slots_filled"] == 1
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_assign_already_accepted_returns_400(self, admin_session):
        gid = _create_gig(admin_session, slots=3, title_suffix="dup")
        _, _, uid = _register_worker("dup")
        r1 = admin_session.post(f"{API}/gigs/{gid}/assign", json={"worker_id": uid})
        assert r1.status_code == 200
        r2 = admin_session.post(f"{API}/gigs/{gid}/assign", json={"worker_id": uid})
        assert r2.status_code == 400
        assert "already" in (r2.json().get("detail") or "").lower()
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_assign_nonexistent_worker_404(self, admin_session):
        gid = _create_gig(admin_session, slots=1, title_suffix="now")
        r = admin_session.post(f"{API}/gigs/{gid}/assign", json={"worker_id": "nope_xyz"})
        assert r.status_code == 404
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_assign_admin_target_404(self, admin_session):
        gid = _create_gig(admin_session, slots=1, title_suffix="admt")
        me = admin_session.get(f"{API}/auth/me").json()
        r = admin_session.post(
            f"{API}/gigs/{gid}/assign", json={"worker_id": me["user_id"]}
        )
        assert r.status_code == 404
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_assign_rejected_worker_400(self, admin_session):
        gid = _create_gig(admin_session, slots=1, title_suffix="rej")
        _, _, uid = _register_worker("rej")
        _set_worker_status(admin_session, uid, "rejected")
        r = admin_session.post(f"{API}/gigs/{gid}/assign", json={"worker_id": uid})
        assert r.status_code == 400
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_assign_suspended_worker_400(self, admin_session):
        gid = _create_gig(admin_session, slots=1, title_suffix="sus")
        _, _, uid = _register_worker("sus")
        _set_worker_status(admin_session, uid, "suspended")
        r = admin_session.post(f"{API}/gigs/{gid}/assign", json={"worker_id": uid})
        assert r.status_code == 400
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_assign_when_all_slots_filled_400(self, admin_session):
        gid = _create_gig(admin_session, slots=1, title_suffix="full")
        _, _, uid1 = _register_worker("full1")
        _, _, uid2 = _register_worker("full2")
        admin_session.post(f"{API}/gigs/{gid}/assign", json={"worker_id": uid1})
        r = admin_session.post(f"{API}/gigs/{gid}/assign", json={"worker_id": uid2})
        assert r.status_code == 400
        assert "slots" in (r.json().get("detail") or "").lower()
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_assign_nonexistent_gig_404(self, admin_session):
        _, _, uid = _register_worker("nogig")
        r = admin_session.post(
            f"{API}/gigs/does_not_exist/assign", json={"worker_id": uid}
        )
        assert r.status_code == 404

    def test_assign_as_worker_403(self, admin_session):
        gid = _create_gig(admin_session, slots=1, title_suffix="403")
        ws, _, _ = _register_worker("403a")
        _, _, uid2 = _register_worker("403b")
        r = ws.post(f"{API}/gigs/{gid}/assign", json={"worker_id": uid2})
        assert r.status_code == 403
        admin_session.delete(f"{API}/gigs/{gid}")


class TestRemoveWorker:
    def test_remove_accepted_decrements_slots(self, admin_session):
        gid = _create_gig(admin_session, slots=2, title_suffix="rmacc")
        _, _, uid = _register_worker("rmacc")
        r = admin_session.post(f"{API}/gigs/{gid}/assign", json={"worker_id": uid})
        aid = r.json()["acceptance_id"]
        # Remove
        rd = admin_session.delete(f"{API}/gigs/{gid}/acceptances/{aid}")
        assert rd.status_code == 200, rd.text
        g = admin_session.get(f"{API}/gigs/{gid}").json()
        assert g["slots_filled"] == 0
        assert g["status"] == "open"
        assert all(a["acceptance_id"] != aid for a in g.get("acceptances", []))
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_remove_reopens_filled_gig(self, admin_session):
        gid = _create_gig(admin_session, slots=1, title_suffix="reopen")
        _, _, uid = _register_worker("reopen")
        r = admin_session.post(f"{API}/gigs/{gid}/assign", json={"worker_id": uid})
        aid = r.json()["acceptance_id"]
        g = admin_session.get(f"{API}/gigs/{gid}").json()
        assert g["status"] == "filled"
        rd = admin_session.delete(f"{API}/gigs/{gid}/acceptances/{aid}")
        assert rd.status_code == 200
        g2 = admin_session.get(f"{API}/gigs/{gid}").json()
        assert g2["status"] == "open"
        assert g2["slots_filled"] == 0
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_remove_requested_does_not_touch_slots(self, admin_session):
        gid = _create_gig(admin_session, slots=2, title_suffix="rmreq")
        ws, _, uid = _register_worker("rmreq")
        _upload_and_verify_id(ws, admin_session, uid)
        ra = ws.post(f"{API}/gigs/{gid}/accept")
        aid = ra.json()["acceptance_id"]
        g_before = admin_session.get(f"{API}/gigs/{gid}").json()
        assert g_before["slots_filled"] == 0
        # Remove the requested row
        rd = admin_session.delete(f"{API}/gigs/{gid}/acceptances/{aid}")
        assert rd.status_code == 200
        g_after = admin_session.get(f"{API}/gigs/{gid}").json()
        assert g_after["slots_filled"] == 0
        # The acceptance should be gone (from both pending_requests and acceptances)
        all_aids = [a["acceptance_id"] for a in g_after.get("pending_requests", [])] + [
            a["acceptance_id"] for a in g_after.get("acceptances", [])
        ]
        assert aid not in all_aids
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_remove_sends_notification(self, admin_session):
        gid = _create_gig(admin_session, slots=2, title_suffix="rmnot")
        ws, _, uid = _register_worker("rmnot")
        r = admin_session.post(f"{API}/gigs/{gid}/assign", json={"worker_id": uid})
        aid = r.json()["acceptance_id"]
        notes_before = ws.get(f"{API}/notifications").json()
        before_count = len([n for n in notes_before if n.get("gig_id") == gid])
        admin_session.delete(f"{API}/gigs/{gid}/acceptances/{aid}")
        notes_after = ws.get(f"{API}/notifications").json()
        after_count = len([n for n in notes_after if n.get("gig_id") == gid])
        assert after_count > before_count
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_remove_nonexistent_acceptance_404(self, admin_session):
        gid = _create_gig(admin_session, slots=1, title_suffix="rm404")
        r = admin_session.delete(f"{API}/gigs/{gid}/acceptances/nope_xyz")
        assert r.status_code == 404
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_remove_wrong_gig_pairing_404(self, admin_session):
        gid_a = _create_gig(admin_session, slots=1, title_suffix="pairA")
        gid_b = _create_gig(admin_session, slots=1, title_suffix="pairB")
        _, _, uid = _register_worker("pair")
        r = admin_session.post(f"{API}/gigs/{gid_a}/assign", json={"worker_id": uid})
        aid = r.json()["acceptance_id"]
        # try to delete it via wrong gig
        rd = admin_session.delete(f"{API}/gigs/{gid_b}/acceptances/{aid}")
        assert rd.status_code == 404
        admin_session.delete(f"{API}/gigs/{gid_a}")
        admin_session.delete(f"{API}/gigs/{gid_b}")

    def test_remove_as_worker_403(self, admin_session):
        gid = _create_gig(admin_session, slots=1, title_suffix="rm403")
        ws, _, uid = _register_worker("rm403")
        r = admin_session.post(f"{API}/gigs/{gid}/assign", json={"worker_id": uid})
        aid = r.json()["acceptance_id"]
        rd = ws.delete(f"{API}/gigs/{gid}/acceptances/{aid}")
        assert rd.status_code == 403
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_assign_after_remove_works(self, admin_session):
        gid = _create_gig(admin_session, slots=1, title_suffix="reassign")
        _, _, uid = _register_worker("reassign")
        r1 = admin_session.post(f"{API}/gigs/{gid}/assign", json={"worker_id": uid})
        aid = r1.json()["acceptance_id"]
        rd = admin_session.delete(f"{API}/gigs/{gid}/acceptances/{aid}")
        assert rd.status_code == 200
        # Re-assign
        r2 = admin_session.post(f"{API}/gigs/{gid}/assign", json={"worker_id": uid})
        assert r2.status_code == 200, r2.text
        assert r2.json()["acceptance_id"] != aid  # new row (hard delete proven)
        admin_session.delete(f"{API}/gigs/{gid}")


class TestIter8RegressionStillPasses:
    """Ensure iter-8 request/approve flow still works alongside new assign flow."""

    def test_request_approve_reject_still_works(self, admin_session):
        gid = _create_gig(admin_session, slots=2, title_suffix="reg8")
        ws, _, uid = _register_worker("reg8")
        _upload_and_verify_id(ws, admin_session, uid)
        ra = ws.post(f"{API}/gigs/{gid}/accept")
        assert ra.status_code == 200
        aid = ra.json()["acceptance_id"]
        # Approve through old endpoint still works
        rap = admin_session.post(f"{API}/gigs/{gid}/requests/{aid}/approve")
        assert rap.status_code == 200, rap.text
        g = admin_session.get(f"{API}/gigs/{gid}").json()
        accs = [a for a in g["acceptances"] if a["acceptance_id"] == aid]
        assert len(accs) == 1
        assert accs[0]["status"] == "accepted"
        # iter-8 acceptance should NOT have assigned_by_admin flag
        assert accs[0].get("assigned_by_admin") is not True
        admin_session.delete(f"{API}/gigs/{gid}")
