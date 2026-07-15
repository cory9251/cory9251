"""Iteration 80 — FRD Addendum B (Specialist Gigs + Interest Flow) backend regression."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://work-connect-147.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

WORKER_EMAIL = "worker.demo@hcobcleaners.com"
WORKER_PW = "WorkerDemo2026!"
ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PW = "HcobAdmin2026!"
TEST_GIG_ID = "gig_32b349ecf057"


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def worker():
    return _login(WORKER_EMAIL, WORKER_PW)


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN_EMAIL, ADMIN_PW)


# --- View tracking ---
def test_view_endpoint_silent(worker):
    r = worker.post(f"{API}/gigs/{TEST_GIG_ID}/view", timeout=15)
    assert r.status_code in (200, 204), f"unexpected {r.status_code} {r.text}"


def test_gig_detail_has_view_and_interest_enrichment(worker):
    r = worker.get(f"{API}/gigs/{TEST_GIG_ID}", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("view_count", 0) >= 1
    # interest_count may be 0 if withdraw test ran and left withdrawn — assert field present
    assert "interest_count" in data
    # my_interest may be None (withdrawn) or object
    assert "my_interest" in data


# --- Interest lifecycle ---
def test_interest_lifecycle_withdraw_reexpress(worker):
    # Ensure interest exists
    r = worker.post(
        f"{API}/gigs/{TEST_GIG_ID}/interest",
        json={"note": "backend test", "availability": "weekends"},
        timeout=15,
    )
    assert r.status_code in (200, 201), f"create interest failed: {r.status_code} {r.text}"

    # Duplicate — should update not duplicate
    r2 = worker.post(
        f"{API}/gigs/{TEST_GIG_ID}/interest",
        json={"note": "updated note", "availability": "weekdays"},
        timeout=15,
    )
    assert r2.status_code in (200, 201)

    detail = worker.get(f"{API}/gigs/{TEST_GIG_ID}").json()
    assert detail.get("my_interest") is not None
    before_count = detail.get("interest_count", 0)
    assert before_count >= 1

    # Withdraw
    r3 = worker.delete(f"{API}/gigs/{TEST_GIG_ID}/interest", timeout=15)
    assert r3.status_code in (200, 204)

    detail2 = worker.get(f"{API}/gigs/{TEST_GIG_ID}").json()
    assert detail2.get("interest_count", 0) == max(0, before_count - 1)
    assert detail2.get("my_interest") in (None, {})

    # Re-express to leave data for FE test
    r4 = worker.post(
        f"{API}/gigs/{TEST_GIG_ID}/interest",
        json={"note": "re-expressed for FE test", "availability": "flexible"},
        timeout=15,
    )
    assert r4.status_code in (200, 201)


# --- Admin interests queue ---
def test_admin_interests_queue(admin):
    r = admin.get(f"{API}/admin/gigs/{TEST_GIG_ID}/interests", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    # response could be a list or wrapped dict
    items = data if isinstance(data, list) else data.get("interests") or data.get("items") or []
    assert isinstance(items, list)
    # After the lifecycle test above, worker demo has re-expressed interest
    def _email(i):
        w = i.get("worker") or {}
        return (i.get("worker_email") or w.get("email") or i.get("email") or "").lower()
    def _name(i):
        w = i.get("worker") or {}
        return i.get("worker_name") or w.get("name") or i.get("name") or ""
    emails = [_email(i) for i in items]
    names = [_name(i) for i in items]
    assert any("worker.demo" in e for e in emails) or any("Worker Demo" in n for n in names), (
        f"Worker Demo not present in admin queue: {items}"
    )


# --- Specialist project validation ---
def test_specialist_gig_missing_photos_rejected(admin):
    payload = {
        "title": "ADDB-TEST invalid",
        "description": "missing photos",
        "posting_template": "specialist_project",
        "category": "specialty",
        "location_city": "Test",
        "location_state": "TX",
        "pay_mode": "flat",
        "pay_amount": 100,
        "date_mode": "tbd",
        "specialist_fields": {
            "photos": [],  # missing
            "condition_notes": "",  # missing
            "quantity": 400,
            "unit": "sq ft",
        },
    }
    r = admin.post(f"{API}/gigs", json=payload, timeout=15)
    assert r.status_code in (400, 422), f"expected 400/422 got {r.status_code} {r.text}"
    body = r.text.lower()
    assert "specialist" in body or "photo" in body or "condition" in body


# --- Normal gig create still works (regression) ---
def test_normal_gig_still_creatable(admin):
    payload = {
        "title": "ADDB-TEST normal regression gig",
        "description": "regression",
        "posting_template": "labor_shift",
        "category": "cleaning",
        "location": "Austin, TX",
        "location_city": "Austin",
        "location_state": "TX",
        "pay_amount": 120,
        "pay_rate": 120,
        "pay_type": "flat",
        "scheduled_date": "2026-02-15",
        "scheduled_time": "09:00",
        "estimated_hours": 4,
    }
    r = admin.post(f"{API}/gigs", json=payload, timeout=15)
    # Accept 200/201; if payload shape differs from what backend expects, capture failure detail
    assert r.status_code in (200, 201), f"normal gig create failed: {r.status_code} {r.text[:400]}"
    gid = r.json().get("id") or r.json().get("gig_id")
    if gid:
        # cleanup
        admin.delete(f"{API}/gigs/{gid}")
