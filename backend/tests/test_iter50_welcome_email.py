"""Iter 50 — Founder welcome email cadence (Cory's welcome).

Verifies the welcome email handler is wired into both register paths
(email + Google OAuth) and that the rendered HTML carries Cory's voice.
Tests don't require actual Resend delivery — they patch the send hook so
they pass in preview where no real Resend key is configured.
"""
import asyncio
import os
import uuid
from unittest.mock import patch

import pytest
import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://work-connect-147.preview.emergentagent.com",
).rstrip("/")


# ---------- Test 1: rendered HTML contains Cory's introduction ---------------
def test_welcome_email_html_contains_founder_message():
    """Direct call to the helper — verify the body has Cory's intro, the
    'finish your profile' CTA, and the founder framing."""
    import sys
    sys.path.insert(0, "/app/backend")
    from notifications import send_worker_welcome_email

    captured = {}

    async def fake_send_user_email(user, *, kind, subject, body_html, cta_label=None, cta_url=None):
        captured["kind"] = kind
        captured["subject"] = subject
        captured["body_html"] = body_html
        captured["cta_label"] = cta_label
        captured["cta_url"] = cta_url
        return True

    with patch("notifications._send_user_email", side_effect=fake_send_user_email):
        result = asyncio.run(
            send_worker_welcome_email({"name": "Alice Tester", "email": "alice@example.com"})
        )

    assert result is True
    assert captured["kind"] == "welcome_worker"
    assert "Alice" in captured["subject"]
    assert "welcome" in captured["subject"].lower()
    body = captured["body_html"].lower()
    # Cory's voice
    assert "cory" in body
    assert "founder" in body
    assert "the hcob network" in body
    assert "structure the unstructured" in body
    assert "baltimore" in body
    # CTA pushes them to finish their profile
    assert captured["cta_label"] == "Finish your profile"
    assert "/crew/profile" in captured["cta_url"]
    # Personalized first-name greeting
    assert "alice" in body  # "Hey Alice"


# ---------- Test 2: empty name falls back gracefully -------------------------
def test_welcome_email_handles_empty_name():
    import sys
    sys.path.insert(0, "/app/backend")
    from notifications import send_worker_welcome_email

    captured = {}

    async def fake_send(user, *, kind, subject, body_html, cta_label=None, cta_url=None):
        captured["subject"] = subject
        captured["body_html"] = body_html
        return True

    with patch("notifications._send_user_email", side_effect=fake_send):
        asyncio.run(
            send_worker_welcome_email({"name": "", "email": "noname@example.com"})
        )
    # Should fall back to "there" so we never address an empty string
    assert "there" in captured["body_html"].lower()
    assert "there" in captured["subject"].lower()


# ---------- Test 3: register endpoint triggers the welcome email -------------
def test_register_endpoint_triggers_welcome_email():
    """The register() function must call send_worker_welcome_email after the
    user is created. We verify this by inspecting the source — robust across
    test ordering and doesn't require an actual Resend send."""
    import sys
    sys.path.insert(0, "/app/backend")
    from routes import auth as auth_module
    import inspect
    src = inspect.getsource(auth_module.register)
    assert "send_worker_welcome_email" in src, (
        "register() doesn't call send_worker_welcome_email — wiring regression"
    )
    # Fired with create_task so the response stays snappy
    assert "create_task" in src


# ---------- Test 4: Google OAuth callback also triggers welcome --------------
def test_google_oauth_callback_triggers_welcome_for_new_users():
    """The Google sign-in path is the OTHER write path for new workers — it
    must also fire the welcome (but only on FIRST login, not subsequent)."""
    import sys
    sys.path.insert(0, "/app/backend")
    from routes import auth as auth_module
    import inspect
    src = inspect.getsource(auth_module.google_session)
    assert "send_worker_welcome_email" in src
    # Make sure it only sends for `is_new` (not on subsequent logins)
    assert "is_new" in src
