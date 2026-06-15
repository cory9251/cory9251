"""Email + SMS notification helpers (Resend + Twilio).

All settings flow:
  app_settings doc in Mongo → env var fallback → safe defaults.

`_public_base()` returns the canonical public origin used in deep-links inside
emails / SMS (background-task safe — no Request object available).

Synchronous SDK calls (resend.Emails.send, TwilioClient.messages.create) MUST
be wrapped with `asyncio.to_thread` by callers — the helpers here are sync.
"""
import os
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional

import resend
from fastapi import Request
from twilio.rest import Client as TwilioClient

from config import (
    db,
    logger,
    RESEND_API_KEY,
    SENDER_EMAIL,
    TWILIO_SID,
    TWILIO_TOKEN,
    TWILIO_FROM,
)


# ---- Public base URL --------------------------------------------------------
def _resolve_public_base(request: Optional[Request] = None) -> str:
    """Return the canonical public origin so blast emails/SMS can include deep
    links. Order of precedence: proxy-forwarded headers → PUBLIC_BASE_URL env
    → safe production fallback."""
    if request is not None:
        fwd_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        fwd_proto = request.headers.get("x-forwarded-proto") or "https"
        if fwd_host and "localhost" not in fwd_host and "0.0.0.0" not in fwd_host:
            return f"{fwd_proto}://{fwd_host}".rstrip("/")
    env_base = (os.environ.get("PUBLIC_BASE_URL") or "").strip()
    if env_base:
        return env_base.rstrip("/")
    return "https://hcobnetwork.com"


def _public_base() -> str:
    """Background-task safe — no Request object available."""
    return _resolve_public_base(None)


# ---- Settings & creds resolution --------------------------------------------
async def _get_settings_doc() -> dict:
    """Return the singleton app_settings document (or empty dict if missing)."""
    doc = await db.app_settings.find_one({"_id": "global"})
    return doc or {}


async def _resolve_email_creds() -> dict:
    s = await _get_settings_doc()
    return {
        "api_key": (s.get("resend_api_key") or RESEND_API_KEY or "").strip(),
        "sender": (s.get("sender_email") or SENDER_EMAIL or "").strip(),
    }


async def _resolve_sms_creds() -> dict:
    s = await _get_settings_doc()
    return {
        "sid": (s.get("twilio_account_sid") or TWILIO_SID or "").strip(),
        "token": (s.get("twilio_auth_token") or TWILIO_TOKEN or "").strip(),
        "from_": (s.get("twilio_from_number") or TWILIO_FROM or "").strip(),
    }


# ---- Sync senders ----------------------------------------------------------
def _send_email_sync(api_key: str, sender: str, to: str, subject: str, html: str) -> dict:
    if not api_key:
        return {"skipped": "no_resend_key"}
    resend.api_key = api_key
    return resend.Emails.send(
        {"from": sender, "to": [to], "subject": subject, "html": html}
    )


def _send_sms_sync(sid: str, token: str, from_: str, to: str, body: str) -> dict:
    if not (sid and token and from_):
        return {"skipped": "no_twilio_creds"}
    c = TwilioClient(sid, token)
    m = c.messages.create(body=body, from_=from_, to=to)
    return {"sid": m.sid}


# ---- Email layout + high-level helpers --------------------------------------
def _email_layout(
    title: str,
    body_html: str,
    cta_label: Optional[str] = None,
    cta_url: Optional[str] = None,
) -> str:
    """Wrap notification HTML in the standard HCOB email shell."""
    cta_block = ""
    if cta_label and cta_url:
        cta_block = (
            f'<p style="margin:24px 0"><a href="{cta_url}" '
            f'style="background:#0044FF;color:#fff;text-decoration:none;padding:14px 22px;'
            f'font-weight:700;display:inline-block">{cta_label}</a></p>'
        )
    return f"""
    <div style="font-family:system-ui,-apple-system,sans-serif;max-width:560px;margin:0 auto;padding:24px">
      <div style="background:#030712;color:#fff;padding:18px 22px;font-weight:900;letter-spacing:-0.02em;font-size:22px">HCOB Network</div>
      <div style="padding:24px 22px;border:1px solid #E5E7EB;border-top:0">
        <h2 style="margin:0 0 12px 0;font-size:20px;color:#030712">{title}</h2>
        <div style="color:#4B5563;line-height:1.55;font-size:14px">{body_html}</div>
        {cta_block}
        <p style="color:#9CA3AF;font-size:11px;margin-top:32px;border-top:1px solid #E5E7EB;padding-top:16px">
          Sent automatically by HCOB Network · Baltimore, MD ·
          <a href="https://hcobnetwork.com" style="color:#0044FF;text-decoration:none">hcobnetwork.com</a>
        </p>
      </div>
    </div>
    """


async def _send_user_email(
    user: dict,
    *,
    kind: str,
    subject: str,
    body_html: str,
    cta_label: Optional[str] = None,
    cta_url: Optional[str] = None,
) -> bool:
    """Fire-and-forget transactional email to a user. Logs failures, never raises.
    Always sends (no preference toggle per product decision)."""
    email = (user or {}).get("email")
    if not email:
        return False
    try:
        creds = await _resolve_email_creds()
        if not creds.get("api_key") or not creds.get("sender"):
            logger.warning(f"[email/{kind}] no Resend creds — skipped for {email}")
            return False
        html = _email_layout(subject, body_html, cta_label=cta_label, cta_url=cta_url)
        await asyncio.to_thread(
            _send_email_sync,
            creds["api_key"], creds["sender"], email, subject, html,
        )
        try:
            await db.email_logs.insert_one({
                "log_id": f"em_{uuid.uuid4().hex[:12]}",
                "user_id": user.get("user_id"),
                "email": email,
                "kind": kind,
                "subject": subject,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass
        return True
    except Exception as e:
        logger.exception(f"[email/{kind}] failed for {email}: {e}")
        return False


async def _send_gig_event_email(
    worker_id: str,
    *,
    kind: str,
    subject: str,
    body_html: str,
    gig_id: Optional[str] = None,
) -> bool:
    """Convenience wrapper — look up worker by id and send a gig-related email."""
    worker = await db.users.find_one({"user_id": worker_id})
    if not worker:
        return False
    cta_url = f"{_public_base()}/crew" + (f"/gigs/{gig_id}" if gig_id else "")
    return await _send_user_email(
        worker, kind=kind, subject=subject, body_html=body_html,
        cta_label="Open in HCOB Network", cta_url=cta_url,
    )
