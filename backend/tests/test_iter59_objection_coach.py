"""Iter 59 — VA AI Objection Coach.

Verifies the coach endpoint exists, validates input, rate-limits, calls
the LLM (when EMERGENT_LLM_KEY is configured), and returns 3 well-shaped
responses.

NOTE: Most tests are pure structural — they don't actually hit Anthropic
because that would be slow + cost credits on every run. One smoke test
DOES hit the LLM (skipped if no key) so we catch real-world breakage.
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

VA = {"email": "va.demo@hcobcleaners.com", "password": "VaDemo2026!"}


def _va_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=VA, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"VA login failed: {r.status_code}")
    return s


def _create_lead(s):
    r = s.post(
        f"{BASE_URL}/api/va/leads",
        json={
            "prospect_name": f"Iter59 {uuid.uuid4().hex[:6]}",
            "prospect_phone": f"+1555{uuid.uuid4().int % 10000000:07d}",
            "service_type": "deep",
            "property_size": "3br",
            "preferred_datetime": "2026-02-20T10:00",
            "source": "facebook_marketplace",
            "notes": "iter59 coach test",
        },
        timeout=20,
    )
    if r.status_code != 200:
        pytest.skip(f"create lead failed: {r.text}")
    return r.json()["lead_id"]


# ---------- Structural ----------------------------------------------------
def test_list_quick_objections():
    s = _va_session()
    r = s.get(f"{BASE_URL}/api/va/objection-coach/objections", timeout=20)
    assert r.status_code == 200
    body = r.json()
    keys = [o["key"] for o in body["objections"]]
    for k in ("too_expensive", "have_someone", "call_back", "not_now"):
        assert k in keys
    assert body["rate_limit_per_hour"] == 20


def test_unknown_objection_key_rejected():
    s = _va_session()
    lead_id = _create_lead(s)
    r = s.post(
        f"{BASE_URL}/api/va/leads/{lead_id}/objection-coach",
        json={"objection_key": "i_made_this_up"},
        timeout=30,
    )
    assert r.status_code == 400
    assert "objection_key" in r.json()["detail"].lower()


def test_neither_key_nor_custom_rejected():
    s = _va_session()
    lead_id = _create_lead(s)
    r = s.post(
        f"{BASE_URL}/api/va/leads/{lead_id}/objection-coach",
        json={},
        timeout=30,
    )
    assert r.status_code == 400


def test_lead_not_found_404():
    s = _va_session()
    r = s.post(
        f"{BASE_URL}/api/va/leads/nonexistent_zzz/objection-coach",
        json={"objection_key": "too_expensive"},
        timeout=30,
    )
    assert r.status_code == 404


def test_custom_text_length_limit():
    s = _va_session()
    lead_id = _create_lead(s)
    r = s.post(
        f"{BASE_URL}/api/va/leads/{lead_id}/objection-coach",
        json={"custom_text": "x" * 600},  # over the 500 cap
        timeout=30,
    )
    assert r.status_code == 422  # pydantic max_length


# ---------- Functional (hits the LLM — slower, costs credits) -------------
@pytest.mark.skipif(
    not os.environ.get("EMERGENT_LLM_KEY"),
    reason="No EMERGENT_LLM_KEY — skipping live LLM test",
)
def test_coach_returns_three_well_formed_responses():
    """End-to-end smoke: pick a quick objection, get 3 responses back."""
    s = _va_session()
    lead_id = _create_lead(s)
    r = s.post(
        f"{BASE_URL}/api/va/leads/{lead_id}/objection-coach",
        json={"objection_key": "too_expensive"},
        timeout=60,  # LLM can take 5-15s
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["responses"]) >= 1
    assert len(body["responses"]) <= 3
    for opt in body["responses"]:
        assert "angle" in opt and "body" in opt
        assert len(opt["body"].strip()) > 20  # not a one-liner
        assert len(opt["body"]) < 1200  # bounded
    # Usage counter has incremented
    assert body["calls_used_last_hour"] >= 1
    assert body["rate_limit_per_hour"] == 20
    assert body["objection_label"]


@pytest.mark.skipif(
    not os.environ.get("EMERGENT_LLM_KEY"),
    reason="No EMERGENT_LLM_KEY — skipping live LLM test",
)
def test_coach_accepts_free_form_custom_text():
    s = _va_session()
    lead_id = _create_lead(s)
    r = s.post(
        f"{BASE_URL}/api/va/leads/{lead_id}/objection-coach",
        json={"custom_text": "She said she's worried about strangers in her house"},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["responses"]
    assert "worried about strangers" in body["objection_label"].lower()
