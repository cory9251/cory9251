"""Iter45 - Worker Agreement gate tests.

Verifies the 3-rule signed checklist a worker must agree to every time they
request a gig. Uses the existing test worker fixture seeded by the main agent
(worker.demo@hcobcleaners.com / WorkerDemo2026!).
"""
import os
import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://work-connect-147.preview.emergentagent.com",
).rstrip("/")

WORKER = {"email": "worker.demo@hcobcleaners.com", "password": "WorkerDemo2026!"}
ADMIN = {"email": "admin@hcobcleaners.com", "password": "HcobAdmin2026!"}

CANONICAL_RULES = [
    "No-shows on first gigs are an automatic deletion from the platform.",
    "You will be professional when on your gig site.",
    "You must clock in on your shift, or you may not be paid.",
]


def _login(creds):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Cannot login as {creds['email']}: {r.status_code} {r.text[:200]}")
    return s


@pytest.fixture(scope="module")
def worker_session():
    return _login(WORKER)


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def open_gig_id(worker_session, admin_session):
    """Find an open gig the worker has not yet requested. If none exists,
    create one as admin. Returns the gig_id."""
    # 1. find a gig where worker has no acceptance
    r = worker_session.get(f"{BASE_URL}/api/gigs?status=open", timeout=20)
    if r.status_code != 200:
        pytest.skip("Cannot list gigs")
    gigs = r.json()
    if not isinstance(gigs, list):
        gigs = gigs.get("items", [])
    for g in gigs:
        gid = g["gig_id"]
        # check if already accepted/requested
        if not g.get("my_acceptance"):
            return gid
    # All gigs already requested — create a fresh one
    r = admin_session.post(
        f"{BASE_URL}/api/gigs",
        json={
            "title": "Iter45 fresh test gig",
            "description": "Test",
            "category": "cleaning",
            "location": "Baltimore",
            "scheduled_at": "2027-01-15T15:00:00+00:00",
            "scheduled_local": "2027-01-15T10:00",
            "pay_rate": 20,
            "pay_type": "hourly",
            "slots": 5,
            "duration_hours": 4,
        },
        timeout=20,
    )
    if r.status_code in (200, 201):
        return r.json()["gig_id"]
    pytest.skip(f"Cannot create gig: {r.status_code} {r.text[:200]}")


def test_get_agreement_rules(worker_session):
    r = worker_session.get(f"{BASE_URL}/api/worker/agreement-rules", timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == "v1"
    assert body["rules"] == CANONICAL_RULES


def test_accept_rejects_missing_body(worker_session, open_gig_id):
    r = worker_session.post(f"{BASE_URL}/api/gigs/{open_gig_id}/accept", json={}, timeout=20)
    assert r.status_code == 422, r.text


def test_accept_rejects_wrong_typed_name(worker_session, open_gig_id):
    r = worker_session.post(
        f"{BASE_URL}/api/gigs/{open_gig_id}/accept",
        json={"typed_name": "Wrong Person", "agreed_rules": CANONICAL_RULES, "version": "v1"},
        timeout=20,
    )
    assert r.status_code == 400
    assert "name" in r.json()["detail"].lower()


def test_accept_rejects_tampered_rules(worker_session, open_gig_id):
    r = worker_session.post(
        f"{BASE_URL}/api/gigs/{open_gig_id}/accept",
        json={
            "typed_name": "Worker Demo",
            "agreed_rules": ["Custom rule I wrote"],
            "version": "v1",
        },
        timeout=20,
    )
    assert r.status_code == 400
    assert "rules" in r.json()["detail"].lower()


def test_accept_rejects_stale_version(worker_session, open_gig_id):
    r = worker_session.post(
        f"{BASE_URL}/api/gigs/{open_gig_id}/accept",
        json={
            "typed_name": "Worker Demo",
            "agreed_rules": CANONICAL_RULES,
            "version": "v0",
        },
        timeout=20,
    )
    assert r.status_code == 400
    assert "version" in r.json()["detail"].lower()


def test_accept_succeeds_with_valid_agreement_and_writes_audit(
    worker_session, open_gig_id
):
    """Whitespace + lowercase normalization on typed_name. Audit doc must
    contain IP, version, and verbatim rules."""
    r = worker_session.post(
        f"{BASE_URL}/api/gigs/{open_gig_id}/accept",
        json={
            "typed_name": "  worker demo  ",
            "agreed_rules": CANONICAL_RULES,
            "version": "v1",
        },
        timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "requested"
    assert body["agreement_id"].startswith("agr_")

    # Audit endpoint must show this agreement with IP, version, rules verbatim
    r2 = worker_session.get(f"{BASE_URL}/api/worker/my-agreements", timeout=20)
    assert r2.status_code == 200
    items = r2.json()["items"]
    assert any(a["agreement_id"] == body["agreement_id"] for a in items)
    latest = next(a for a in items if a["agreement_id"] == body["agreement_id"])
    assert latest["rules"] == CANONICAL_RULES
    assert latest["version"] == "v1"
    assert latest["ip"]
    assert latest["worker_name"] == "Worker Demo"


def test_duplicate_accept_blocked(worker_session, open_gig_id):
    """Second accept on the same gig must fail with 'already' error, not
    re-trigger the agreement gate (since agreement is checked AFTER the
    duplicate check actually... let's verify the message reflects 'already')."""
    r = worker_session.post(
        f"{BASE_URL}/api/gigs/{open_gig_id}/accept",
        json={
            "typed_name": "Worker Demo",
            "agreed_rules": CANONICAL_RULES,
            "version": "v1",
        },
        timeout=20,
    )
    assert r.status_code == 400
    assert "already" in r.json()["detail"].lower()


def test_my_agreements_endpoint_requires_worker_role(admin_session):
    """Admin (non-worker) should be 403 on /worker/my-agreements."""
    r = admin_session.get(f"{BASE_URL}/api/worker/my-agreements", timeout=20)
    assert r.status_code == 403
