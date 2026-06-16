"""Iter 38: VA Commission analytics endpoint."""
import os
import time
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PASSWORD = "HcobAdmin2026!"


def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


def test_analytics_default_shape():
    admin = admin_session()
    r = admin.get(f"{API}/pm/analytics")
    assert r.status_code == 200, r.text
    body = r.json()
    # Required keys
    for k in ("velocity", "funnel", "leaks", "params"):
        assert k in body, f"missing {k}"
    # Default window = 6 months
    assert len(body["velocity"]) == 6
    # Each velocity row shape
    for row in body["velocity"]:
        for k in ("period", "paid", "owner_approved", "pm_approved", "pending", "rejected", "total", "count"):
            assert k in row, f"velocity row missing {k}: {row}"
        # Sanity: total = paid + owner_approved + pm_approved + pending (rounded)
        expected = round(
            row["paid"] + row["owner_approved"] + row["pm_approved"] + row["pending"], 2
        )
        assert abs(row["total"] - expected) < 0.01, row


def test_analytics_funnel_monotonic():
    """Each funnel stage must be >= the next (paid ≤ booked ≤ quoted ≤ contacted ≤ leads)."""
    admin = admin_session()
    r = admin.get(f"{API}/pm/analytics")
    assert r.status_code == 200
    for v in r.json()["funnel"]:
        assert v["leads"] >= v["contacted"], v
        assert v["contacted"] >= v["quoted"], v
        assert v["quoted"] >= v["booked"], v
        assert v["booked"] >= v["paid"], v
        # Conversion = paid / leads
        if v["leads"]:
            expected = round((v["paid"] / v["leads"]) * 100, 1)
            assert abs(v["conversion"] - expected) < 0.1, v


def test_analytics_leak_threshold_filters():
    admin = admin_session()
    # leak_days=1 should return >= number of leads stuck >= 7 days
    r1 = admin.get(f"{API}/pm/analytics", params={"leak_days": 1})
    r7 = admin.get(f"{API}/pm/analytics", params={"leak_days": 7})
    r21 = admin.get(f"{API}/pm/analytics", params={"leak_days": 21})
    assert r1.status_code == r7.status_code == r21.status_code == 200
    c1 = len(r1.json()["leaks"])
    c7 = len(r7.json()["leaks"])
    c21 = len(r21.json()["leaks"])
    # More days threshold ⇒ fewer or equal leaks
    assert c1 >= c7 >= c21, f"expected monotone {c1} >= {c7} >= {c21}"


def test_analytics_months_clamped():
    admin = admin_session()
    # months gets clamped to 1..12
    r = admin.get(f"{API}/pm/analytics", params={"months": 999})
    assert r.status_code == 200
    assert len(r.json()["velocity"]) == 12
    r = admin.get(f"{API}/pm/analytics", params={"months": 0})
    assert r.status_code == 200
    assert len(r.json()["velocity"]) == 1


def test_analytics_requires_admin():
    """Worker accounts must NOT be able to read analytics."""
    ts = int(time.time() * 1000)
    s = requests.Session()
    r = s.post(
        f"{API}/auth/register",
        json={
            "email": f"iter38_{ts}@example.com",
            "password": "Test1234!",
            "name": "Iter38 Worker",
        },
    )
    assert r.status_code == 200, r.text
    worker = r.json()
    try:
        r = s.get(f"{API}/pm/analytics")
        assert r.status_code == 403, f"worker shouldn't access analytics, got {r.status_code}"
    finally:
        admin = admin_session()
        admin.delete(f"{API}/admin/workers/{worker['user_id']}")
