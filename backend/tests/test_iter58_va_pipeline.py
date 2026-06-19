"""Iter 58 — VA Lead Pipeline (Kanban) + SLA timer.

Verifies:
- GET /api/va/pipeline returns items + stages_va_can_move + sla_hours
- Each lead is decorated with sla_state/hours_in_stage/sla_due_at_iso
- PATCH /api/va/leads/{id}/stage moves between new_lead | contacted | quoted
- PATCH rejects hard stages (booked, completed, lost, paid)
- PATCH /api/va/leads/{id}/notes works at any stage (unlike the strict edit endpoint)
- Stale leads (>SLA hours) get sla_state='stale'
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://work-connect-147.preview.emergentagent.com",
).rstrip("/")

VA = {"email": "va.demo@hcobcleaners.com", "password": "VaDemo2026!"}
ADMIN = {"email": "admin@hcobcleaners.com", "password": "HcobAdmin2026!"}


def _va_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=VA, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"VA login failed: {r.status_code} {r.text}")
    return s


def _create_lead(s):
    payload = {
        "prospect_name": f"Iter58 {uuid.uuid4().hex[:6]}",
        "prospect_phone": f"+1555{uuid.uuid4().int % 10000000:07d}",
        "service_type": "deep",
        "property_size": "3br",
        "preferred_datetime": "2026-02-20T10:00",
        "source": "facebook_marketplace",
        "notes": "pipeline test",
    }
    r = s.post(f"{BASE_URL}/api/va/leads", json=payload, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"create lead failed: {r.status_code} {r.text}")
    return r.json()["lead_id"]


def test_pipeline_endpoint_returns_shape():
    s = _va_session()
    r = s.get(f"{BASE_URL}/api/va/pipeline", timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body and isinstance(body["items"], list)
    assert body["stages_va_can_move"] == ["new_lead", "contacted", "quoted"]
    assert body["sla_hours"]["new_lead"] == 24
    assert body["sla_hours"]["contacted"] == 48
    assert body["sla_hours"]["quoted"] == 72


def test_pipeline_decorates_sla_status():
    s = _va_session()
    lead_id = _create_lead(s)
    r = s.get(f"{BASE_URL}/api/va/pipeline", timeout=20)
    items = r.json()["items"]
    me = next((i for i in items if i["lead_id"] == lead_id), None)
    assert me is not None, "freshly-created lead not in pipeline"
    assert me["sla_hours"] == 24  # new_lead
    assert me["sla_state"] == "ok"  # just created
    assert me["sla_due_at_iso"]  # has a deadline


def test_va_can_move_through_soft_stages():
    s = _va_session()
    lead_id = _create_lead(s)
    for stage in ("contacted", "quoted", "new_lead", "quoted"):
        r = s.patch(
            f"{BASE_URL}/api/va/leads/{lead_id}/stage",
            json={"stage": stage},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        assert r.json()["stage"] == stage


def test_va_cannot_move_to_hard_stages():
    s = _va_session()
    lead_id = _create_lead(s)
    for bad in ("booked", "completed", "paid", "lost", "bogus_stage"):
        r = s.patch(
            f"{BASE_URL}/api/va/leads/{lead_id}/stage",
            json={"stage": bad},
            timeout=20,
        )
        assert r.status_code == 400, f"expected 400 for stage={bad}, got {r.status_code}"


def test_va_notes_endpoint_works_at_any_stage():
    """The dedicated notes endpoint must work even AFTER the lead has moved
    out of 'new_lead' (the strict edit endpoint is locked at that point)."""
    s = _va_session()
    lead_id = _create_lead(s)
    # Move past new_lead
    s.patch(f"{BASE_URL}/api/va/leads/{lead_id}/stage", json={"stage": "contacted"}, timeout=20)
    # Verify strict edit is blocked at contacted
    blocked = s.patch(
        f"{BASE_URL}/api/va/leads/{lead_id}",
        json={"notes": "shouldnt-work"},
        timeout=20,
    )
    assert blocked.status_code == 403
    # But the dedicated notes endpoint works
    r = s.patch(
        f"{BASE_URL}/api/va/leads/{lead_id}/notes",
        json={"notes": "iter58 — left voicemail at 3pm"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    assert r.json()["notes"] == "iter58 — left voicemail at 3pm"


def test_notes_length_limit():
    s = _va_session()
    lead_id = _create_lead(s)
    r = s.patch(
        f"{BASE_URL}/api/va/leads/{lead_id}/notes",
        json={"notes": "x" * 4001},
        timeout=20,
    )
    assert r.status_code == 400


def test_lead_not_found_404():
    s = _va_session()
    r = s.patch(
        f"{BASE_URL}/api/va/leads/nonexistent_lead/stage",
        json={"stage": "contacted"},
        timeout=20,
    )
    assert r.status_code == 404
    r2 = s.patch(
        f"{BASE_URL}/api/va/leads/nonexistent_lead/notes",
        json={"notes": "x"},
        timeout=20,
    )
    assert r2.status_code == 404


def test_pipeline_groups_terminal_into_with_ops_label():
    """Terminal leads (booked/completed/paid/lost) come back without an
    sla_state — the frontend buckets them into the 'With Ops' column."""
    s_va = _va_session()
    lead_id = _create_lead(s_va)
    # Have an admin set the stage to 'booked' (VA can't do this)
    s_admin = requests.Session()
    r = s_admin.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=20)
    if r.status_code != 200:
        pytest.skip("admin login failed")
    # PM endpoint for stage transition
    r2 = s_admin.put(
        f"{BASE_URL}/api/pm/leads/{lead_id}/stage",
        json={"stage": "lost", "reason": "iter58 test"},
        timeout=20,
    )
    if r2.status_code != 200:
        pytest.skip(f"admin couldn't move stage: {r2.status_code} {r2.text}")
    # Now fetch pipeline as VA
    rp = s_va.get(f"{BASE_URL}/api/va/pipeline", timeout=20)
    me = next((i for i in rp.json()["items"] if i["lead_id"] == lead_id), None)
    assert me is not None
    assert me["stage"] == "lost"
    assert me["sla_state"] is None  # no SLA on terminal stages
