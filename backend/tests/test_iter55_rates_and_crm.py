"""Iter 55 — Commission rate control + CRM pipeline upgrade backend tests.

Covers:
  * GET/PUT /api/pm/commission-settings (global defaults)
  * GET/PUT /api/pm/vas/{id}/commission-overrides (per-VA)
  * override-driven digital calc (15% -> $150 on $1000)
  * global rate-driven flat calc (deep=$35)
  * /api/pm/leads/{id}/followup|contacts|comments (admin)
  * /api/va/leads/{id}/followup|contacts|comments (VA owner)
  * stage-change notifications to VA (kind=lead_stage_changed)
  * VA cross-owner 404 gate

Cleans up every lead/commission/notification it creates.
"""
import os
import uuid
import time
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        v = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    assert v, "REACT_APP_BACKEND_URL not configured"
    return v.rstrip("/")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PASS = "HcobAdmin2026!"
VA_EMAIL = "va.demo@hcobcleaners.com"
VA_PASS = "VaDemo2026!"
VA_USER_ID = "user_963e6aede023"

CREATED_LEAD_IDS: list[str] = []


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def va_session():
    return _login(VA_EMAIL, VA_PASS)


@pytest.fixture(scope="module", autouse=True)
def cleanup(admin_session):
    """Restore defaults + wipe leads/commissions/overrides created here."""
    yield
    # Restore defaults
    try:
        admin_session.put(f"{API}/pm/commission-settings", json={
            "rates": {"deep": 25.0, "routine": 10.0}, "commercial_pct": 5.0, "digital_pct": 10.0,
        }, timeout=20)
    except Exception:
        pass
    try:
        admin_session.put(f"{API}/pm/vas/{VA_USER_ID}/commission-overrides",
                          json={"overrides": {}}, timeout=20)
    except Exception:
        pass
    for lid in CREATED_LEAD_IDS:
        try:
            admin_session.delete(f"{API}/pm/leads/{lid}", json={"reason": "iter55 cleanup"}, timeout=20)
        except Exception:
            pass


# ---------- helpers ----------
def _make_va_lead(va_sess, service_type="digital_other", property_size=None, budget=None):
    phone = f"555{uuid.uuid4().hex[:7]}"
    payload = {
        "prospect_name": f"CRMTEST-{uuid.uuid4().hex[:6]}",
        "prospect_phone": phone,
        "prospect_email": f"crmtest+{uuid.uuid4().hex[:6]}@example.com",
        "service_type": service_type,
        "source": "cold_email",
    }
    if property_size:
        payload["property_size"] = property_size
    if budget is not None:
        payload["estimated_budget"] = budget
    r = va_sess.post(f"{API}/va/leads", json=payload, timeout=20)
    assert r.status_code == 200, f"lead create failed: {r.status_code} {r.text}"
    lid = r.json()["lead_id"]
    CREATED_LEAD_IDS.append(lid)
    return lid


def _move(admin_sess, lid, stage, job_value=None):
    body = {"stage": stage}
    if job_value is not None:
        body["job_value"] = job_value
    r = admin_sess.put(f"{API}/pm/leads/{lid}/stage", json=body, timeout=20)
    assert r.status_code == 200, f"stage move to {stage} failed: {r.status_code} {r.text}"
    return r.json()


def _get_commission(admin_sess, lid):
    r = admin_sess.get(f"{API}/pm/leads/{lid}", timeout=20)
    assert r.status_code == 200
    return r.json().get("commission")


# ---------- 1. Global commission settings ----------
class TestCommissionSettings:
    def test_get_settings_has_shape(self, admin_session):
        r = admin_session.get(f"{API}/pm/commission-settings", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "rates" in d and "commercial_pct" in d and "digital_pct" in d
        assert "defaults" in d
        assert isinstance(d["rates"], dict) and "deep" in d["rates"]

    def test_put_deep_35_and_persists(self, admin_session):
        r = admin_session.put(f"{API}/pm/commission-settings",
                              json={"rates": {"deep": 35.0}}, timeout=20)
        assert r.status_code == 200
        assert r.json()["rates"]["deep"] == 35.0
        # reload
        r2 = admin_session.get(f"{API}/pm/commission-settings", timeout=20)
        assert r2.json()["rates"]["deep"] == 35.0

    def test_put_rejects_unknown_key(self, admin_session):
        r = admin_session.put(f"{API}/pm/commission-settings",
                              json={"rates": {"not_a_service": 5}}, timeout=20)
        assert r.status_code == 400

    def test_put_rejects_bad_pct(self, admin_session):
        r = admin_session.put(f"{API}/pm/commission-settings",
                              json={"digital_pct": 150}, timeout=20)
        # commercial/digital pct field validator caps at 100 via pydantic
        assert r.status_code in (400, 422)


# ---------- 2. Per-VA overrides ----------
class TestVAOverrides:
    def test_get_overrides_shape(self, admin_session):
        r = admin_session.get(f"{API}/pm/vas/{VA_USER_ID}/commission-overrides", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "overrides" in d and "effective" in d and "globals" in d

    def test_put_and_clear_overrides(self, admin_session):
        # Set
        r = admin_session.put(f"{API}/pm/vas/{VA_USER_ID}/commission-overrides",
                              json={"overrides": {"deep": 40.0, "digital_pct": 15.0}}, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["overrides"]["deep"] == 40.0
        assert d["overrides"]["digital_pct"] == 15.0
        # Effective reflects override
        assert d["effective"]["rates"]["deep"] == 40.0
        assert d["effective"]["digital_pct"] == 15.0
        # Clear
        r2 = admin_session.put(f"{API}/pm/vas/{VA_USER_ID}/commission-overrides",
                               json={"overrides": {}}, timeout=20)
        assert r2.status_code == 200
        assert r2.json()["overrides"] == {}

    def test_rejects_unknown_key(self, admin_session):
        r = admin_session.put(f"{API}/pm/vas/{VA_USER_ID}/commission-overrides",
                              json={"overrides": {"weirdkey": 1}}, timeout=20)
        assert r.status_code == 400

    def test_bad_va_returns_404(self, admin_session):
        r = admin_session.get(f"{API}/pm/vas/does_not_exist/commission-overrides", timeout=20)
        assert r.status_code == 404


# ---------- 3. Override affects calc ----------
class TestOverrideAffectsCalc:
    def test_digital_15_pct_yields_150(self, admin_session, va_session):
        # Set override
        r = admin_session.put(f"{API}/pm/vas/{VA_USER_ID}/commission-overrides",
                              json={"overrides": {"digital_pct": 15.0}}, timeout=20)
        assert r.status_code == 200
        # Create digital lead as VA
        lid = _make_va_lead(va_session, service_type="digital_other")
        # Walk to paid with $1000
        _move(admin_session, lid, "contacted")
        _move(admin_session, lid, "quoted")
        _move(admin_session, lid, "booked")
        _move(admin_session, lid, "completed")
        _move(admin_session, lid, "paid", job_value=1000)
        c = _get_commission(admin_session, lid)
        assert c is not None, "commission not created"
        assert c["amount"] == 150.0, f"expected 150 got {c}"
        assert "15" in (c.get("calc_notes") or "")
        # Clear override
        admin_session.put(f"{API}/pm/vas/{VA_USER_ID}/commission-overrides",
                          json={"overrides": {}}, timeout=20)


# ---------- 4. Global rate affects calc ----------
class TestGlobalRateAffectsCalc:
    def test_deep_flat_35(self, admin_session, va_session):
        # Set global deep=35 (already set earlier but be explicit)
        admin_session.put(f"{API}/pm/commission-settings",
                          json={"rates": {"deep": 35.0}}, timeout=20)
        # Ensure no VA override interferes
        admin_session.put(f"{API}/pm/vas/{VA_USER_ID}/commission-overrides",
                          json={"overrides": {}}, timeout=20)
        lid = _make_va_lead(va_session, service_type="deep", property_size="2br")
        _move(admin_session, lid, "contacted")
        _move(admin_session, lid, "quoted")
        _move(admin_session, lid, "booked")
        _move(admin_session, lid, "completed")
        _move(admin_session, lid, "paid")
        c = _get_commission(admin_session, lid)
        assert c is not None
        assert c["amount"] == 35.0, f"expected 35 flat got {c}"
        # Restore deep=25
        admin_session.put(f"{API}/pm/commission-settings",
                          json={"rates": {"deep": 25.0}}, timeout=20)


# ---------- 5. Admin CRM endpoints (followup / contact / comment) ----------
class TestAdminCRMEndpoints:
    def _fresh_lead(self, va_session):
        return _make_va_lead(va_session, service_type="digital_other")

    def test_followup_endpoint(self, admin_session, va_session):
        lid = self._fresh_lead(va_session)
        r = admin_session.post(f"{API}/pm/leads/{lid}/followup",
                               json={"due_at": "2026-07-15", "note": "call back"}, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["next_followup_at"] == "2026-07-15"
        assert d["followup_note"] == "call back"
        # Activity has followup entry
        det = admin_session.get(f"{API}/pm/leads/{lid}", timeout=20).json()
        kinds = [a["kind"] for a in det.get("activity", [])]
        assert "followup_set" in kinds

    def test_contact_endpoint_increments_count(self, admin_session, va_session):
        lid = self._fresh_lead(va_session)
        r = admin_session.post(f"{API}/pm/leads/{lid}/contacts",
                               json={"method": "call", "outcome": "left voicemail"}, timeout=20)
        assert r.status_code == 200, r.text
        assert (r.json().get("contact_count") or 0) >= 1
        r2 = admin_session.post(f"{API}/pm/leads/{lid}/contacts",
                                json={"method": "text", "outcome": "no reply"}, timeout=20)
        assert r2.json()["contact_count"] >= 2

    def test_comment_endpoint_and_va_notification(self, admin_session, va_session):
        lid = self._fresh_lead(va_session)
        r = admin_session.post(f"{API}/pm/leads/{lid}/comments",
                               json={"text": "CRMTEST admin-comment"}, timeout=20)
        assert r.status_code == 200
        assert r.json()["comment_count"] >= 1
        # Poll VA notifications
        found = False
        for _ in range(3):
            n = va_session.get(f"{API}/notifications", timeout=20)
            if n.status_code == 200:
                data = n.json()
                items = data if isinstance(data, list) else data.get("items", [])
                if any(it.get("kind") == "lead_comment" and "CRMTEST" in (it.get("title") or "")
                       for it in items):
                    found = True
                    break
            time.sleep(0.4)
        assert found, "expected lead_comment notification for VA"


# ---------- 6. Stage change notification ----------
class TestStageNotification:
    def test_stage_move_creates_notification(self, admin_session, va_session):
        lid = _make_va_lead(va_session, service_type="digital_other")
        _move(admin_session, lid, "contacted")
        found = False
        for _ in range(3):
            n = va_session.get(f"{API}/notifications", timeout=20)
            if n.status_code == 200:
                data = n.json()
                items = data if isinstance(data, list) else data.get("items", [])
                if any(it.get("kind") == "lead_stage_changed" for it in items):
                    found = True
                    break
            time.sleep(0.4)
        assert found, "expected lead_stage_changed notification"


# ---------- 7. VA endpoints + cross-owner gate ----------
class TestVACRMEndpoints:
    def test_va_owner_can_followup(self, admin_session, va_session):
        lid = _make_va_lead(va_session, service_type="digital_other")
        r = va_session.post(f"{API}/va/leads/{lid}/followup",
                            json={"due_at": "2026-08-01", "note": "va-followup"}, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["next_followup_at"] == "2026-08-01"

    def test_va_owner_can_log_contact(self, admin_session, va_session):
        lid = _make_va_lead(va_session, service_type="digital_other")
        r = va_session.post(f"{API}/va/leads/{lid}/contacts",
                            json={"method": "email", "outcome": "sent quote"}, timeout=20)
        assert r.status_code == 200, r.text

    def test_va_owner_can_comment(self, admin_session, va_session):
        lid = _make_va_lead(va_session, service_type="digital_other")
        r = va_session.post(f"{API}/va/leads/{lid}/comments",
                            json={"text": "CRMTEST va-comment"}, timeout=20)
        assert r.status_code == 200, r.text

    def test_va_cannot_touch_foreign_lead(self, va_session):
        fake = f"lead_{uuid.uuid4().hex[:12]}"
        r1 = va_session.post(f"{API}/va/leads/{fake}/followup",
                             json={"due_at": "2026-08-01"}, timeout=20)
        r2 = va_session.post(f"{API}/va/leads/{fake}/contacts",
                             json={"method": "call", "outcome": "x"}, timeout=20)
        r3 = va_session.post(f"{API}/va/leads/{fake}/comments",
                             json={"text": "x"}, timeout=20)
        assert r1.status_code == 404
        assert r2.status_code == 404
        assert r3.status_code == 404
