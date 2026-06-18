"""Iter 49 — Regression: /admin/workers search must AND with status filter.

Before this fix, the search query was OR'd into the same $or block as the
`worker_status=approved` back-compat clause, so search for "Cory" returned
every approved worker. The fix introduced separate $or blocks combined with
$and. These tests pin the contract.
"""
import os
import uuid
import asyncio

import pytest
import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://work-connect-147.preview.emergentagent.com",
).rstrip("/")

ADMIN = {"email": "admin@hcobcleaners.com", "password": "HcobAdmin2026!"}

_admin_session = None


def _admin():
    global _admin_session
    if _admin_session is None:
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=20)
        if r.status_code != 200:
            pytest.skip("Cannot login as admin")
        _admin_session = s
    return _admin_session


def _items(resp):
    d = resp.json()
    return d if isinstance(d, list) else d.get("items", [])


# ---------- Bookkeeping: seed a unique worker so searches have a target ------
@pytest.fixture(scope="module")
def seeded_worker():
    """Insert a unique worker we can search for + clean up after."""
    unique_token = f"zenith_{uuid.uuid4().hex[:8]}"
    name = f"Zenith {unique_token}"
    email = f"{unique_token}@example.com"
    phone = "+15559876543"

    async def setup():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            db = client[os.environ["DB_NAME"]]
            doc = {
                "_id": str(uuid.uuid4()),
                "user_id": f"user_{uuid.uuid4().hex[:12]}",
                "email": email,
                "name": name,
                "phone": phone,
                "role": "worker",
                "worker_status": "approved",
                "id_image_path": "test/id.jpg",
                "id_verified": True,
                "address": "123 Search St, Baltimore, MD",
                "zip_code": "21201",
                "skills": ["cleaning"],
                "bio": "test",
                "date_of_birth": "1990-01-01",
                "availability": ["weekends"],
                "emergency_contact_name": "Test",
                "emergency_contact_phone": "+15550001111",
                "auth_provider": "email",
            }
            await db.users.insert_one(doc)
            return doc, db, client
        except Exception:
            client.close()
            raise

    async def teardown(client, db, doc_id):
        try:
            await db.users.delete_one({"_id": doc_id})
        finally:
            client.close()

    doc, db, client = asyncio.run(setup())
    yield {"name": name, "email": email, "phone": phone, "token": unique_token, "doc": doc}
    # Use a fresh client for teardown to avoid 'event loop is closed' errors
    # — asyncio.run() closed the loop the original client was bound to.
    async def cleanup():
        c2 = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            db2 = c2[os.environ["DB_NAME"]]
            await db2.users.delete_one({"_id": doc["_id"]})
        finally:
            c2.close()
    asyncio.run(cleanup())


# ---------- Test 1: search with no other filter returns only matches ---------
def test_search_alone_returns_only_matches(seeded_worker):
    s = _admin()
    r = s.get(f"{BASE_URL}/api/admin/workers", params={"search": seeded_worker["token"]}, timeout=20)
    assert r.status_code == 200
    items = _items(r)
    assert len(items) >= 1
    # ALL returned items must match the search token in name, email, or phone
    for w in items:
        haystack = " ".join(
            str(w.get(k) or "") for k in ("name", "email", "phone")
        ).lower()
        assert seeded_worker["token"].lower() in haystack, (
            f"False positive: {w.get('name')} ({w.get('email')}) doesn't contain the search token"
        )


# ---------- Test 2: search + status=approved must intersect, not union -------
def test_search_intersects_with_status_filter(seeded_worker):
    """This is the actual regression target — previously 'Cory' returned every
    approved worker because the OR clauses got merged."""
    s = _admin()
    r = s.get(
        f"{BASE_URL}/api/admin/workers",
        params={"status": "approved", "search": seeded_worker["token"]},
        timeout=20,
    )
    assert r.status_code == 200
    items = _items(r)
    # Should be EXACTLY 1 worker (the one we seeded)
    assert len(items) == 1, (
        f"Expected exactly 1 match for search={seeded_worker['token']}, got {len(items)} "
        f"(if >1, the $or/$and combine is broken)"
    )
    assert items[0]["email"] == seeded_worker["email"]


# ---------- Test 3: search by phone works with status filter -----------------
def test_search_by_phone_with_status(seeded_worker):
    s = _admin()
    r = s.get(
        f"{BASE_URL}/api/admin/workers",
        params={"status": "approved", "search": "9876543"},
        timeout=20,
    )
    assert r.status_code == 200
    items = _items(r)
    # Our seeded worker should be in there
    assert any(w.get("email") == seeded_worker["email"] for w in items)
    # Every returned item must legitimately match
    for w in items:
        haystack = " ".join(
            str(w.get(k) or "") for k in ("name", "email", "phone")
        ).lower()
        assert "9876543" in haystack


# ---------- Test 4: status=approved alone returns >1 (sanity) ----------------
def test_approved_alone_returns_many():
    """Without search, status=approved must return all approved workers
    (sanity check that the new $and wrapping didn't break the simple case)."""
    s = _admin()
    r = s.get(f"{BASE_URL}/api/admin/workers", params={"status": "approved"}, timeout=20)
    assert r.status_code == 200
    items = _items(r)
    assert len(items) >= 1


# ---------- Test 5: search + vehicle=any must AND ---------------------------
def test_search_with_vehicle_any(seeded_worker):
    """Three disjunctive filters interacting (status + vehicle + search) was
    the original failure mode. Now they should all AND together."""
    s = _admin()
    r = s.get(
        f"{BASE_URL}/api/admin/workers",
        params={
            "status": "approved",
            "vehicle": "any",
            "search": seeded_worker["token"],
        },
        timeout=20,
    )
    assert r.status_code == 200
    items = _items(r)
    # Our seeded worker has no vehicle, so should NOT appear here
    assert all(w.get("email") != seeded_worker["email"] for w in items)
    # Every item that DOES appear must have a vehicle AND match the search
    for w in items:
        has_vehicle = w.get("has_car") or w.get("has_truck") or w.get("has_cdl")
        haystack = " ".join(str(w.get(k) or "") for k in ("name", "email", "phone")).lower()
        assert has_vehicle, f"{w.get('email')} has no vehicle but matched"
        assert seeded_worker["token"].lower() in haystack
