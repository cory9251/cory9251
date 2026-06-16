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



async def _log_blast(
    *,
    kind: str,                       # "gig" | "project"
    gig_id: Optional[str],
    gig_title: Optional[str],
    project_id: Optional[str],
    project_title: Optional[str],
    channels: list,
    counts: dict,
    workers_targeted: int,
    sent_by_id: str,
    sent_by_name: Optional[str] = None,
    extra: Optional[dict] = None,
) -> str:
    """Append a single send event to `blast_logs`. Powers the Blasts report.

    Returns the new `blast_id` so callers can reconcile counts later (e.g.
    after the background email/sms/push fan-out completes)."""
    blast_id = f"blast_{uuid.uuid4().hex[:12]}"
    doc = {
        "blast_id": blast_id,
        "kind": kind,
        "gig_id": gig_id,
        "gig_title": gig_title,
        "project_id": project_id,
        "project_title": project_title,
        "channels": list(channels or []),
        "in_app": int(counts.get("in_app") or 0),
        "email": int(counts.get("email") or 0),
        "sms": int(counts.get("sms") or 0),
        "push": int(counts.get("push") or 0),
        "email_failed": int(counts.get("email_failed") or 0),
        "sms_failed": int(counts.get("sms_failed") or 0),
        "workers_targeted": int(workers_targeted or 0),
        "sent_by_id": sent_by_id,
        "sent_by_name": sent_by_name,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        doc["extra"] = extra
    try:
        await db.blast_logs.insert_one(doc)
    except Exception as e:
        logger.error(f"Failed to log blast: {e}")
    return blast_id


# ----------------------------------------------------------------------------
# Background fan-out: email / sms / push to a list of workers.
#
# Cloudflare drops requests that take longer than ~100s. At ~150-300ms per
# Resend HTTP call and one push call per device, blasting 500-1,000 workers
# sequentially blows past that limit. We MUST not block the HTTP request on
# the fan-out; the request returns immediately with in-app counts (which are
# fast — one batched insert) and this helper runs concurrently in the
# background.
# ----------------------------------------------------------------------------
# Background fan-out: email / sms / push to a list of workers.
#
# Cloudflare drops requests that take longer than ~100s. At ~150-300ms per
# Resend HTTP call and one push call per device, blasting 500-1,000 workers
# sequentially blows past that limit. We MUST not block the HTTP request on
# the fan-out; the request returns immediately with in-app counts (which are
# fast — one batched insert) and this helper runs concurrently in the
# background.
# ----------------------------------------------------------------------------
async def fanout_blast_channels(
    *,
    workers: list,
    channels: list,
    subject: str,
    html: str,
    sms_body: str,
    push_payload: dict,
    blast_log_id: Optional[str] = None,
    # Per-channel concurrency. Tuned for typical 3rd-party rate limits:
    #   - Resend free tier: 25 req/s → serial with 50ms gap = ~20 req/s headroom
    #   - Twilio: pace at ~1 SMS/s by default
    #   - Web Push (our own VAPID): can fan out wider
    email_concurrency: int = 5,
    sms_concurrency: int = 1,
    push_concurrency: int = 30,
) -> dict:
    """Send email / sms / push in parallel to many workers. Each channel has
    its own concurrency cap so a slow provider can't stall the others, and
    we stay under typical free-tier rate limits.

    Push imports are deferred to avoid an import cycle
    (notifications.py → push_service.py → config.py)."""
    from push_service import _send_push_to_user
    from config import VAPID_PRIVATE_KEY

    email_creds = await _resolve_email_creds() if "email" in channels else None
    sms_creds = await _resolve_sms_creds() if "sms" in channels else None
    counts = {"email": 0, "sms": 0, "push": 0, "email_failed": 0, "sms_failed": 0}

    # ---- Email channel (rate-limited) ---------------------------------------
    async def send_one_email(w: dict, sem: asyncio.Semaphore) -> None:
        async with sem:
            if not (w.get("email") and email_creds):
                return
            try:
                await asyncio.to_thread(
                    _send_email_sync,
                    email_creds["api_key"],
                    email_creds["sender"],
                    w["email"],
                    subject,
                    html,
                )
                counts["email"] += 1
            except Exception as e:
                # Resend 429 ("Too many requests") is the most common failure
                # at scale. We log + count it and keep going — workers who
                # missed an email still get in-app + push.
                logger.error(f"blast email failed for {w.get('email')}: {e}")
                counts["email_failed"] += 1

    # ---- SMS channel (rate-limited) -----------------------------------------
    async def send_one_sms(w: dict, sem: asyncio.Semaphore) -> None:
        async with sem:
            if not (w.get("phone") and sms_creds):
                return
            try:
                await asyncio.to_thread(
                    _send_sms_sync,
                    sms_creds["sid"],
                    sms_creds["token"],
                    sms_creds["from_"],
                    w["phone"],
                    sms_body,
                )
                counts["sms"] += 1
            except Exception as e:
                logger.error(f"blast sms failed for {w.get('phone')}: {e}")
                counts["sms_failed"] += 1

    # ---- Push channel (in-house) --------------------------------------------
    async def send_one_push(w: dict, sem: asyncio.Semaphore) -> None:
        async with sem:
            try:
                sent = await _send_push_to_user(w["user_id"], push_payload)
                counts["push"] += sent
            except Exception as e:
                logger.error(f"blast push failed for {w.get('user_id')}: {e}")

    coros = []
    if "email" in channels and email_creds:
        sem_e = asyncio.Semaphore(max(1, int(email_concurrency)))
        coros.extend(send_one_email(w, sem_e) for w in workers)
    if "sms" in channels and sms_creds:
        sem_s = asyncio.Semaphore(max(1, int(sms_concurrency)))
        coros.extend(send_one_sms(w, sem_s) for w in workers)
    if "push" in channels and VAPID_PRIVATE_KEY:
        sem_p = asyncio.Semaphore(max(1, int(push_concurrency)))
        coros.extend(send_one_push(w, sem_p) for w in workers)

    if coros:
        await asyncio.gather(*coros, return_exceptions=True)

    # Reconcile counts on the persisted blast log entry so the Blasts report
    # shows the real numbers once the background job finishes.
    if blast_log_id:
        try:
            await db.blast_logs.update_one(
                {"blast_id": blast_log_id},
                {
                    "$set": {
                        "email": counts["email"],
                        "sms": counts["sms"],
                        "push": counts["push"],
                        "email_failed": counts["email_failed"],
                        "sms_failed": counts["sms_failed"],
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
            )
        except Exception as e:
            logger.error(f"failed to reconcile blast log {blast_log_id}: {e}")

    return counts
