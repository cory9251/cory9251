"""Iteration 21 backend tests — Gig Pin Tags (rush, priority_need, same_day, top_pay)

Covers:
- PUT /api/gigs/{id}/tags  (admin sets/clears tags; replaces array)
- PUT /api/gigs/{id}/rush  (back-compat — adds/removes 'rush' to existing tags)
- POST /api/gigs/{id}/blast (idempotent rush-tag merge)
- GET /api/public/gigs  (exposes tags, hides PII, sorts pinned first)
- GET /api/gigs (admin feed) and GET /api/gigs/{id} return `tags`
- 403 for read-only admin and worker on /tags endpoint
- Invalid tag values rejected (422)
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


@pytest.fixture(scope="session")
def ro_admin_session(admin_session):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": RO_ADMIN_EMAIL, "password": RO_ADMIN_PASS})
    if r.status_code == 200:
        return s
    admin_session.post(
        f"{API}/admin/admins",
        json={
            "name": "Read Only Admin",
            "email": RO_ADMIN_EMAIL,
            "password": RO_ADMIN_PASS,
            "is_read_only": True,
        },
    )
    s2 = requests.Session()
    s2.headers.update({"Content-Type": "application/json"})
    lr = s2.post(f"{API}/auth/login", json={"email": RO_ADMIN_EMAIL, "password": RO_ADMIN_PASS})
    assert lr.status_code == 200, lr.text
    return s2


@pytest.fixture(scope="session")
def worker_session(admin_session):
    uniq = uuid.uuid4().hex[:8]
    email = f"TEST_iter21_W_{uniq}@example.com"
    pw = "Worker123!"
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": pw, "name": f"Iter21 W {uniq}"},
    )
    assert r.status_code in (200, 201), r.text
    body = r.json()
    uid = body.get("user_id") or body.get("user", {}).get("user_id")
    # approve so they can hit gigs feed
    admin_session.put(
        f"{API}/admin/workers/{uid}/profile",
        json={
            "worker_status": "approved",
            "id_verified": True,
            "skills": ["residential_cleaning"],
            "zip_code": "94110",
            "city": "SF",
            "state": "CA",
            "phone": "4155559999",
            "address": "9 Way",
            "date_of_birth": "1990-01-01",
            "availability": ["weekday_mornings"],
        },
    )
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    return s


# ---------- Helpers ----------
def _create_gig(admin_session, *, pay_rate=25.0, title_suffix=""):
    body = {
        "title": f"TEST_iter21_gig_{uuid.uuid4().hex[:6]}{title_suffix}",
        "description": "iter21 tag test gig",
        "category": "cleaning",
        "subcategory": "residential_cleaning",
        "location": "San Francisco, CA",
        "address_line": "123 Pretend St",  # PII — must be stripped on /public
        "zip_code": "94110",
        "scheduled_date": "2026-12-31",
        "scheduled_at": "2026-12-31T10:00:00Z",
        "pay_rate": pay_rate,
        "pay_type": "hourly",
        "slots": 2,
        "duration_hours": 4,
        "contact_phone": "4155551234",
        "status": "open",
    }
    r = admin_session.post(f"{API}/gigs", json=body)
    assert r.status_code in (200, 201), r.text
    data = r.json()
    # response is the created gig or {gigs:[...]} for recurrence; handle both
    if isinstance(data, dict) and data.get("gigs"):
        return data["gigs"][0]
    return data


@pytest.fixture(scope="session")
def gig_for_tags(admin_session):
    return _create_gig(admin_session, pay_rate=25, title_suffix="_tagtest")


@pytest.fixture(scope="session")
def gig_for_rush_endpoint(admin_session):
    return _create_gig(admin_session, pay_rate=20, title_suffix="_rushep")


@pytest.fixture(scope="session")
def gig_for_blast(admin_session):
    return _create_gig(admin_session, pay_rate=30, title_suffix="_blast")


# ---------- Tests: PUT /tags ----------
class TestSetTags:
    def test_set_single_tag(self, admin_session, gig_for_tags):
        gid = gig_for_tags["gig_id"]
        r = admin_session.put(f"{API}/gigs/{gid}/tags", json={"tags": ["priority_need"]})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert data["tags"] == ["priority_need"]
        assert data["is_rush"] is True
        # Verify persistence
        g = admin_session.get(f"{API}/gigs/{gid}").json()
        assert g["tags"] == ["priority_need"]
        assert g["is_rush"] is True
        assert g.get("rush_at") is not None

    def test_set_multiple_tags(self, admin_session, gig_for_tags):
        gid = gig_for_tags["gig_id"]
        r = admin_session.put(
            f"{API}/gigs/{gid}/tags",
            json={"tags": ["rush", "same_day", "top_pay"]},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert set(data["tags"]) == {"rush", "same_day", "top_pay"}
        assert data["is_rush"] is True
        g = admin_session.get(f"{API}/gigs/{gid}").json()
        assert set(g["tags"]) == {"rush", "same_day", "top_pay"}

    def test_dedup_tags(self, admin_session, gig_for_tags):
        gid = gig_for_tags["gig_id"]
        r = admin_session.put(
            f"{API}/gigs/{gid}/tags", json={"tags": ["rush", "rush", "same_day"]}
        )
        assert r.status_code == 200
        assert r.json()["tags"] == ["rush", "same_day"]

    def test_clear_tags(self, admin_session, gig_for_tags):
        gid = gig_for_tags["gig_id"]
        r = admin_session.put(f"{API}/gigs/{gid}/tags", json={"tags": []})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["tags"] == []
        assert data["is_rush"] is False
        g = admin_session.get(f"{API}/gigs/{gid}").json()
        assert g["tags"] == []
        assert g["is_rush"] is False
        assert g.get("rush_at") in (None, "")

    def test_invalid_tag_rejected(self, admin_session, gig_for_tags):
        gid = gig_for_tags["gig_id"]
        r = admin_session.put(
            f"{API}/gigs/{gid}/tags", json={"tags": ["not_a_real_tag"]}
        )
        # Pydantic Literal → 422 expected
        assert r.status_code == 422, r.text

    def test_set_tags_404(self, admin_session):
        r = admin_session.put(
            f"{API}/gigs/gig_nonexistent12345/tags", json={"tags": ["rush"]}
        )
        assert r.status_code == 404


# ---------- Tests: PUT /rush back-compat ----------
class TestRushEndpointKeepsOtherTags:
    def test_rush_endpoint_adds_rush_keeps_other_tags(
        self, admin_session, gig_for_rush_endpoint
    ):
        gid = gig_for_rush_endpoint["gig_id"]
        # Seed with priority_need + top_pay
        admin_session.put(
            f"{API}/gigs/{gid}/tags", json={"tags": ["priority_need", "top_pay"]}
        )
        # Now flip rush ON via /rush
        r = admin_session.put(f"{API}/gigs/{gid}/rush", json={"is_rush": True})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "rush" in data["tags"]
        assert "priority_need" in data["tags"]
        assert "top_pay" in data["tags"]
        assert data["is_rush"] is True

    def test_rush_off_keeps_other_tags_pinned(
        self, admin_session, gig_for_rush_endpoint
    ):
        gid = gig_for_rush_endpoint["gig_id"]
        # Should still have priority_need + top_pay + rush from prev test
        r = admin_session.put(f"{API}/gigs/{gid}/rush", json={"is_rush": False})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "rush" not in data["tags"]
        assert "priority_need" in data["tags"] and "top_pay" in data["tags"]
        # Still pinned because other tags remain
        assert data["is_rush"] is True

    def test_rush_off_with_no_other_tags_unpins(self, admin_session):
        gig = _create_gig(admin_session, title_suffix="_rushonly")
        gid = gig["gig_id"]
        admin_session.put(f"{API}/gigs/{gid}/tags", json={"tags": ["rush"]})
        r = admin_session.put(f"{API}/gigs/{gid}/rush", json={"is_rush": False})
        assert r.status_code == 200
        data = r.json()
        assert data["tags"] == []
        assert data["is_rush"] is False


# ---------- Tests: blast idempotency ----------
class TestBlastTagMerge:
    def test_blast_adds_rush_tag(self, admin_session, gig_for_blast):
        gid = gig_for_blast["gig_id"]
        # Pre-seed with same_day to verify merge
        admin_session.put(f"{API}/gigs/{gid}/tags", json={"tags": ["same_day"]})
        r = admin_session.post(f"{API}/gigs/{gid}/blast", json={"channels": ["email"]})
        assert r.status_code == 200, r.text
        g = admin_session.get(f"{API}/gigs/{gid}").json()
        assert "rush" in g["tags"]
        assert "same_day" in g["tags"]
        assert g["is_rush"] is True

    def test_blast_idempotent_no_duplicate_rush(self, admin_session, gig_for_blast):
        gid = gig_for_blast["gig_id"]
        admin_session.post(f"{API}/gigs/{gid}/blast", json={"channels": ["email"]})
        admin_session.post(f"{API}/gigs/{gid}/blast", json={"channels": ["email"]})
        g = admin_session.get(f"{API}/gigs/{gid}").json()
        assert g["tags"].count("rush") == 1


# ---------- Tests: GET /public/gigs ----------
class TestPublicFeed:
    def test_public_feed_exposes_tags_and_hides_pii(self, admin_session):
        gig = _create_gig(admin_session, pay_rate=99, title_suffix="_pub")
        gid = gig["gig_id"]
        admin_session.put(
            f"{API}/gigs/{gid}/tags", json={"tags": ["rush", "top_pay"]}
        )
        r = requests.get(f"{API}/public/gigs?limit=24")
        assert r.status_code == 200, r.text
        rows = r.json()
        match = next((x for x in rows if x["gig_id"] == gid), None)
        assert match is not None, "Created public gig not in feed"
        assert "tags" in match
        assert set(match["tags"]) == {"rush", "top_pay"}
        # PII must be stripped
        assert "address_line" not in match
        assert "contact_phone" not in match

    def test_public_feed_sort_pinned_first(self, admin_session):
        # Create a high-pay untagged gig and a low-pay tagged gig
        low_tagged = _create_gig(admin_session, pay_rate=15, title_suffix="_sortlow")
        high_untagged = _create_gig(admin_session, pay_rate=80, title_suffix="_sorthi")
        admin_session.put(
            f"{API}/gigs/{low_tagged['gig_id']}/tags",
            json={"tags": ["priority_need"]},
        )
        admin_session.put(
            f"{API}/gigs/{high_untagged['gig_id']}/tags", json={"tags": []}
        )
        r = requests.get(f"{API}/public/gigs?limit=24")
        assert r.status_code == 200
        rows = r.json()
        idx_low = next(
            (i for i, x in enumerate(rows) if x["gig_id"] == low_tagged["gig_id"]),
            None,
        )
        idx_high = next(
            (
                i
                for i, x in enumerate(rows)
                if x["gig_id"] == high_untagged["gig_id"]
            ),
            None,
        )
        assert idx_low is not None and idx_high is not None
        # tagged must come before untagged regardless of pay
        assert idx_low < idx_high, (
            f"tagged gig (idx {idx_low}) should sort before untagged (idx {idx_high})"
        )


# ---------- Tests: GET /gigs admin feed + GET /gigs/{id} return tags ----------
class TestGigFeedsReturnTags:
    def test_admin_gigs_list_has_tags(self, admin_session, gig_for_blast):
        r = admin_session.get(f"{API}/gigs")
        assert r.status_code == 200
        gigs = r.json()
        match = next(
            (g for g in gigs if g["gig_id"] == gig_for_blast["gig_id"]), None
        )
        assert match is not None
        assert "tags" in match
        assert isinstance(match["tags"], list)

    def test_admin_gig_detail_has_tags(self, admin_session, gig_for_blast):
        gid = gig_for_blast["gig_id"]
        r = admin_session.get(f"{API}/gigs/{gid}")
        assert r.status_code == 200
        assert "tags" in r.json()

    def test_worker_gigs_list_has_tags(self, worker_session):
        r = worker_session.get(f"{API}/gigs")
        assert r.status_code == 200
        gigs = r.json()
        assert all("tags" in g for g in gigs) or len(gigs) == 0


# ---------- Tests: Authorization ----------
class TestAuthorization:
    def test_worker_cannot_set_tags(self, worker_session, gig_for_blast):
        gid = gig_for_blast["gig_id"]
        r = worker_session.put(f"{API}/gigs/{gid}/tags", json={"tags": ["rush"]})
        assert r.status_code in (401, 403), r.text

    def test_ro_admin_cannot_set_tags(self, ro_admin_session, gig_for_blast):
        gid = gig_for_blast["gig_id"]
        r = ro_admin_session.put(f"{API}/gigs/{gid}/tags", json={"tags": ["rush"]})
        assert r.status_code == 403, r.text
        assert "read-only" in r.text.lower() or "Read-only" in r.text

    def test_anon_cannot_set_tags(self, gig_for_blast):
        gid = gig_for_blast["gig_id"]
        r = requests.put(f"{API}/gigs/{gid}/tags", json={"tags": ["rush"]})
        assert r.status_code in (401, 403)
