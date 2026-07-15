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


# ---- Admin bell notifications ----------------------------------------------
async def notify_admins(title: str, body: str = "", url: Optional[str] = None) -> int:
    """Drop an in-app bell notification for every admin user."""
    admin_ids = await db.users.distinct("user_id", {"role": "admin"})
    if not admin_ids:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    await db.notifications.insert_many(
        [
            {
                "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
                "user_id": uid,
                "title": title,
                "body": body,
                "url": url,
                "read": False,
                "created_at": now,
            }
            for uid in admin_ids
        ]
    )
    return len(admin_ids)


async def email_admins(
    subject: str,
    title: str,
    body_html: str,
    cta_label: Optional[str] = None,
    cta_url: Optional[str] = None,
) -> bool:
    """Best-effort email to the owner's lead inbox (settings override → env).
    Logs failures, never raises — lead capture must not fail on email issues."""
    try:
        creds = await _resolve_email_creds()
        s = await _get_settings_doc()
        to = (
            s.get("quote_notify_email")
            or os.environ.get("HCOB_OWNER_EMAIL", "corymclarke7126@gmail.com")
        ).strip()
        if not (creds.get("api_key") and creds.get("sender") and to):
            return False
        html = _email_layout(title, body_html, cta_label, cta_url)
        await asyncio.to_thread(
            _send_email_sync, creds["api_key"], creds["sender"], to, subject, html
        )
        return True
    except Exception as e:
        logger.error(f"email_admins failed ({subject}): {e}")
        return False


# ---- Blast safety (kill switch + cooldown) ---------------------------------
# These guards exist because a SEV1 incident (Feb-2026) showed that without
# them a single misclick or duplicate user record can drain the Resend quota.
# Source of truth: env var → app_settings.blast_kill_switch (mongo).
BLAST_COOLDOWN_SECONDS = int(os.environ.get("BLAST_COOLDOWN_SECONDS", "300"))


async def is_blast_disabled() -> bool:
    """Return True if blasts are disabled (env var OR DB toggle).

    Env var `BLAST_KILL_SWITCH=1` is the emergency override. The DB toggle in
    `app_settings.blast_kill_switch` is set via the Owner UI / API and
    survives across deploys."""
    if (os.environ.get("BLAST_KILL_SWITCH") or "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    try:
        s = await db.app_settings.find_one({"_id": "global"}, {"_id": 0, "blast_kill_switch": 1})
        return bool((s or {}).get("blast_kill_switch"))
    except Exception:
        return False


# ---- Public base URL --------------------------------------------------------
def _resolve_public_base(request: Optional[Request] = None) -> str:
    """Return the canonical public origin so blast emails/SMS can include deep
    links. Order of precedence: proxy-forwarded headers → PUBLIC_BASE_URL env
    (when it's NOT a preview URL) → safe production fallback."""
    if request is not None:
        fwd_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        fwd_proto = request.headers.get("x-forwarded-proto") or "https"
        if fwd_host and "localhost" not in fwd_host and "0.0.0.0" not in fwd_host:
            return f"{fwd_proto}://{fwd_host}".rstrip("/")
    env_base = (os.environ.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    # In production we want links to go to the canonical hcobnetwork.com
    # domain — never to the preview/dev domains. If the env var still points
    # at a preview hostname (legacy / dev override / forgotten env), ignore
    # it and fall through to the production default. The user can still
    # explicitly override by setting PUBLIC_BASE_URL to a non-preview URL.
    if env_base and (
        "preview.emergentagent.com" in env_base
        or "emergent.host" in env_base
        or "preview.emergent" in env_base
    ):
        env_base = ""
    if env_base:
        return env_base
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


# Twilio / A2P 10DLC carrier compliance: every outbound SMS must include an
# opt-out disclosure. We append "Reply STOP to opt out." exactly once — the
# guard makes it idempotent so callers that already added their own footer
# don't get it duplicated. Kept short (<=25 chars) so it rarely pushes a
# single-segment SMS into a second billable segment.
SMS_STOP_FOOTER = "Reply STOP to opt out."


def _with_stop_footer(body: str) -> str:
    text = (body or "").rstrip()
    lower = text.lower()
    if "reply stop" in lower or "text stop" in lower:
        return text
    return f"{text}\n\n{SMS_STOP_FOOTER}"


def _send_sms_sync(sid: str, token: str, from_: str, to: str, body: str) -> dict:
    if not (sid and token and from_):
        return {"skipped": "no_twilio_creds"}
    c = TwilioClient(sid, token)
    m = c.messages.create(body=_with_stop_footer(body), from_=from_, to=to)
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


async def send_worker_welcome_email(user: dict) -> bool:
    """Founder welcome message — fired once when a new worker registers.
    Voiced as Cory (founder); never auto-resent. The CTA deep-links to the
    profile page so the worker can finish their setup and unlock booking."""
    first_name = (user.get("name") or "").split(" ")[0] or "there"
    body_html = f"""
      <p style="margin:0 0 16px;font-size:16px;line-height:1.6;color:#030712">
        Hey {first_name},
      </p>
      <p style="margin:0 0 16px;font-size:15px;line-height:1.7;color:#030712">
        My name is <strong>Cory</strong>, and I&rsquo;m the founder of The HCOB Network. I created this
        platform to bring value to customers and more opportunities to smaller businesses &mdash;
        established and non-established alike. Either way, we structure the unstructured.
      </p>
      <p style="margin:0 0 16px;font-size:15px;line-height:1.7;color:#030712">
        There are so many talented professionals in Baltimore, and we want to bring amazing people
        like you the work you deserve.
      </p>
      <p style="margin:0 0 24px;font-size:15px;line-height:1.7;color:#030712">
        Thank you for signing up.
      </p>
      <div style="border:1px solid #E5E7EB;background:#FFFBEB;padding:16px;margin:0 0 8px">
        <div style="font-family:'JetBrains Mono',ui-monospace,Menlo,monospace;font-size:10px;letter-spacing:0.2em;text-transform:uppercase;color:#92400E;margin-bottom:8px">
          Quick next step
        </div>
        <p style="margin:0;font-size:14px;line-height:1.6;color:#030712">
          Finish your profile and upload a photo of your ID. The moment those are in, we&rsquo;ll
          review and activate your account so you can start claiming shifts.
        </p>
      </div>
    """
    return await _send_user_email(
        user,
        kind="welcome_worker",
        subject=f"Welcome to The HCOB Network, {first_name}",
        body_html=body_html,
        cta_label="Finish your profile",
        cta_url=f"{_public_base()}/crew/me",
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

    Safety guarantees (post Feb-2026 SEV1):
      • Re-checks `is_blast_disabled()` on entry — Owner can kill an in-flight
        blast by flipping the toggle.
      • Dedupes `workers` by email (and by phone for SMS) so duplicate user
        rows can't multiply sends.
      • Persists `sent_emails` on the blast log so a retried fan-out skips
        addresses already mailed in this blast.

    Push imports are deferred to avoid an import cycle
    (notifications.py → push_service.py → config.py)."""
    from push_service import _send_push_to_user
    from config import VAPID_PRIVATE_KEY

    # ---- Kill switch (1) — pre-flight ---------------------------------------
    if await is_blast_disabled():
        logger.warning(
            f"[blast {blast_log_id}] aborted: blast_kill_switch is ON. "
            f"channels={channels} workers={len(workers)}"
        )
        if blast_log_id:
            try:
                await db.blast_logs.update_one(
                    {"blast_id": blast_log_id},
                    {"$set": {
                        "aborted": True,
                        "abort_reason": "kill_switch",
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }},
                )
            except Exception:
                pass
        return {"email": 0, "sms": 0, "push": 0, "email_failed": 0, "sms_failed": 0, "aborted": True}

    # ---- Idempotency — skip addresses already sent in this blast ------------
    already_sent_emails: set = set()
    already_sent_phones: set = set()
    if blast_log_id:
        try:
            prior = await db.blast_logs.find_one(
                {"blast_id": blast_log_id},
                {"_id": 0, "sent_emails": 1, "sent_phones": 1},
            )
            already_sent_emails = set((prior or {}).get("sent_emails") or [])
            already_sent_phones = set((prior or {}).get("sent_phones") or [])
        except Exception:
            pass

    # ---- Dedupe workers ------------------------------------------------------
    # If duplicate user docs share the same email, we MUST only send once.
    # Same for phone numbers on SMS. We keep the first occurrence so the
    # push channel (which is per-user_id, not per-email) still gets every
    # device the user has registered.
    unique_email_workers: list = []
    seen_emails: set = set()
    for w in workers:
        em = (w.get("email") or "").strip().lower()
        if em and em not in seen_emails and em not in already_sent_emails:
            seen_emails.add(em)
            unique_email_workers.append(w)

    unique_sms_workers: list = []
    seen_phones: set = set()
    for w in workers:
        ph = (w.get("phone") or "").strip()
        if ph and ph not in seen_phones and ph not in already_sent_phones:
            seen_phones.add(ph)
            unique_sms_workers.append(w)

    logger.info(
        f"[blast {blast_log_id}] starting fanout: channels={channels} "
        f"workers={len(workers)} unique_emails={len(unique_email_workers)} "
        f"unique_phones={len(unique_sms_workers)}"
    )

    email_creds = await _resolve_email_creds() if "email" in channels else None
    sms_creds = await _resolve_sms_creds() if "sms" in channels else None
    counts = {"email": 0, "sms": 0, "push": 0, "email_failed": 0, "sms_failed": 0}

    # Track addresses actually attempted so we can persist them and skip on retry.
    sent_emails_now: set = set()
    sent_phones_now: set = set()

    # ---- Email channel (rate-limited) ---------------------------------------
    async def send_one_email(w: dict, sem: asyncio.Semaphore) -> None:
        async with sem:
            # Kill-switch re-check inside the loop so flipping it mid-blast
            # halts further sends as soon as the running tasks pick up.
            if await is_blast_disabled():
                return
            if not (w.get("email") and email_creds):
                return
            em = w["email"].strip().lower()
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
                sent_emails_now.add(em)
            except Exception as e:
                # Resend 429 ("Too many requests") is the most common failure
                # at scale. We log + count it and keep going — workers who
                # missed an email still get in-app + push.
                logger.error(f"blast email failed for {w.get('email')}: {e}")
                counts["email_failed"] += 1

    # ---- SMS channel (rate-limited) -----------------------------------------
    async def send_one_sms(w: dict, sem: asyncio.Semaphore) -> None:
        async with sem:
            if await is_blast_disabled():
                return
            if not (w.get("phone") and sms_creds):
                return
            ph = w["phone"].strip()
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
                sent_phones_now.add(ph)
            except Exception as e:
                logger.error(f"blast sms failed for {w.get('phone')}: {e}")
                counts["sms_failed"] += 1

    # ---- Push channel (in-house) --------------------------------------------
    async def send_one_push(w: dict, sem: asyncio.Semaphore) -> None:
        async with sem:
            if await is_blast_disabled():
                return
            try:
                sent = await _send_push_to_user(w["user_id"], push_payload)
                counts["push"] += sent
            except Exception as e:
                logger.error(f"blast push failed for {w.get('user_id')}: {e}")

    coros = []
    if "email" in channels and email_creds:
        sem_e = asyncio.Semaphore(max(1, int(email_concurrency)))
        coros.extend(send_one_email(w, sem_e) for w in unique_email_workers)
    if "sms" in channels and sms_creds:
        sem_s = asyncio.Semaphore(max(1, int(sms_concurrency)))
        coros.extend(send_one_sms(w, sem_s) for w in unique_sms_workers)
    if "push" in channels and VAPID_PRIVATE_KEY:
        sem_p = asyncio.Semaphore(max(1, int(push_concurrency)))
        # Push is keyed by user_id — dedupe by user_id (not email/phone).
        seen_ids: set = set()
        unique_push_workers: list = []
        for w in workers:
            uid = w.get("user_id")
            if uid and uid not in seen_ids:
                seen_ids.add(uid)
                unique_push_workers.append(w)
        coros.extend(send_one_push(w, sem_p) for w in unique_push_workers)

    if coros:
        await asyncio.gather(*coros, return_exceptions=True)

    # Reconcile counts + persist recipients on the blast log so a retry of
    # this same blast_id can skip already-sent addresses (idempotency).
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
                    },
                    "$addToSet": {
                        "sent_emails": {"$each": list(sent_emails_now)},
                        "sent_phones": {"$each": list(sent_phones_now)},
                    },
                },
            )
        except Exception as e:
            logger.error(f"failed to reconcile blast log {blast_log_id}: {e}")

    logger.info(
        f"[blast {blast_log_id}] done: email={counts['email']} "
        f"sms={counts['sms']} push={counts['push']} "
        f"failed=email:{counts['email_failed']}/sms:{counts['sms_failed']}"
    )
    return counts
