"""
Backend tests for the VA Commission Marketing Program — Phase 1.

Covers:
- VA self-signup with role=va → pending status
- VA submit lead blocked until approved
- Duplicate lead prevention (phone OR email)
- Self-referral prevention (address match)
- Mechie (PM) lead stage transitions: Booked → commission created (calculating),
  Paid → moved to pending_approval queue
- Commission approval flow: PM approve → Owner sign-off → mark paid
- Double-payment prevention
- Owner bulk-approve
- VA earnings/dashboard
- Commercial accounts CRUD + log revenue
- Violation log capture
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://work-connect-147.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

OWNER_EMAIL = "admin@hcobcleaners.com"
OWNER_PASSWORD = "HcobAdmin2026!"
MECHIE_EMAIL = "mechiebadlong77@gmail.com"
MECHIE_PASSWORD = "Mechie2026!"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"Login failed {email}: {r.text}"
    return s


@pytest.fixture(scope="session")
def owner_session():
    return _login(OWNER_EMAIL, OWNER_PASSWORD)


@pytest.fixture(scope="session")
def mechie_session():
    return _login(MECHIE_EMAIL, MECHIE_PASSWORD)


def _new_va(prefix="vatest", phone="5551112222", address="100 Test St, Baltimore MD"):
    email = f"{prefix}+{uuid.uuid4().hex[:6]}@example.com"
    s = requests.Session()
    r = s.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": "vapass123",
            "name": f"VA {email.split('@')[0]}",
            "role": "va",
            "va_phone": phone,
            "va_address": address,
        },
        timeout=20,
    )
    assert r.status_code == 200, r.text
    return s, r.json(), email


@pytest.fixture
def approved_va(mechie_session):
    s, me, email = _new_va()
    # Approve
    r = mechie_session.post(f"{API}/pm/vas/{me['user_id']}/approve", json={}, timeout=20)
    assert r.status_code == 200, r.text
    return s, me, email


# ---------------------------- Tests -----------------------------------
def test_mechie_seeded(mechie_session):
    r = mechie_session.get(f"{API}/auth/me", timeout=10)
    j = r.json()
    assert j["role"] == "admin"
    assert j["is_program_manager"] is True


def test_owner_flag_set(owner_session):
    r = owner_session.get(f"{API}/auth/me", timeout=10)
    j = r.json()
    assert j["role"] == "admin"
    assert j["is_owner"] is True


def test_va_self_signup_is_pending():
    s, me, email = _new_va()
    assert me["role"] == "va"
    assert me["va_status"] == "pending"
    # Block lead submission while pending
    r = s.post(
        f"{API}/va/leads",
        json={
            "prospect_name": "X",
            "prospect_phone": "5551239999",
            "service_type": "deep",
            "property_size": "1br",
            "source": "other",
        },
        timeout=20,
    )
    assert r.status_code == 403


def test_va_lead_submit_after_approval(approved_va):
    s, me, _email = approved_va
    r = s.post(
        f"{API}/va/leads",
        json={
            "prospect_name": "Lead Smith",
            "prospect_phone": f"4{uuid.uuid4().int % 10**9:09d}",
            "prospect_email": f"lead+{uuid.uuid4().hex[:6]}@example.com",
            "service_type": "deep",
            "property_size": "3br",
            "source": "facebook_groups",
        },
        timeout=20,
    )
    assert r.status_code == 200, r.text
    lead = r.json()
    assert lead["stage"] == "new_lead"
    assert lead["va_user_id"] == me["user_id"]


def test_duplicate_lead_block(approved_va):
    s, _, _ = approved_va
    phone = f"4{uuid.uuid4().int % 10**9:09d}"
    email = f"dup+{uuid.uuid4().hex[:6]}@example.com"
    payload = {
        "prospect_name": "Dup Smith",
        "prospect_phone": phone,
        "prospect_email": email,
        "service_type": "routine",
        "property_size": "2br",
        "source": "referral",
    }
    r = s.post(f"{API}/va/leads", json=payload, timeout=20)
    assert r.status_code == 200
    # Same phone — block
    r2 = s.post(f"{API}/va/leads", json={**payload, "prospect_email": f"alt+{uuid.uuid4().hex[:6]}@example.com"}, timeout=20)
    assert r2.status_code == 409
    assert r2.json()["detail"]["code"] == "duplicate_lead"
    # Same email, different phone — also block
    r3 = s.post(f"{API}/va/leads", json={**payload, "prospect_phone": f"9{uuid.uuid4().int % 10**9:09d}"}, timeout=20)
    assert r3.status_code == 409


def test_self_referral_block(approved_va):
    s, _, _ = approved_va
    r = s.post(
        f"{API}/va/leads",
        json={
            "prospect_name": "Self",
            "prospect_phone": f"4{uuid.uuid4().int % 10**9:09d}",
            "prospect_address": "100 test st  baltimore md",  # matches registered (case/space-insensitive)
            "service_type": "deep",
            "property_size": "2br",
            "source": "referral",
        },
        timeout=20,
    )
    assert r.status_code == 400
    assert "Self-referral" in r.json()["detail"]


def test_commission_lifecycle(approved_va, mechie_session, owner_session):
    s, me, _ = approved_va
    # Submit a lead
    payload = {
        "prospect_name": "Lifecycle Client",
        "prospect_phone": f"4{uuid.uuid4().int % 10**9:09d}",
        "service_type": "deep",  # $25 flat
        "property_size": "3br",
        "source": "craigslist",
    }
    lead = s.post(f"{API}/va/leads", json=payload, timeout=20).json()
    lead_id = lead["lead_id"]

    # PM moves through stages: contacted → quoted → booked → completed → paid
    for stage in ("contacted", "quoted", "booked", "completed", "paid"):
        body = {"stage": stage}
        if stage == "paid":
            body["job_value"] = 300
        r = mechie_session.put(f"{API}/pm/leads/{lead_id}/stage", json=body, timeout=20)
        assert r.status_code == 200, f"stage {stage}: {r.text}"

    # Commission should now be pending_approval
    queue = mechie_session.get(f"{API}/pm/commissions", timeout=20).json()
    comm = next((c for c in queue["items"] if c["lead_id"] == lead_id), None)
    assert comm is not None and comm["status"] == "pending_approval"
    assert comm["amount"] == 25.0

    # PM approves
    r = mechie_session.post(f"{API}/pm/commissions/{comm['commission_id']}/approve", json={"note": "ok"}, timeout=20)
    assert r.status_code == 200 and r.json()["status"] == "pm_approved"

    # Owner queue
    oq = owner_session.get(f"{API}/owner/payouts/queue", timeout=20).json()
    assert any(c["commission_id"] == comm["commission_id"] for c in oq["items"])

    # Owner approves
    r = owner_session.post(f"{API}/owner/payouts/{comm['commission_id']}/approve", timeout=20)
    assert r.status_code == 200 and r.json()["status"] == "owner_approved"

    # Mark paid
    r = owner_session.post(
        f"{API}/owner/payouts/{comm['commission_id']}/mark-paid",
        json={"payout_reference": "ref-x", "payout_method": "venmo"},
        timeout=20,
    )
    assert r.status_code == 200 and r.json()["status"] == "paid"

    # Double-pay block
    r = owner_session.post(
        f"{API}/owner/payouts/{comm['commission_id']}/mark-paid",
        json={},
        timeout=20,
    )
    assert r.status_code == 400
    assert "double-payment" in r.json()["detail"].lower()


def test_va_dashboard_and_earnings(approved_va, mechie_session, owner_session):
    s, _, _ = approved_va
    # Submit + push to paid
    payload = {
        "prospect_name": "Dash Client",
        "prospect_phone": f"5{uuid.uuid4().int % 10**9:09d}",
        "service_type": "moveout",  # $25 flat
        "property_size": "4br",
        "source": "other",
    }
    lead = s.post(f"{API}/va/leads", json=payload, timeout=20).json()
    for stage in ("booked", "completed", "paid"):
        body = {"stage": stage}
        if stage == "paid":
            body["job_value"] = 500
        mechie_session.put(f"{API}/pm/leads/{lead['lead_id']}/stage", json=body, timeout=20)

    dash = s.get(f"{API}/va/dashboard", timeout=20).json()
    assert dash["va_status"] == "approved"
    # Pending should be > 0 because Mechie hasn't approved yet
    assert dash["commissions_pending"] >= 25.0

    earn = s.get(f"{API}/va/earnings", timeout=20).json()
    assert earn["totals"]["all_time"] >= 25.0
    assert len(earn["items"]) >= 1


def test_va_status_suspend_blocks_lead_submit(approved_va, mechie_session):
    s, me, _ = approved_va
    r = mechie_session.post(f"{API}/pm/vas/{me['user_id']}/suspend", json={"note": "test"}, timeout=20)
    assert r.status_code == 200
    # Suspended VA's sessions are killed — re-authenticate to fetch /auth/me (and see 401)
    r2 = s.get(f"{API}/auth/me", timeout=20)
    assert r2.status_code == 401


def test_pm_violations_logged(approved_va, mechie_session):
    s, _, _ = approved_va
    s.post(
        f"{API}/va/leads",
        json={
            "prospect_name": "Self",
            "prospect_phone": f"4{uuid.uuid4().int % 10**9:09d}",
            "prospect_address": "100 test st  baltimore md",
            "service_type": "deep",
            "property_size": "2br",
            "source": "referral",
        },
        timeout=20,
    )
    violations = mechie_session.get(f"{API}/pm/violations", timeout=20).json()
    assert len(violations["items"]) >= 1


def test_commercial_account_revenue(approved_va, mechie_session, owner_session):
    _, me, _ = approved_va
    # Make sure VA is approved (previous test may have suspended)
    mechie_session.post(f"{API}/pm/vas/{me['user_id']}/approve", json={}, timeout=20)
    r = mechie_session.post(
        f"{API}/pm/commercial-accounts",
        json={
            "account_name": f"Acme Corp {uuid.uuid4().hex[:4]}",
            "va_user_id": me["user_id"],
            "monthly_revenue": 1000.0,
        },
        timeout=20,
    )
    assert r.status_code == 200, r.text
    acct = r.json()
    # Log revenue
    r = mechie_session.post(
        f"{API}/pm/commercial-accounts/{acct['account_id']}/log-revenue",
        json={"revenue": 2000, "period": "2026-06"},
        timeout=20,
    )
    assert r.status_code == 200
    comm = r.json()
    assert comm["amount"] == 100.0  # 5% of 2000
    assert comm["status"] == "pending_approval"


def test_owner_bulk_approve(approved_va, mechie_session, owner_session):
    s, me, _ = approved_va
    # Approve VA if suspended
    mechie_session.post(f"{API}/pm/vas/{me['user_id']}/approve", json={}, timeout=20)
    # Create 2 leads → push to paid → PM approves both
    ids = []
    for i in range(2):
        payload = {
            "prospect_name": f"Bulk {i}",
            "prospect_phone": f"6{uuid.uuid4().int % 10**9:09d}",
            "service_type": "deep",
            "property_size": "2br",
            "source": "other",
        }
        lead = s.post(f"{API}/va/leads", json=payload, timeout=20).json()
        for stage in ("booked", "completed", "paid"):
            body = {"stage": stage}
            if stage == "paid":
                body["job_value"] = 300
            mechie_session.put(f"{API}/pm/leads/{lead['lead_id']}/stage", json=body, timeout=20)
        ids.append(lead["lead_id"])
    # PM approve each commission
    q = mechie_session.get(f"{API}/pm/commissions", timeout=20).json()
    target_comms = [c for c in q["items"] if c["lead_id"] in ids]
    for c in target_comms:
        mechie_session.post(f"{API}/pm/commissions/{c['commission_id']}/approve", json={}, timeout=20)

    # Owner bulk approve for this VA
    r = owner_session.post(
        f"{API}/owner/payouts/bulk-approve",
        json={"va_user_id": me["user_id"]},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["approved_count"] >= len(target_comms)
