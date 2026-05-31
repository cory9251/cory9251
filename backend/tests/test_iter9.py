"""ITER-9 tests: GET /api/admin/requests — global pending-requests queue.

Spec:
- Returns ALL acceptances with status='requested', sorted by requested_at ASC.
- Each row enriched with gig + worker fields.
- 401 unauth, 403 worker.
- After approve/reject the row disappears.
- /admin/stats.pending_requests count == len(/admin/requests).
- Empty -> [].
- Regression: per-gig pending_requests array on GET /gigs/{id} still works.
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


# ---------------- helpers (mirror test_iter8.py) ----------------
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


def _register_worker(prefix="iter9"):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"TEST_{prefix}_{uuid.uuid4().hex[:8]}@ex.com"
    r = s.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": "Worker123!",
            "name": f"Iter9 {prefix}",
            "phone": "+15550009999",
            "role": "worker",
        },
    )
    assert r.status_code == 200, r.text
    me = s.get(f"{API}/auth/me").json()
    return s, email, me["user_id"]


def _upload_id(ws):
    old_ct = ws.headers.pop("Content-Type", None)
    files = {"file": ("id.png", b"\x89PNG\r\n\x1a\nfake", "image/png")}
    r = ws.post(f"{API}/profile/id", files=files)
    if old_ct:
        ws.headers["Content-Type"] = old_ct
    assert r.status_code == 200, r.text


def _verify_id(admin_sess, uid):
    r = admin_sess.post(f"{API}/admin/workers/{uid}/verify-id")
    assert r.status_code == 200


def _ready_worker(admin_sess, prefix="iter9"):
    ws, email, uid = _register_worker(prefix)
    _upload_id(ws)
    _verify_id(admin_sess, uid)
    return ws, email, uid


def _create_gig(admin_sess, slots=2, title_suffix=""):
    payload = {
        "title": f"TEST_iter9_{title_suffix or uuid.uuid4().hex[:6]}",
        "description": "iter9 gig",
        "category": "cleaning",
        "subcategory": "deep-clean",
        "location": "Mission St, 94110",
        "address_line": "9999 Iter9 Ave",
        "scheduled_date": "2026-12-15",
        "pay_rate": 30,
        "pay_type": "hourly",
        "slots": slots,
    }
    r = admin_sess.post(f"{API}/gigs", json=payload)
    assert r.status_code == 200, r.text
    return r.json()["gig_id"]


def _stats_pending(admin_sess):
    r = admin_sess.get(f"{API}/admin/stats")
    assert r.status_code == 200, r.text
    return r.json().get("pending_requests", 0)


# ---------------- Tests ----------------
class TestAuthorization:
    def test_unauthenticated_returns_401(self):
        # fresh session, no cookie
        r = requests.get(f"{API}/admin/requests")
        assert r.status_code == 401, r.text

    def test_worker_caller_returns_403(self, admin_session):
        ws, _, _ = _register_worker("authz403")
        r = ws.get(f"{API}/admin/requests")
        assert r.status_code == 403, r.text


class TestEnrichmentAndOrdering:
    def test_pending_request_shows_up_enriched(self, admin_session):
        gid = _create_gig(admin_session, slots=2, title_suffix="enrich")
        ws, email, uid = _ready_worker(admin_session, "enrich")
        ra = ws.post(f"{API}/gigs/{gid}/accept")
        assert ra.status_code == 200, ra.text
        aid = ra.json()["acceptance_id"]

        r = admin_session.get(f"{API}/admin/requests")
        assert r.status_code == 200, r.text
        rows = r.json()
        assert isinstance(rows, list)
        match = [row for row in rows if row.get("acceptance_id") == aid]
        assert len(match) == 1, f"expected our aid in queue, got rows={rows}"
        row = match[0]
        # status + ids
        assert row.get("status") == "requested"
        assert row.get("gig_id") == gid
        assert row.get("worker_id") == uid
        # worker enrichment
        assert row.get("worker_email", "").lower() == email.lower()
        assert row.get("worker_name")
        assert "worker_phone" in row  # enriched key present (may be empty string if register didn't persist)
        assert row.get("worker_id_verified") is True
        assert row.get("worker_status") == "approved"
        # gig enrichment
        g = row.get("gig") or {}
        assert g.get("title", "").startswith("TEST_iter9_")
        assert g.get("category") == "cleaning"
        assert g.get("subcategory") == "deep-clean"
        assert g.get("location")
        assert g.get("scheduled_date") == "2026-12-15"
        assert g.get("pay_rate") == 30
        assert g.get("pay_type") == "hourly"
        assert g.get("slots") == 2
        assert g.get("slots_filled") == 0
        assert g.get("status") == "open"
        # no mongo _id leaking
        assert "_id" not in row
        assert "_id" not in g

        admin_session.delete(f"{API}/gigs/{gid}")

    def test_sorted_oldest_first(self, admin_session):
        gid_a = _create_gig(admin_session, slots=3, title_suffix="ordA")
        gid_b = _create_gig(admin_session, slots=3, title_suffix="ordB")
        ws1, _, _ = _ready_worker(admin_session, "ord1")
        r1 = ws1.post(f"{API}/gigs/{gid_a}/accept")
        aid1 = r1.json()["acceptance_id"]
        time.sleep(1.2)  # ensure requested_at differs
        ws2, _, _ = _ready_worker(admin_session, "ord2")
        r2 = ws2.post(f"{API}/gigs/{gid_b}/accept")
        aid2 = r2.json()["acceptance_id"]

        rows = admin_session.get(f"{API}/admin/requests").json()
        idx1 = next((i for i, r in enumerate(rows) if r["acceptance_id"] == aid1), -1)
        idx2 = next((i for i, r in enumerate(rows) if r["acceptance_id"] == aid2), -1)
        assert idx1 != -1 and idx2 != -1
        assert idx1 < idx2, f"expected aid1 (older) before aid2; got {idx1} vs {idx2}"

        admin_session.delete(f"{API}/gigs/{gid_a}")
        admin_session.delete(f"{API}/gigs/{gid_b}")


class TestRemovedAfterAction:
    def test_approve_removes_from_queue_and_stats(self, admin_session):
        gid = _create_gig(admin_session, slots=2, title_suffix="apprrm")
        ws, _, _ = _ready_worker(admin_session, "apprrm")
        ra = ws.post(f"{API}/gigs/{gid}/accept")
        aid = ra.json()["acceptance_id"]
        before_count = _stats_pending(admin_session)
        before_rows = admin_session.get(f"{API}/admin/requests").json()
        assert any(r["acceptance_id"] == aid for r in before_rows)
        assert before_count == len(before_rows)

        ap = admin_session.post(f"{API}/gigs/{gid}/requests/{aid}/approve")
        assert ap.status_code == 200, ap.text

        after_rows = admin_session.get(f"{API}/admin/requests").json()
        assert not any(r["acceptance_id"] == aid for r in after_rows)
        after_count = _stats_pending(admin_session)
        assert after_count == len(after_rows)
        assert after_count == before_count - 1

        admin_session.delete(f"{API}/gigs/{gid}")

    def test_reject_removes_from_queue_and_stats(self, admin_session):
        gid = _create_gig(admin_session, slots=2, title_suffix="rejrm")
        ws, _, _ = _ready_worker(admin_session, "rejrm")
        ra = ws.post(f"{API}/gigs/{gid}/accept")
        aid = ra.json()["acceptance_id"]
        before_rows = admin_session.get(f"{API}/admin/requests").json()
        assert any(r["acceptance_id"] == aid for r in before_rows)
        before_count = _stats_pending(admin_session)

        rj = admin_session.post(f"{API}/gigs/{gid}/requests/{aid}/reject")
        assert rj.status_code == 200, rj.text

        after_rows = admin_session.get(f"{API}/admin/requests").json()
        assert not any(r["acceptance_id"] == aid for r in after_rows)
        after_count = _stats_pending(admin_session)
        assert after_count == len(after_rows)
        assert after_count == before_count - 1

        admin_session.delete(f"{API}/gigs/{gid}")


class TestStatsParity:
    def test_count_matches_queue_length(self, admin_session):
        rows = admin_session.get(f"{API}/admin/requests").json()
        count = _stats_pending(admin_session)
        assert count == len(rows)


class TestRegressionPerGigPending:
    def test_per_gig_pending_requests_still_populated(self, admin_session):
        gid = _create_gig(admin_session, slots=2, title_suffix="regrgg")
        ws, _, _ = _ready_worker(admin_session, "regrgg")
        ra = ws.post(f"{API}/gigs/{gid}/accept")
        aid = ra.json()["acceptance_id"]
        g = admin_session.get(f"{API}/gigs/{gid}").json()
        # iter-8 splits pending_requests vs acceptances
        pending = g.get("pending_requests") or []
        assert any(p.get("acceptance_id") == aid for p in pending)
        # And global queue also includes it
        rows = admin_session.get(f"{API}/admin/requests").json()
        assert any(r["acceptance_id"] == aid for r in rows)

        admin_session.delete(f"{API}/gigs/{gid}")
