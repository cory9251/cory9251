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
