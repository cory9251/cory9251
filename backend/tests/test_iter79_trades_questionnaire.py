"""Iter 79 — FRD Addendum A: Signup Questionnaire Redesign, Worker Classes,
Equipment Verification & Skill Reclassification.

Covers: questionnaire save+sync, trade claim lifecycle (incl. returned+edit),
licensed trades gating, admin trade manager CRUD, filters, metrics,
doc-only badges (Forklift/CDL) end-to-end.
"""
import io
import os
import uuid
import time
import pytest
import requests

BASE_URL = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=", 1)[1].splitlines()[0]
).rstrip("/")
ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PW = "HcobAdmin2026!"
WORKER_DEMO_EMAIL = "worker.demo@hcobcleaners.com"
WORKER_DEMO_PW = "WorkerDemo2026!"


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return s


def _hdr(tok):
    # kept for compat but returns empty dict; sessions carry cookies
    return {}


def _tiny_jpg():
    # Minimal valid JPEG bytes (2x2 gray)
    return bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707"
        "07090908 0a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c"
        "1c2837292c30313434341f27393d38323c2e333432ffdb0043010909090c0b0c180d"
        "0d1832211c213232323232323232323232323232323232323232323232323232323232"
        "3232323232323232323232323232323232323232323232ffc00011080002000203012"
        "200021101031101ffc4001f0000010501010101010100000000000000000102030405"
        "060708090a0bffc400b5100002010303020403050504040000017d0102030004115"
        "12131410613516107227114328191a1082342b1c11552d1f02433627282090a161718"
        "191a25262728292a3435363738393a434445464748494a535455565758595a6364656"
        "6676869 6a737475767778797a838485868788898a92939495969798999aa2a3a4a5a"
        "6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3"
        "e4e5e6 e7e8e9eaf1f2f3f4f5f6f7f8f9faffc4001f010003010101010101010101010"
        "0000000000001020304050607 08090a0bffc400b511000201020404030407050404000"
        "1027700010203110405213106124151076171132232 8108144291a1b1c109233352f"
        "0156272d10a162434e125f11718191a262728292a35363738393a434445464748494a"
        "535455565758595a636465666768696a737475767778797a82838485868788898a92"
        "93949596 9798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9"
        "cad2d3d4d5d6d7d8d9dae2e3e4e5e6e7e8e9eaf2f3f4f5f6 f7f8f9faffda000c03010"
        "002110311003f00fbfcfffd9".replace(" ", "")
    )


def _png():
    # 1x1 PNG
    import base64
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNgYAAAAAMAA"
        "SsJTYQAAAAASUVORK5CYII="
    )


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PW)


@pytest.fixture(scope="module")
def demo_worker_token():
    return _login(WORKER_DEMO_EMAIL, WORKER_DEMO_PW)


def _create_fresh_worker():
    """Register a new worker via public /api/auth/register."""
    email = f"e2e79.{uuid.uuid4().hex[:8]}@example.com"
    pw = "Test1234!"
    payload = {
        "email": email, "password": pw, "role": "worker",
        "name": f"E2E79 {uuid.uuid4().hex[:4]}",
        "phone": f"555{uuid.uuid4().int % 10000000:07d}",
        "zip_code": "21201",
    }
    r = requests.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=15)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    tok = _login(email, pw)
    me = tok.get(f"{BASE_URL}/api/auth/me").json()
    return tok, me, email


# ---------------- Questionnaire save + skills sync ----------------
class TestQuestionnaire:
    def test_save_questionnaire_and_skills_sync(self):
        tok, me, email = _create_fresh_worker()
        r = tok.put(
            f"{BASE_URL}/api/profile/questionnaire",
            json={
                "work_classes": ["general_labor"],
                "general_skills": ["deep_cleaning", "moving"],
                "general_experience": "1_3_yr",
                "work_attributes": ["bilingual"],
                "bilingual_languages": "Spanish",
            },
            timeout=15,
        )
        assert r.status_code == 200, r.text
        u = r.json()
        assert "general_labor" in (u.get("work_classes") or [])
        assert set(u.get("general_skills") or []) >= {"deep_cleaning", "moving"}
        # attributes must NOT leak into skills
        skills = u.get("skills") or []
        assert "bilingual" not in skills, f"attribute leaked into skills: {skills}"

    def test_driving_requires_vehicle(self):
        tok, me, email = _create_fresh_worker()
        r = tok.put(
            f"{BASE_URL}/api/profile/questionnaire",
            json={"general_skills": ["driving"]},
            timeout=15,
        )
        assert r.status_code == 400, f"expected 400 without vehicle, got {r.status_code}: {r.text}"

    def test_driving_ok_with_car(self):
        tok, me, email = _create_fresh_worker()
        # Toggle car via profile update
        r = tok.put(f"{BASE_URL}/api/profile", json={"has_car": True})
        assert r.status_code == 200, r.text
        r = tok.put(
            f"{BASE_URL}/api/profile/questionnaire",
            json={"general_skills": ["driving"]},
        )
        assert r.status_code == 200, r.text


# ---------------- Trade claim lifecycle ----------------
class TestTradeClaimLifecycle:
    def test_carpet_cleaning_full_lifecycle(self, admin_token):
        tok, me, email = _create_fresh_worker()
        uid = me["user_id"]

        # 1) start claim (empty)
        r = tok.put(f"{BASE_URL}/api/profile/trades/carpet_cleaning", json={})
        assert r.status_code == 200, r.text

        # 2) submit blocked — no checklist / no photo
        r = tok.post(f"{BASE_URL}/api/profile/trades/carpet_cleaning/submit")
        assert r.status_code == 400
        assert "photo" in r.text.lower() or "checklist" in r.text.lower()

        # 3) fill checklist + details + experience
        r = tok.put(
            f"{BASE_URL}/api/profile/trades/carpet_cleaning",
            json={
                "checklist": {"machine": True, "wand_hoses": True},
                "detail_fields": {"machine": "portable Rug Doctor MP-C2D"},
                "experience": "1_3_yr",
            },
        )
        assert r.status_code == 200, r.text

        # 4) still blocked — no photo yet
        r = tok.post(f"{BASE_URL}/api/profile/trades/carpet_cleaning/submit")
        assert r.status_code == 400

        # 5) upload a photo
        r = tok.post(
            f"{BASE_URL}/api/profile/trades/carpet_cleaning/photos",
            files={"file": ("m.png", _png(), "image/png")},
        )
        assert r.status_code == 200, r.text

        # 6) submit — pending
        r = tok.post(f"{BASE_URL}/api/profile/trades/carpet_cleaning/submit")
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "pending"

        # 7) admin returns the claim with a note
        r = admin_token.post(
            f"{BASE_URL}/api/admin/trade-claims/{uid}/carpet_cleaning/return",
            json={"note": "Please add machine serial photo"},
        )
        assert r.status_code == 200, r.text

        # 8) worker fetches claims — should be returned + admin_note set
        r = tok.get(f"{BASE_URL}/api/profile/trades")
        assert r.status_code == 200
        claim = next(c for c in r.json()["claims"] if c["trade"] == "carpet_cleaning")
        assert claim["status"] == "returned"
        assert claim.get("admin_note")

        # 9) worker edits claim — status flips back to incomplete
        r = tok.put(
            f"{BASE_URL}/api/profile/trades/carpet_cleaning",
            json={"detail_fields": {"machine": "portable Rug Doctor MP-C2D (updated)"}},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "incomplete"

        # 10) re-submit
        r = tok.post(f"{BASE_URL}/api/profile/trades/carpet_cleaning/submit")
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

        # 11) admin verify
        r = admin_token.post(
            f"{BASE_URL}/api/admin/trade-claims/{uid}/carpet_cleaning/verify",
        )
        assert r.status_code == 200

        # 12) worker skills now include carpet_cleaning
        u = tok.get(f"{BASE_URL}/api/auth/me").json()
        assert "carpet_cleaning" in (u.get("skills") or []), f"skills={u.get('skills')}"

        # 13) grace extend
        r = admin_token.post(
            f"{BASE_URL}/api/admin/trade-claims/{uid}/carpet_cleaning/grace", json={"days": 15},
        )
        assert r.status_code == 200
        assert r.json().get("grace_until")

    def test_licensed_trade_requires_license_and_photo(self):
        tok, me, email = _create_fresh_worker()
        # Start plumbing
        r = tok.put(f"{BASE_URL}/api/profile/trades/plumbing",
                         json={"checklist": {"tools": True}, "experience": "3_plus_yr"})
        assert r.status_code == 200
        # Submit blocked — no license number, no upload
        r = tok.post(f"{BASE_URL}/api/profile/trades/plumbing/submit")
        assert r.status_code == 400
        assert "license" in r.text.lower()
        # Add license number — still blocked (no upload)
        r = tok.put(f"{BASE_URL}/api/profile/trades/plumbing",
                         json={"license_number": "PL-12345"})
        assert r.status_code == 200
        r = tok.post(f"{BASE_URL}/api/profile/trades/plumbing/submit")
        assert r.status_code == 400
        # Upload license doc
        r = tok.post(
            f"{BASE_URL}/api/profile/trades/plumbing/photos",
            files={"file": ("lic.png", _png(), "image/png")},
        )
        assert r.status_code == 200, r.text
        r = tok.post(f"{BASE_URL}/api/profile/trades/plumbing/submit")
        assert r.status_code == 200
        assert r.json().get("status") == "pending"


# ---------------- Admin trade manager CRUD ----------------
class TestAdminTradesCRUD:
    def test_create_edit_delete_trade(self, admin_token):
        name = f"TEST Trade {uuid.uuid4().hex[:6]}"
        # Create
        r = admin_token.post(f"{BASE_URL}/api/admin/trades",
                          json={"label": name, "licensed": False, "active": True,
                                "photo_hint": "hint", "checklist": [{"label": "Tool A"}, {"label": "Tool B", "detail_label": "size"}]})
        assert r.status_code == 200, r.text
        tid = r.json()["trade_id"]

        # Show up in public defs
        tok, _, _ = _create_fresh_worker()
        r = tok.get(f"{BASE_URL}/api/trades/definitions")
        assert r.status_code == 200
        assert any(t["trade_id"] == tid for t in r.json()["trades"])

        # Edit — add a checklist item
        r = admin_token.put(f"{BASE_URL}/api/admin/trades/{tid}",
                         json={"label": name, "licensed": False, "active": True,
                               "photo_hint": "hint", "checklist": [
                                   {"label": "Tool A"}, {"label": "Tool B", "detail_label": "size"},
                                   {"label": "Tool C", "photo_required": True}]})
        assert r.status_code == 200
        assert len(r.json()["checklist"]) == 3

        # Delete (no claims)
        r = admin_token.delete(f"{BASE_URL}/api/admin/trades/{tid}")
        assert r.status_code == 200

    def test_delete_blocked_when_claims_exist(self, admin_token):
        # Create then have a worker claim
        name = f"TEST DelBlock {uuid.uuid4().hex[:6]}"
        r = admin_token.post(f"{BASE_URL}/api/admin/trades",
                          json={"label": name, "licensed": False, "active": True,
                                "photo_hint": None, "checklist": [{"label": "x"}]})
        tid = r.json()["trade_id"]
        tok, _, _ = _create_fresh_worker()
        r = tok.put(f"{BASE_URL}/api/profile/trades/{tid}", json={})
        assert r.status_code == 200
        # Delete blocked
        r = admin_token.delete(f"{BASE_URL}/api/admin/trades/{tid}")
        assert r.status_code == 400
        # cleanup
        tok.delete(f"{BASE_URL}/api/profile/trades/{tid}")
        admin_token.delete(f"{BASE_URL}/api/admin/trades/{tid}")


# ---------------- Admin filters + metrics ----------------
class TestAdminFiltersAndMetrics:
    def test_trade_claims_filter(self, admin_token):
        for st in ("pending", "returned", "verified", "all"):
            r = admin_token.get(f"{BASE_URL}/api/admin/trade-claims?status={st}")
            assert r.status_code == 200, f"{st}: {r.text}"
            assert "claims" in r.json()

    def test_metrics_shape(self, admin_token):
        r = admin_token.get(f"{BASE_URL}/api/admin/trades/metrics")
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d["trades"], list)
        for row in d["trades"]:
            assert "pct_verified" in row and "total" in row

    def test_worker_filters(self, admin_token):
        for q in ("work_class=specialist", "trade=carpet_cleaning&trade_status=verified",
                  "attributes=bilingual"):
            r = admin_token.get(f"{BASE_URL}/api/admin/workers?{q}")
            assert r.status_code == 200, f"{q}: {r.text}"


# ---------------- Doc-only badges (Forklift / CDL) ----------------
class TestDocOnlyBadges:
    def test_forklift_cdl_visible_and_doconly(self):
        tok, me, email = _create_fresh_worker()
        r = tok.get(f"{BASE_URL}/api/worker/badges")
        assert r.status_code == 200
        badges = r.json()
        fork = next((b for b in badges if "Forklift" in (b.get("name") or "")), None)
        cdl = next((b for b in badges if "CDL" in (b.get("name") or "")), None)
        assert fork and cdl, f"forklift/cdl missing. Names: {[b.get('name') for b in badges]}"
        assert fork.get("question_count") == 0
        assert cdl.get("question_count") == 0

    def test_doconly_full_flow(self, admin_token):
        tok, me, email = _create_fresh_worker()
        uid = me["user_id"]
        r = tok.get(f"{BASE_URL}/api/worker/badges")
        fork = next(b for b in r.json() if "Forklift" in (b.get("name") or ""))
        bid = fork["badge_id"]

        # Upload doc directly — auto-creates test_passed application
        r = tok.post(f"{BASE_URL}/api/worker/badges/{bid}/documents",
                          files={"file": ("cert.png", _png(), "image/png")})
        assert r.status_code == 200, r.text

        # Submit for review
        r = tok.post(f"{BASE_URL}/api/worker/badges/{bid}/submit", json={"notes": "please review"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending_review"

        # Admin finds application, approves
        r = admin_token.get(f"{BASE_URL}/api/admin/badge-applications?status=pending_review")
        assert r.status_code == 200
        app = next((a for a in r.json() if a["user_id"] == uid and a["badge_id"] == bid), None)
        assert app, "application not visible to admin"
        r = admin_token.post(
            f"{BASE_URL}/api/admin/badge-applications/{app['application_id']}/approve", json={"note": "verified"},
        )
        assert r.status_code == 200

        # Worker skills gets forklift tag
        u = tok.get(f"{BASE_URL}/api/auth/me").json()
        assert "forklift" in (u.get("skills") or []), f"skills={u.get('skills')}"


# ---------------- Regression: demo worker ----------------
class TestRegressionDemoWorker:
    def test_worker_demo_profile_complete_and_feed(self, demo_worker_token):
        me = demo_worker_token.get(f"{BASE_URL}/api/auth/me").json()
        assert me.get("email") == WORKER_DEMO_EMAIL
        missing = me.get("profile_missing_fields") or []
        assert missing == [] or missing == None, f"demo worker profile incomplete: {missing}"
        r = demo_worker_token.get(f"{BASE_URL}/api/gigs")
        assert r.status_code == 200

    def test_admin_workers_list(self, admin_token):
        r = admin_token.get(f"{BASE_URL}/api/admin/workers")
        assert r.status_code == 200


# ---------------- Regression: target_trade gig ----------------
class TestTargetTradeGig:
    def test_create_targeted_gig_invalid_trade(self, admin_token):
        payload = {
            "title": "TEST target invalid",
            "description": "x",
            "category": "cleaning",
            "location": "Baltimore · 21201",
            "scheduled_date": "Mon Jun 01 · 10:00 AM",
            "pay_rate": 25,
            "pay_type": "hourly",
            "slots": 1,
            "target_trade": "not_a_real_trade",
        }
        r = admin_token.post(f"{BASE_URL}/api/gigs", json=payload)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
