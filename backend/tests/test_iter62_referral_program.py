"""Iter 62 — Contractor Referral Program (Phase 1 MVP).

Verifies the full FRD flow + Cory's spec changes:
  - Worker can submit a referral from anywhere (no source-job required)
  - Required fields enforced (address, description, category)
  - Intent flag (for_self vs for_another) stored
  - Lifecycle: submitted → quoted → paid (commission accrues) → released
  - Commission rate is admin-configurable
  - Self-fulfillment auto-flips status + voids commission
  - Worker sees own + admin sees all
"""
import os
import uuid

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://work-connect-147.preview.emergentagent.com",
).rstrip("/")

WORKER = {"email": "worker.demo@hcobcleaners.com", "password": "WorkerDemo2026!"}
ADMIN = {"email": "admin@hcobcleaners.com", "password": "HcobAdmin2026!"}


def _worker_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=WORKER, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Worker login failed: {r.status_code}")
    return s


def _admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code}")
    return s


def _submit(s, **overrides):
    body = {
        "property_address": f"Iter62 {uuid.uuid4().hex[:6]} Main St, Baltimore MD",
        "opportunity_description": "Spotted carpet that needs deep cleaning at end-of-lease",
        "service_category": "carpet_cleaning",
        "intent": "for_another",
    }
    body.update(overrides)
    r = s.post(f"{BASE_URL}/api/worker/referrals", json=body, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"submit failed: {r.status_code} {r.text}")
    return r.json()


def test_worker_can_submit_referral():
    s = _worker_session()
    body = _submit(s)
    assert body["referral_id"].startswith("ref_")
    assert body["status"] == "submitted"
    assert body["referring_contractor_id"]
    assert body["intent"] == "for_another"
    assert body["commission_status"] == "pending"


def test_worker_required_fields():
    s = _worker_session()
    # Missing address
    r = s.post(
        f"{BASE_URL}/api/worker/referrals",
        json={
            "opportunity_description": "missing addr",
            "service_category": "carpet_cleaning",
        },
        timeout=20,
    )
    assert r.status_code == 422
    # Missing description
    r2 = s.post(
        f"{BASE_URL}/api/worker/referrals",
        json={"property_address": "123 X", "service_category": "carpet_cleaning"},
        timeout=20,
    )
    assert r2.status_code == 422
    # Invalid category
    r3 = s.post(
        f"{BASE_URL}/api/worker/referrals",
        json={
            "property_address": "123 X",
            "opportunity_description": "long enough",
            "service_category": "bogus_category",
        },
        timeout=20,
    )
    assert r3.status_code == 400


def test_worker_lists_own_referrals_with_totals():
    s = _worker_session()
    _submit(s)
    r = s.get(f"{BASE_URL}/api/worker/referrals", timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and len(body["items"]) >= 1
    assert "totals" in body
    for k in ("commission_pending", "commission_eligible", "commission_paid"):
        assert k in body["totals"]
    assert isinstance(body["service_categories"], list)


def test_intent_for_self_persists():
    s = _worker_session()
    body = _submit(s, intent="for_self")
    assert body["intent"] == "for_self"


def test_admin_sees_all_referrals():
    sw = _worker_session()
    sa = _admin_session()
    body = _submit(sw)
    r = sa.get(f"{BASE_URL}/api/admin/referrals", timeout=20)
    assert r.status_code == 200
    items = r.json()["items"]
    ids = [i["referral_id"] for i in items]
    assert body["referral_id"] in ids
    assert "counts" in r.json()


def test_admin_can_filter_by_status():
    sa = _admin_session()
    r = sa.get(f"{BASE_URL}/api/admin/referrals?status=submitted", timeout=20)
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert item["status"] == "submitted"


def test_admin_lifecycle_quoted_paid_released():
    sw = _worker_session()
    sa = _admin_session()
    rid = _submit(sw)["referral_id"]
    # quote $500
    r = sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"status": "quoted", "quoted_amount": 500},
        timeout=20,
    )
    assert r.json()["quoted_amount"] == 500.0
    # mark paid → commission accrues at 10% = $50
    r2 = sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"status": "paid"},
        timeout=20,
    )
    body = r2.json()
    assert body["status"] == "paid"
    assert body["commission_amount"] == 50
    assert body["commission_status"] == "eligible"
    # release
    r3 = sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"status": "commission_released"},
        timeout=20,
    )
    body3 = r3.json()
    assert body3["status"] == "commission_released"
    assert body3["commission_status"] == "paid"
    assert body3["commission_paid_date"]


def test_self_fulfillment_voids_commission():
    """If admin assigns the referring contractor to the lead, status flips
    to self_fulfilled and commission is voided."""
    sw = _worker_session()
    sa = _admin_session()
    sub = _submit(sw)
    rid = sub["referral_id"]
    referrer_id = sub["referring_contractor_id"]
    # Quote it first
    sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"status": "quoted", "quoted_amount": 800},
        timeout=20,
    )
    # Assign to the referrer himself
    r = sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"assigned_contractor_id": referrer_id},
        timeout=20,
    )
    body = r.json()
    assert body["status"] == "self_fulfilled"
    assert body["commission_amount"] == 0
    assert body["commission_status"] == "void"


def test_admin_can_void():
    sw = _worker_session()
    sa = _admin_session()
    rid = _submit(sw)["referral_id"]
    r = sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"status": "void", "admin_notes": "test void"},
        timeout=20,
    )
    body = r.json()
    assert body["status"] == "void"
    assert body["commission_status"] == "void"


def test_commission_rate_configurable():
    sa = _admin_session()
    # Set to 15%
    r = sa.put(
        f"{BASE_URL}/api/admin/referrals/settings",
        json={"commission_rate": 0.15},
        timeout=20,
    )
    assert r.status_code == 200
    assert r.json()["commission_rate"] == 0.15
    # Submit + mark paid → should use new rate
    sw = _worker_session()
    rid = _submit(sw)["referral_id"]
    sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"status": "quoted", "quoted_amount": 1000},
        timeout=20,
    )
    r2 = sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"status": "paid"},
        timeout=20,
    )
    # 1000 * 0.15 = 150
    assert r2.json()["commission_amount"] == 150
    # Restore default
    sa.put(
        f"{BASE_URL}/api/admin/referrals/settings",
        json={"commission_rate": 0.10},
        timeout=20,
    )


def test_release_blocked_until_paid():
    """Try to release commission before mark paid → 400."""
    sw = _worker_session()
    sa = _admin_session()
    rid = _submit(sw)["referral_id"]
    sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"status": "quoted", "quoted_amount": 500},
        timeout=20,
    )
    r = sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"status": "commission_released"},
        timeout=20,
    )
    assert r.status_code == 400
    assert "paid" in r.json()["detail"].lower()


def test_worker_cannot_access_admin_endpoints():
    sw = _worker_session()
    r = sw.get(f"{BASE_URL}/api/admin/referrals", timeout=20)
    assert r.status_code == 403


def test_va_cannot_submit_referral():
    """Only workers can submit — VAs/customers/admins cannot."""
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "va.demo@hcobcleaners.com", "password": "VaDemo2026!"},
        timeout=20,
    )
    if r.status_code != 200:
        pytest.skip("VA login failed")
    r2 = s.post(
        f"{BASE_URL}/api/worker/referrals",
        json={
            "property_address": "VA tried this",
            "opportunity_description": "should be blocked",
            "service_category": "carpet_cleaning",
        },
        timeout=20,
    )
    assert r2.status_code == 403


# ---------------------------------------------------------------------------
# Referral Status Update Notifications (Iter 62 engagement add-on)
# ---------------------------------------------------------------------------
# Whenever an admin moves a referral through the pipeline, the system sends
# the referring worker an email (always) + an SMS for milestone statuses
# (paid / commission_released). Every attempt — including skipped ones — is
# recorded in the `referral_notifications` collection so we can verify
# behavior without mocking Resend/Twilio.
import time
from pymongo import MongoClient


def _mongo_db():
    """Direct Mongo handle so tests can read the audit collection."""
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        pytest.skip("MONGO_URL/DB_NAME not set — cannot verify audit log")
    return MongoClient(mongo_url)[db_name]


def _wait_for_notification(db_h, referral_id: str, status: str, timeout_s: float = 4.0):
    """Poll the audit collection for up to N seconds — BackgroundTasks fire
    after the HTTP response so we need a tiny grace window."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        row = db_h.referral_notifications.find_one({
            "referral_id": referral_id,
            "status": status,
        })
        if row:
            return row
        time.sleep(0.2)
    return None


def test_status_update_emits_notification_on_under_review():
    """Moving from submitted → under_review should trigger an audit row +
    email attempt for the referring worker."""
    sw = _worker_session()
    sa = _admin_session()
    rid = _submit(sw)["referral_id"]
    r = sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"status": "under_review"},
        timeout=20,
    )
    assert r.status_code == 200
    db_h = _mongo_db()
    row = _wait_for_notification(db_h, rid, "under_review")
    assert row is not None, "No referral_notifications row recorded"
    assert "email" in row["channels_attempted"]
    # SMS should NOT fire for non-milestone statuses
    assert "sms" not in row["channels_attempted"]


def test_status_update_quoted_triggers_email_only():
    sw = _worker_session()
    sa = _admin_session()
    rid = _submit(sw)["referral_id"]
    r = sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"status": "quoted", "quoted_amount": 600},
        timeout=20,
    )
    assert r.status_code == 200
    db_h = _mongo_db()
    row = _wait_for_notification(db_h, rid, "quoted")
    assert row is not None
    assert "email" in row["channels_attempted"]
    assert "sms" not in row["channels_attempted"]


def test_status_update_paid_triggers_sms_milestone():
    """`paid` is a milestone — both email AND SMS should be attempted
    (SMS attempted only if user has phone & creds — `channels_attempted`
    records the attempt regardless of skip)."""
    sw = _worker_session()
    sa = _admin_session()
    rid = _submit(sw)["referral_id"]
    sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"status": "quoted", "quoted_amount": 1000},
        timeout=20,
    )
    r = sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"status": "paid"},
        timeout=20,
    )
    assert r.status_code == 200
    assert r.json()["commission_amount"] == 100  # 10% of 1000
    db_h = _mongo_db()
    row = _wait_for_notification(db_h, rid, "paid")
    assert row is not None
    assert "email" in row["channels_attempted"]
    # SMS is only attempted if the worker has a phone on file. If demo
    # worker has a phone, we expect 'sms' in channels_attempted.
    user = db_h.users.find_one({"email": "worker.demo@hcobcleaners.com"})
    if user and user.get("phone"):
        assert "sms" in row["channels_attempted"]


def test_status_update_commission_released_triggers_sms_milestone():
    sw = _worker_session()
    sa = _admin_session()
    rid = _submit(sw)["referral_id"]
    sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"status": "quoted", "quoted_amount": 500},
        timeout=20,
    )
    sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"status": "paid"},
        timeout=20,
    )
    r = sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"status": "commission_released"},
        timeout=20,
    )
    assert r.status_code == 200
    db_h = _mongo_db()
    row = _wait_for_notification(db_h, rid, "commission_released")
    assert row is not None
    assert "email" in row["channels_attempted"]
    user = db_h.users.find_one({"email": "worker.demo@hcobcleaners.com"})
    if user and user.get("phone"):
        assert "sms" in row["channels_attempted"]


def test_status_update_void_emits_notification():
    sw = _worker_session()
    sa = _admin_session()
    rid = _submit(sw)["referral_id"]
    r = sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"status": "void", "admin_notes": "Customer ghosted"},
        timeout=20,
    )
    assert r.status_code == 200
    db_h = _mongo_db()
    row = _wait_for_notification(db_h, rid, "void")
    assert row is not None
    assert "email" in row["channels_attempted"]


def test_no_notification_when_status_unchanged():
    """If admin updates ONLY quoted_amount (no status change), the
    referrer should NOT be re-notified — avoids spam from minor edits."""
    sw = _worker_session()
    sa = _admin_session()
    rid = _submit(sw)["referral_id"]
    # First move to quoted to seed a notification
    sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"status": "quoted", "quoted_amount": 400},
        timeout=20,
    )
    db_h = _mongo_db()
    _wait_for_notification(db_h, rid, "quoted")
    initial = db_h.referral_notifications.count_documents({"referral_id": rid})
    # Now edit quoted_amount only — no status change
    r = sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"quoted_amount": 450},
        timeout=20,
    )
    assert r.status_code == 200
    time.sleep(1.0)  # give background tasks a chance to (not) fire
    after = db_h.referral_notifications.count_documents({"referral_id": rid})
    assert after == initial, "Should not emit extra notifications on no-status edit"


def test_self_fulfillment_emits_self_fulfilled_notification():
    """Auto-flip to self_fulfilled (admin assigns referrer) should send a
    'your referral was closed' email."""
    sw = _worker_session()
    sa = _admin_session()
    sub = _submit(sw)
    rid = sub["referral_id"]
    referrer_id = sub["referring_contractor_id"]
    r = sa.patch(
        f"{BASE_URL}/api/admin/referrals/{rid}",
        json={"assigned_contractor_id": referrer_id},
        timeout=20,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "self_fulfilled"
    db_h = _mongo_db()
    row = _wait_for_notification(db_h, rid, "self_fulfilled")
    assert row is not None
    assert "email" in row["channels_attempted"]

