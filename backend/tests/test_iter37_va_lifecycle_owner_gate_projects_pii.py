"""Iter37 — coverage for the routes extracted from server.py in Phase 3f.

Specifically targets gaps not exercised by prior 98 tests:

1.  Full VA-Commission lifecycle from a *fresh* commission through
    `paid` with the Owner double-pay guard:
       booked → paid → pm_approved → owner_approved → paid → (re-pay 400)
2.  Owner-only permission gate: an admin WITHOUT `is_owner` (e.g. Mechie,
    the Program Manager) must get 403 on every `/api/owner/*` route.
3.  Projects worker-view PII gating: project structure visible to any
    logged-in worker, but crew first-names are hidden until that worker
    is *approved* on at least one of the project's gigs.

Run:
    REACT_APP_BACKEND_URL=... pytest backend/tests/test_iter37_*.py -q
"""
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

OWNER_EMAIL = "admin@hcobcleaners.com"
OWNER_PASSWORD = "HcobAdmin2026!"
MECHIE_EMAIL = "mechiebadlong77@gmail.com"   # admin, is_program_manager, NOT is_owner
MECHIE_PASSWORD = "Mechie2026!"


# --------------------------- shared helpers ------------------------------
def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def owner_session():
    return _login(OWNER_EMAIL, OWNER_PASSWORD)


@pytest.fixture(scope="session")
def mechie_session():
    """Admin role, is_program_manager=True, is_owner=False — used to verify
    the Owner permission gate."""
    s = _login(MECHIE_EMAIL, MECHIE_PASSWORD)
    me = s.get(f"{API}/auth/me", timeout=10).json()
    assert me.get("role") == "admin"
    # Cannot be the Owner — that's the whole point of using Mechie for this gate test
    assert not me.get("is_owner"), \
        "Mechie should NOT be is_owner — fix test_credentials.md or seed"
    return s


def _register_va(prefix: str, address: str = "100 IterTest Ln, Baltimore MD"):
    email = f"iter37va_{prefix}_{uuid.uuid4().hex[:6]}@example.com"
    s = requests.Session()
    r = s.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": "vapass123",
            "name": f"VA37 {prefix}",
            "role": "va",
            "va_phone": "555" + uuid.uuid4().hex[:7],
            "va_address": address,
        },
        timeout=20,
    )
    assert r.status_code == 200, r.text
    return s, r.json()["user_id"], email


def _approve_va(admin: requests.Session, va_user_id: str) -> None:
    r = admin.post(f"{API}/pm/vas/{va_user_id}/approve", json={}, timeout=20)
    assert r.status_code == 200, r.text


def _new_lead(va: requests.Session, phone: str | None = None) -> dict:
    payload = {
        "prospect_name": f"Prospect {uuid.uuid4().hex[:5]}",
        "prospect_phone": phone or "410" + uuid.uuid4().hex[:7],
        "prospect_email": f"prospect_{uuid.uuid4().hex[:6]}@example.com",
        "prospect_address": f"{uuid.uuid4().int % 9999} Customer Rd, Baltimore MD",
        "service_type": "deep",         # flat $25 — predictable amount
        "property_size": "2br",
        "preferred_datetime": datetime.now(timezone.utc).date().isoformat(),
        "source": "facebook_marketplace",
        "notes": "iter37 lifecycle test",
    }
    r = va.post(f"{API}/va/leads", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()


# =========================================================================
# 1.  Full lifecycle: booked → paid → pm_approved → owner_approved →
#     paid, plus the double-pay guard (re-marking paid returns 400).
# =========================================================================
class TestVACommissionFullLifecycle:
    """End-to-end happy path that wasn't fully covered by prior tests."""

    def test_full_lifecycle_with_double_pay_guard(self, owner_session, mechie_session):
        # 1. Provision approved VA + submit a lead
        va, va_id, _ = _register_va("life")
        _approve_va(mechie_session, va_id)
        lead = _new_lead(va)
        lead_id = lead["lead_id"]

        # 2. PM transitions booked → commission record created (calculating)
        r = mechie_session.put(
            f"{API}/pm/leads/{lead_id}/stage",
            json={"stage": "booked"},
            timeout=20,
        )
        assert r.status_code == 200, r.text

        # 3. PM transitions paid → commission moved to pending_approval
        r = mechie_session.put(
            f"{API}/pm/leads/{lead_id}/stage",
            json={"stage": "paid"},
            timeout=20,
        )
        assert r.status_code == 200, r.text

        # 4. Find commission via PM queue
        r = mechie_session.get(f"{API}/pm/commissions?va_user_id={va_id}", timeout=20)
        assert r.status_code == 200
        items = r.json()["items"]
        assert items, "Expected at least one commission for this VA"
        comm = next(c for c in items if c.get("lead_id") == lead_id)
        comm_id = comm["commission_id"]
        assert comm["status"] == "pending_approval"
        assert float(comm["amount"]) == 25.0       # deep flat $25

        # 5. PM approves → pm_approved
        r = mechie_session.post(
            f"{API}/pm/commissions/{comm_id}/approve",
            json={"note": "iter37 approve"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pm_approved"

        # 6. Owner sign-off → owner_approved
        r = owner_session.post(
            f"{API}/owner/payouts/{comm_id}/approve", json={}, timeout=20
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "owner_approved"

        # 7. Owner marks paid → paid
        r = owner_session.post(
            f"{API}/owner/payouts/{comm_id}/mark-paid",
            json={"payout_reference": "iter37-ref", "payout_method": "zelle"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        paid_doc = r.json()
        assert paid_doc["status"] == "paid"
        assert paid_doc["payout_reference"] == "iter37-ref"
        assert paid_doc["payout_method"] == "zelle"

        # 8. Double-pay guard — second mark-paid must return 400
        r = owner_session.post(
            f"{API}/owner/payouts/{comm_id}/mark-paid",
            json={"payout_reference": "should-fail"},
            timeout=20,
        )
        assert r.status_code == 400, (
            f"Expected double-pay guard (400), got {r.status_code}: {r.text}"
        )
        body = r.json()
        detail = body.get("detail") or body.get("message") or str(body)
        assert "already" in detail.lower() and "paid" in detail.lower(), \
            f"Expected 'already paid' message, got: {detail}"

        # 9. Sanity — VA earnings/dashboard reflect total_paid >= 25
        r = va.get(f"{API}/va/dashboard", timeout=20)
        assert r.status_code == 200
        assert r.json()["total_paid"] >= 25.0

    def test_owner_approve_requires_pm_approved_first(
        self, owner_session, mechie_session
    ):
        """Owner cannot sign off a commission that is still pending_approval."""
        va, va_id, _ = _register_va("preapp")
        _approve_va(mechie_session, va_id)
        lead = _new_lead(va)
        # Move to paid → pending_approval (no PM approve)
        mechie_session.put(
            f"{API}/pm/leads/{lead['lead_id']}/stage", json={"stage": "booked"}, timeout=20
        )
        mechie_session.put(
            f"{API}/pm/leads/{lead['lead_id']}/stage", json={"stage": "paid"}, timeout=20
        )
        items = mechie_session.get(
            f"{API}/pm/commissions?va_user_id={va_id}", timeout=20
        ).json()["items"]
        comm = next(c for c in items if c.get("lead_id") == lead["lead_id"])

        r = owner_session.post(
            f"{API}/owner/payouts/{comm['commission_id']}/approve",
            json={},
            timeout=20,
        )
        assert r.status_code == 400, r.text
        assert "pm_approved" in (r.json().get("detail") or "").lower()

    def test_mark_paid_requires_owner_approved_first(
        self, owner_session, mechie_session
    ):
        """Cannot skip Owner sign-off and mark a pm_approved commission as paid."""
        va, va_id, _ = _register_va("skipowner")
        _approve_va(mechie_session, va_id)
        lead = _new_lead(va)
        mechie_session.put(
            f"{API}/pm/leads/{lead['lead_id']}/stage", json={"stage": "booked"}, timeout=20
        )
        mechie_session.put(
            f"{API}/pm/leads/{lead['lead_id']}/stage", json={"stage": "paid"}, timeout=20
        )
        comm = next(
            c
            for c in mechie_session.get(
                f"{API}/pm/commissions?va_user_id={va_id}", timeout=20
            ).json()["items"]
            if c.get("lead_id") == lead["lead_id"]
        )
        # PM-approve only
        mechie_session.post(
            f"{API}/pm/commissions/{comm['commission_id']}/approve", json={}, timeout=20
        )
        # Try to mark-paid (no owner sign-off yet)
        r = owner_session.post(
            f"{API}/owner/payouts/{comm['commission_id']}/mark-paid",
            json={},
            timeout=20,
        )
        assert r.status_code == 400, r.text
        assert "owner_approved" in (r.json().get("detail") or "").lower()


# =========================================================================
# 2.  Owner permission gate — only is_owner=True admins may hit /owner/*
# =========================================================================
class TestOwnerPermissionGate:
    """An admin who lacks is_owner must get 403 on every Owner route."""

    @pytest.mark.parametrize(
        "method,path,json_body",
        [
            ("GET", "/owner/dashboard", None),
            ("GET", "/owner/payouts/queue", None),
            ("POST", "/owner/payouts/fake_commission_id/approve", {}),
            ("POST", "/owner/payouts/bulk-approve",
             {"va_user_id": "fake_va"}),
            ("POST", "/owner/payouts/fake_commission_id/mark-paid", {}),
        ],
    )
    def test_non_owner_admin_blocked(self, mechie_session, method, path, json_body):
        url = f"{API}{path}"
        if method == "GET":
            r = mechie_session.get(url, timeout=20)
        else:
            r = mechie_session.post(url, json=json_body, timeout=20)
        assert r.status_code == 403, (
            f"{method} {path}: expected 403 for non-owner admin, got {r.status_code} {r.text}"
        )

    def test_owner_can_hit_dashboard(self, owner_session):
        r = owner_session.get(f"{API}/owner/dashboard", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        # Sanity — payload shape preserved by refactor
        for key in (
            "payout_queue_count",
            "payout_queue_amount",
            "month_total_commissions",
            "top_by_volume",
            "alerts",
        ):
            assert key in body, f"missing key {key} in /owner/dashboard"


# =========================================================================
# 3.  Projects worker-view PII gating
# =========================================================================
class TestProjectsWorkerViewPII:
    """Worker can always see project structure; crew first-names hidden
    until the requesting worker is accepted on at least one project gig."""

    def _make_worker(self):
        email = f"iter37wkr_{uuid.uuid4().hex[:6]}@example.com"
        s = requests.Session()
        r = s.post(
            f"{API}/auth/register",
            json={
                "email": email,
                "password": "wkrpass123",
                "name": f"Worker37 {email.split('@')[0]}",
                "role": "worker",
            },
            timeout=20,
        )
        assert r.status_code == 200, r.text
        return s, r.json()["user_id"], email

    def test_crew_hidden_until_worker_approved_on_gig(self, owner_session):
        # 1. Admin creates a project
        proj_payload = {
            "title": f"Iter37 Project {uuid.uuid4().hex[:5]}",
            "description": "PII gating test",
        }
        r = owner_session.post(f"{API}/projects", json=proj_payload, timeout=20)
        assert r.status_code == 200, r.text
        project_id = r.json()["project_id"]

        # 2. Admin creates a gig and links it to the project
        future = (datetime.now(timezone.utc) + timedelta(days=21)).isoformat()
        gig_payload = {
            "title": f"Iter37 Gig {uuid.uuid4().hex[:5]}",
            "description": "structure check",
            "category": "cleaning",
            "location": "Houston",
            "address_line": "123 Iter37 Rd, Houston TX",
            "scheduled_date": "Mon, Jun 01 · 9:00 AM",
            "scheduled_at": future,
            "pay_rate": 20.0,
            "pay_type": "hourly",
            "slots": 2,
            "duration_hours": 4.0,
            "payment_timeline": "2_3_days",
            "contact_phone": "+12815550100",
        }
        r = owner_session.post(f"{API}/gigs", json=gig_payload, timeout=20)
        assert r.status_code == 200, r.text
        gig_id = r.json()["gig_id"]
        r = owner_session.post(
            f"{API}/gigs/{gig_id}/link-to-project",
            json={"project_id": project_id, "sync_defaults": False},
            timeout=20,
        )
        assert r.status_code == 200, r.text

        # 3. Two workers — one will be approved, one will be the requester
        crew_session, crew_uid, _ = self._make_worker()
        outsider_session, outsider_uid, _ = self._make_worker()

        # 4. Admin assigns the crew worker directly to the gig
        r = owner_session.post(
            f"{API}/gigs/{gig_id}/assign",
            json={"worker_id": crew_uid},
            timeout=20,
        )
        assert r.status_code in (200, 201), (
            f"Assign worker failed: {r.status_code} {r.text}"
        )

        # 5. Outsider hits worker-view → crew_visible must be False
        r = outsider_session.get(
            f"{API}/projects/{project_id}/worker-view", timeout=20
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["project_id"] == project_id
        assert body["title"] == proj_payload["title"]
        # Structure (linked_gigs) is visible for any worker
        assert isinstance(body.get("linked_gigs"), list)
        # Crew identity must be hidden for outsider
        assert body.get("crew_visible") is False, (
            f"Outsider should NOT see crew, got crew_visible={body.get('crew_visible')}"
        )
        # No crew first-names leaked anywhere in linked_gigs
        for g in body.get("linked_gigs", []):
            assert not g.get("crew"), (
                f"Outsider got crew list in gig payload: {g.get('crew')}"
            )

        # 6. Approved crew worker hits worker-view → crew_visible True
        r = crew_session.get(
            f"{API}/projects/{project_id}/worker-view", timeout=20
        )
        assert r.status_code == 200, r.text
        body2 = r.json()
        assert body2.get("crew_visible") is True, (
            f"Approved crew should see crew, got crew_visible={body2.get('crew_visible')}"
        )

        # Cleanup — archive project + delete gig is best-effort (admin only)
        owner_session.delete(f"{API}/projects/{project_id}", timeout=20)
