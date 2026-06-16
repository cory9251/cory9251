"""HCOB Network — Gig Opportunity Management Platform."""
# Loading order matters: backend.config calls load_dotenv() on import. Every
# module below it can then read env vars normally.
from config import (  # noqa: F401 — re-exported for legacy imports
    MONGO_URL,
    DB_NAME,
    JWT_SECRET,
    JWT_ALG,
    APP_NAME,
    EMERGENT_LLM_KEY,
    STORAGE_URL,
    RESEND_API_KEY,
    SENDER_EMAIL,
    TWILIO_SID,
    TWILIO_TOKEN,
    TWILIO_FROM,
    VAPID_PUBLIC_KEY,
    VAPID_PRIVATE_KEY,
    VAPID_SUBJECT,
    logger,
    client,
    db,
)
from constants import (
    WORKER_SKILLS,
    SKILL_LABELS,
    GIG_CATEGORY_TO_SKILLS,
    AVAILABILITY_OPTIONS,
    EXPERIENCE_OPTIONS,
    TSHIRT_SIZES,
    REQUIRED_PROFILE_FIELDS,
    GIG_TAG_VALUES,
)
from storage import init_storage, put_object, get_object, _ext_from
from auth_deps import (
    hash_password,
    verify_password,
    new_session_token,
    SESSION_DAYS,
    cookie_kwargs,
    _profile_missing_fields,
    _is_profile_complete,
    _get_user_by_id,
    _worker_rating_stats,
    get_current_user,
    require_admin,
)
from notifications import (
    _resolve_public_base,
    _public_base,
    _get_settings_doc,
    _resolve_email_creds,
    _resolve_sms_creds,
    _send_email_sync,
    _send_sms_sync,
    _email_layout,
    _send_user_email,
    _send_gig_event_email,
    _log_blast,
)
from routes.messages import router as messages_router, _message_digest_runner
from routes.push import router as push_router
from routes.auth import router as auth_router
from routes.profile import router as profile_router, _upload_user_image
from routes.gigs import (
    router as gigs_router,
    _gig_doc,
    _strip_sensitive_for_worker,
    _effective_status,
    _resolve_pay,
    _resolve_break_minutes,
    _compute_paid_hours,
    _compute_earnings,
    _format_gig_email,
    _format_gig_sms,
    _notify_matching_workers_of_new_gig,
    _publish_due_gigs_loop,  # noqa: F401 — exported for future startup wiring
)
from routes.admin import (
    router as admin_router,
    AdminProfileUpdateIn,
    AdminGigNoteIn,
    WorkerMessageIn,
    AcceptanceRoleIn,
    AdminCreateIn,
    AdminRoleUpdateIn,
    GIG_ROLES,
    GIG_ROLE_LABELS,  # noqa: F401 — UI surfaces use it via /api routes that may import it
)
from routes.reports import router as reports_router
from routes.va import router as va_router
from routes.pm import router as pm_router
from routes.owner import router as owner_router
from routes.projects import router as projects_router
from push_service import _send_push_to_user, _send_push_sync, PushSubscriptionGone  # noqa: F401
from models import (
    GigCategory,
    PayType,
    GigRecurrence,
    GigTag,
    WorkerStatus,
    RegisterIn,
    LoginIn,
    GoogleSessionIn,
    ProfileUpdateIn,
    GigIn,
    GigPatch,
    RushToggleIn,
    GigTagsIn,
    AssignWorkerIn,
    CancelShiftIn,
    WorkerPayIn,
    AcceptancePayIn,
    TimesheetApproveIn,
    TimesheetEditIn,
    AdminRatingIn,
    ClientRatingLinkIn,
    ClientRatingSubmitIn,
    SettingsIn,
    SettingsTestIn,
    QuoteRequestIn,
    QuoteRequestPatch,
    PushKeysIn,
    PushSubscriptionIn,
    PushTestIn,
    AdminResetPasswordIn,
    ForgotPasswordIn,
    ResetPasswordIn,
    ChangePasswordIn,
    WorkerStatusIn,
    MessageSendIn,
    OpenDMIn,
)

import os
import uuid
import json
import logging
import secrets
import asyncio
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal, Dict

import bcrypt
import jwt
import requests
import resend
from fastapi import (
    FastAPI,
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Depends,
    Request,
    Response,
    UploadFile,
    File,
    Form,
    Query,
    Header,
    Body,
)
from fastapi.responses import Response as FastAPIResponse, HTMLResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: F401 — used in tests via patching
from pydantic import BaseModel, EmailStr, Field
from twilio.rest import Client as TwilioClient
from pywebpush import webpush, WebPushException

# ----------------------------------------------------------------------------
# FastAPI app
# ----------------------------------------------------------------------------
app = FastAPI(title="HCOB Network API")
api = APIRouter(prefix="/api")


@api.get("/")
async def root():
    return {"service": "hcob-network", "ok": True}


# ---- Auth ------------------------------------------------------------------
# All /auth/* routes live in routes/auth.py — register, login, logout, me,
# google session exchange, forgot/reset/change password.


# ---- Profile / uploads -----------------------------------------------------
# All /profile/* + /files/{path} routes live in routes/profile.py. The
# `_upload_user_image` helper is re-exported there (admin worker-ID upload
# below still uses it via `from routes.profile import _upload_user_image`).


# ---- Gigs ------------------------------------------------------------------
# All /gigs/* routes (CRUD + accept/withdraw/approve/reject/assign/remove +
# cancel-shift + backup logic) live in routes/gigs.py. The helpers
# _gig_doc, _strip_sensitive_for_worker, _effective_status, _resolve_pay,
# _resolve_break_minutes, _compute_paid_hours, _compute_earnings,
# _format_gig_email, _format_gig_sms, _notify_matching_workers_of_new_gig,
# and _publish_due_gigs_loop are re-exported there for other modules.


# ---- Web Push (PWA notifications) -----------------------------------------
# Subscription/status/test endpoints live in routes/push.py and the fan-out
# send helper lives in push_service.py — both imported above.


# ---- Gig blast / rush / tags / publish + helpers ---------------------------
# All moved to routes/gigs.py.


# ---- Notifications ---------------------------------------------------------
@api.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    items = (
        await db.notifications.find({"user_id": user["user_id"]}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(100)
    )
    return items


@api.post("/notifications/{notification_id}/read")
async def mark_read(notification_id: str, user: dict = Depends(get_current_user)):
    await db.notifications.update_one(
        {"notification_id": notification_id, "user_id": user["user_id"]},
        {"$set": {"read": True}},
    )
    return {"ok": True}


# ---- Admin endpoints -------------------------------------------------------
# ---- Admin endpoints -------------------------------------------------------
# All /admin/workers/* (list/match/get/profile/verify-id/id-upload/approve/
# reject/suspend/reinstate/reset-password) + /admin/requests + /admin/stats
# + /admin/users/{id}/reset-password + /admin/workers/{id}/pay + per-
# acceptance pay override + timesheet endpoints all live in routes/admin.py.


# ---- Owner-only global user reset (works for admins, VAs, anyone) -----------
# Owner-only /admin/users/{id}/reset-password moved to routes/admin.py.

# ---- Public forgot-password / reset-password flow ---------------------------
# Moved to routes/auth.py.


# DELETE /admin/workers/{id} moved to routes/admin.py.
# ---- Self-service password change ------------------------------------------
# Moved to routes/auth.py.


# ---- Clock in / out --------------------------------------------------------
# Moved to routes/gigs.py.

# /admin/stats moved to routes/admin.py.
# ----------------------------------------------------------------------------
# Pay, timesheet approval, reports, and Google Sheets export
# ----------------------------------------------------------------------------
# Pay overrides + timesheet endpoints moved to routes/admin.py.


# ----------------------------------------------------------------------------
# Worker ratings — admin manual stars + public client feedback link
# ----------------------------------------------------------------------------
@api.put("/gigs/{gig_id}/acceptances/{acceptance_id}/rating")
async def admin_set_rating(
    gig_id: str,
    acceptance_id: str,
    payload: AdminRatingIn,
    admin: dict = Depends(require_admin),
):
    """Admin sets a 1-5 star rating + optional private note for a worker on a
    specific gig. Pass `clear=true` to remove the rating."""
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Acceptance not found")

    set_ops: dict = {}
    unset_ops: dict = {}
    if payload.clear:
        unset_ops["admin_rating"] = ""
        unset_ops["admin_rating_note"] = ""
        unset_ops["admin_rating_at"] = ""
        unset_ops["admin_rating_by"] = ""
    else:
        if payload.stars is None:
            raise HTTPException(400, "stars (1-5) required unless clear=true")
        if payload.stars < 1 or payload.stars > 5:
            raise HTTPException(400, "stars must be between 1 and 5")
        set_ops["admin_rating"] = int(payload.stars)
        set_ops["admin_rating_at"] = datetime.now(timezone.utc).isoformat()
        set_ops["admin_rating_by"] = admin["email"]
        if payload.note is not None:
            set_ops["admin_rating_note"] = payload.note

    ops: dict = {}
    if set_ops:
        ops["$set"] = set_ops
    if unset_ops:
        ops["$unset"] = unset_ops
    await db.gig_acceptances.update_one({"acceptance_id": acceptance_id}, ops)
    logger.info(
        f"Admin {admin['email']} set rating {payload.stars} on {acceptance_id}"
    )
    return {"ok": True, "admin_rating": set_ops.get("admin_rating")}



@api.put("/gigs/{gig_id}/acceptances/{acceptance_id}/admin-note")
async def admin_set_gig_note(
    gig_id: str,
    acceptance_id: str,
    payload: AdminGigNoteIn,
    admin: dict = Depends(require_admin),
):
    """Per-gig private admin note about this worker on this gig. Separate
    from the rating note. Pass an empty string or null to clear."""
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Acceptance not found")
    text = (payload.note or "").strip()
    if not text:
        await db.gig_acceptances.update_one(
            {"acceptance_id": acceptance_id},
            {
                "$unset": {
                    "admin_gig_note": "",
                    "admin_gig_note_at": "",
                    "admin_gig_note_by": "",
                }
            },
        )
    else:
        await db.gig_acceptances.update_one(
            {"acceptance_id": acceptance_id},
            {
                "$set": {
                    "admin_gig_note": text,
                    "admin_gig_note_at": datetime.now(timezone.utc).isoformat(),
                    "admin_gig_note_by": admin["email"],
                }
            },
        )
    return {"ok": True}


@api.post("/admin/workers/{user_id}/message")
async def admin_send_worker_message(
    user_id: str,
    payload: WorkerMessageIn,
    admin: dict = Depends(require_admin),
):
    """Drop a notification into the worker's inbox. Surfaces in /notifications
    and (if gig_id provided) is visible on that gig's detail page."""
    worker = await db.users.find_one({"user_id": user_id})
    if not worker or worker.get("role") != "worker":
        raise HTTPException(404, "Worker not found")
    body = (payload.body or "").strip()
    if not body:
        raise HTTPException(400, "Message body required")
    title = (payload.title or "Message from HCOB").strip()
    if payload.gig_id:
        gig = await db.gigs.find_one({"gig_id": payload.gig_id}, {"_id": 0, "title": 1})
        if gig and not payload.title:
            title = f"Note for: {gig.get('title')}"

    notif_id = f"ntf_{uuid.uuid4().hex[:12]}"
    await db.notifications.insert_one(
        {
            "notification_id": notif_id,
            "user_id": user_id,
            "gig_id": payload.gig_id,
            "title": title,
            "body": body,
            "from_admin": admin["email"],
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    logger.info(
        f"Admin {admin['email']} sent message to worker {worker.get('email')}: {title}"
    )
    return {"ok": True, "notification_id": notif_id}




@api.put("/gigs/{gig_id}/acceptances/{acceptance_id}/role")
async def admin_set_gig_role(
    gig_id: str,
    acceptance_id: str,
    payload: AcceptanceRoleIn,
    admin: dict = Depends(require_admin),
):
    """Set a worker's per-gig role (worker / manager / lead / trainer).
    Workers see their role + their crew's roles after they're approved."""
    if payload.role not in GIG_ROLES:
        raise HTTPException(400, f"role must be one of {GIG_ROLES}")
    res = await db.gig_acceptances.update_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id},
        {"$set": {"gig_role": payload.role}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Acceptance not found")
    return {"ok": True, "gig_role": payload.role}


@api.get("/public/gigs/{gig_id}")
async def public_gig_lookup(gig_id: str):
    """Public no-auth view of a gig — used by direct share links. Strips the
    private address line; the rest is the same info workers see when browsing.
    Returns 404 for cancelled gigs."""
    gig = await db.gigs.find_one({"gig_id": gig_id}, {"_id": 0})
    if not gig:
        raise HTTPException(404, "Gig not found")
    if gig.get("status") == "cancelled":
        raise HTTPException(404, "Gig is no longer available")
    # Strip sensitive fields
    safe = {
        "gig_id": gig["gig_id"],
        "title": gig.get("title"),
        "description": gig.get("description"),
        "category": gig.get("category"),
        "subcategory": gig.get("subcategory"),
        "location": gig.get("location"),
        "scheduled_date": gig.get("scheduled_date"),
        "scheduled_at": gig.get("scheduled_at"),
        "scheduled_local": gig.get("scheduled_local"),
        "start_time": gig.get("start_time"),
        "duration_hours": gig.get("duration_hours"),
        "pay_rate": gig.get("pay_rate"),
        "pay_type": gig.get("pay_type"),
        "payment_timeline": gig.get("payment_timeline") or "2_3_days",
        "payment_timeline_note": gig.get("payment_timeline_note"),
        "slots": gig.get("slots"),
        "slots_filled": gig.get("slots_filled"),
        "status": gig.get("status"),
    }
    return safe


# --- HTML escape helper for the OG share endpoint ---
def _html_escape(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


@api.get("/share/gigs/{gig_id}", response_class=HTMLResponse)
async def share_gig_og(gig_id: str, request: Request):
    """Server-rendered HTML page with Open Graph + Twitter Card meta tags so
    that social previews (iMessage, Slack, WhatsApp, Facebook, Twitter, LinkedIn)
    unfurl with the gig's title, category, pay, and a branded image.

    Real browsers see a meta-refresh to `/gigs/{gig_id}` so they land on the
    React app immediately. Bots that just scrape the head will read the tags."""
    gig = await db.gigs.find_one({"gig_id": gig_id}, {"_id": 0})
    # Use proxy-forwarded headers if present so the canonical host matches the
    # public URL (not the internal cluster hostname FastAPI sees). Falls back
    # to env vars, then request.base_url.
    fwd_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    fwd_proto = request.headers.get("x-forwarded-proto") or "https"
    if fwd_host:
        base = f"{fwd_proto}://{fwd_host}"
    else:
        base = (
            os.environ.get("PUBLIC_BASE_URL")
            or str(request.base_url).rstrip("/")
        )
    base = base.rstrip("/")
    canonical = f"{base}/api/share/gigs/{gig_id}"
    react_url = f"{base}/gigs/{gig_id}"
    og_image = f"{base}/og-default.png"

    if not gig or gig.get("status") == "cancelled":
        title = "Gig no longer available — HCOB Network"
        desc = "This gig has been filled or removed. See open gigs at HCOB Network."
        html = f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{_html_escape(title)}</title>
<meta name="description" content="{_html_escape(desc)}" />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="HCOB Network" />
<meta property="og:title" content="{_html_escape(title)}" />
<meta property="og:description" content="{_html_escape(desc)}" />
<meta property="og:image" content="{og_image}" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta property="og:url" content="{canonical}" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{_html_escape(title)}" />
<meta name="twitter:description" content="{_html_escape(desc)}" />
<meta name="twitter:image" content="{og_image}" />
<meta http-equiv="refresh" content="0;url={react_url}" />
<link rel="canonical" href="{canonical}" />
</head><body><p>Redirecting… <a href="{react_url}">View on HCOB Network</a>.</p></body></html>"""
        return HTMLResponse(content=html, status_code=200)

    title_raw = gig.get("title") or "HCOB Network Gig"
    category = (gig.get("category") or "").title()
    sub = (gig.get("subcategory") or "").replace("_", " ")
    pay = gig.get("pay_rate")
    pay_type = gig.get("pay_type") or "hourly"
    location = gig.get("location") or "Baltimore, MD"
    scheduled = gig.get("scheduled_date") or "TBD"
    pay_str = f"${pay:.0f}{'/hr' if pay_type == 'hourly' else ' flat'}" if pay else ""

    title_full = f"{title_raw} — {pay_str} · {location} · HCOB Network"
    parts = [category]
    if sub and sub != "general":
        parts.append(sub)
    if pay_str:
        parts.append(pay_str)
    parts.append(location)
    parts.append(f"Scheduled {scheduled}")
    desc = " · ".join(parts) + ". Apply on HCOB Network."

    # Use the dynamic OG image if available; otherwise fall back to default
    dynamic_og_image = f"{base}/api/share/gigs/{gig_id}/og-image"

    html = f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{_html_escape(title_full)}</title>
<meta name="description" content="{_html_escape(desc)}" />
<meta name="theme-color" content="#0044FF" />

<meta property="og:type" content="website" />
<meta property="og:site_name" content="HCOB Network" />
<meta property="og:title" content="{_html_escape(title_raw)} — {_html_escape(pay_str)}" />
<meta property="og:description" content="{_html_escape(desc)}" />
<meta property="og:image" content="{dynamic_og_image}" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta property="og:image:alt" content="{_html_escape(title_raw)} on HCOB Network" />
<meta property="og:url" content="{canonical}" />
<meta property="og:locale" content="en_US" />

<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{_html_escape(title_raw)} — {_html_escape(pay_str)}" />
<meta name="twitter:description" content="{_html_escape(desc)}" />
<meta name="twitter:image" content="{dynamic_og_image}" />

<link rel="canonical" href="{canonical}" />
<link rel="icon" href="/favicon.ico" />
<meta http-equiv="refresh" content="0;url={react_url}" />
<style>body{{margin:0;padding:64px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#030712;color:#fff;text-align:center;}}a{{color:#0044FF;}}</style>
</head>
<body>
<h1>Redirecting to HCOB Network…</h1>
<p>If you are not redirected automatically, <a href="{react_url}">click here to view this gig</a>.</p>
<script>window.location.replace("{react_url}");</script>
</body></html>"""
    return HTMLResponse(content=html, status_code=200)


@api.get("/share/gigs/{gig_id}/og-image", response_class=Response)
async def share_gig_og_image(gig_id: str):
    """Dynamically rendered 1200x630 PNG for the gig's social preview. Falls
    back to the default site OG image if the gig is missing/cancelled or PIL
    fails for any reason."""
    gig = await db.gigs.find_one({"gig_id": gig_id}, {"_id": 0})
    fallback_path = "/app/frontend/public/og-default.png"
    if not gig or gig.get("status") == "cancelled":
        try:
            with open(fallback_path, "rb") as f:
                return Response(content=f.read(), media_type="image/png")
        except FileNotFoundError:
            raise HTTPException(404, "Image unavailable")

    try:
        from PIL import Image, ImageDraw, ImageFont
        import os

        def find_font(size, bold=False):
            cands = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
            for c in cands:
                if os.path.exists(c):
                    return ImageFont.truetype(c, size)
            return ImageFont.load_default()

        W, H = 1200, 630
        INK = (3, 7, 18)
        BLUE = (0, 68, 255)
        WHITE = (255, 255, 255)
        RED = (239, 68, 68)
        YELLOW = (234, 179, 8)
        ORANGE = (249, 115, 22)

        TAG_STYLE = {
            "rush": ("RUSH", RED, WHITE),
            "priority_need": ("PRIORITY", ORANGE, WHITE),
            "same_day": ("SAME DAY", YELLOW, INK),
            "top_pay": ("TOP PAY", BLUE, WHITE),
        }

        img = Image.new("RGB", (W, H), INK)
        d = ImageDraw.Draw(img)
        # Subtle grid
        for x in range(0, W, 60):
            d.line([(x, 0), (x, H)], fill=(20, 25, 40), width=1)
        for y in range(0, H, 60):
            d.line([(0, y), (W, y)], fill=(20, 25, 40), width=1)
        d.rectangle([(0, 0), (W, 8)], fill=BLUE)

        # Logo
        d.rounded_rectangle([(80, 80), (160, 160)], radius=12, fill=BLUE)
        bolt = [(130, 98), (108, 130), (122, 130), (116, 152), (140, 118), (126, 118), (132, 98)]
        d.polygon(bolt, fill=WHITE)

        # Branding text
        d.text((180, 92), "HCOB NETWORK", font=find_font(38, bold=True), fill=WHITE)
        d.text((180, 134), "DISPATCH · BALTIMORE, MD", font=find_font(18), fill=BLUE)

        # Category label
        cat = (gig.get("category") or "").upper()
        sub = (gig.get("subcategory") or "").replace("_", " ").upper()
        cat_label = f"{cat} · {sub}" if sub and sub != "GENERAL" else cat
        d.text((80, 220), cat_label, font=find_font(22, bold=True), fill=(180, 195, 215))

        # Gig title (wrapped to 2 lines)
        title = gig.get("title") or "HCOB Gig"
        font_title = find_font(76, bold=True)
        # Naive wrap by char width
        words = title.split()
        lines = []
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if d.textlength(test, font=font_title) > 1040 and cur:
                lines.append(cur)
                cur = w
            else:
                cur = test
        if cur:
            lines.append(cur)
        lines = lines[:2]
        if len(lines) == 2 and d.textlength(title, font=font_title) > 2080:
            lines[1] = lines[1][:40] + "…"
        ty = 270
        for ln in lines:
            d.text((80, ty), ln, font=font_title, fill=WHITE)
            ty += 86

        # Meta line: location · scheduled · pay
        loc = gig.get("location") or "Baltimore, MD"
        sched = gig.get("scheduled_date") or "TBD"
        pay = gig.get("pay_rate")
        pay_type = gig.get("pay_type") or "hourly"
        pay_str = f"${int(pay)}{'/hr' if pay_type == 'hourly' else ' flat'}" if pay else ""
        meta_parts = [loc, sched]
        if pay_str:
            meta_parts.append(pay_str)
        d.text((80, 470), " · ".join(meta_parts), font=find_font(28), fill=(180, 195, 215))

        # Pay block (right side, big)
        if pay_str:
            font_pay = find_font(82, bold=True)
            pw = d.textlength(pay_str, font=font_pay)
            d.text((W - 80 - pw, 250), pay_str, font=font_pay, fill=BLUE)
            d.text((W - 80 - pw + (pw - d.textlength("PAY", font=find_font(20, bold=True))) / 2, 226), "PAY", font=find_font(20, bold=True), fill=(180, 195, 215))

        # Tag pills bottom-right
        active_tags = [t for t in (gig.get("tags") or []) if t in TAG_STYLE]
        if active_tags:
            px = W - 60
            py = H - 80
            font_pill = find_font(22, bold=True)
            for t in reversed(active_tags):
                label, bg, fg = TAG_STYLE[t]
                tw = d.textlength(label, font=font_pill)
                pw_ = int(tw + 36)
                d.rounded_rectangle([(px - pw_, py), (px, py + 48)], radius=24, fill=bg)
                d.text((px - pw_ + 18, py + 12), label, font=font_pill, fill=fg)
                px -= pw_ + 12

        from io import BytesIO
        buf = BytesIO()
        img.save(buf, "PNG", optimize=True)
        return Response(content=buf.getvalue(), media_type="image/png", headers={"Cache-Control": "public, max-age=300"})
    except Exception as e:
        logger.exception("OG image generation failed for gig %s: %s", gig_id, e)
        try:
            with open(fallback_path, "rb") as f:
                return Response(content=f.read(), media_type="image/png")
        except FileNotFoundError:
            raise HTTPException(500, "Image generation failed")


@api.get("/public/gigs")
async def public_gig_feed(limit: int = Query(3, ge=1, le=24)):
    """Public no-auth feed of currently-open + upcoming gigs for the marketing
    landing page. RUSH first, then highest-paying, then newest. Address and
    contact phone are never exposed; only marketing-safe fields."""
    gigs = (
        await db.gigs.find(
            {"status": {"$in": ["open", "coming_soon"]}},
            {"_id": 0},
        )
        .sort([("is_rush", -1), ("pay_rate", -1), ("created_at", -1)])
        .to_list(limit)
    )
    return [
        {
            "gig_id": g["gig_id"],
            "title": g.get("title"),
            "category": g.get("category"),
            "subcategory": g.get("subcategory"),
            "location": g.get("location"),
            "scheduled_date": g.get("scheduled_date"),
            "scheduled_at": g.get("scheduled_at"),
            "scheduled_local": g.get("scheduled_local"),
            "pay_rate": g.get("pay_rate"),
            "pay_type": g.get("pay_type"),
            "payment_timeline": g.get("payment_timeline") or "2_3_days",
            "slots": g.get("slots"),
            "slots_filled": g.get("slots_filled"),
            "status": g.get("status"),
            "is_rush": bool(g.get("is_rush")),
            "tags": [t for t in (g.get("tags") or []) if t in GIG_TAG_VALUES],
        }
        for g in gigs
    ]


# ----------------------------------------------------------------------------
# Public quote-request lead capture from /customers — emails the owner with
# the lead and stores it so admins can follow up.
# ----------------------------------------------------------------------------
# Owner contact defaults. Both overridable via app_settings (Settings page).
HCOB_OWNER_PHONE = os.environ.get("HCOB_OWNER_PHONE", "+14108709347")
HCOB_OWNER_EMAIL = os.environ.get("HCOB_OWNER_EMAIL", "corymclarke7126@gmail.com")


def _format_quote_email(q: dict) -> tuple[str, str]:
    """Build a (subject, html_body) pair for the owner's lead notification."""
    rows = [
        ("Name", q.get("name")),
        ("Phone", q.get("phone")),
        ("Email", q.get("email")),
        ("Service", q.get("service")),
        ("Timeline", q.get("timeline")),
        ("Address", q.get("address")),
    ]
    table_rows = "".join(
        f"<tr><td style='padding:6px 12px;color:#4B5563;font-size:13px;width:100px'>{k}</td>"
        f"<td style='padding:6px 12px;color:#030712;font-weight:600;font-size:14px'>{v}</td></tr>"
        for k, v in rows
        if v
    )
    message_block = ""
    if q.get("message"):
        message_block = (
            f"<div style='margin-top:16px;padding:14px;background:#F9FAFB;border-left:3px solid #0044FF;color:#030712;font-size:14px;line-height:1.5'>"
            f"{q['message']}</div>"
        )
    phone_link = f"tel:{q.get('phone', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')}"
    subject = f"[HCOB Lead] {q.get('name')} — {q.get('service')} ({q.get('timeline')})"
    html = (
        f"<div style='font-family:Inter,Arial,sans-serif;max-width:600px;padding:20px;background:#F9FAFB'>"
        f"<div style='background:#FFFFFF;border:1px solid #E5E7EB;padding:24px'>"
        f"<div style='font-size:11px;letter-spacing:2px;color:#0044FF;font-weight:bold'>NEW QUOTE REQUEST · HCOB NETWORK</div>"
        f"<h2 style='margin:6px 0 16px 0;font-size:22px;color:#030712'>{q.get('name')}</h2>"
        f"<table cellspacing='0' style='border-collapse:collapse;border:1px solid #E5E7EB;width:100%'>"
        f"{table_rows}"
        f"</table>"
        f"{message_block}"
        f"<table cellpadding='0' cellspacing='0' style='margin-top:22px'><tr>"
        f"<td bgcolor='#0044FF' style='padding:0 8px 0 0'>"
        f"<a href='{phone_link}' style='display:inline-block;padding:12px 22px;background:#0044FF;color:#FFFFFF;font-size:14px;font-weight:bold;text-decoration:none'>"
        f"📞 Call {q.get('name', '').split()[0] if q.get('name') else 'them'}"
        f"</a></td>"
        f"<td bgcolor='#030712'>"
        f"<a href='https://hcobnetwork.com/ops/quotes' style='display:inline-block;padding:12px 22px;background:#030712;color:#FFFFFF;font-size:14px;font-weight:bold;text-decoration:none'>"
        f"Open lead inbox →"
        f"</a></td>"
        f"</tr></table>"
        f"<p style='font-size:11px;color:#9CA3AF;margin-top:18px'>"
        f"Lead ID: {q.get('quote_id')} · Received {q.get('created_at')}"
        f"</p>"
        f"</div></div>"
    )
    return subject, html


@api.post("/public/quote-requests")
async def create_quote_request(payload: QuoteRequestIn, request: Request):
    """Lead capture from the customer marketing page. No auth required."""
    # Honeypot — bots fill hidden fields, real users don't. Silently accept.
    if (payload.website or "").strip():
        return {"ok": True, "quote_id": "spam_ignored"}

    name = payload.name.strip()
    phone = payload.phone.strip()
    if not name or not phone:
        raise HTTPException(400, "Name and phone are required.")

    # Light rate-limit: max 5 leads per IP per hour.
    ip = (request.client.host if request.client else "") or "unknown"
    one_hour_ago = (
        datetime.now(timezone.utc) - timedelta(hours=1)
    ).isoformat()
    recent = await db.quote_requests.count_documents(
        {"ip": ip, "created_at": {"$gte": one_hour_ago}}
    )
    if recent >= 5:
        raise HTTPException(
            429,
            "Too many requests. Please call (410) 870-9347 directly — we'll help right away.",
        )

    quote_id = f"qr_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    doc = {
        "quote_id": quote_id,
        "name": name,
        "phone": phone,
        "email": (payload.email or "").strip() or None,
        "service": payload.service.strip(),
        "timeline": payload.timeline.strip(),
        "message": (payload.message or "").strip() or None,
        "address": (payload.address or "").strip() or None,
        "status": "new",
        "admin_note": None,
        "ip": ip,
        "user_agent": (request.headers.get("user-agent") or "")[:200],
        "created_at": now_iso,
        # Notification delivery status (email-first now, sms field kept for
        # backward-compat with existing admin UI).
        "notify_sent": False,
        "notify_error": None,
        "sms_sent": False,
        "sms_error": None,
    }
    await db.quote_requests.insert_one(doc)

    # Email the owner — primary delivery channel for new leads.
    settings_doc = await _get_settings_doc()
    email_creds = await _resolve_email_creds()
    owner_email = (
        (settings_doc.get("quote_notify_email") or HCOB_OWNER_EMAIL)
    ).strip()
    notify_sent = False
    notify_err = None
    if email_creds and email_creds.get("api_key") and owner_email:
        try:
            subject, html = _format_quote_email(doc)
            await asyncio.to_thread(
                _send_email_sync,
                email_creds["api_key"],
                email_creds["sender"],
                owner_email,
                subject,
                html,
            )
            notify_sent = True
        except Exception as e:
            notify_err = str(e)[:200]
            logger.error(f"Quote-request email failed for {quote_id}: {e}")
    else:
        notify_err = "no_email_creds"

    await db.quote_requests.update_one(
        {"quote_id": quote_id},
        {"$set": {"notify_sent": notify_sent, "notify_error": notify_err}},
    )

    return {
        "ok": True,
        "quote_id": quote_id,
        "message": "Thanks! We'll text or call you back shortly. For urgent needs call (410) 870-9347.",
    }


@api.get("/admin/quote-requests")
async def list_quote_requests(
    status: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    admin: dict = Depends(require_admin),
):
    q = {}
    if status:
        q["status"] = status
    rows = (
        await db.quote_requests.find(q, {"_id": 0, "ip": 0, "user_agent": 0})
        .sort("created_at", -1)
        .to_list(limit)
    )
    counts = {
        "new": await db.quote_requests.count_documents({"status": "new"}),
        "contacted": await db.quote_requests.count_documents({"status": "contacted"}),
        "won": await db.quote_requests.count_documents({"status": "won"}),
        "lost": await db.quote_requests.count_documents({"status": "lost"}),
        "dismissed": await db.quote_requests.count_documents({"status": "dismissed"}),
    }
    return {"items": rows, "counts": counts}


@api.patch("/admin/quote-requests/{quote_id}")
async def update_quote_request(
    quote_id: str, payload: QuoteRequestPatch, admin: dict = Depends(require_admin)
):
    existing = await db.quote_requests.find_one({"quote_id": quote_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Quote request not found")
    updates = {}
    if payload.status is not None:
        updates["status"] = payload.status
    if payload.admin_note is not None:
        updates["admin_note"] = payload.admin_note
    if not updates:
        return existing
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.quote_requests.update_one({"quote_id": quote_id}, {"$set": updates})
    return await db.quote_requests.find_one(
        {"quote_id": quote_id}, {"_id": 0, "ip": 0, "user_agent": 0}
    )


# ----------------------------------------------------------------------------
# Admin user management (super admins only — read-only admins blocked by
# require_admin's method check)
# ----------------------------------------------------------------------------
@api.get("/admin/admins")
async def list_admin_users(admin: dict = Depends(require_admin)):
    """List all admin users so the Settings page can show who has access."""
    rows = await db.users.find(
        {"role": "admin"}, {"_id": 0, "password_hash": 0}
    ).sort("created_at", 1).to_list(200)
    # Public-shape each row
    return [
        {
            "user_id": r["user_id"],
            "name": r.get("name"),
            "email": r.get("email"),
            "is_read_only": bool(r.get("is_read_only")),
            "created_at": r.get("created_at"),
            "is_self": r["user_id"] == admin["user_id"],
        }
        for r in rows
    ]


@api.post("/admin/admins")
async def create_admin_user(
    payload: AdminCreateIn,
    admin: dict = Depends(require_admin),
):
    """Create a new admin user. Read-only admins are blocked by the method
    check in require_admin."""
    name = (payload.name or "").strip()
    email = (payload.email or "").strip().lower()
    if not name:
        raise HTTPException(400, "Name required")
    if "@" not in email or "." not in email:
        raise HTTPException(400, "Valid email required")
    if len(payload.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(400, "An account with that email already exists")
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    doc = {
        "user_id": user_id,
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": name,
        "role": "admin",
        "is_read_only": bool(payload.is_read_only),
        "phone": "",
        "address": "",
        "bio": "",
        "skills": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "auth_provider": "local",
        "id_verified": True,  # admins don't need ID verification
    }
    await db.users.insert_one(doc)
    logger.info(
        f"Admin {admin['email']} created new admin {email} (read_only={doc['is_read_only']})"
    )
    return {
        "user_id": user_id,
        "name": name,
        "email": email,
        "is_read_only": doc["is_read_only"],
        "created_at": doc["created_at"],
    }


@api.put("/admin/admins/{user_id}")
async def update_admin_user(
    user_id: str,
    payload: AdminRoleUpdateIn,
    admin: dict = Depends(require_admin),
):
    """Toggle read-only flag on an admin OR promote a worker → admin / demote
    an admin → worker."""
    target = await db.users.find_one({"user_id": user_id})
    if not target:
        raise HTTPException(404, "User not found")

    updates: dict = {}
    if payload.promote_to_admin:
        if target.get("role") == "admin":
            raise HTTPException(400, "Already an admin")
        updates["role"] = "admin"
        updates["is_read_only"] = bool(payload.is_read_only)
    elif payload.demote_to_worker:
        if target.get("user_id") == admin["user_id"]:
            raise HTTPException(400, "You can't demote yourself")
        if target.get("role") != "admin":
            raise HTTPException(400, "Not an admin")
        updates["role"] = "worker"
        updates["is_read_only"] = False
        updates["worker_status"] = "approved"
    elif payload.is_read_only is not None:
        if target.get("role") != "admin":
            raise HTTPException(400, "Read-only flag only applies to admins")
        if target.get("user_id") == admin["user_id"] and payload.is_read_only:
            raise HTTPException(400, "You can't make yourself read-only")
        updates["is_read_only"] = bool(payload.is_read_only)
    else:
        raise HTTPException(400, "Nothing to update")

    await db.users.update_one({"user_id": user_id}, {"$set": updates})
    if updates.get("role") == "worker":
        # When demoting, drop their sessions so they re-login as worker
        await db.sessions.delete_many({"user_id": user_id})
    logger.info(f"Admin {admin['email']} updated admin {target.get('email')}: {updates}")
    return await _get_user_by_id(user_id)


@api.delete("/admin/admins/{user_id}")
async def delete_admin_user(user_id: str, admin: dict = Depends(require_admin)):
    """Demote+delete an admin account. Cannot delete yourself or the last
    full-access admin."""
    if user_id == admin["user_id"]:
        raise HTTPException(400, "You can't delete yourself")
    target = await db.users.find_one({"user_id": user_id})
    if not target or target.get("role") != "admin":
        raise HTTPException(404, "Admin not found")
    # Guardrail: never let admin count drop to 0 full-access admins
    full_count = await db.users.count_documents(
        {"role": "admin", "is_read_only": {"$ne": True}, "user_id": {"$ne": user_id}}
    )
    if full_count == 0:
        raise HTTPException(
            400, "Can't delete the last full-access admin — promote someone first"
        )
    await db.users.delete_one({"user_id": user_id})
    await db.sessions.delete_many({"user_id": user_id})
    logger.info(f"Admin {admin['email']} deleted admin {target.get('email')}")
    return {"ok": True}






@api.post("/gigs/{gig_id}/acceptances/{acceptance_id}/rating-link")
async def admin_generate_client_rating_link(
    gig_id: str,
    acceptance_id: str,
    payload: ClientRatingLinkIn,
    admin: dict = Depends(require_admin),
):
    """Generate (or regenerate) a public client-feedback token for an
    acceptance. Returns the absolute URL the admin can share with the client.

    Tokens never expire — they're invalidated once a client submits OR when
    regenerate=true is sent."""
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Acceptance not found")

    token = acceptance.get("client_rating_token")
    if not token or payload.regenerate:
        token = secrets.token_urlsafe(20)

    set_ops: dict = {
        "client_rating_token": token,
        "client_rating_token_at": datetime.now(timezone.utc).isoformat(),
    }
    if payload.client_email is not None:
        set_ops["client_email"] = payload.client_email.strip().lower() or None
    # Regenerate also clears any previous submission so the new token is valid
    if payload.regenerate:
        set_ops["client_rating"] = None
        set_ops["client_rating_note"] = None
        set_ops["client_rating_at"] = None
        set_ops["client_rating_submitted_name"] = None
    await db.gig_acceptances.update_one({"acceptance_id": acceptance_id}, {"$set": set_ops})

    base = os.environ.get("FRONTEND_BASE_URL", "").rstrip("/")
    url = f"{base}/rate/{token}" if base else f"/rate/{token}"
    return {
        "token": token,
        "url": url,
        "client_email": set_ops.get("client_email"),
    }


@api.get("/public/rating/{token}")
async def public_rating_lookup(token: str):
    """Public, no-auth lookup. Returns minimum info needed for the client to
    leave a rating: worker name, gig title, gig date, gig location."""
    acceptance = await db.gig_acceptances.find_one(
        {"client_rating_token": token}, {"_id": 0}
    )
    if not acceptance:
        raise HTTPException(404, "Rating link not found or already used")
    gig = await db.gigs.find_one(
        {"gig_id": acceptance["gig_id"]},
        {"_id": 0, "title": 1, "category": 1, "scheduled_date": 1, "location": 1},
    )
    worker = await db.users.find_one(
        {"user_id": acceptance["worker_id"]},
        {"_id": 0, "name": 1},
    )
    return {
        "token": token,
        "worker_name": (worker or {}).get("name") or "Worker",
        "gig_title": (gig or {}).get("title") or "",
        "gig_category": (gig or {}).get("category") or "",
        "gig_scheduled_date": (gig or {}).get("scheduled_date") or "",
        "gig_location": (gig or {}).get("location") or "",
    }


@api.post("/public/rating/{token}")
async def public_rating_submit(token: str, payload: ClientRatingSubmitIn):
    """Public submission of a client rating. After submission, the token is
    burned so the URL can't be reused. Admin can regenerate."""
    if payload.stars < 1 or payload.stars > 5:
        raise HTTPException(400, "stars must be between 1 and 5")
    acceptance = await db.gig_acceptances.find_one({"client_rating_token": token})
    if not acceptance:
        raise HTTPException(404, "Rating link not found or already used")
    if acceptance.get("client_rating") is not None:
        raise HTTPException(
            400,
            "This rating has already been submitted. Ask HCOB for a new link if you want to change it.",
        )
    await db.gig_acceptances.update_one(
        {"acceptance_id": acceptance["acceptance_id"]},
        {
            "$set": {
                "client_rating": int(payload.stars),
                "client_rating_note": (payload.note or "").strip() or None,
                "client_rating_at": datetime.now(timezone.utc).isoformat(),
                "client_rating_submitted_name": (payload.client_name or "").strip() or None,
                "client_rating_token": None,  # burn so it can't be replayed
            }
        },
    )
    logger.info(
        f"Client rating submitted: {payload.stars} on {acceptance['acceptance_id']}"
    )
    return {"ok": True, "stars": payload.stars}





# ---- Reports + /me/earnings ------------------------------------------------
# All admin/reports/* endpoints + /me/earnings + their builders
# (workers/gigs/activity/earnings/blasts/timesheets reports + Google Sheets
# export) live in routes/reports.py.
# ---- Admin settings (Resend / Twilio) --------------------------------------
def _mask(value: Optional[str]) -> dict:
    v = (value or "").strip()
    if not v:
        return {"has_value": False, "last4": ""}
    return {"has_value": True, "last4": v[-4:] if len(v) >= 4 else v}


@api.get("/admin/settings")
async def get_settings(admin: dict = Depends(require_admin)):
    """Return masked settings + which channels are usable."""
    s = await _get_settings_doc()
    email = await _resolve_email_creds()
    sms = await _resolve_sms_creds()
    gs_json = s.get("google_service_account_json") or ""
    gs_email = ""
    if gs_json:
        try:
            import json as _json
            gs_email = _json.loads(gs_json).get("client_email", "")
        except Exception:
            gs_email = ""
    return {
        "resend_api_key": _mask(s.get("resend_api_key")),
        "sender_email": s.get("sender_email") or SENDER_EMAIL or "",
        "twilio_account_sid": _mask(s.get("twilio_account_sid")),
        "twilio_auth_token": _mask(s.get("twilio_auth_token")),
        "twilio_from_number": s.get("twilio_from_number") or TWILIO_FROM or "",
        "email_ready": bool(email["api_key"] and email["sender"]),
        "sms_ready": bool(sms["sid"] and sms["token"] and sms["from_"]),
        "google_sheets_ready": bool(gs_json),
        "google_sheets_service_email": gs_email,
        "google_sheets_share_email": s.get("google_sheets_share_email") or "",
        "updated_at": s.get("updated_at"),
        "updated_by": s.get("updated_by"),
    }


@api.put("/admin/settings")
async def update_settings(
    payload: SettingsIn, admin: dict = Depends(require_admin)
):
    """Update settings. Empty string clears a field; None leaves it unchanged."""
    incoming = payload.model_dump(exclude_unset=True)
    update_set: dict = {}
    unset: dict = {}
    for k, v in incoming.items():
        if v is None:
            continue
        v = v.strip()
        if v == "":
            unset[k] = ""
        else:
            update_set[k] = v

    if not update_set and not unset:
        return {"ok": True, "changed": 0}

    update_set["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_set["updated_by"] = admin["email"]
    ops: dict = {"$set": update_set}
    if unset:
        ops["$unset"] = unset

    await db.app_settings.update_one({"_id": "global"}, ops, upsert=True)
    return {"ok": True, "changed": len(update_set) + len(unset)}


@api.post("/admin/settings/test")
async def test_settings(
    payload: SettingsTestIn, admin: dict = Depends(require_admin)
):
    """Send a test email or SMS to verify saved credentials."""
    if payload.channel == "email":
        creds = await _resolve_email_creds()
        if not creds["api_key"]:
            raise HTTPException(400, "Resend API key not set")
        try:
            result = await asyncio.to_thread(
                _send_email_sync,
                creds["api_key"],
                creds["sender"],
                payload.to,
                "HCOB Network — test email",
                "<p>This is a test email from HCOB Network settings. If you see this, your Resend credentials are working.</p>",
            )
            return {"ok": True, "result": result}
        except Exception as e:
            raise HTTPException(400, f"Email test failed: {e}")

    if payload.channel == "sms":
        creds = await _resolve_sms_creds()
        if not (creds["sid"] and creds["token"] and creds["from_"]):
            raise HTTPException(400, "Twilio credentials incomplete")
        try:
            result = await asyncio.to_thread(
                _send_sms_sync,
                creds["sid"],
                creds["token"],
                creds["from_"],
                payload.to,
                "HCOB Network — test SMS. Your Twilio credentials are working.",
            )
            return {"ok": True, "result": result}
        except Exception as e:
            raise HTTPException(400, f"SMS test failed: {e}")










api.include_router(messages_router)
api.include_router(push_router)
api.include_router(auth_router)
api.include_router(profile_router)
api.include_router(gigs_router)
api.include_router(admin_router)
api.include_router(reports_router)
api.include_router(va_router)
api.include_router(pm_router)
api.include_router(owner_router)
api.include_router(projects_router)
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.sessions.create_index("session_token", unique=True)
    await db.gigs.create_index("gig_id", unique=True)
    await db.gig_acceptances.create_index([("gig_id", 1), ("worker_id", 1)], unique=True)
    await db.notifications.create_index("user_id")

    # Messenger indexes
    await db.threads.create_index("thread_id", unique=True)
    await db.threads.create_index("participant_ids")
    await db.threads.create_index("last_message_at")
    await db.messages.create_index([("thread_id", 1), ("created_at", -1)])
    await db.thread_reads.create_index(
        [("thread_id", 1), ("user_id", 1)], unique=True
    )

    # Legacy backfill: ensure every gig has is_rush as a bool (not null) so
    # the public landing feed sorts correctly. Idempotent.
    await db.gigs.update_many(
        {"is_rush": {"$exists": False}},
        {"$set": {"is_rush": False, "rush_at": None}},
    )
    # Backfill tags array on legacy docs (any pre-tag-feature gig). If the
    # gig was previously flagged as rush, carry that into tags so the visual
    # treatment stays consistent.
    await db.gigs.update_many(
        {"tags": {"$exists": False}, "is_rush": True},
        {"$set": {"tags": ["rush"]}},
    )
    await db.gigs.update_many(
        {"tags": {"$exists": False}},
        {"$set": {"tags": []}},
    )
    # Backfill break_minutes on legacy gigs
    await db.gigs.update_many(
        {"break_minutes": {"$exists": False}},
        {"$set": {"break_minutes": 0}},
    )
    # Backfill payment_timeline on legacy gigs
    await db.gigs.update_many(
        {"payment_timeline": {"$exists": False}},
        {"$set": {"payment_timeline": "2_3_days", "payment_timeline_note": None}},
    )
    # Backfill project_id on legacy gigs
    await db.gigs.update_many(
        {"project_id": {"$exists": False}},
        {"$set": {"project_id": None}},
    )
    # Backfill scheduled_local on legacy gigs. The wall-clock string is the
    # single source of truth for display — without it, the calendar/feed have
    # to fall back to parsing scheduled_at as UTC and converting to the
    # viewer's local TZ (which makes the displayed hour drift). For legacy
    # docs we derive scheduled_local from scheduled_at assuming the platform's
    # default TZ (America/New_York — HCOB Baltimore HQ). On a brand-new gig
    # the frontend sends scheduled_local explicitly so this never runs.
    try:
        from zoneinfo import ZoneInfo
        _site_tz = ZoneInfo(os.environ.get("HCOB_SITE_TZ", "America/New_York"))
    except Exception:
        _site_tz = None
    legacy_gigs = await db.gigs.find(
        {"scheduled_local": {"$in": [None, ""]}, "scheduled_at": {"$ne": None}},
        {"gig_id": 1, "scheduled_at": 1},
    ).to_list(length=None)
    for lg in legacy_gigs:
        sa = lg.get("scheduled_at")
        if not sa:
            continue
        try:
            dt = datetime.fromisoformat(str(sa).replace("Z", "+00:00"))
            if _site_tz and dt.tzinfo is not None:
                dt_local = dt.astimezone(_site_tz)
            else:
                dt_local = dt
            sl = dt_local.strftime("%Y-%m-%dT%H:%M")
            await db.gigs.update_one(
                {"gig_id": lg["gig_id"]},
                {"$set": {"scheduled_local": sl}},
            )
        except Exception:
            continue
    # Projects collection indices
    await db.projects.create_index("project_id", unique=True)
    await db.projects.create_index([("archived", 1), ("created_at", -1)])
    await db.gigs.create_index("project_id")

    # Blast logs — Reports → Blasts
    await db.blast_logs.create_index([("sent_at", -1)])
    await db.blast_logs.create_index("gig_id")
    await db.blast_logs.create_index("project_id")

    # Password reset tokens — public forgot/reset flow
    await db.password_reset_tokens.create_index("token", unique=True)
    await db.password_reset_tokens.create_index("user_id")
    await db.password_reset_tokens.create_index("expires_at")

    # VA Commission Program indices
    await db.va_leads.create_index("lead_id", unique=True)
    await db.va_leads.create_index("va_user_id")
    await db.va_leads.create_index("prospect_phone_norm")
    await db.va_leads.create_index("prospect_email_norm")
    await db.va_leads.create_index([("created_at", -1)])
    await db.commissions.create_index("commission_id", unique=True)
    await db.commissions.create_index("lead_id")
    await db.commissions.create_index("va_user_id")
    await db.commissions.create_index("status")
    await db.commercial_accounts.create_index("account_id", unique=True)
    await db.commercial_accounts.create_index("va_user_id")
    await db.va_violations.create_index("va_user_id")
    await db.va_violations.create_index([("created_at", -1)])

    # Seed admin
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@gigblast.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "GigBlast2026!")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one(
            {
                "user_id": f"user_{uuid.uuid4().hex[:12]}",
                "email": admin_email,
                "password_hash": hash_password(admin_password),
                "name": "Operations Admin",
                "role": "admin",
                "phone": "",
                "address": "",
                "bio": "",
                "skills": [],
                "avatar_path": None,
                "id_image_path": None,
                "id_verified": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "auth_provider": "local",
            }
        )
        logger.info(f"Seeded admin user {admin_email}")
    elif not verify_password(admin_password, existing.get("password_hash", "")):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password)}},
        )

    # Production unlock failsafe — if OWNER_RESET_EMAIL + OWNER_RESET_PASSWORD
    # are BOTH set in the environment, forcibly reset that user's password on
    # boot. Designed for emergency lockout recovery in production. Remove the
    # env vars after using.
    reset_email = (os.environ.get("OWNER_RESET_EMAIL") or "").strip().lower()
    reset_pwd = (os.environ.get("OWNER_RESET_PASSWORD") or "").strip()
    if reset_email and reset_pwd:
        target = await db.users.find_one({"email": reset_email})
        if target:
            await db.users.update_one(
                {"email": reset_email},
                {"$set": {"password_hash": hash_password(reset_pwd)}},
            )
            await db.sessions.delete_many({"user_id": target.get("user_id")})
            logger.warning(
                f"[OWNER_RESET] Forcibly reset password for {reset_email} on startup. "
                f"REMOVE OWNER_RESET_EMAIL and OWNER_RESET_PASSWORD env vars now."
            )
        else:
            logger.error(f"[OWNER_RESET] Email {reset_email} not found in users.")

    # Mark the HCOB admin as Owner for VA Commission final payout sign-off.
    await db.users.update_one(
        {"email": "admin@hcobcleaners.com"},
        {"$set": {"is_owner": True}},
    )

    # Seed Mechie (Program Manager) — Mechiebadlong77@gmail.com
    mechie_email = "mechiebadlong77@gmail.com"
    mechie_password = "Mechie2026!"
    mechie = await db.users.find_one({"email": mechie_email})
    if not mechie:
        await db.users.insert_one(
            {
                "user_id": f"user_{uuid.uuid4().hex[:12]}",
                "email": mechie_email,
                "password_hash": hash_password(mechie_password),
                "name": "Mechie (Program Manager)",
                "role": "admin",
                "is_program_manager": True,
                "is_owner": False,
                "must_change_password": True,
                "phone": "",
                "address": "",
                "bio": "",
                "skills": [],
                "avatar_path": None,
                "id_image_path": None,
                "id_verified": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "auth_provider": "local",
            }
        )
        logger.info(f"Seeded Program Manager {mechie_email}")
    else:
        # Ensure the program_manager flag is set on every boot (idempotent)
        await db.users.update_one(
            {"email": mechie_email},
            {"$set": {"is_program_manager": True}},
        )

    init_storage()

    # Kick off background tasks
    asyncio.create_task(_message_digest_runner())


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
