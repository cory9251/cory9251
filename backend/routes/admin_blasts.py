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
from html import escape as _html_escape
import re
import asyncio
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth_deps import require_admin
from config import db, logger
from notifications import (
    _send_user_email,
    _send_sms_sync,
    _resolve_sms_creds,
    is_blast_disabled,
)
from routes.admin import _filter_workers

router = APIRouter()


# Block-level tags that indicate the body is already proper HTML (i.e. came
# from the TipTap editor). When we see ANY of these we trust the input and
# only do merge-tag substitution; otherwise we normalize plain text below.
_BLOCK_TAG_RE = re.compile(
    r"<\s*(p|div|h[1-6]|ul|ol|li|table|tr|td|th|blockquote|br|pre)[\s>/]",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"(?<![\"'>=])(https?://[^\s<>\"']+)")


# Inline styles applied to bare block-level tags coming from the TipTap
# editor. Email clients (Outlook desktop, Gmail web in some modes) strip
# <style> blocks, so we MUST set spacing/typography via inline `style=`
# attributes for consistent rendering. The same styles are mirrored in
# `.email-preview-html` (index.css) so the live preview matches.
_EMAIL_BLOCK_STYLES = {
    "p": "margin:0 0 14px;line-height:1.6",
    "h1": "margin:18px 0 10px;font-size:22px;font-weight:800;line-height:1.25;letter-spacing:-0.01em",
    "h2": "margin:18px 0 10px;font-size:18px;font-weight:800;line-height:1.3;letter-spacing:-0.01em",
    "h3": "margin:14px 0 8px;font-size:15px;font-weight:700",
    "ul": "margin:0 0 14px;padding-left:22px;list-style:disc",
    "ol": "margin:0 0 14px;padding-left:22px;list-style:decimal",
    "li": "margin:4px 0",
    "blockquote": "margin:12px 0;padding:12px 14px;border-left:3px solid #0044FF;background:#F5F8FF;color:#030712",
    "a": "color:#0044FF;text-decoration:underline",
}
# Match the opening tag of a block element WITHOUT a style attribute. We
# only inject — never overwrite — so admins who explicitly set a style
# keep their choice.
_BARE_BLOCK_OPEN_RE = re.compile(
    r"<(p|h1|h2|h3|ul|ol|li|blockquote|a)(\s[^>]*)?>",
    re.IGNORECASE,
)


def _inline_block_styles(html: str) -> str:
    """Add inline style attributes to bare block-level tags so email
    clients that strip <style> blocks still render proper spacing."""
    if not html or "<" not in html:
        return html or ""

    def _add_style(m: re.Match) -> str:
        tag = m.group(1).lower()
        attrs = m.group(2) or ""
        if "style=" in attrs.lower():
            # Respect existing inline styles — admin or another transform set them.
            return m.group(0)
        style = _EMAIL_BLOCK_STYLES.get(tag)
        if not style:
            return m.group(0)
        return f'<{tag}{attrs} style="{style}">'

    return _BARE_BLOCK_OPEN_RE.sub(_add_style, html)


def _normalize_plain_text_to_html(text: str) -> str:
    """Turn a plain-text email body into well-formed HTML so it renders
    properly in Resend (and every other email client).

    Rules:
      • If the body already contains block-level HTML, return as-is
        (TipTap's output goes through this branch untouched).
      • Otherwise scan line-by-line, grouping consecutive bullet/numbered
        lines into <ul>/<ol> and flushing other consecutive lines into
        <p> blocks (blank line → new paragraph).
      • Apply minimal markdown-ish inline formatting:
          **bold**   → <strong>bold</strong>
          _italic_   → <em>italic</em>
      • Auto-link bare http(s) URLs.
      • All other text is HTML-escaped so admins can't accidentally inject
        broken markup.
    """
    if not text:
        return ""
    if _BLOCK_TAG_RE.search(text):
        # Already proper HTML — return verbatim (TipTap path).
        return text

    raw = text.replace("\r\n", "\n").replace("\r", "\n")

    def _inline(s: str) -> str:
        s = _html_escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"<em>\1</em>", s)
        s = _URL_RE.sub(
            r'<a href="\1" style="color:#0044FF;text-decoration:underline">\1</a>',
            s,
        )
        return s

    lines = raw.split("\n")
    out: list[str] = []
    para_buf: list[str] = []  # accumulating non-list lines (single paragraph)
    ul_buf: list[str] = []    # accumulating bullet items
    ol_buf: list[str] = []    # accumulating numbered items

    def _flush_para():
        if para_buf:
            joined = "<br/>".join(_inline(ln) for ln in para_buf)
            out.append(
                f'<p style="margin:0 0 14px;line-height:1.6">{joined}</p>'
            )
            para_buf.clear()

    def _flush_ul():
        if ul_buf:
            items = "".join(
                f'<li style="margin:4px 0">{_inline(i)}</li>' for i in ul_buf
            )
            out.append(
                f'<ul style="margin:0 0 14px;padding-left:22px">{items}</ul>'
            )
            ul_buf.clear()

    def _flush_ol():
        if ol_buf:
            items = "".join(
                f'<li style="margin:4px 0">{_inline(i)}</li>' for i in ol_buf
            )
            out.append(
                f'<ol style="margin:0 0 14px;padding-left:22px">{items}</ol>'
            )
            ol_buf.clear()

    def _flush_all():
        _flush_para()
        _flush_ul()
        _flush_ol()

    for ln in lines:
        stripped = ln.rstrip()
        if not stripped.strip():
            # Blank line — paragraph/list boundary
            _flush_all()
            continue
        # Bullet?
        m = re.match(r"^\s*[-*]\s+(.*)$", stripped)
        if m:
            _flush_para()
            _flush_ol()
            ul_buf.append(m.group(1))
            continue
        # Numbered?
        m = re.match(r"^\s*\d+[.)]\s+(.*)$", stripped)
        if m:
            _flush_para()
            _flush_ul()
            ol_buf.append(m.group(1))
            continue
        # Regular line → accumulate into paragraph (flush any pending lists first)
        _flush_ul()
        _flush_ol()
        para_buf.append(stripped)

    _flush_all()
    return "".join(out)


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
        "sms_body": (
            "HCOB: Hey {{first_name}}, add a payout method (Zelle/Chime/Apple Cash)"
            " so we can pay you fast - takes 30 sec."
        ),
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
        "sms_body": (
            "HCOB: {{first_name}}, finish your profile so we can send you gigs -"
            " phone, address, emergency contact, ID photo. A few minutes tops."
        ),
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
        "sms_body": (
            "HCOB: {{first_name}}, upload a photo of your ID so we can clear you"
            " for shifts. 30 sec - we never share it."
        ),
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
        "sms_body": (
            "HCOB: {{first_name}}, got time this week? Tap 'Available' in the app"
            " and we'll surface your name first when shifts drop."
        ),
    },
    {
        "key": "custom",
        "title": "Custom — write your own",
        "subject": "",
        "body_html": "",
        "cta_label": "",
        "cta_path": "",
        "sms_body": "",
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
    work_class: Optional[str] = None  # "general_labor" | "specialist"
    trade: Optional[str] = None  # specialist trade id
    trade_status: Optional[str] = None  # "pending" | "verified" | "returned" | "any"
    attributes: Optional[str] = None  # comma-separated work attributes


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
        work_class=f.work_class,
        trade=f.trade,
        trade_status=f.trade_status,
        attributes=f.attributes,
    )
    # Only include workers with a valid email — can't email without one.
    return [w for w in workers if (w.get("email") or "").strip()]


def _sms_eligible(workers: list[dict]) -> list[dict]:
    """Twilio A2P 10DLC: only text workers with an explicit opt-in AND a
    phone number of record. This is a hard gate — no override, ever."""
    return [
        w for w in workers
        if w.get("sms_opt_in") is True and (w.get("phone") or "").strip()
    ]


# ============================================================================
# Preview — count + first 5 recipients
# ============================================================================
class PreviewIn(BaseModel):
    audience: AudienceFilter


@router.post("/admin/email-blast/preview")
async def preview_blast(payload: PreviewIn, admin: dict = Depends(require_admin)):
    audience = await _build_audience(payload.audience)
    sms_pool = _sms_eligible(audience)
    return {
        "count": len(audience),
        "email_count": len(audience),
        "sms_count": len(sms_pool),
        "preview": [
            {"user_id": w["user_id"], "name": w.get("name") or "(no name)", "email": w["email"]}
            for w in audience[:5]
        ],
        "sms_preview": [
            {"user_id": w["user_id"], "name": w.get("name") or "(no name)", "phone": w.get("phone")}
            for w in sms_pool[:5]
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
    # Multichannel blast (channels default to email-only for back-compat)
    channels: List[str] = Field(default_factory=lambda: ["email"])
    sms_body: Optional[str] = Field(default=None, max_length=1600)


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


def _render_body(body: str, worker: dict) -> str:
    """Body-specific render: substitute merge tags, normalize plain text
    to HTML, then inline-style block tags so every email client renders
    paragraphs/lists/headings with consistent spacing — Outlook desktop
    and Gmail strip <style> blocks aggressively."""
    return _inline_block_styles(
        _normalize_plain_text_to_html(_render(body, worker))
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

    channels = [c for c in (payload.channels or ["email"]) if c in ("email", "sms")]
    if not channels:
        raise HTTPException(400, "Pick at least one channel (email or sms).")
    if "sms" in channels and not (payload.sms_body or "").strip():
        raise HTTPException(400, "SMS body is required when the SMS channel is selected.")

    # Always render an absolute URL for the CTA so the email button works.
    cta_url = (
        f"{_public_base().rstrip('/')}{payload.cta_path}"
        if payload.cta_path
        else None
    )

    # TEST send — one copy to the admin who clicked the button. Doesn't
    # touch cooldown logs. Useful for proofreading before firing.
    # For a test with the SMS channel selected we ALSO fire an SMS to the
    # admin's own phone (if any) so they can proof the text body too.
    if payload.test_only:
        result = {"test_only": True, "email": {"sent": 0}, "sms": {"sent": 0, "skipped": None}}
        if "email" in channels:
            ok = await _send_user_email(
                admin,
                kind="blast_test",
                subject=_render(payload.subject, admin),
                body_html=_render_body(payload.body_html, admin),
                cta_label=payload.cta_label or "",
                cta_url=cta_url or "",
            )
            result["email"] = {"sent": 1 if ok else 0, "ok": bool(ok)}
        if "sms" in channels:
            admin_phone = (admin.get("phone") or "").strip()
            if not admin_phone:
                result["sms"] = {"sent": 0, "skipped": "admin_has_no_phone"}
            else:
                creds = await _resolve_sms_creds()
                try:
                    r = await asyncio.to_thread(
                        _send_sms_sync, creds["sid"], creds["token"], creds["from_"],
                        admin_phone, _render(payload.sms_body or "", admin),
                    )
                    result["sms"] = {"sent": 0 if r.get("skipped") else 1, "raw": r}
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"blast test SMS failed: {e}")
                    result["sms"] = {"sent": 0, "skipped": "send_error"}
        # Back-compat top-level fields (older UIs read `sent`)
        result["sent"] = result["email"]["sent"] + result["sms"]["sent"]
        result["skipped_cooldown"] = 0
        return result

    audience = await _build_audience(payload.audience)
    if not audience:
        raise HTTPException(400, "Audience is empty — no workers match the filters.")

    cooldown_cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()

    # ---- Email fan-out --------------------------------------------------
    email_sent = email_skipped = email_failed = 0
    if "email" in channels:
        for w in audience:
            if not payload.bypass_cooldown:
                recent = await db.email_blast_log.find_one({
                    "template_key": payload.template_key,
                    "user_id": w["user_id"],
                    "channel": {"$in": [None, "email"]},
                    "sent_at": {"$gt": cooldown_cutoff},
                })
                if recent:
                    email_skipped += 1
                    continue
            try:
                ok = await _send_user_email(
                    w,
                    kind="blast",
                    subject=_render(payload.subject, w),
                    body_html=_render_body(payload.body_html, w),
                    cta_label=payload.cta_label or "",
                    cta_url=cta_url or "",
                )
                await db.email_blast_log.insert_one({
                    "template_key": payload.template_key,
                    "channel": "email",
                    "user_id": w["user_id"],
                    "email": w["email"],
                    "subject": payload.subject,
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                    "sent_by_admin_id": admin.get("user_id"),
                    "delivered": bool(ok),
                })
                if ok:
                    email_sent += 1
                else:
                    email_failed += 1
            except Exception as e:  # noqa: BLE001
                email_failed += 1
                logger.warning(f"email-blast send to {w.get('email')} failed: {e}")

    # ---- SMS fan-out (opt-in gated) ------------------------------------
    sms_sent = sms_skipped_cooldown = sms_skipped_consent = sms_failed = 0
    if "sms" in channels:
        sms_pool = _sms_eligible(audience)
        # Anyone in the base audience who isn't SMS-eligible counts as a
        # consent skip so the admin can see WHY the sms number is smaller.
        sms_skipped_consent = len(audience) - len(sms_pool)
        creds = await _resolve_sms_creds()
        for w in sms_pool:
            if not payload.bypass_cooldown:
                recent = await db.email_blast_log.find_one({
                    "template_key": payload.template_key,
                    "user_id": w["user_id"],
                    "channel": "sms",
                    "sent_at": {"$gt": cooldown_cutoff},
                })
                if recent:
                    sms_skipped_cooldown += 1
                    continue
            body = _render(payload.sms_body or "", w)
            try:
                r = await asyncio.to_thread(
                    _send_sms_sync, creds["sid"], creds["token"], creds["from_"],
                    (w.get("phone") or "").strip(), body,
                )
                delivered = not r.get("skipped")
                await db.email_blast_log.insert_one({
                    "template_key": payload.template_key,
                    "channel": "sms",
                    "user_id": w["user_id"],
                    "phone": w.get("phone"),
                    "subject": payload.subject,  # kept for consistency with email rows
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                    "sent_by_admin_id": admin.get("user_id"),
                    "delivered": bool(delivered),
                })
                if delivered:
                    sms_sent += 1
                else:
                    sms_failed += 1
            except Exception as e:  # noqa: BLE001
                sms_failed += 1
                logger.warning(f"sms-blast send to {w.get('phone')} failed: {e}")

    return {
        # Legacy top-level fields (used by older frontend versions)
        "sent": email_sent,
        "skipped_cooldown": email_skipped,
        "failed": email_failed,
        "audience_size": len(audience),
        # New per-channel breakdown
        "channels": channels,
        "email": {
            "sent": email_sent,
            "skipped_cooldown": email_skipped,
            "failed": email_failed,
        },
        "sms": {
            "sent": sms_sent,
            "skipped_cooldown": sms_skipped_cooldown,
            "skipped_consent": sms_skipped_consent,
            "failed": sms_failed,
        },
    }
