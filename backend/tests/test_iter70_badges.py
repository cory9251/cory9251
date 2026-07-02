"""Iteration 70 — Professional Certified Badges & Testing System tests.

Covers:
- Worker: list badges, get test (no correct_index leak), submit test (pass/fail),
  no retakes, docs upload/delete, submit for review.
- Admin: list applications enriched, approve, reject, reset.
- Admin badge CRUD + AI quiz generation.
- Gig gating (required_badge_id).
- Regression: normal open gigs still requestable.
"""
import io
import os
import struct
import zlib
import time
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://work-connect-147.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PASSWORD = "HcobAdmin2026!"
WORKER_EMAIL = "worker.demo@hcobcleaners.com"
WORKER_PASSWORD = "WorkerDemo2026!"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


def _tiny_png() -> bytes:
    # minimal 1x1 PNG
    sig = b"\x89PNG\r\n\x1a\n"
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff"))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.text}"
    return s


@pytest.fixture(scope="session")
def worker_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": WORKER_EMAIL, "password": WORKER_PASSWORD})
    assert r.status_code == 200, f"worker login failed: {r.text}"
    return s


@pytest.fixture(scope="session")
def db():
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


def _noop(x):
    return x


@pytest.fixture(scope="session")
def worker_id(db):
    u = db.users.find_one({"email": WORKER_EMAIL}, {"_id": 0, "user_id": 1})
    assert u, "worker user not found"
    return u["user_id"]


@pytest.fixture(scope="session")
def cleanup_worker_apps(db, worker_id):
    """Reset test state — remove any pre-existing badge apps and certified_badges for the demo worker."""
    db.badge_applications.delete_many({"user_id": worker_id})
    db.users.update_one({"user_id": worker_id}, {"$set": {"certified_badges": []}})
    yield
    db.badge_applications.delete_many({"user_id": worker_id})
    db.users.update_one({"user_id": worker_id}, {"$set": {"certified_badges": []}})


@pytest.fixture(scope="session")
def seed_badges(db):
    """Return list of seeded badges with full questions (for building answer arrays)."""
    badges = list(db.badges.find({"active": True}, {"_id": 0}))
    assert len(badges) >= 6, f"expected at least 6 seeded badges, got {len(badges)}"
    return badges


# ---------------------------------------------------------------------------
# Worker badge listing & test retrieval
# ---------------------------------------------------------------------------
class TestWorkerBadges:
    def test_list_badges(self, worker_session, cleanup_worker_apps):
        r = worker_session.get(f"{API}/worker/badges")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 6
        for b in data:
            assert b["question_count"] == 8
            assert b["certified"] is False
            assert b["application"] is None
            assert "correct_index" not in str(b)

    def test_get_test_no_leak(self, worker_session, seed_badges):
        bid = seed_badges[0]["badge_id"]
        r = worker_session.get(f"{API}/worker/badges/{bid}/test")
        assert r.status_code == 200
        data = r.json()
        assert len(data["questions"]) == 8
        for q in data["questions"]:
            assert "q" in q and "options" in q
            assert "correct_index" not in q


# ---------------------------------------------------------------------------
# Fail flow (one badge) + no-retake enforcement
# ---------------------------------------------------------------------------
class TestFailFlow:
    def test_fail_and_no_retake(self, worker_session, seed_badges):
        badge = seed_badges[0]
        bid = badge["badge_id"]
        wrong = [(q["correct_index"] + 1) % len(q["options"]) for q in badge["questions"]]
        r = worker_session.post(f"{API}/worker/badges/{bid}/test", json={"answers": wrong})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["passed"] is False
        assert j["status"] == "test_failed"

        # Second attempt blocked
        r2 = worker_session.post(f"{API}/worker/badges/{bid}/test", json={"answers": wrong})
        assert r2.status_code == 400
        assert "already" in r2.text.lower() or "retake" in r2.text.lower()

        # GET test also blocked
        r3 = worker_session.get(f"{API}/worker/badges/{bid}/test")
        assert r3.status_code == 400


# ---------------------------------------------------------------------------
# Pass flow + docs + submit for review
# ---------------------------------------------------------------------------
@pytest.fixture(scope="class")
def passed_badge(worker_session, seed_badges):
    """Take + pass a DIFFERENT badge than the failed one."""
    badge = seed_badges[1]
    bid = badge["badge_id"]
    correct = [q["correct_index"] for q in badge["questions"]]
    r = worker_session.post(f"{API}/worker/badges/{bid}/test", json={"answers": correct})
    assert r.status_code == 200
    j = r.json()
    assert j["passed"] is True
    assert j["status"] == "test_passed"
    assert j["score_pct"] == 100
    return badge


class TestPassAndSubmit:
    def test_submit_without_anything_400(self, worker_session, passed_badge):
        r = worker_session.post(
            f"{API}/worker/badges/{passed_badge['badge_id']}/submit",
            json={"portfolio_links": [], "notes": "test"},
        )
        assert r.status_code == 400

    def test_upload_and_remove_doc(self, worker_session, passed_badge):
        bid = passed_badge["badge_id"]
        files = {"file": ("proof.png", _tiny_png(), "image/png")}
        r = worker_session.post(f"{API}/worker/badges/{bid}/documents", files=files)
        assert r.status_code == 200, r.text
        docs = r.json()["documents"]
        assert len(docs) >= 1
        path = docs[-1]["path"]

        # remove
        r2 = worker_session.delete(f"{API}/worker/badges/{bid}/documents", params={"path": path})
        assert r2.status_code == 200

    def test_submit_with_link(self, worker_session, passed_badge):
        bid = passed_badge["badge_id"]
        r = worker_session.post(
            f"{API}/worker/badges/{bid}/submit",
            json={"portfolio_links": ["https://example.com/work"], "notes": "please review"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending_review"


# ---------------------------------------------------------------------------
# Admin review — approve
# ---------------------------------------------------------------------------
class TestAdminReview:
    def test_list_pending_enriched(self, admin_session, worker_id):
        r = admin_session.get(f"{API}/admin/badge-applications", params={"status": "pending_review"})
        assert r.status_code == 200
        apps = r.json()
        mine = [a for a in apps if a["user_id"] == worker_id]
        assert len(mine) >= 1
        a = mine[0]
        assert a.get("worker_name") == "Worker Demo"
        assert a.get("badge_name")
        assert a.get("score_pct") is not None

    def test_approve(self, admin_session, worker_session, worker_id, db):
        apps = admin_session.get(
            f"{API}/admin/badge-applications", params={"status": "pending_review"}
        ).json()
        mine = [a for a in apps if a["user_id"] == worker_id]
        app_id = mine[0]["application_id"]
        badge_id = mine[0]["badge_id"]
        r = admin_session.post(
            f"{API}/admin/badge-applications/{app_id}/approve",
            json={"note": "looks good"},
        )
        assert r.status_code == 200

        # Verify user has certified_badges + worker view shows certified
        u = db.users.find_one({"user_id": worker_id}, {"_id": 0, "certified_badges": 1})
        assert badge_id in (u.get("certified_badges") or [])

        wb = worker_session.get(f"{API}/worker/badges").json()
        for b in wb:
            if b["badge_id"] == badge_id:
                assert b["certified"] is True

        # Notification created
        n = db.notifications.find_one({"user_id": worker_id, "title": {"$regex": "You're certified"}})
        assert n is not None


# ---------------------------------------------------------------------------
# Admin Badge CRUD + AI quiz + reject/reset
# ---------------------------------------------------------------------------
class TestAdminBadgeCRUD:
    _created_id = None

    def test_create_invalid_correct_index(self, admin_session):
        bad = {
            "name": "TEST_bad_badge",
            "questions": [{"q": "x?", "options": ["a", "b"], "correct_index": 5}],
        }
        r = admin_session.post(f"{API}/admin/badges", json=bad)
        assert r.status_code == 400

    def test_create_ok(self, admin_session):
        payload = {
            "name": "TEST_HVAC Basics",
            "color": "#333333",
            "pass_pct": 75,
            "questions": [
                {"q": "Q1?", "options": ["a", "b", "c", "d"], "correct_index": 1},
                {"q": "Q2?", "options": ["a", "b", "c", "d"], "correct_index": 0},
            ],
        }
        r = admin_session.post(f"{API}/admin/badges", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["name"] == "TEST_HVAC Basics"
        assert data["pass_pct"] == 75
        TestAdminBadgeCRUD._created_id = data["badge_id"]

    def test_update_inactive_hidden_from_worker(self, admin_session, worker_session):
        bid = TestAdminBadgeCRUD._created_id
        assert bid
        r = admin_session.put(f"{API}/admin/badges/{bid}", json={"active": False})
        assert r.status_code == 200
        wb = worker_session.get(f"{API}/worker/badges").json()
        assert not any(b["badge_id"] == bid for b in wb)

    def test_delete_badge(self, admin_session):
        bid = TestAdminBadgeCRUD._created_id
        r = admin_session.delete(f"{API}/admin/badges/{bid}")
        assert r.status_code == 200

    def test_ai_quiz_generation(self, admin_session):
        r = admin_session.post(
            f"{API}/admin/badges/generate-quiz",
            json={"topic": "HVAC repair basics", "num_questions": 4},
            timeout=90,
        )
        assert r.status_code == 200, r.text
        qs = r.json()["questions"]
        assert len(qs) == 4
        for q in qs:
            assert 0 <= q["correct_index"] < len(q["options"])
            assert len(q["options"]) == 4


# ---------------------------------------------------------------------------
# Gig gating
# ---------------------------------------------------------------------------
@pytest.fixture(scope="class")
def agreement_rules(worker_session):
    r = worker_session.get(f"{API}/worker/agreement-rules")
    assert r.status_code == 200
    return r.json()


class TestGigGating:
    _gig_id_gated = None
    _gig_id_open = None
    _gate_badge_id = None

    def test_admin_create_gated_gig(self, admin_session, seed_badges, worker_id, db):
        # Pick a badge the worker does NOT have (index 2 - plumber, worker was approved for index 1)
        u = db.users.find_one({"user_id": worker_id}, {"certified_badges": 1})
        held = set(u.get("certified_badges") or [])
        gate = next(b for b in seed_badges if b["badge_id"] not in held)
        TestGigGating._gate_badge_id = gate["badge_id"]

        payload = {
            "title": "TEST_gated_gig",
            "description": "gated test",
            "category": "cleaning",
            "location": "Anytown",
            "scheduled_date": "2030-01-01",
            "pay_rate": 100,
            "pay_type": "flat",
            "slots": 1,
            "duration_hours": 2,
            "required_badge_id": gate["badge_id"],
            "status": "open",
        }
        r = admin_session.post(f"{API}/gigs", json=payload)
        assert r.status_code in (200, 201), r.text
        TestGigGating._gig_id_gated = r.json()["gig_id"]

    def test_worker_gig_list_shows_required_badge(self, worker_session):
        r = worker_session.get(f"{API}/gigs")
        assert r.status_code == 200
        gigs = r.json()
        # gigs may be paginated dict or list
        items = gigs if isinstance(gigs, list) else gigs.get("items") or gigs.get("gigs") or []
        found = next((g for g in items if g.get("gig_id") == TestGigGating._gig_id_gated), None)
        assert found, "gated gig not found in worker feed"
        assert found.get("required_badge")
        assert found["required_badge"].get("name")
        assert found.get("has_required_badge") is False

    def test_worker_accept_blocked_403(self, worker_session, agreement_rules):
        body = {
            "typed_name": "Worker Demo",
            "agreed_rules": agreement_rules["rules"],
            "version": agreement_rules["version"],
        }
        r = worker_session.post(
            f"{API}/gigs/{TestGigGating._gig_id_gated}/accept", json=body
        )
        assert r.status_code == 403
        assert "certification" in r.text.lower()

    def test_certify_and_accept_succeeds(self, admin_session, worker_session, worker_id, db, agreement_rules):
        # Directly certify via admin - shortcut using approve on a synthetic app or DB update
        db.users.update_one(
            {"user_id": worker_id},
            {"$addToSet": {"certified_badges": TestGigGating._gate_badge_id}},
        )
        body = {
            "typed_name": "Worker Demo",
            "agreed_rules": agreement_rules["rules"],
            "version": agreement_rules["version"],
        }
        r = worker_session.post(
            f"{API}/gigs/{TestGigGating._gig_id_gated}/accept", json=body
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "requested"

    def test_gig_detail_attaches_required_badge(self, admin_session):
        r = admin_session.get(f"{API}/gigs/{TestGigGating._gig_id_gated}")
        assert r.status_code == 200
        assert r.json().get("required_badge_id")

    # Regression: plain open gig without required_badge_id still works
    def test_regression_open_gig(self, admin_session, worker_session, db, agreement_rules):
        payload = {
            "title": "TEST_open_regression_gig",
            "description": "open",
            "category": "cleaning",
            "location": "Anytown",
            "scheduled_date": "2030-01-02",
            "pay_rate": 100,
            "pay_type": "flat",
            "slots": 1,
            "duration_hours": 2,
            "status": "open",
        }
        r = admin_session.post(f"{API}/gigs", json=payload)
        assert r.status_code in (200, 201)
        gid = r.json()["gig_id"]
        TestGigGating._gig_id_open = gid
        body = {
            "typed_name": "Worker Demo",
            "agreed_rules": agreement_rules["rules"],
            "version": agreement_rules["version"],
        }
        r2 = worker_session.post(f"{API}/gigs/{gid}/accept", json=body)
        assert r2.status_code == 200, r2.text
        assert r2.json()["status"] == "requested"

    def test_cleanup_gigs(self, admin_session, db):
        for gid in [TestGigGating._gig_id_gated, TestGigGating._gig_id_open]:
            if gid:
                admin_session.delete(f"{API}/gigs/{gid}")


# ---------------------------------------------------------------------------
# Reject + Reset paths (use fresh app on different badge)
# ---------------------------------------------------------------------------
class TestRejectAndReset:
    def test_reject_flow(self, worker_session, admin_session, seed_badges, db, worker_id):
        # find a badge with no application yet
        apps = list(db.badge_applications.find({"user_id": worker_id}))
        used = {a["badge_id"] for a in apps}
        badge = next(b for b in seed_badges if b["badge_id"] not in used)
        bid = badge["badge_id"]
        correct = [q["correct_index"] for q in badge["questions"]]
        r = worker_session.post(f"{API}/worker/badges/{bid}/test", json={"answers": correct})
        assert r.status_code == 200
        r = worker_session.post(
            f"{API}/worker/badges/{bid}/submit",
            json={"portfolio_links": ["https://example.com/x"]},
        )
        assert r.status_code == 200
        # find app
        app = db.badge_applications.find_one({"user_id": worker_id, "badge_id": bid})
        app_id = app["application_id"]
        rr = admin_session.post(
            f"{API}/admin/badge-applications/{app_id}/reject",
            json={"note": "not enough proof"},
        )
        assert rr.status_code == 200
        app2 = db.badge_applications.find_one({"application_id": app_id})
        assert app2["status"] == "rejected"
        assert app2["admin_note"] == "not enough proof"

    def test_reset_flow(self, admin_session, db, worker_id):
        # find any existing app to reset
        app = db.badge_applications.find_one({"user_id": worker_id})
        assert app, "expected at least one application from prior tests"
        app_id = app["application_id"]
        r = admin_session.post(f"{API}/admin/badge-applications/{app_id}/reset")
        assert r.status_code == 200
        gone = db.badge_applications.find_one({"application_id": app_id})
        assert gone is None
