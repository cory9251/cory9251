"""
Iter (Jan 2026) — VA Digital Services backend tests
Tests: digital-settings GET/PUT, VA digital lead creation, property_size guard,
pm digital category filter, admin assign-va, pipeline stages, /va/projects.
"""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PWD = "HcobAdmin2026!"
VA_EMAIL = "va.demo@hcobcleaners.com"
VA_PWD = "VaDemo2026!"

DIGITAL_FAMILY = {
    "product_sourcing", "web_development", "app_development",
    "social_media_marketing", "seo_content", "graphic_design", "digital_other"
}


def _login(email, pwd):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd}, timeout=30)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text[:200]}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN_EMAIL, ADMIN_PWD)


@pytest.fixture(scope="module")
def va():
    return _login(VA_EMAIL, VA_PWD)


# ---------- digital-settings (VA read-only) ----------
def test_va_digital_settings_get(va):
    r = va.get(f"{BASE_URL}/api/va/digital-settings", timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "commission_pct" in j
    assert isinstance(j["commission_pct"], (int, float))
    assert "service_types" in j and isinstance(j["service_types"], list)
    assert set(j["service_types"]) >= DIGITAL_FAMILY


# ---------- PM digital-settings GET/PUT persists ----------
def test_pm_digital_settings_get_and_put_persists(admin):
    r = admin.get(f"{BASE_URL}/api/pm/digital-settings", timeout=20)
    assert r.status_code == 200
    original = float(r.json()["commission_pct"])

    r2 = admin.put(f"{BASE_URL}/api/pm/digital-settings", json={"commission_pct": 15}, timeout=20)
    assert r2.status_code == 200, r2.text
    assert float(r2.json()["commission_pct"]) == 15.0

    r3 = admin.get(f"{BASE_URL}/api/pm/digital-settings", timeout=20)
    assert float(r3.json()["commission_pct"]) == 15.0

    restore = original if original else 10
    r4 = admin.put(f"{BASE_URL}/api/pm/digital-settings", json={"commission_pct": restore}, timeout=20)
    assert r4.status_code == 200
    assert float(r4.json()["commission_pct"]) == float(restore)


# ---------- property_size guard ----------
def test_va_create_cleaning_lead_missing_property_size_returns_400(va):
    phone = f"555{int(time.time())%10000000:07d}"
    payload = {
        "prospect_name": "TEST_iter_cleaning_missing_ps",
        "prospect_phone": phone,
        "service_type": "deep",
        "source": "referral",
    }
    r = va.post(f"{BASE_URL}/api/va/leads", json=payload, timeout=20)
    assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text[:200]}"
    body = r.text.lower()
    assert "property size" in body or "property_size" in body


def test_va_create_digital_lead_no_property_size_required(va):
    phone = f"556{int(time.time()*1000)%10000000:07d}"
    payload = {
        "prospect_name": "TEST_iter_digital_lead",
        "prospect_phone": phone,
        "service_type": "web_development",
        "estimated_budget": 2000,
        "source": "referral",
    }
    r = va.post(f"{BASE_URL}/api/va/leads", json=payload, timeout=20)
    assert r.status_code in (200, 201), r.text
    data = r.json()
    lead_id = data.get("lead_id") or data.get("id") or (data.get("lead", {}) or {}).get("lead_id")
    assert lead_id, f"no lead id in response: {data}"


@pytest.fixture(scope="module")
def digital_lead_id(va):
    phone = f"557{int(time.time()*1000)%10000000:07d}"
    payload = {
        "prospect_name": "TEST_iter_digital_pipeline",
        "prospect_phone": phone,
        "service_type": "web_development",
        "estimated_budget": 2000,
        "source": "referral",
    }
    r = va.post(f"{BASE_URL}/api/va/leads", json=payload, timeout=20)
    assert r.status_code in (200, 201), r.text
    d = r.json()
    lid = d.get("lead_id") or d.get("id") or (d.get("lead", {}) or {}).get("lead_id")
    assert lid
    return lid


# ---------- pm category filter ----------
def _extract_leads(data):
    if isinstance(data, list):
        return data
    return data.get("leads") or data.get("items") or []


def test_pm_leads_category_digital_only(admin, digital_lead_id):
    r = admin.get(f"{BASE_URL}/api/pm/leads?category=digital", timeout=20)
    assert r.status_code == 200
    leads = _extract_leads(r.json())
    assert isinstance(leads, list) and len(leads) > 0
    ids = {l.get("lead_id") or l.get("id") for l in leads}
    assert digital_lead_id in ids, f"digital lead not found in digital category (ids sample: {list(ids)[:5]})"
    stypes = {l.get("service_type") for l in leads}
    non_digital = stypes - DIGITAL_FAMILY - {None}
    assert not non_digital, f"non-digital leaked into digital category: {non_digital}"


def test_pm_leads_category_cleaning_excludes_digital(admin, digital_lead_id):
    r = admin.get(f"{BASE_URL}/api/pm/leads?category=cleaning", timeout=20)
    assert r.status_code == 200
    leads = _extract_leads(r.json())
    ids = {l.get("lead_id") or l.get("id") for l in leads}
    assert digital_lead_id not in ids
    stypes = {l.get("service_type") for l in leads}
    leak = stypes & DIGITAL_FAMILY
    assert not leak, f"digital leaked into cleaning: {leak}"


# ---------- pipeline stages + commission on paid ----------
def test_admin_move_digital_lead_through_stages_and_pay(admin, digital_lead_id):
    for stg in ["contacted", "quoted", "booked", "completed"]:
        r = admin.put(
            f"{BASE_URL}/api/pm/leads/{digital_lead_id}/stage",
            json={"stage": stg}, timeout=20
        )
        assert r.status_code in (200, 204), f"stage {stg} failed: {r.status_code} {r.text[:200]}"

    r = admin.put(
        f"{BASE_URL}/api/pm/leads/{digital_lead_id}/stage",
        json={"stage": "paid", "job_value": 3000}, timeout=20
    )
    assert r.status_code in (200, 204), f"paid stage failed: {r.status_code} {r.text[:200]}"

    r2 = admin.get(f"{BASE_URL}/api/pm/leads/{digital_lead_id}", timeout=20)
    assert r2.status_code == 200
    lead = r2.json()
    # digital_pct commission at 10% of 3000 = 300
    # Commission may be under nested payout or commission field — poll commissions endpoint
    # Check on lead payload first
    comm_amt = None
    for k in ("commission_amount", "commission"):
        v = lead.get(k)
        if isinstance(v, (int, float)):
            comm_amt = float(v)
            break
        if isinstance(v, dict) and v.get("amount") is not None:
            comm_amt = float(v["amount"])
            break
    if comm_amt is None:
        # Look up commissions collection via API if there is one
        rc = admin.get(f"{BASE_URL}/api/pm/commissions", timeout=20)
        if rc.status_code == 200:
            items = _extract_leads(rc.json())
            match = next((c for c in items if c.get("lead_id") == digital_lead_id), None)
            if match:
                comm_amt = float(match.get("amount") or 0)
    assert comm_amt is not None, f"no commission found for {digital_lead_id}; lead keys={list(lead.keys())}"
    assert abs(comm_amt - 300.0) < 0.01, f"commission mismatch: expected 300.0 got {comm_amt}"


# ---------- assign-va + /va/projects ----------
def test_admin_assign_delivery_va_and_va_projects_lists(admin, va, digital_lead_id):
    r = admin.get(f"{BASE_URL}/api/pm/vas", timeout=20)
    assert r.status_code == 200, r.text
    vas = r.json().get("items", [])
    va_demo = next((v for v in vas if v.get("email") == VA_EMAIL), None)
    assert va_demo, f"VA demo not found in {len(vas)} VAs"
    va_id = va_demo.get("user_id")
    assert va_id

    r2 = admin.post(
        f"{BASE_URL}/api/pm/leads/{digital_lead_id}/assign-va",
        json={"va_user_id": va_id}, timeout=20
    )
    assert r2.status_code in (200, 204), f"assign-va failed: {r2.status_code} {r2.text[:200]}"

    r3 = va.get(f"{BASE_URL}/api/va/projects", timeout=20)
    assert r3.status_code == 200, r3.text
    j = r3.json()
    items = j if isinstance(j, list) else j.get("items") or j.get("projects") or []
    ids = {p.get("lead_id") or p.get("id") for p in items}
    assert digital_lead_id in ids, f"assigned lead not in /va/projects; got sample {list(ids)[:5]}"


def test_va_can_fetch_assigned_digital_lead_detail(va, digital_lead_id):
    r = va.get(f"{BASE_URL}/api/va/leads/{digital_lead_id}", timeout=20)
    assert r.status_code == 200, f"VA cannot fetch assigned lead: {r.status_code} {r.text[:200]}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
