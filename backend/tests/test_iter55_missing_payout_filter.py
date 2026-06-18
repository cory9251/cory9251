"""Iter 55 — "Missing payout" admin filter + dashboard stat.

After Iter 54 surfaced the payout-collection feature, the engagement
follow-up: admin needs an at-a-glance "who can't I pay?" view.

Verifies:
- GET /api/admin/workers?payout_status=missing returns only workers without
  payout_method on file (filters out workers who have set one)
- GET /api/admin/workers?payout_status=set is the inverse
- GET /api/admin/stats returns a `missing_payout` integer count
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

ADMIN = {"email": "admin@hcobcleaners.com", "password": "HcobAdmin2026!"}
WORKER = {"email": "worker.demo@hcobcleaners.com", "password": "WorkerDemo2026!"}


def _admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code}")
    return s


def _worker_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=WORKER, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Worker login failed: {r.status_code}")
    return s


def test_stats_includes_missing_payout_count():
    s = _admin_session()
    r = s.get(f"{BASE_URL}/api/admin/stats", timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "missing_payout" in body
    assert isinstance(body["missing_payout"], int)
    assert body["missing_payout"] >= 0


def test_workers_filter_missing_payout():
    """Setting worker.demo's payout, then verifying:
    - missing list does NOT include them
    - set list DOES include them
    - clearing puts them back in the missing list
    """
    admin = _admin_session()
    worker = _worker_session()

    # Set payout
    r = worker.put(
        f"{BASE_URL}/api/profile",
        json={"payout_method": "zelle", "payout_handle": "(555) 111-2222"},
        timeout=20,
    )
    assert r.status_code == 200, r.text

    # missing list must NOT include this worker
    missing = admin.get(
        f"{BASE_URL}/api/admin/workers?payout_status=missing", timeout=20
    ).json()
    emails = [w["email"] for w in missing]
    assert WORKER["email"] not in emails, "Worker with payout set is still in missing list"

    # set list MUST include them
    set_list = admin.get(
        f"{BASE_URL}/api/admin/workers?payout_status=set", timeout=20
    ).json()
    set_emails = [w["email"] for w in set_list]
    assert WORKER["email"] in set_emails, "Worker with payout set is missing from 'set' list"

    # Clear and re-check
    worker.put(f"{BASE_URL}/api/profile", json={"payout_method": ""}, timeout=20)
    missing_again = admin.get(
        f"{BASE_URL}/api/admin/workers?payout_status=missing", timeout=20
    ).json()
    assert WORKER["email"] in [w["email"] for w in missing_again]


def test_payout_filter_invalid_value_is_ignored():
    """Garbage value should just return the unfiltered list (no 400)."""
    s = _admin_session()
    r = s.get(f"{BASE_URL}/api/admin/workers?payout_status=garbage", timeout=20)
    assert r.status_code == 200
    # Without filter, count should be >= the missing-only count
    all_workers = s.get(f"{BASE_URL}/api/admin/workers", timeout=20).json()
    assert len(r.json()) == len(all_workers), (
        "Garbage payout_status should be treated as no-filter"
    )
