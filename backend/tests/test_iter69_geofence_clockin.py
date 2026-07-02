"""Iter69: Geofenced + schedule-restricted worker clock-in.

Covers all 5 backend scenarios from the review request:
 1. schedule gate (too early)  → 400
 2. geofence block (too far)   → 403 with distance in the message
 3. geofence pass (on site)    → 200 { location_verified: True }
 4. GPS-denied → 200 flagged
 5. ungeocodable address → 200 flagged, location_verified false
Plus:
 - gig create response includes site_lat/site_lng
 - update_gig re-geocodes when address_line changes
 - worker with only 'requested' acceptance cannot see address_line / site_lat / site_lng
 - clock-out still works after geofenced clock-in
 - worker without acceptance is blocked from clock-in (400)
"""
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

def _load_backend_url() -> str:
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    # Fallback to frontend/.env
    env_path = "/app/frontend/.env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not set")


BASE_URL = _load_backend_url() + "/api"

ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PASSWORD = "HcobAdmin2026!"
WORKER_EMAIL = "worker.demo@hcobcleaners.com"
WORKER_PASSWORD = "WorkerDemo2026!"
WORKER_USER_ID = "user_1e39f9bf376e"

REAL_ADDRESS = "100 N Charles St, Baltimore, MD"
SITE_LAT, SITE_LNG = 39.2908, -76.6157
ON_SITE = (39.2905, -76.6155)   # ~35m
FAR_AWAY = (38.9072, -77.0369)  # DC ~56km
GARBAGE_ADDRESS = f"zzz fake qqq 00000 nowhere-{uuid.uuid4().hex[:6]}"

CREATED_GIG_IDS: list[str] = []
CREATED_ACCEPTANCE_IDS: list[str] = []


# ---------- fixtures ----------
def _login(session: requests.Session, email: str, password: str) -> dict:
    r = session.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def admin_session() -> requests.Session:
    s = requests.Session()
    _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)
    return s


@pytest.fixture(scope="module")
def worker_session() -> requests.Session:
    s = requests.Session()
    _login(s, WORKER_EMAIL, WORKER_PASSWORD)
    return s


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _create_gig(admin_session, *, address_line: str, scheduled_offset_seconds: int, title_prefix: str = "GEOTEST") -> dict:
    """Space out Nominatim calls by 1.2s (rate limit 1/s)."""
    time.sleep(1.2)
    sched = datetime.now(timezone.utc) + timedelta(seconds=scheduled_offset_seconds)
    payload = {
        "title": f"{title_prefix}-{uuid.uuid4().hex[:6]}",
        "description": "Automated geofence clock-in test",
        "category": "cleaning",
        "location": "Baltimore, MD",
        "address_line": address_line,
        "scheduled_date": sched.strftime("%a %b %d, %I:%M %p UTC"),
        "scheduled_at": _iso(sched),
        "pay_rate": 25.0,
        "pay_type": "hourly",
        "slots": 2,
    }
    r = admin_session.post(f"{BASE_URL}/gigs", json=payload, timeout=30)
    assert r.status_code == 200, f"create_gig failed: {r.status_code} {r.text}"
    g = r.json()
    CREATED_GIG_IDS.append(g["gig_id"])
    return g


def _assign_worker(admin_session, gig_id: str, worker_id: str = WORKER_USER_ID) -> dict:
    r = admin_session.post(f"{BASE_URL}/gigs/{gig_id}/assign", json={"worker_id": worker_id}, timeout=15)
    assert r.status_code == 200, f"assign failed: {r.status_code} {r.text}"
    return r.json()


# ---------- 1. schedule gate ----------
class TestScheduleGate:
    def test_future_gig_clockin_too_early(self, admin_session, worker_session):
        gig = _create_gig(admin_session, address_line=REAL_ADDRESS, scheduled_offset_seconds=3600)
        assert gig.get("site_lat") is not None and gig.get("site_lng") is not None, "should geocode real address on create"
        _assign_worker(admin_session, gig["gig_id"])
        r = worker_session.post(
            f"{BASE_URL}/gigs/{gig['gig_id']}/clock-in",
            json={"lat": ON_SITE[0], "lng": ON_SITE[1], "accuracy": 10},
            timeout=15,
        )
        assert r.status_code == 400, f"expected 400 too-early, got {r.status_code}: {r.text}"
        assert "too early" in r.text.lower(), r.text


# ---------- 2. geofence block ----------
class TestGeofenceBlock:
    def test_far_from_site_returns_403_with_distance(self, admin_session, worker_session):
        gig = _create_gig(admin_session, address_line=REAL_ADDRESS, scheduled_offset_seconds=-3600)
        assert gig.get("site_lat") is not None
        _assign_worker(admin_session, gig["gig_id"])
        r = worker_session.post(
            f"{BASE_URL}/gigs/{gig['gig_id']}/clock-in",
            json={"lat": FAR_AWAY[0], "lng": FAR_AWAY[1], "accuracy": 10},
            timeout=15,
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"
        body = r.text.lower()
        assert "too far from the job site" in body, body
        # Should include a distance number
        assert any(ch.isdigit() for ch in body), "distance number should be in error message"


# ---------- 3. geofence pass ----------
class TestGeofencePass:
    def test_on_site_verified_and_persisted(self, admin_session, worker_session):
        gig = _create_gig(admin_session, address_line=REAL_ADDRESS, scheduled_offset_seconds=-3600)
        _assign_worker(admin_session, gig["gig_id"])
        r = worker_session.post(
            f"{BASE_URL}/gigs/{gig['gig_id']}/clock-in",
            json={"lat": ON_SITE[0], "lng": ON_SITE[1], "accuracy": 8},
            timeout=15,
        )
        assert r.status_code == 200, f"expected 200 verified, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["location_verified"] is True
        assert data["location_flagged"] is False
        assert isinstance(data["distance_m"], (int, float))
        assert data["distance_m"] < 250

        # verify acceptance persistence via admin (acceptances embedded in gig detail)
        acc_r = admin_session.get(f"{BASE_URL}/gigs/{gig['gig_id']}", timeout=15)
        assert acc_r.status_code == 200
        gig_detail = acc_r.json()
        rows = list(gig_detail.get("acceptances") or []) + list(gig_detail.get("pending_requests") or [])
        my = next((a for a in rows if a.get("worker_id") == WORKER_USER_ID), None)
        assert my is not None
        assert my["location_verified"] is True
        assert my["clock_in_lat"] == ON_SITE[0]
        assert my["clock_in_lng"] == ON_SITE[1]
        assert my["clock_in_distance_m"] < 250
        CREATED_ACCEPTANCE_IDS.append(my["acceptance_id"])

    def test_clockout_still_works_after_geofenced_clockin(self, worker_session):
        # relies on the previous test having clocked-in the last GEOTEST gig
        gig_id = CREATED_GIG_IDS[-1]
        r = worker_session.post(f"{BASE_URL}/gigs/{gig_id}/clock-out", json={}, timeout=15)
        assert r.status_code == 200, f"clock-out failed: {r.status_code} {r.text}"
        data = r.json()
        assert data.get("ok") is True or "hours" in data or "clock_out_at" in data


# ---------- 4. GPS denied flag ----------
class TestGpsDeniedFlag:
    def test_no_gps_but_real_address_flagged(self, admin_session, worker_session):
        gig = _create_gig(admin_session, address_line=REAL_ADDRESS, scheduled_offset_seconds=-3600)
        _assign_worker(admin_session, gig["gig_id"])
        r = worker_session.post(
            f"{BASE_URL}/gigs/{gig['gig_id']}/clock-in",
            json={"location_error": "User denied Geolocation"},
            timeout=15,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        assert data["location_flagged"] is True
        assert data["location_verified"] is False

        acc_r = admin_session.get(f"{BASE_URL}/gigs/{gig['gig_id']}", timeout=15)
        gig_detail = acc_r.json()
        rows = list(gig_detail.get("acceptances") or []) + list(gig_detail.get("pending_requests") or [])
        my = next((a for a in rows if a.get("worker_id") == WORKER_USER_ID), None)
        assert my["location_flagged"] is True
        assert my.get("location_flag_reason")
        assert "denied" in my["location_flag_reason"].lower() or "gps" in my["location_flag_reason"].lower()


# ---------- 5. ungeocodable address flag ----------
class TestUngeocodableFlag:
    def test_garbage_address_still_allows_flagged_clockin(self, admin_session, worker_session):
        gig = _create_gig(admin_session, address_line=GARBAGE_ADDRESS, scheduled_offset_seconds=-3600)
        assert gig.get("site_lat") is None, "garbage address should not geocode"
        _assign_worker(admin_session, gig["gig_id"])
        r = worker_session.post(
            f"{BASE_URL}/gigs/{gig['gig_id']}/clock-in",
            json={"lat": ON_SITE[0], "lng": ON_SITE[1], "accuracy": 10},
            timeout=15,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        assert data["location_flagged"] is True
        assert data["location_verified"] is False


# ---------- 6. update_gig re-geocode ----------
class TestUpdateReGeocode:
    def test_edit_address_line_regeocodes(self, admin_session):
        gig = _create_gig(admin_session, address_line=GARBAGE_ADDRESS + " v2", scheduled_offset_seconds=7200)
        assert gig.get("site_lat") is None
        time.sleep(1.2)
        r = admin_session.put(
            f"{BASE_URL}/gigs/{gig['gig_id']}",
            json={"address_line": REAL_ADDRESS},
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        updated = r.json()
        # some endpoints return {ok: true} — refetch to be safe
        r2 = admin_session.get(f"{BASE_URL}/gigs/{gig['gig_id']}", timeout=15)
        assert r2.status_code == 200
        gig2 = r2.json()
        assert gig2.get("site_lat") is not None, f"re-geocode did not populate site_lat: {gig2}"
        assert gig2.get("site_lng") is not None


# ---------- 7. security: requested worker cannot see address / coords ----------
class TestAddressPrivacyForRequestedWorker:
    def test_requested_worker_cannot_see_coords(self, admin_session, worker_session):
        gig = _create_gig(admin_session, address_line=REAL_ADDRESS, scheduled_offset_seconds=7200)
        gid = gig["gig_id"]
        # Worker sends a request (not approved) — supply the full agreement body.
        agreement = {
            "typed_name": "Worker Demo",
            "agreed_rules": [
                "No-shows on first gigs are an automatic deletion from the platform.",
                "You will be professional when on your gig site.",
                "You must clock in on your shift, or you may not be paid.",
            ],
            "version": "v1",
        }
        r = worker_session.post(f"{BASE_URL}/gigs/{gid}/accept", json=agreement, timeout=15)
        assert r.status_code in (200, 201), f"request-to-accept failed: {r.status_code} {r.text}"

        # Detail GET as worker
        r2 = worker_session.get(f"{BASE_URL}/gigs/{gid}", timeout=15)
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert "address_line" not in body or not body.get("address_line"), f"address leaked: {body.get('address_line')}"
        assert body.get("site_lat") in (None, ""), f"site_lat leaked: {body.get('site_lat')}"
        assert body.get("site_lng") in (None, ""), f"site_lng leaked: {body.get('site_lng')}"

        # Also check the gigs list (worker feed)
        r3 = worker_session.get(f"{BASE_URL}/gigs", timeout=15)
        assert r3.status_code == 200
        listing = r3.json()
        entries = listing if isinstance(listing, list) else listing.get("gigs", [])
        mine = next((g for g in entries if g.get("gig_id") == gid), None)
        if mine is not None:
            assert not mine.get("address_line"), f"list leaked address_line: {mine}"
            assert mine.get("site_lat") in (None, ""), f"list leaked site_lat: {mine}"
            assert mine.get("site_lng") in (None, ""), f"list leaked site_lng: {mine}"


# ---------- 8. worker w/o acceptance is blocked ----------
class TestNoAcceptanceBlocked:
    def test_worker_without_acceptance_gets_400(self, admin_session, worker_session):
        gig = _create_gig(admin_session, address_line=REAL_ADDRESS, scheduled_offset_seconds=-3600)
        # Do NOT assign / accept
        r = worker_session.post(
            f"{BASE_URL}/gigs/{gig['gig_id']}/clock-in",
            json={"lat": ON_SITE[0], "lng": ON_SITE[1]},
            timeout=15,
        )
        assert r.status_code == 400, f"expected 400 no-acceptance, got {r.status_code}: {r.text}"
        assert "approved" in r.text.lower() or "request" in r.text.lower()


# ---------- teardown: clean up GEOTEST gigs + acceptances ----------
def teardown_module(module):
    s = requests.Session()
    try:
        _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)
    except Exception:
        return
    for gid in CREATED_GIG_IDS:
        try:
            s.delete(f"{BASE_URL}/gigs/{gid}", timeout=15)
        except Exception:
            pass
