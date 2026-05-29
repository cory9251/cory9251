"""Tests for the new Admin Settings (Resend/Twilio creds) endpoints + blast regression."""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://work-connect-147.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@gigblast.com"
ADMIN_PASSWORD = "GigBlast2026!"

UNIQUE = uuid.uuid4().hex[:8]
WORKER_EMAIL = f"TEST_settings_worker_{UNIQUE}@example.com"
WORKER_PASSWORD = "Worker123!"

FAKE_RESEND_KEY = "re_FAKE_TEST_KEY_abcdef1234567890"
FAKE_RESEND_KEY_2 = "re_FAKE_TEST_KEY_zyxwvu0987654321"
FAKE_SENDER = "ops+test@example.com"
FAKE_TW_SID = "ACfaketestsid000000000000000aaaa1234"
FAKE_TW_TOKEN = "faketwiliotoken00000000000000abcd"
FAKE_TW_FROM = "+15555550100"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.text}"
    return s


@pytest.fixture(scope="module")
def worker_session():
    s = requests.Session()
    r = s.post(
        f"{API}/auth/register",
        json={"email": WORKER_EMAIL, "password": WORKER_PASSWORD, "name": "Settings Worker", "role": "worker"},
    )
    assert r.status_code == 200, f"worker register failed: {r.text}"
    return s


@pytest.fixture(scope="module", autouse=True)
def _reset_settings_at_end(admin_session):
    """Clear out any leftover settings after this module runs."""
    yield
    try:
        admin_session.put(
            f"{API}/admin/settings",
            json={
                "resend_api_key": "",
                "sender_email": "",
                "twilio_account_sid": "",
                "twilio_auth_token": "",
                "twilio_from_number": "",
            },
        )
    except Exception:
        pass


# ---- AuthZ -----------------------------------------------------------------
def test_settings_requires_auth():
    r = requests.get(f"{API}/admin/settings")
    assert r.status_code == 401


def test_settings_forbidden_for_worker(worker_session):
    r = worker_session.get(f"{API}/admin/settings")
    assert r.status_code == 403


def test_settings_put_forbidden_for_worker(worker_session):
    r = worker_session.put(f"{API}/admin/settings", json={"resend_api_key": "x"})
    assert r.status_code == 403


def test_settings_test_forbidden_for_worker(worker_session):
    r = worker_session.post(f"{API}/admin/settings/test", json={"channel": "email", "to": "x@y.com"})
    assert r.status_code == 403


# ---- GET masking + flags ---------------------------------------------------
def test_get_settings_shape_when_empty(admin_session):
    # Start by clearing
    admin_session.put(
        f"{API}/admin/settings",
        json={
            "resend_api_key": "",
            "sender_email": "",
            "twilio_account_sid": "",
            "twilio_auth_token": "",
            "twilio_from_number": "",
        },
    )
    r = admin_session.get(f"{API}/admin/settings")
    assert r.status_code == 200
    d = r.json()
    for k in ["resend_api_key", "twilio_account_sid", "twilio_auth_token"]:
        assert isinstance(d[k], dict)
        assert "has_value" in d[k] and "last4" in d[k]
        assert d[k]["has_value"] is False
        assert d[k]["last4"] == ""
    assert d["email_ready"] is False
    assert d["sms_ready"] is False


# ---- PUT save Resend + sender, then GET masks ------------------------------
def test_put_resend_then_get_shows_last4_and_ready(admin_session):
    r = admin_session.put(
        f"{API}/admin/settings",
        json={"resend_api_key": FAKE_RESEND_KEY, "sender_email": FAKE_SENDER},
    )
    assert r.status_code == 200, r.text

    r2 = admin_session.get(f"{API}/admin/settings")
    assert r2.status_code == 200
    d = r2.json()
    assert d["resend_api_key"]["has_value"] is True
    assert d["resend_api_key"]["last4"] == FAKE_RESEND_KEY[-4:]
    assert d["sender_email"] == FAKE_SENDER
    assert d["email_ready"] is True
    # Plain key should NEVER be returned
    assert FAKE_RESEND_KEY not in r2.text


def test_partial_update_omitted_field_unchanged(admin_session):
    # Update only sender_email; resend_api_key should NOT change
    new_sender = "new+sender@example.com"
    r = admin_session.put(f"{API}/admin/settings", json={"sender_email": new_sender})
    assert r.status_code == 200
    d = admin_session.get(f"{API}/admin/settings").json()
    assert d["sender_email"] == new_sender
    assert d["resend_api_key"]["has_value"] is True
    assert d["resend_api_key"]["last4"] == FAKE_RESEND_KEY[-4:]
    assert d["email_ready"] is True


def test_overwrite_resend_key_updates_last4(admin_session):
    r = admin_session.put(f"{API}/admin/settings", json={"resend_api_key": FAKE_RESEND_KEY_2})
    assert r.status_code == 200
    d = admin_session.get(f"{API}/admin/settings").json()
    assert d["resend_api_key"]["last4"] == FAKE_RESEND_KEY_2[-4:]


def test_clear_resend_with_empty_string(admin_session):
    r = admin_session.put(f"{API}/admin/settings", json={"resend_api_key": ""})
    assert r.status_code == 200
    d = admin_session.get(f"{API}/admin/settings").json()
    assert d["resend_api_key"]["has_value"] is False
    assert d["resend_api_key"]["last4"] == ""
    assert d["email_ready"] is False


# ---- Twilio SMS ready/clear ------------------------------------------------
def test_save_all_twilio_makes_sms_ready(admin_session):
    r = admin_session.put(
        f"{API}/admin/settings",
        json={
            "twilio_account_sid": FAKE_TW_SID,
            "twilio_auth_token": FAKE_TW_TOKEN,
            "twilio_from_number": FAKE_TW_FROM,
        },
    )
    assert r.status_code == 200
    d = admin_session.get(f"{API}/admin/settings").json()
    assert d["twilio_account_sid"]["has_value"] is True
    assert d["twilio_account_sid"]["last4"] == FAKE_TW_SID[-4:]
    assert d["twilio_auth_token"]["has_value"] is True
    assert d["twilio_auth_token"]["last4"] == FAKE_TW_TOKEN[-4:]
    assert d["twilio_from_number"] == FAKE_TW_FROM
    assert d["sms_ready"] is True
    # Plain values must not leak
    assert FAKE_TW_SID not in str(d)
    assert FAKE_TW_TOKEN not in str(d)


def test_clear_sid_and_token_resets_sms_ready(admin_session):
    r = admin_session.put(
        f"{API}/admin/settings",
        json={"twilio_account_sid": "", "twilio_auth_token": ""},
    )
    assert r.status_code == 200
    d = admin_session.get(f"{API}/admin/settings").json()
    assert d["twilio_account_sid"]["has_value"] is False
    assert d["twilio_auth_token"]["has_value"] is False
    assert d["sms_ready"] is False


# ---- /admin/settings/test --------------------------------------------------
def test_test_email_400_when_no_key(admin_session):
    admin_session.put(f"{API}/admin/settings", json={"resend_api_key": ""})
    r = admin_session.post(
        f"{API}/admin/settings/test",
        json={"channel": "email", "to": "anybody@example.com"},
    )
    assert r.status_code == 400
    assert "resend" in r.text.lower() or "api key" in r.text.lower()


def test_test_email_400_with_fake_key(admin_session):
    admin_session.put(
        f"{API}/admin/settings",
        json={"resend_api_key": FAKE_RESEND_KEY, "sender_email": FAKE_SENDER},
    )
    r = admin_session.post(
        f"{API}/admin/settings/test",
        json={"channel": "email", "to": "anybody@example.com"},
    )
    # Should fail gracefully with 400 (Resend rejects fake key), not crash 500
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
    assert "failed" in r.text.lower() or "email" in r.text.lower()


def test_test_sms_400_when_incomplete(admin_session):
    # Make sure twilio is empty
    admin_session.put(
        f"{API}/admin/settings",
        json={"twilio_account_sid": "", "twilio_auth_token": "", "twilio_from_number": ""},
    )
    r = admin_session.post(
        f"{API}/admin/settings/test",
        json={"channel": "sms", "to": "+15555550100"},
    )
    assert r.status_code == 400
    assert "twilio" in r.text.lower() or "incomplete" in r.text.lower()


# ---- Blast regression: uses DB key over env --------------------------------
def test_blast_uses_db_resend_key_and_degrades_gracefully(admin_session, worker_session):
    # 1. Save fake Resend creds
    r = admin_session.put(
        f"{API}/admin/settings",
        json={"resend_api_key": FAKE_RESEND_KEY, "sender_email": FAKE_SENDER},
    )
    assert r.status_code == 200

    # 2. Ensure worker has email (registered above -> has email)
    me = worker_session.get(f"{API}/auth/me").json()
    assert me.get("email")

    # 3. Create a gig
    gig_payload = {
        "title": f"TEST settings blast {UNIQUE}",
        "description": "Testing blast with DB-saved creds",
        "category": "labor",
        "location": "Remote",
        "pay_type": "hourly",
        "pay_rate": 25,
        "scheduled_date": "2026-12-31",
        "slots": 1,
    }
    rg = admin_session.post(f"{API}/gigs", json=gig_payload)
    assert rg.status_code == 200, rg.text
    gig_id = rg.json()["gig_id"]

    # 4. Blast email channel
    rb = admin_session.post(
        f"{API}/gigs/{gig_id}/blast", json={"channels": ["email"]}
    )
    assert rb.status_code == 200, rb.text
    body = rb.json()
    assert body["ok"] is True
    counts = body["counts"]
    # Fake key should make Resend reject -> email_failed incremented; no 500
    # Either the send threw (email_failed >=1) OR it returned skipped (then email=1 but neither acceptable since key IS set)
    assert counts["email"] + counts["email_failed"] >= 1
    # With a fake key, we expect at least one failure
    assert counts["email_failed"] >= 1, f"expected email_failed>=1, got {counts}"

    # 5. Cleanup gig
    admin_session.delete(f"{API}/gigs/{gig_id}")

    # 6. Clear the key
    admin_session.put(f"{API}/admin/settings", json={"resend_api_key": ""})
