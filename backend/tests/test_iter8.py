"""ITER-8 tests: per-gig request/approve/reject acceptance flow.

New model:
- /auth/register defaults worker_status='approved' (was 'pending')
- POST /gigs/{id}/accept => creates acceptance with status='requested', NO slot reservation
- POST /gigs/{id}/requests/{aid}/approve => flips to 'accepted', increments slots_filled
- POST /gigs/{id}/requests/{aid}/reject => DELETES the acceptance
- Withdraw on 'requested' => delete (no slot change); on 'accepted' => decrement
- Admin GET /gigs/{id} => returns pending_requests[] + acceptances[]
- Admin GET /admin/stats => includes pending_requests count
"""
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


# --------------------------- helpers ---------------------------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


def _register_worker(prefix="iter8"):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"TEST_{prefix}_{uuid.uuid4().hex[:8]}@ex.com"
    r = s.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": "Worker123!",
            "name": "Test Worker",
            "phone": "+15550001111",
            "role": "worker",
        },
    )
    assert r.status_code == 200, r.text
    me = s.get(f"{API}/auth/me").json()
    return s, email, me["user_id"]


def _upload_id(ws):
    # Important: don't pass Content-Type=application/json from session - requests
    # auto-sets multipart boundary when files= is given AND no header set.
    old_ct = ws.headers.pop("Content-Type", None)
    files = {"file": ("id.png", b"\x89PNG\r\n\x1a\nfake", "image/png")}
    r = ws.post(f"{API}/profile/id", files=files)
    if old_ct:
        ws.headers["Content-Type"] = old_ct
    assert r.status_code == 200, r.text


def _verify_id(admin_sess, uid):
    r = admin_sess.post(f"{API}/admin/workers/{uid}/verify-id")
    assert r.status_code == 200


def _ready_worker(admin_sess, prefix="iter8"):
    """Approved + ID verified worker, ready to /accept."""
    ws, email, uid = _register_worker(prefix)
    _upload_id(ws)
    _verify_id(admin_sess, uid)
    return ws, email, uid


def _create_gig(admin_sess, slots=2, title_suffix=""):
    payload = {
        "title": f"TEST_iter8_{title_suffix or uuid.uuid4().hex[:6]}",
        "description": "iter8 gig",
        "category": "cleaning",
        "location": "Public St, 94110",
        "address_line": "1234 Oak Ave, Apt 7B, San Francisco CA 94110",
        "scheduled_date": "2026-12-01",
        "pay_rate": 25,
        "pay_type": "hourly",
        "slots": slots,
    }
    r = admin_sess.post(f"{API}/gigs", json=payload)
    assert r.status_code == 200, r.text
    return r.json()["gig_id"]


# --------------------------- Tests ---------------------------
class TestRegisterDefaultsApproved:
    def test_new_worker_is_auto_approved(self):
        ws, _, _ = _register_worker("autoapp")
        me = ws.get(f"{API}/auth/me").json()
        assert me.get("worker_status") == "approved"


class TestAcceptCreatesRequest:
    def test_accept_creates_requested_no_slot_decrement(self, admin_session):
        gid = _create_gig(admin_session, slots=2, title_suffix="reqcreate")
        ws, _, _ = _ready_worker(admin_session, "reqcreate")
        r = ws.post(f"{API}/gigs/{gid}/accept")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "requested"
        assert "acceptance_id" in body
        # No slot decrement
        g = admin_session.get(f"{API}/gigs/{gid}").json()
        assert g["slots_filled"] == 0
        assert g["status"] == "open"
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_worker_get_gig_hides_address_while_requested(self, admin_session):
        gid = _create_gig(admin_session, slots=2, title_suffix="hideaddr")
        ws, _, _ = _ready_worker(admin_session, "hideaddr")
        r = ws.post(f"{API}/gigs/{gid}/accept")
        aid = r.json()["acceptance_id"]
        # Worker view: address hidden, my_acceptance.status=requested
        rg = ws.get(f"{API}/gigs/{gid}").json()
        assert rg.get("address_line") in (None, "")
        assert rg.get("my_acceptance", {}).get("status") == "requested"
        assert rg["my_acceptance"]["acceptance_id"] == aid
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_clockin_blocked_while_requested(self, admin_session):
        gid = _create_gig(admin_session, slots=2, title_suffix="ciblock")
        ws, _, _ = _ready_worker(admin_session, "ciblock")
        ws.post(f"{API}/gigs/{gid}/accept")
        r = ws.post(f"{API}/gigs/{gid}/clock-in")
        assert r.status_code == 400
        msg = (r.json().get("detail") or "").lower()
        assert "pending" in msg or "approval" in msg or "request" in msg
        admin_session.delete(f"{API}/gigs/{gid}")


class TestApproveRequest:
    def test_approve_flow_full(self, admin_session):
        gid = _create_gig(admin_session, slots=1, title_suffix="apprfull")
        ws, _, uid = _ready_worker(admin_session, "apprfull")
        ra = ws.post(f"{API}/gigs/{gid}/accept")
        aid = ra.json()["acceptance_id"]
        # Approve
        rap = admin_session.post(f"{API}/gigs/{gid}/requests/{aid}/approve")
        assert rap.status_code == 200, rap.text
        # Verify by fetching the gig as admin — acceptance now has 'accepted' status
        g = admin_session.get(f"{API}/gigs/{gid}").json()
        assert g["slots_filled"] == 1
        assert g["status"] == "filled"
        accs = g.get("acceptances", [])
        assert len(accs) == 1
        assert accs[0]["status"] == "accepted"
        assert accs[0].get("accepted_at")
        assert accs[0].get("approved_by") == ADMIN_EMAIL
        # Worker sees address + accepted status
        gw = ws.get(f"{API}/gigs/{gid}").json()
        assert gw.get("address_line")
        assert gw["my_acceptance"]["status"] == "accepted"
        # Worker can now clock-in
        rin = ws.post(f"{API}/gigs/{gid}/clock-in")
        assert rin.status_code == 200, rin.text
        # Notification created for worker
        notes = ws.get(f"{API}/notifications").json()
        assert any(n.get("gig_id") == gid for n in notes)
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_approve_404_if_not_found(self, admin_session):
        gid = _create_gig(admin_session, slots=1, title_suffix="appr404")
        r = admin_session.post(f"{API}/gigs/{gid}/requests/nope_xyz/approve")
        assert r.status_code == 404
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_approve_400_if_already_accepted(self, admin_session):
        gid = _create_gig(admin_session, slots=2, title_suffix="apprdbl")
        ws, _, _ = _ready_worker(admin_session, "apprdbl")
        ra = ws.post(f"{API}/gigs/{gid}/accept")
        aid = ra.json()["acceptance_id"]
        admin_session.post(f"{API}/gigs/{gid}/requests/{aid}/approve")
        # second approve should fail
        r2 = admin_session.post(f"{API}/gigs/{gid}/requests/{aid}/approve")
        assert r2.status_code == 400
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_approve_400_when_all_slots_filled(self, admin_session):
        gid = _create_gig(admin_session, slots=1, title_suffix="apprfull2")
        wa, _, _ = _ready_worker(admin_session, "apprA")
        wb, _, _ = _ready_worker(admin_session, "apprB")
        ra = wa.post(f"{API}/gigs/{gid}/accept")
        rb = wb.post(f"{API}/gigs/{gid}/accept")
        aida, aidb = ra.json()["acceptance_id"], rb.json()["acceptance_id"]
        ok = admin_session.post(f"{API}/gigs/{gid}/requests/{aida}/approve")
        assert ok.status_code == 200
        # second approve must fail with 400
        fail = admin_session.post(f"{API}/gigs/{gid}/requests/{aidb}/approve")
        assert fail.status_code == 400
        msg = (fail.json().get("detail") or "").lower()
        assert "slot" in msg or "filled" in msg
        admin_session.delete(f"{API}/gigs/{gid}")


class TestRejectRequest:
    def test_reject_deletes_acceptance(self, admin_session):
        gid = _create_gig(admin_session, slots=2, title_suffix="rejdel")
        ws, _, uid = _ready_worker(admin_session, "rejdel")
        ra = ws.post(f"{API}/gigs/{gid}/accept")
        aid = ra.json()["acceptance_id"]
        r = admin_session.post(f"{API}/gigs/{gid}/requests/{aid}/reject")
        assert r.status_code == 200, r.text
        # worker my_acceptance should be null/missing
        gw = ws.get(f"{API}/gigs/{gid}").json()
        assert not gw.get("my_acceptance")
        # Slot still 0
        ga = admin_session.get(f"{API}/gigs/{gid}").json()
        assert ga["slots_filled"] == 0
        # Notification
        notes = ws.get(f"{API}/notifications").json()
        assert any(n.get("gig_id") == gid for n in notes)
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_reject_404_unknown(self, admin_session):
        gid = _create_gig(admin_session, title_suffix="rej404")
        r = admin_session.post(f"{API}/gigs/{gid}/requests/nope/reject")
        assert r.status_code == 404
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_reject_400_if_already_accepted(self, admin_session):
        gid = _create_gig(admin_session, slots=2, title_suffix="rejacc")
        ws, _, _ = _ready_worker(admin_session, "rejacc")
        ra = ws.post(f"{API}/gigs/{gid}/accept")
        aid = ra.json()["acceptance_id"]
        admin_session.post(f"{API}/gigs/{gid}/requests/{aid}/approve")
        r = admin_session.post(f"{API}/gigs/{gid}/requests/{aid}/reject")
        assert r.status_code == 400
        admin_session.delete(f"{API}/gigs/{gid}")


class TestAdminGigViewSplits:
    def test_admin_sees_pending_and_acceptances(self, admin_session):
        gid = _create_gig(admin_session, slots=3, title_suffix="adminsplit")
        wa, _, _ = _ready_worker(admin_session, "splitA")
        wb, _, _ = _ready_worker(admin_session, "splitB")
        ra = wa.post(f"{API}/gigs/{gid}/accept")
        rb = wb.post(f"{API}/gigs/{gid}/accept")
        # approve wa, leave wb pending
        admin_session.post(f"{API}/gigs/{gid}/requests/{ra.json()['acceptance_id']}/approve")
        g = admin_session.get(f"{API}/gigs/{gid}").json()
        assert "pending_requests" in g
        assert "acceptances" in g
        assert len(g["pending_requests"]) == 1
        assert g["pending_requests"][0]["status"] == "requested"
        assert all(a["status"] != "requested" for a in g["acceptances"])
        # enrichment (backend uses worker_ prefix naming)
        pr = g["pending_requests"][0]
        for k in ("worker_name", "worker_email", "worker_phone", "worker_id_verified", "worker_status"):
            assert k in pr, f"missing key {k} in {list(pr.keys())}"
        admin_session.delete(f"{API}/gigs/{gid}")


class TestAdminStatsPendingRequests:
    def test_pending_requests_counted(self, admin_session):
        before = admin_session.get(f"{API}/admin/stats").json()
        prev = before.get("pending_requests", 0)
        gid = _create_gig(admin_session, slots=2, title_suffix="statsreq")
        ws, _, _ = _ready_worker(admin_session, "statsreq")
        ws.post(f"{API}/gigs/{gid}/accept")
        after = admin_session.get(f"{API}/admin/stats").json()
        assert "pending_requests" in after
        assert after["pending_requests"] >= prev + 1
        admin_session.delete(f"{API}/gigs/{gid}")


class TestWithdraw:
    def test_withdraw_requested_no_slot_change(self, admin_session):
        gid = _create_gig(admin_session, slots=1, title_suffix="wdreq")
        ws, _, _ = _ready_worker(admin_session, "wdreq")
        ws.post(f"{API}/gigs/{gid}/accept")
        # gig still open since no approval
        assert admin_session.get(f"{API}/gigs/{gid}").json()["status"] == "open"
        r = ws.post(f"{API}/gigs/{gid}/withdraw")
        assert r.status_code == 200
        g = admin_session.get(f"{API}/gigs/{gid}").json()
        assert g["slots_filled"] == 0
        assert g["status"] == "open"
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_withdraw_accepted_decrements_and_reopens(self, admin_session):
        gid = _create_gig(admin_session, slots=1, title_suffix="wdacc")
        ws, _, _ = _ready_worker(admin_session, "wdacc")
        ra = ws.post(f"{API}/gigs/{gid}/accept")
        admin_session.post(f"{API}/gigs/{gid}/requests/{ra.json()['acceptance_id']}/approve")
        assert admin_session.get(f"{API}/gigs/{gid}").json()["status"] == "filled"
        r = ws.post(f"{API}/gigs/{gid}/withdraw")
        assert r.status_code == 200
        g = admin_session.get(f"{API}/gigs/{gid}").json()
        assert g["slots_filled"] == 0
        assert g["status"] == "open"
        admin_session.delete(f"{API}/gigs/{gid}")


class TestBannedWorkersCannotRequest:
    def test_rejected_worker_cannot_request(self, admin_session):
        gid = _create_gig(admin_session, title_suffix="banrej")
        ws, email, uid = _ready_worker(admin_session, "banrej")
        admin_session.post(f"{API}/admin/workers/{uid}/reject")
        rl = ws.post(f"{API}/auth/login", json={"email": email, "password": "Worker123!"})
        assert rl.status_code == 200
        r = ws.post(f"{API}/gigs/{gid}/accept")
        assert r.status_code == 403
        admin_session.delete(f"{API}/gigs/{gid}")

    def test_suspended_worker_cannot_request(self, admin_session):
        gid = _create_gig(admin_session, title_suffix="bansus")
        ws, email, uid = _ready_worker(admin_session, "bansus")
        admin_session.post(f"{API}/admin/workers/{uid}/suspend")
        rl = ws.post(f"{API}/auth/login", json={"email": email, "password": "Worker123!"})
        assert rl.status_code == 200
        r = ws.post(f"{API}/gigs/{gid}/accept")
        assert r.status_code == 403
        admin_session.delete(f"{API}/gigs/{gid}")
