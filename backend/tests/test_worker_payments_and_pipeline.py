"""Iteration 73 backend tests: worker payments, lost-lead recovery, idempotency.

Seeds a gig_acceptance directly in mongo (bypassing geofenced clock-in) then
exercises the admin approve-timesheet + worker-payments mark-paid flow, and
tests the PM lost-lead recovery flow.
"""
import os
import time
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://work-connect-147.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@hcobcleaners.com", "password": "HcobAdmin2026!"}
WORKER_EMAIL = "worker.demo@hcobcleaners.com"
VA = {"email": "va.demo@hcobcleaners.com", "password": "VaDemo2026!"}

# Direct mongo access for fixture seeding
_mc = MongoClient("mongodb://localhost:27017")
_mdb = _mc[os.environ.get("DB_NAME", "test_database")]


def _login(session: requests.Session, creds: dict) -> dict:
    r = session.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login {creds['email']} failed: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    _login(s, ADMIN)
    return s


@pytest.fixture(scope="module")
def va_session():
    s = requests.Session()
    _login(s, VA)
    return s


@pytest.fixture(scope="module")
def seeded_fixture():
    """Seed a TEST_ gig + approved-timesheet acceptance in mongo."""
    now = datetime.now(timezone.utc)
    gig_id = f"TEST_gig_{uuid.uuid4().hex[:10]}"
    acc_id = f"TEST_acc_{uuid.uuid4().hex[:10]}"

    worker = _mdb.users.find_one({"email": WORKER_EMAIL})
    assert worker, "worker demo user not seeded"

    gig = {
        "gig_id": gig_id,
        "title": "TEST_Worker Pay Fixture Gig",
        "status": "in_progress",
        "date": now.date().isoformat(),
        "created_at": now.isoformat(),
        "hourly_rate": 25.0,
        "pay_type": "hourly",
    }
    _mdb.gigs.insert_one(gig)

    clock_in = now - timedelta(hours=3)
    clock_out = now - timedelta(hours=1)
    acc = {
        "acceptance_id": acc_id,
        "gig_id": gig_id,
        "worker_id": worker["user_id"],
        "worker_name": worker.get("name") or "Worker Demo",
        "accepted_at": clock_in.isoformat(),
        "clock_in_at": clock_in.isoformat(),
        "clock_out_at": clock_out.isoformat(),
        "hours_worked": 2.0,
        "pay_rate_applied": 25.0,
        "pay_type_applied": "hourly",
        "earnings": 50.0,
        "timesheet_approved": False,
    }
    _mdb.gig_acceptances.insert_one(acc)

    yield {"gig_id": gig_id, "acceptance_id": acc_id, "worker_id": worker["user_id"], "amount": 50.0}

    # cleanup
    _mdb.gigs.delete_many({"gig_id": gig_id})
    _mdb.gig_acceptances.delete_many({"acceptance_id": acc_id})
    _mdb.ledger_entries.delete_many({"source_acceptance_id": acc_id})
    _mdb.notifications.delete_many({"gig_id": gig_id})


# ---------------- approve-timesheet ----------------
class TestApproveTimesheet:
    def test_approve_timesheet(self, admin_session, seeded_fixture):
        gid = seeded_fixture["gig_id"]
        aid = seeded_fixture["acceptance_id"]
        r = admin_session.post(
            f"{API}/gigs/{gid}/acceptances/{aid}/approve-timesheet",
            json={},
            timeout=20,
        )
        assert r.status_code == 200, f"approve-timesheet failed: {r.status_code} {r.text}"
        data = r.json()
        assert data.get("timesheet_approved") is True
        # verify DB stamp
        doc = _mdb.gig_acceptances.find_one({"acceptance_id": aid})
        assert doc["timesheet_approved"] is True
        assert doc.get("timesheet_approved_at")


# ---------------- worker-payments listing ----------------
class TestWorkerPaymentsList:
    def test_list_unpaid_shows_fixture(self, admin_session, seeded_fixture):
        r = admin_session.get(f"{API}/admin/worker-payments?status=unpaid", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data and "summary" in data
        items = [i for i in data["items"] if i["acceptance_id"] == seeded_fixture["acceptance_id"]]
        assert len(items) == 1, f"fixture not in unpaid list; got {len(data['items'])} items"
        it = items[0]
        assert it["amount"] == 50.0
        assert it["paid_at"] is None
        assert it["worker_id"] == seeded_fixture["worker_id"]
        s = data["summary"]
        assert s["unpaid_count"] >= 1
        assert s["unpaid_total"] >= 50.0
        assert s["workers_owed"] >= 1

    def test_filter_paid_excludes_unpaid(self, admin_session, seeded_fixture):
        r = admin_session.get(f"{API}/admin/worker-payments?status=paid", timeout=20)
        assert r.status_code == 200
        ids = [i["acceptance_id"] for i in r.json()["items"]]
        assert seeded_fixture["acceptance_id"] not in ids


# ---------------- mark-paid + ledger + notification ----------------
class TestMarkPaid:
    def test_mark_paid_creates_ledger_and_notification(self, admin_session, seeded_fixture):
        aid = seeded_fixture["acceptance_id"]
        wid = seeded_fixture["worker_id"]
        r = admin_session.post(
            f"{API}/admin/worker-payments/mark-paid",
            json={
                "acceptance_ids": [aid],
                "payout_method": "zelle",
                "payout_reference": "TX1",
            },
            timeout=20,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        paid_ids = [p["acceptance_id"] for p in data["paid"]]
        assert aid in paid_ids
        # DB stamp
        doc = _mdb.gig_acceptances.find_one({"acceptance_id": aid})
        assert doc.get("paid_at")
        assert doc.get("payout_method") == "zelle"
        assert doc.get("payout_reference") == "TX1"
        # Ledger entry
        entry = _mdb.ledger_entries.find_one({"source_acceptance_id": aid})
        assert entry, "ledger entry not created"
        assert entry.get("source") == "worker_payout"
        assert entry.get("category") == "payroll"
        assert abs(float(entry.get("amount", 0)) - 50.0) < 0.01
        # Notification
        notif = _mdb.notifications.find_one({"user_id": wid, "title": {"$regex": "paid"}})
        assert notif, "worker notification not created"

    def test_ledger_endpoint_shows_entry(self, admin_session, seeded_fixture):
        r = admin_session.get(f"{API}/admin/ledger?category=payroll", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        entries = data.get("items") if isinstance(data, dict) else data
        assert entries is not None
        matches = [e for e in entries if e.get("source_acceptance_id") == seeded_fixture["acceptance_id"]]
        assert len(matches) == 1, f"expected 1 ledger entry, got {len(matches)}"
        assert matches[0].get("source") == "worker_payout"

    def test_mark_paid_idempotent(self, admin_session, seeded_fixture):
        aid = seeded_fixture["acceptance_id"]
        # second call: should skip as already-paid, no dup ledger
        before = _mdb.ledger_entries.count_documents({"source_acceptance_id": aid})
        r = admin_session.post(
            f"{API}/admin/worker-payments/mark-paid",
            json={"acceptance_ids": [aid]},
            timeout=20,
        )
        assert r.status_code == 200
        data = r.json()
        skipped_ids = [s["acceptance_id"] for s in data["skipped"]]
        assert aid in skipped_ids
        reasons = [s["reason"] for s in data["skipped"] if s["acceptance_id"] == aid]
        assert "already paid" in reasons
        after = _mdb.ledger_entries.count_documents({"source_acceptance_id": aid})
        assert before == after, "duplicate ledger entry created"

    def test_mark_paid_not_approved(self, admin_session):
        # random acceptance id → not approved / not found
        r = admin_session.post(
            f"{API}/admin/worker-payments/mark-paid",
            json={"acceptance_ids": [f"TEST_bogus_{uuid.uuid4().hex[:8]}"]},
            timeout=20,
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["skipped"]) == 1
        assert data["skipped"][0]["reason"] == "not approved"


# ---------------- lost-lead recovery ----------------
class TestLostLeadRecovery:
    @pytest.fixture(scope="class")
    def lead_id(self, admin_session, va_session):
        # create a lead via VA submit
        payload = {
            "prospect_name": f"TEST_Recovery_{uuid.uuid4().hex[:6]}",
            "prospect_phone": "5551230001",
            "prospect_email": f"test_recover_{uuid.uuid4().hex[:6]}@example.com",
            "prospect_address": "1 Test St",
            "service_type": "routine",
            "property_size": "2br",
            "preferred_datetime": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            "source": "referral",
        }
        r = va_session.post(f"{API}/va/leads", json=payload, timeout=20)
        assert r.status_code in (200, 201), f"lead create failed: {r.status_code} {r.text}"
        lid = r.json().get("lead_id") or r.json().get("lead", {}).get("lead_id")
        assert lid
        yield lid
        _mdb.va_leads.delete_many({"lead_id": lid})
        _mdb.commissions.delete_many({"lead_id": lid})
        _mdb.va_lead_activity.delete_many({"lead_id": lid})

    def test_move_to_lost_then_recover(self, admin_session, lead_id):
        # move to lost
        r = admin_session.put(f"{API}/pm/leads/{lead_id}/stage", json={"stage": "lost"}, timeout=20)
        assert r.status_code == 200, r.text
        lead = _mdb.va_leads.find_one({"lead_id": lead_id})
        assert lead["stage"] == "lost"

        # recover to quoted
        r = admin_session.put(f"{API}/pm/leads/{lead_id}/stage", json={"stage": "quoted"}, timeout=20)
        assert r.status_code == 200, f"lost->quoted failed: {r.status_code} {r.text}"
        assert _mdb.va_leads.find_one({"lead_id": lead_id})["stage"] == "quoted"

        # move to booked → commission revived as calculating
        r = admin_session.put(
            f"{API}/pm/leads/{lead_id}/stage",
            json={"stage": "booked", "job_value": 200.0},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        assert _mdb.va_leads.find_one({"lead_id": lead_id})["stage"] == "booked"

        comm = _mdb.commissions.find_one({"lead_id": lead_id})
        assert comm, "commission not created after booked"
        assert comm.get("status") == "calculating", f"expected calculating, got {comm.get('status')}"
