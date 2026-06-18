"""Admin Email Blast — send templated or custom emails to a filtered worker
audience (e.g. "all workers missing a payout method").

3-step flow:
  1. POST /admin/email-blast/preview → returns recipient count + first 5
  2. POST /admin/email-blast/test    → sends ONE copy to the admin's own email
  3. POST /admin/email-blast/send    → sends to all recipients in the audience

Safeguards:
  - 3-day per-template + per-worker cooldown (stored in `email_blast_log`)
  - Global blast kill-switch (`is_blast_disabled()`) respected
  - Merge tags ({{name}}, {{first_name}}, {{email}}) substituted per recipient
  - Audience filters mirror /admin/workers exactly via the shared
    `_filter_workers()` helper — no drift between the blast composer and
    the workers list page.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth_deps import require_admin
from config import db, logger
from notifications import _send_user_email, is_blast_disabled
from routes.admin import _filter_workers

router = APIRouter()


# ============================================================================
# Built-in templates — admin can pick one as a starting point then edit.
# ============================================================================
EMAIL_TEMPLATES = [
    {
        "key": "payout_request",
        "title": "Ask workers to add payment method",
        "subject": "Add your payment method so we can pay you, {{first_name}}",
        "body_html": (
            "<p>Hi {{first_name}},</p>"
            "<p>We just need one more thing from you — your <b>payment method</b>"
            " so we know where to send your pay after each shift.</p>"
            "<p>Takes 30 seconds — choose Zelle, Apple Cash, or Chime, then enter"
            " your phone/email/$username.</p>"
            "<p>— HCOB Network</p>"
        ),
        "cta_label": "Add my payment method",
        "cta_path": "/crew/me",
    },
    {
        "key": "profile_complete",
        "title": "Ask workers to complete their profile",
        "subject": "Finish your HCOB profile, {{first_name}}",
        "body_html": (
            "<p>Hi {{first_name}},</p>"
            "<p>Your profile is missing a few details that we need before we can"
            " send you gigs. It only takes a few minutes — phone, address,"
            " emergency contact, and a photo of your ID.</p>"
            "<p>— HCOB Network</p>"
        ),
        "cta_label": "Complete my profile",
        "cta_path": "/crew/me",
    },
    {
        "key": "id_upload",
        "title": "Ask workers to upload their ID",
        "subject": "We need your ID to clear you for shifts",
        "body_html": (
            "<p>Hi {{first_name}},</p>"
            "<p>Before we can put you on a shift, we need a photo of your"
            " government-issued ID. We use this to verify you and to comply with"
            " labor laws. It only takes 30 seconds and we never share it.</p>"
            "<p>— HCOB Network</p>"
        ),
        "cta_label": "Upload my ID",
        "cta_path": "/crew/me",
    },
    {
        "key": "shift_availability",
        "title": "Check who's available this week",
        "subject": "Got time this week? Tap if you're available",
        "body_html": (
            "<p>Hi {{first_name}},</p>"
            "<p>We're staffing up for the next few days. If you're available,"
            " tap the button below and your profile will float to the top of"
            " our list when shifts go out.</p>"
            "<p>— HCOB Network</p>"
        ),
        "cta_label": "I'm available this week",
        "cta_path": "/crew",
    },
    {
        "key": "custom",
        "title": "Custom — write your own",
        "subject": "",
        "body_html": "",
        "cta_label": "",
        "cta_path": "",
    },
]


@router.get("/admin/email-templates")
async def list_templates(admin: dict = Depends(require_admin)):
    return {"templates": EMAIL_TEMPLATES}


# ============================================================================
# Audience filter (mirrors /admin/workers exactly)
# ============================================================================
class AudienceFilter(BaseModel):
    status: Optional[str] = None  # "all" | "approved" | "pending" | "rejected" | "suspended"
    skills: Optional[str] = None  # comma-separated
    availability: Optional[str] = None  # comma-separated
    zip_code: Optional[str] = None
    zip_prefix: Optional[str] = None
    vehicle: Optional[str] = None
    profile_complete: Optional[bool] = None
    min_rating: Optional[float] = None
    available_now: Optional[bool] = None
    payout_status: Optional[str] = None  # "missing" | "set"
    id_status: Optional[str] = None  # "missing" | "submitted" | "verified"
    search: Optional[str] = None


async def _build_audience(f: AudienceFilter) -> list[dict]:
    status = f.status if f.status and f.status != "all" else None
    workers = await _filter_workers(
        status=status,
        skills=f.skills,
        availability=f.availability,
        zip_code=f.zip_code,
        zip_prefix=f.zip_prefix,
        vehicle=f.vehicle,
        profile_complete=f.profile_complete,
        min_rating=f.min_rating,
        available_now=f.available_now,
        payout_status=f.payout_status,
        id_status=f.id_status,
        search=f.search,
    )
    # Only include workers with a valid email — can't email without one.
    return [w for w in workers if (w.get("email") or "").strip()]


# ============================================================================
# Preview — count + first 5 recipients
# ============================================================================
class PreviewIn(BaseModel):
    audience: AudienceFilter


@router.post("/admin/email-blast/preview")
async def preview_blast(payload: PreviewIn, admin: dict = Depends(require_admin)):
    audience = await _build_audience(payload.audience)
    return {
        "count": len(audience),
        "preview": [
            {"user_id": w["user_id"], "name": w.get("name") or "(no name)", "email": w["email"]}
            for w in audience[:5]
        ],
    }


# ============================================================================
# Send — test or full blast
# ============================================================================
class BlastSendIn(BaseModel):
    audience: AudienceFilter
    subject: str = Field(..., min_length=1, max_length=200)
    body_html: str = Field(..., min_length=1, max_length=20000)
    cta_label: Optional[str] = None
    cta_path: Optional[str] = None  # relative path like "/crew/me"
    template_key: str = Field(default="custom")  # for cooldown bucketing
    test_only: bool = False  # send ONE copy to admin's email and stop
    bypass_cooldown: bool = False  # admin override


def _render(template: str, worker: dict) -> str:
    """Substitute the merge tags inside a subject or body."""
    name = (worker.get("name") or "").strip()
    first_name = name.split(" ")[0] if name else "there"
    return (
        template
        .replace("{{name}}", name or "there")
        .replace("{{first_name}}", first_name)
        .replace("{{email}}", worker.get("email") or "")
    )


def _public_base() -> str:
    # Defer import so test-time reloads of notifications module pick up env changes.
    from notifications import _resolve_public_base
    return _resolve_public_base()


@router.post("/admin/email-blast/send")
async def send_blast(payload: BlastSendIn, admin: dict = Depends(require_admin)):
    # Global kill-switch always wins.
    if await is_blast_disabled():
        raise HTTPException(503, "Blasts are temporarily disabled by admin settings.")

    if payload.cta_path and not payload.cta_path.startswith("/"):
        raise HTTPException(400, "cta_path must start with '/'")

    # Always render an absolute URL for the CTA so the email button works.
    cta_url = (
        f"{_public_base().rstrip('/')}{payload.cta_path}"
        if payload.cta_path
        else None
    )

    # TEST send — one copy to the admin who clicked the button. Doesn't
    # touch cooldown logs. Useful for proofreading the email before firing.
    if payload.test_only:
        ok = await _send_user_email(
            admin,
            kind="blast_test",
            subject=_render(payload.subject, admin),
            body_html=_render(payload.body_html, admin),
            cta_label=payload.cta_label or "",
            cta_url=cta_url or "",
        )
        return {"sent": 1 if ok else 0, "skipped_cooldown": 0, "test_only": True, "ok": ok}

    audience = await _build_audience(payload.audience)
    if not audience:
        raise HTTPException(400, "Audience is empty — no workers match the filters.")

    cooldown_cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    sent = 0
    skipped_cooldown = 0
    failed = 0

    for w in audience:
        # Per-template, per-worker 3-day cooldown.
        if not payload.bypass_cooldown:
            recent = await db.email_blast_log.find_one({
                "template_key": payload.template_key,
                "user_id": w["user_id"],
                "sent_at": {"$gt": cooldown_cutoff},
            })
            if recent:
                skipped_cooldown += 1
                continue
        try:
            ok = await _send_user_email(
                w,
                kind="blast",
                subject=_render(payload.subject, w),
                body_html=_render(payload.body_html, w),
                cta_label=payload.cta_label or "",
                cta_url=cta_url or "",
            )
            # Log the cooldown record regardless of delivery success — we
            # never want a transient Resend failure to result in the same
            # worker getting emailed twice on the next click. The admin will
            # see the `failed` count and can fix Resend creds and re-send
            # with bypass_cooldown=True if they truly need a retry.
            await db.email_blast_log.insert_one({
                "template_key": payload.template_key,
                "user_id": w["user_id"],
                "email": w["email"],
                "subject": payload.subject,
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "sent_by_admin_id": admin.get("user_id"),
                "delivered": bool(ok),
            })
            if ok:
                sent += 1
            else:
                failed += 1
        except Exception as e:  # noqa: BLE001
            failed += 1
            logger.warning(f"email-blast send to {w.get('email')} failed: {e}")

    return {
        "sent": sent,
        "skipped_cooldown": skipped_cooldown,
        "failed": failed,
        "audience_size": len(audience),
    }
