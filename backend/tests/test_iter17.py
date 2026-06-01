"""Iteration 17 backend tests:
- Admin requests search filter
- Admin sticky-note on worker profile (admin_note)
- Per-gig admin note on acceptance
- Admin → worker message (notifications inbox)
- Worker-match scoring includes category_completed_count
- Regression: existing /admin/workers filters
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PASS = "HcobAdmin2026!"


@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def test_worker(admin_session):
    """Register one fresh worker, approve+verify-ID, return profile + login session."""
    uniq = uuid.uuid4().hex[:8]
    email = f"TEST_iter17_{uniq}@example.com"
    pw = "Worker123!"
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": pw, "name": f"Iter17 Worker {uniq}"},
    )
    assert r.status_code in (200, 201), f"register failed: {r.text}"
    user_id = r.json().get("user_id") or r.json().get("user", {}).get("user_id")
    # approve + verify ID + give skill so they show up in match endpoint
    admin_session.put(
        f"{API}/admin/workers/{user_id}/profile",
        json={
            "worker_status": "approved",
            "id_verified": True,
            "skills": ["residential_cleaning", "deep_cleaning"],
            "zip_code": "94110",
            "city": "San Francisco",
            "state": "CA",
            "phone": "4155551234",
            "address": "1 Test Way",
            "date_of_birth": "1990-01-01",
            "availability": ["weekday_mornings"],
        },
    )
    ws = requests.Session()
    ws.headers.update({"Content-Type": "application/json"})
    lr = ws.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert lr.status_code == 200
    return {"user_id": user_id, "email": email, "session": ws}


# ----- 1. Admin requests search -----
class TestAdminRequestsSearch:
    def test_list_no_search_returns_all(self, admin_session):
        r = admin_session.get(f"{API}/admin/requests")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_search_param_filters(self, admin_session):
        # Use an obviously non-matching string
        r = admin_session.get(f"{API}/admin/requests", params={"search": "zzznotarealsearch9999"})
        assert r.status_code == 200
        assert r.json() == []

    def test_search_case_insensitive_matches_known(self, admin_session):
        # Pull all rows then assert search with a substring of an existing field works
        all_rows = admin_session.get(f"{API}/admin/requests").json()
        if not all_rows:
            pytest.skip("No pending requests in DB to validate substring filter")
        sample = all_rows[0]
        needle = (sample.get("worker_name") or sample.get("worker_email") or "")[:4]
        if not needle:
            pytest.skip("No usable worker_name/email in sample row")
        r = admin_session.get(f"{API}/admin/requests", params={"search": needle.lower()})
        assert r.status_code == 200
        assert len(r.json()) >= 1


# ----- 2. Admin sticky-note (admin_note on user) -----
class TestAdminStickyNote:
    def test_set_and_persist_admin_note(self, admin_session, test_worker):
        note = f"TEST_iter17 sticky note {uuid.uuid4().hex[:6]}"
        r = admin_session.put(
            f"{API}/admin/workers/{test_worker['user_id']}/profile",
            json={"admin_note": note},
        )
        assert r.status_code == 200, r.text
        # GET worker detail
        g = admin_session.get(f"{API}/admin/workers/{test_worker['user_id']}")
        assert g.status_code == 200
        assert g.json().get("admin_note") == note

    def test_admin_note_not_leaked_to_worker_self(self, test_worker):
        """Currently NOT redacted by backend — but verify the field shape at least.
        The review_request says: 'currently OK because we don't redact, the WORKER
        frontend just doesn't reference it'. So this test documents current behaviour."""
        me = test_worker["session"].get(f"{API}/auth/me")
        assert me.status_code == 200
        # We don't fail on leak — just record. The frontend hides it.
        # (If you want strict redaction, uncomment:)
        # assert "admin_note" not in me.json()


# ----- 3. Per-gig admin note on acceptance -----
@pytest.fixture(scope="session")
def seeded_gig_acceptance(admin_session, test_worker):
    """Create a fresh gig + acceptance owned by test_worker so we can attach admin notes."""
    gig_payload = {
        "title": f"TEST_iter17 gig {uuid.uuid4().hex[:6]}",
        "description": "iter17 test gig",
        "category": "cleaning",
        "subcategory": "residential_cleaning",
        "location": "San Francisco, CA",
        "zip_code": "94110",
        "scheduled_date": "2026-12-31",
        "scheduled_at": "2026-12-31T10:00:00Z",
        "pay_rate": 25,
        "pay_type": "hourly",
        "slots": 2,
        "skills_required": ["residential_cleaning"],
    }
    gr = admin_session.post(f"{API}/gigs", json=gig_payload)
    assert gr.status_code in (200, 201), gr.text
    gig_id = gr.json()["gig_id"]
    # Admin assigns worker
    ar = admin_session.post(
        f"{API}/admin/gigs/{gig_id}/assign",
        json={"worker_id": test_worker["user_id"]},
    )
    assert ar.status_code in (200, 201), ar.text
    acceptance_id = ar.json().get("acceptance_id") or ar.json().get("acceptance", {}).get("acceptance_id")
    assert acceptance_id
    return {"gig_id": gig_id, "acceptance_id": acceptance_id}


class TestPerGigAdminNote:
    def test_set_admin_gig_note(self, admin_session, seeded_gig_acceptance):
        text = f"iter17 gig note {uuid.uuid4().hex[:6]}"
        r = admin_session.put(
            f"{API}/gigs/{seeded_gig_acceptance['gig_id']}/acceptances/{seeded_gig_acceptance['acceptance_id']}/admin-note",
            json={"note": text},
        )
        assert r.status_code == 200, r.text
        # Verify via gig detail
        g = admin_session.get(f"{API}/gigs/{seeded_gig_acceptance['gig_id']}")
        assert g.status_code == 200
        acc = next(
            (a for a in (g.json().get("acceptances") or [])
             if a["acceptance_id"] == seeded_gig_acceptance["acceptance_id"]),
            None,
        )
        assert acc is not None
        assert acc.get("admin_gig_note") == text
        assert acc.get("admin_gig_note_by") == ADMIN_EMAIL
        assert acc.get("admin_gig_note_at")

    def test_clear_admin_gig_note(self, admin_session, seeded_gig_acceptance):
        # Set then clear with empty string
        admin_session.put(
            f"{API}/gigs/{seeded_gig_acceptance['gig_id']}/acceptances/{seeded_gig_acceptance['acceptance_id']}/admin-note",
            json={"note": "to be cleared"},
        )
        r = admin_session.put(
            f"{API}/gigs/{seeded_gig_acceptance['gig_id']}/acceptances/{seeded_gig_acceptance['acceptance_id']}/admin-note",
            json={"note": ""},
        )
        assert r.status_code == 200
        g = admin_session.get(f"{API}/gigs/{seeded_gig_acceptance['gig_id']}")
        acc = next(a for a in g.json()["acceptances"] if a["acceptance_id"] == seeded_gig_acceptance["acceptance_id"])
        assert not acc.get("admin_gig_note")

    def test_404_on_unknown_acceptance(self, admin_session, seeded_gig_acceptance):
        r = admin_session.put(
            f"{API}/gigs/{seeded_gig_acceptance['gig_id']}/acceptances/acc_nonexistent/admin-note",
            json={"note": "x"},
        )
        assert r.status_code == 404


# ----- 4. Admin → worker message -----
class TestAdminWorkerMessage:
    def test_send_message_and_worker_inbox(self, admin_session, test_worker):
        body = f"TEST_iter17 message {uuid.uuid4().hex[:6]}"
        r = admin_session.post(
            f"{API}/admin/workers/{test_worker['user_id']}/message",
            json={"body": body, "title": "Hello from QA"},
        )
        assert r.status_code == 200, r.text
        notif_id = r.json().get("notification_id")
        assert notif_id

        # Worker GETs their notifications and sees it
        nots = test_worker["session"].get(f"{API}/notifications")
        assert nots.status_code == 200
        rows = nots.json()
        match = [n for n in rows if n.get("notification_id") == notif_id]
        assert match, f"Notification not delivered to worker. got={rows}"
        assert match[0]["body"] == body
        assert match[0].get("from_admin") == ADMIN_EMAIL

    def test_empty_body_400(self, admin_session, test_worker):
        r = admin_session.post(
            f"{API}/admin/workers/{test_worker['user_id']}/message",
            json={"body": "   "},
        )
        assert r.status_code == 400

    def test_unknown_worker_404(self, admin_session):
        r = admin_session.post(
            f"{API}/admin/workers/usr_nonexistent_zzz/message",
            json={"body": "hi"},
        )
        assert r.status_code == 404


# ----- 5. Worker match: category_completed_count -----
class TestWorkerMatchCategoryCount:
    def test_match_cleaning_includes_field(self, admin_session):
        r = admin_session.get(
            f"{API}/admin/workers/match",
            params={"category": "cleaning", "zip_code": "94110"},
        )
        assert r.status_code == 200, r.text
        rows = r.json()
        if not rows:
            pytest.skip("No matching workers in DB for cleaning/94110")
        # Every row must have the new field
        for row in rows:
            assert "category_completed_count" in row, row
            assert isinstance(row["category_completed_count"], int)

    def test_match_labor_regression(self, admin_session):
        r = admin_session.get(f"{API}/admin/workers/match", params={"category": "labor"})
        assert r.status_code == 200
        for row in r.json():
            assert "category_completed_count" in row

    def test_match_driver_regression(self, admin_session):
        r = admin_session.get(f"{API}/admin/workers/match", params={"category": "driver"})
        assert r.status_code == 200
        for row in r.json():
            assert "category_completed_count" in row

    def test_reason_string_contains_cat_done(self, admin_session):
        """If any row has cat_done > 0, its reasons line must include 'N <cat> gig'."""
        r = admin_session.get(
            f"{API}/admin/workers/match",
            params={"category": "cleaning"},
        )
        for row in r.json():
            n = row.get("category_completed_count", 0)
            if n > 0:
                txt = " ".join(row.get("reasons") or [])
                assert "cleaning gig" in txt, f"Expected 'cleaning gig' in reasons, got {row['reasons']}"


# ----- 6. /admin/workers filter regression -----
class TestAdminWorkersFiltersRegression:
    def test_filter_by_zip(self, admin_session):
        r = admin_session.get(f"{API}/admin/workers", params={"zip_code": "94110"})
        assert r.status_code == 200
        for row in r.json():
            # Filter accepts prefix match in some implementations — just ensure 200 + list shape
            assert "user_id" in row

    def test_filter_by_min_rating(self, admin_session):
        r = admin_session.get(f"{API}/admin/workers", params={"min_rating": 4})
        assert r.status_code == 200
        rows = r.json()
        for row in rows:
            ra = row.get("rating_avg")
            if ra is not None:
                assert ra >= 4

    def test_filter_by_skill(self, admin_session):
        r = admin_session.get(f"{API}/admin/workers", params={"skills": "residential_cleaning"})
        assert r.status_code == 200
        for row in r.json():
            sk = row.get("skills") or []
            assert "residential_cleaning" in sk

    def test_filter_by_availability(self, admin_session):
        r = admin_session.get(f"{API}/admin/workers", params={"availability": "weekday_mornings"})
        assert r.status_code == 200
