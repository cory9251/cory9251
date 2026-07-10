"""Iteration 74 — Worker name resolution in /api/admin/worker-payments.

Bug: page showed literal 'Worker' when acceptance.worker_name was empty/missing.
Fix: batch-resolve names live from db.users (priority: live user.name → snapshot
worker_name → email → 'Worker'); mark-paid resolves same way and passes into
log_worker_payout_expense so ledger entry description/vendor carry real name.
"""
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://work-connect-147.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@hcobcleaners.com", "password": "HcobAdmin2026!"}
WORKER_EMAIL = "worker.demo@hcobcleaners.com"

_mc = MongoClient("mongodb://localhost:27017")
_mdb = _mc[os.environ.get("DB_NAME", "test_database")]


def _login(session, creds):
    r = session.post(f"{API}/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    _login(s, ADMIN)
    return s


@pytest.fixture(scope="module")
def worker():
    w = _mdb.users.find_one({"email": WORKER_EMAIL})
    assert w, "worker demo not seeded"
    return w


@pytest.fixture(scope="module")
def seeded(worker):
    """Two acceptances: one with worker_name='', one with worker_name field omitted."""
    now = datetime.now(timezone.utc)
    gig_id_a = f"TEST_gig_iter74A_{uuid.uuid4().hex[:8]}"
    gig_id_b = f"TEST_gig_iter74B_{uuid.uuid4().hex[:8]}"
    acc_empty = f"TEST_accE_{uuid.uuid4().hex[:8]}"
    acc_missing = f"TEST_accM_{uuid.uuid4().hex[:8]}"

    for gid in (gig_id_a, gig_id_b):
        _mdb.gigs.insert_one({
            "gig_id": gid,
            "title": f"TEST_Iter74 Name Resolution Gig ({gid[-4:]})",
            "status": "in_progress",
            "date": now.date().isoformat(),
            "created_at": now.isoformat(),
            "hourly_rate": 20.0,
            "pay_type": "hourly",
        })

    clock_in = now - timedelta(hours=4)
    clock_out = now - timedelta(hours=1)
    base = {
        "worker_id": worker["user_id"],
        "accepted_at": clock_in.isoformat(),
        "clock_in_at": clock_in.isoformat(),
        "clock_out_at": clock_out.isoformat(),
        "hours_worked": 3.0,
        "paid_hours": 3.0,
        "pay_rate_applied": 20.0,
        "pay_type_applied": "hourly",
        "earnings": 60.0,
        "timesheet_approved": True,
        "timesheet_approved_at": now.isoformat(),
    }
    # Row A: worker_name = "" (empty)
    _mdb.gig_acceptances.insert_one({**base, "gig_id": gig_id_a, "acceptance_id": acc_empty, "worker_name": ""})
    # Row B: worker_name omitted entirely
    _mdb.gig_acceptances.insert_one({**base, "gig_id": gig_id_b, "acceptance_id": acc_missing})

    yield {
        "gig_id_a": gig_id_a,
        "gig_id_b": gig_id_b,
        "acc_empty": acc_empty,
        "acc_missing": acc_missing,
        "worker_id": worker["user_id"],
        "expected_name": worker.get("name") or "Worker Demo",
    }

    _mdb.gigs.delete_many({"gig_id": {"$in": [gig_id_a, gig_id_b]}})
    _mdb.gig_acceptances.delete_many({"acceptance_id": {"$in": [acc_empty, acc_missing]}})
    _mdb.ledger_entries.delete_many({"source_acceptance_id": {"$in": [acc_empty, acc_missing]}})
    _mdb.notifications.delete_many({"gig_id": {"$in": [gig_id_a, gig_id_b]}})


class TestWorkerNameResolution:
    def test_list_resolves_real_name_for_empty_and_missing(self, admin_session, seeded):
        r = admin_session.get(f"{API}/admin/worker-payments?status=unpaid", timeout=20)
        assert r.status_code == 200, r.text
        items = {i["acceptance_id"]: i for i in r.json()["items"]}
        assert seeded["acc_empty"] in items
        assert seeded["acc_missing"] in items
        for aid in (seeded["acc_empty"], seeded["acc_missing"]):
            wn = items[aid]["worker_name"]
            assert wn == seeded["expected_name"], (
                f"acceptance {aid} worker_name={wn!r} — expected {seeded['expected_name']!r}"
            )
            assert wn.lower() != "worker", f"{aid} fell back to literal 'Worker'"
            assert wn.strip(), f"{aid} worker_name empty"

    def test_mark_paid_writes_real_name_to_ledger(self, admin_session, seeded):
        aid = seeded["acc_empty"]
        r = admin_session.post(
            f"{API}/admin/worker-payments/mark-paid",
            json={"acceptance_ids": [aid], "payout_method": "zelle", "payout_reference": "IT74A"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        assert aid in [p["acceptance_id"] for p in r.json()["paid"]]

        entry = _mdb.ledger_entries.find_one({"source_acceptance_id": aid})
        assert entry, "ledger entry not created"
        expected = seeded["expected_name"]
        desc = entry.get("description") or ""
        vendor = entry.get("vendor") or entry.get("payee") or ""
        assert expected in desc, f"description missing real name: {desc!r}"
        assert "Worker payout" in desc
        assert expected in vendor or vendor == expected, f"vendor missing real name: {vendor!r}"

    def test_mark_paid_idempotent_no_dup_ledger(self, admin_session, seeded):
        aid = seeded["acc_empty"]
        before = _mdb.ledger_entries.count_documents({"source_acceptance_id": aid})
        r = admin_session.post(
            f"{API}/admin/worker-payments/mark-paid",
            json={"acceptance_ids": [aid]},
            timeout=20,
        )
        assert r.status_code == 200
        data = r.json()
        skipped = {s["acceptance_id"]: s["reason"] for s in data["skipped"]}
        assert skipped.get(aid) == "already paid"
        after = _mdb.ledger_entries.count_documents({"source_acceptance_id": aid})
        assert before == after, "duplicate ledger entry created on re-run"

    def test_ledger_endpoint_shows_real_name(self, admin_session, seeded):
        r = admin_session.get(f"{API}/admin/ledger?category=payroll", timeout=20)
        assert r.status_code == 200
        data = r.json()
        entries = data.get("items") if isinstance(data, dict) else data
        matches = [e for e in entries if e.get("source_acceptance_id") == seeded["acc_empty"]]
        assert len(matches) == 1
        assert seeded["expected_name"] in (matches[0].get("description") or "")

    def test_summary_totals_coherent(self, admin_session, seeded):
        r = admin_session.get(f"{API}/admin/worker-payments", timeout=20)
        assert r.status_code == 200
        s = r.json()["summary"]
        # totals should be numeric and non-negative
        assert isinstance(s["unpaid_total"], (int, float)) and s["unpaid_total"] >= 0
        assert isinstance(s["paid_total"], (int, float)) and s["paid_total"] >= 0
        assert s["unpaid_count"] >= 1  # acc_missing still unpaid
        assert s["workers_owed"] >= 1
