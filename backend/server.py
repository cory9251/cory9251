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
    BlastIn,
    RushToggleIn,
    GigTagsIn,
    AssignWorkerIn,
    CancelShiftIn,
    WorkerPayIn,
    AcceptancePayIn,
    TimesheetApproveIn,
    TimesheetEditIn,
    ProjectDefaults,
    ProjectIn,
    ProjectPatch,
    ProjectNoteIn,
    LinkGigToProjectIn,
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
# Projects — bundle 2+ gigs that share a job site so crews can coordinate
# ----------------------------------------------------------------------------

def _serialize_project(p: dict) -> dict:
    """Strip Mongo's _id and return the safe view."""
    out = {k: v for k, v in p.items() if k != "_id"}
    out.setdefault("defaults", {})
    out.setdefault("notes", [])
    out.setdefault("archived", False)
    return out


def _apply_project_defaults_to_gig(gig_payload: dict, defaults: dict) -> dict:
    """Pre-fill the optional fields on a new gig from the project defaults.
    Returns a new dict (does not mutate the input). Only fills fields that
    are empty/None on the gig payload — never overwrites explicit values."""
    if not defaults:
        return gig_payload
    merged = dict(gig_payload)
    for key in ("location", "address_line", "scheduled_date", "scheduled_at",
                "payment_timeline", "payment_timeline_note", "contact_phone"):
        if defaults.get(key) and not merged.get(key):
            merged[key] = defaults[key]
    return merged


@api.post("/projects")
async def create_project(payload: ProjectIn, admin: dict = Depends(require_admin)):
    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    doc = {
        "project_id": project_id,
        "title": payload.title.strip(),
        "description": payload.description or "",
        "client_name": (payload.client_name or "").strip() or None,
        "defaults": payload.defaults.model_dump() if payload.defaults else {},
        "notes": [],
        "archived": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": admin["user_id"],
    }
    await db.projects.insert_one(doc)
    return _serialize_project(doc)


@api.get("/projects")
async def list_projects(
    archived: bool = Query(False),
    q: Optional[str] = Query(None),
    admin: dict = Depends(require_admin),
):
    """List projects with linked-gig + crew counts. `q` filters by title or client."""
    query: dict = {"archived": archived}
    if q and q.strip():
        rx = {"$regex": q.strip(), "$options": "i"}
        query["$or"] = [{"title": rx}, {"client_name": rx}]
    projects = await db.projects.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    if not projects:
        return []
    pids = [p["project_id"] for p in projects]
    gigs = await db.gigs.find({"project_id": {"$in": pids}}, {"_id": 0, "gig_id": 1, "project_id": 1, "status": 1, "slots": 1, "slots_filled": 1, "scheduled_at": 1}).to_list(2000)
    gig_ids_by_proj: Dict[str, List[str]] = {}
    slots_by_proj: Dict[str, Dict[str, int]] = {}
    dates_by_proj: Dict[str, List[str]] = {}
    for g in gigs:
        gig_ids_by_proj.setdefault(g["project_id"], []).append(g["gig_id"])
        s = slots_by_proj.setdefault(g["project_id"], {"slots": 0, "filled": 0})
        s["slots"] += int(g.get("slots") or 0)
        s["filled"] += int(g.get("slots_filled") or 0)
        if g.get("scheduled_at"):
            dates_by_proj.setdefault(g["project_id"], []).append(g["scheduled_at"])
    # Crew counts via acceptances
    accs = await db.gig_acceptances.find(
        {"gig_id": {"$in": [g["gig_id"] for g in gigs]}, "status": {"$in": ["accepted", "on_the_clock", "clocked_in", "completed"]}},
        {"_id": 0, "gig_id": 1, "worker_id": 1},
    ).to_list(5000)
    worker_set_by_proj: Dict[str, set] = {}
    gig_to_proj = {g["gig_id"]: g["project_id"] for g in gigs}
    for a in accs:
        pid = gig_to_proj.get(a["gig_id"])
        if pid:
            worker_set_by_proj.setdefault(pid, set()).add(a["worker_id"])
    out = []
    for p in projects:
        pid = p["project_id"]
        dates = sorted(dates_by_proj.get(pid, []))
        out.append({
            **_serialize_project(p),
            "gig_count": len(gig_ids_by_proj.get(pid, [])),
            "worker_count": len(worker_set_by_proj.get(pid, set())),
            "slots_total": slots_by_proj.get(pid, {}).get("slots", 0),
            "slots_filled": slots_by_proj.get(pid, {}).get("filled", 0),
            "first_scheduled_at": dates[0] if dates else None,
            "last_scheduled_at": dates[-1] if dates else None,
        })
    return out


@api.get("/projects/{project_id}")
async def get_project(project_id: str, admin: dict = Depends(require_admin)):
    """Full project: details + linked gigs + combined roster (admin view)."""
    proj = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not proj:
        raise HTTPException(404, "Project not found")
    gigs = await db.gigs.find({"project_id": project_id}, {"_id": 0}).sort("scheduled_at", 1).to_list(500)
    gig_ids = [g["gig_id"] for g in gigs]
    accs = await db.gig_acceptances.find({"gig_id": {"$in": gig_ids}}, {"_id": 0}).to_list(2000)
    worker_ids = list({a["worker_id"] for a in accs})
    workers = await db.users.find(
        {"user_id": {"$in": worker_ids}},
        {"_id": 0, "user_id": 1, "name": 1, "email": 1, "phone": 1, "first_name": 1, "last_name": 1},
    ).to_list(2000)
    wmap = {w["user_id"]: w for w in workers}
    gtitle = {g["gig_id"]: g.get("title") for g in gigs}
    gcat = {g["gig_id"]: g.get("category") for g in gigs}
    crew = []
    for a in accs:
        if a.get("status") not in ("accepted", "on_the_clock", "clocked_in", "completed", "requested"):
            continue
        w = wmap.get(a["worker_id"]) or {}
        crew.append({
            "acceptance_id": a["acceptance_id"],
            "gig_id": a["gig_id"],
            "gig_title": gtitle.get(a["gig_id"]),
            "gig_category": gcat.get(a["gig_id"]),
            "worker_id": a["worker_id"],
            "worker_name": w.get("name") or (
                f"{w.get('first_name','')} {w.get('last_name','')}".strip()
            ),
            "worker_email": w.get("email"),
            "worker_phone": w.get("phone"),
            "gig_role": a.get("gig_role") or "worker",
            "status": a.get("status"),
        })
    return {
        **_serialize_project(proj),
        "gigs": gigs,
        "crew": crew,
    }


@api.put("/projects/{project_id}")
async def update_project(project_id: str, payload: ProjectPatch, admin: dict = Depends(require_admin)):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return await get_project(project_id, admin)
    if "defaults" in updates and updates["defaults"] is not None:
        # Already a dict via model_dump; keep as-is
        pass
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    updates["updated_by"] = admin["email"]
    r = await db.projects.update_one({"project_id": project_id}, {"$set": updates})
    if r.matched_count == 0:
        raise HTTPException(404, "Project not found")
    return await get_project(project_id, admin)


@api.delete("/projects/{project_id}")
async def archive_project(project_id: str, admin: dict = Depends(require_admin)):
    """Soft-archive a project and unlink all child gigs (gigs keep existing)."""
    proj = await db.projects.find_one({"project_id": project_id})
    if not proj:
        raise HTTPException(404, "Project not found")
    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {"archived": True, "archived_at": datetime.now(timezone.utc).isoformat()}},
    )
    await db.gigs.update_many({"project_id": project_id}, {"$set": {"project_id": None}})
    return {"ok": True, "unlinked_gigs": True}


@api.get("/projects/{project_id}/worker-view")
async def get_project_worker_view(
    project_id: str, user: dict = Depends(get_current_user)
):
    """Read-only project view for workers. Project structure (title, gigs,
    roles, slots) is visible to ANY logged-in worker so they can shop the
    feed. Crew identity (first names + roles per gig) is only revealed once
    the requesting worker is APPROVED on at least one project gig — matches
    the same gate as the per-gig 'You're working alongside' card."""
    if user.get("role") not in ("worker", "admin"):
        raise HTTPException(403, "Workers and admins only")

    proj = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not proj or proj.get("archived"):
        raise HTTPException(404, "Project not found")

    # Pull every gig linked to this project
    gigs = await db.gigs.find({"project_id": project_id}, {"_id": 0}).sort(
        "scheduled_at", 1
    ).to_list(200)
    if not gigs:
        return {
            "project_id": project_id,
            "title": proj.get("title"),
            "description": proj.get("description") or "",
            "scheduled_window": None,
            "linked_gigs": [],
            "crew_visible": False,
            "my_gigs": [],
        }

    # The worker's own acceptances across the project's gigs
    my_acceptances = []
    if user.get("role") == "worker":
        my_acceptances = await db.gig_acceptances.find(
            {
                "worker_id": user["user_id"],
                "gig_id": {"$in": [g["gig_id"] for g in gigs]},
            },
            {"_id": 0},
        ).to_list(200)
    my_acc_by_gig = {a["gig_id"]: a for a in my_acceptances}

    # Worker can see crew identity only if they're already approved on at
    # least one project gig (status that isn't 'requested').
    approved_statuses = {"accepted", "on_the_clock", "clocked_in", "completed"}
    crew_visible = (
        user.get("role") == "admin"
        or any(a.get("status") in approved_statuses for a in my_acceptances)
    )

    # Approved roster for every project gig (PII stripped — first name only)
    crew_by_gig: Dict[str, List[dict]] = {}
    if crew_visible:
        all_accs = await db.gig_acceptances.find(
            {
                "gig_id": {"$in": [g["gig_id"] for g in gigs]},
                "status": {"$in": list(approved_statuses)},
            },
            {"_id": 0, "gig_id": 1, "worker_id": 1, "gig_role": 1, "status": 1},
        ).to_list(2000)
        wids = list({a["worker_id"] for a in all_accs})
        wlookup = await db.users.find(
            {"user_id": {"$in": wids}},
            {"_id": 0, "user_id": 1, "name": 1, "first_name": 1, "last_name": 1},
        ).to_list(2000)
        wmap = {w["user_id"]: w for w in wlookup}
        for a in all_accs:
            w = wmap.get(a["worker_id"]) or {}
            first = (
                w.get("first_name")
                or (w.get("name") or "").split()[0]
                or "Crew"
            )
            crew_by_gig.setdefault(a["gig_id"], []).append(
                {
                    "first_name": first,
                    "gig_role": a.get("gig_role") or "worker",
                    "is_me": a["worker_id"] == user.get("user_id"),
                    "status": a.get("status"),
                }
            )

    # Build the gig list with worker-safe fields only
    safe_gigs = []
    my_gig_titles = []
    for g in gigs:
        mine = my_acc_by_gig.get(g["gig_id"])
        slots_open = max(0, (g.get("slots") or 0) - (g.get("slots_filled") or 0))
        is_approved_here = mine and mine.get("status") in approved_statuses
        safe_gigs.append(
            {
                "gig_id": g["gig_id"],
                "title": g.get("title"),
                "category": g.get("category"),
                "subcategory": g.get("subcategory"),
                "description_snippet": (g.get("description") or "")[:200],
                "scheduled_date": g.get("scheduled_date"),
                "scheduled_at": g.get("scheduled_at"),
                # Public location only (city/state) — never the address line
                "location": g.get("location"),
                "slots": g.get("slots") or 0,
                "slots_filled": g.get("slots_filled") or 0,
                "slots_open": slots_open,
                "pay_rate": g.get("pay_rate"),
                "pay_type": g.get("pay_type"),
                "status": g.get("status"),
                "tags": g.get("tags") or [],
                "is_rush": bool(g.get("is_rush")),
                "my_acceptance_status": mine.get("status") if mine else None,
                "my_gig_role": mine.get("gig_role") if mine else None,
                "approved_crew": crew_by_gig.get(g["gig_id"], [])
                if crew_visible
                else None,
                "approved_count": len(crew_by_gig.get(g["gig_id"], []))
                if crew_visible
                else g.get("slots_filled") or 0,
            }
        )
        if is_approved_here:
            my_gig_titles.append(g.get("title"))

    # Scheduled window (earliest → latest gig date)
    dates = [g.get("scheduled_at") for g in gigs if g.get("scheduled_at")]
    window = None
    if dates:
        window = {"start": min(dates), "end": max(dates)}

    return {
        "project_id": project_id,
        "title": proj.get("title"),
        "description": proj.get("description") or "",
        "scheduled_window": window,
        "linked_gigs": safe_gigs,
        "crew_visible": crew_visible,
        "my_gigs": my_gig_titles,
    }


@api.post("/projects/{project_id}/notes")
async def add_project_note(project_id: str, payload: ProjectNoteIn, admin: dict = Depends(require_admin)):
    if not payload.text or not payload.text.strip():
        raise HTTPException(400, "Note text is required")
    proj = await db.projects.find_one({"project_id": project_id})
    if not proj:
        raise HTTPException(404, "Project not found")
    note = {
        "note_id": f"note_{uuid.uuid4().hex[:12]}",
        "author_id": admin["user_id"],
        "author_name": admin.get("name") or admin.get("email"),
        "text": payload.text.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.projects.update_one(
        {"project_id": project_id},
        {"$push": {"notes": note}},
    )
    return note


@api.delete("/projects/{project_id}/notes/{note_id}")
async def delete_project_note(project_id: str, note_id: str, admin: dict = Depends(require_admin)):
    r = await db.projects.update_one(
        {"project_id": project_id},
        {"$pull": {"notes": {"note_id": note_id}}},
    )
    if r.modified_count == 0:
        raise HTTPException(404, "Note not found")
    return {"ok": True}


@api.post("/gigs/{gig_id}/link-to-project")
async def link_gig_to_project(gig_id: str, payload: LinkGigToProjectIn, admin: dict = Depends(require_admin)):
    """Attach an existing gig to a project. Optionally pull the project's
    defaults onto the gig in the same call."""
    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")
    proj = await db.projects.find_one({"project_id": payload.project_id})
    if not proj:
        raise HTTPException(404, "Project not found")
    updates: dict = {"project_id": payload.project_id}
    if payload.sync_defaults:
        # Always overwrite when admin opts in
        d = proj.get("defaults") or {}
        for key in ("location", "address_line", "scheduled_date", "scheduled_at",
                    "payment_timeline", "payment_timeline_note", "contact_phone"):
            if d.get(key) is not None:
                updates[key] = d[key]
    await db.gigs.update_one({"gig_id": gig_id}, {"$set": updates})
    return {"ok": True, "project_id": payload.project_id}


@api.delete("/gigs/{gig_id}/project")
async def unlink_gig_from_project(gig_id: str, admin: dict = Depends(require_admin)):
    r = await db.gigs.update_one({"gig_id": gig_id}, {"$set": {"project_id": None}})
    if r.matched_count == 0:
        raise HTTPException(404, "Gig not found")
    return {"ok": True}


def _format_project_email(project: dict, gigs: list, base_url: str = "") -> str:
    base = (base_url or _resolve_public_base()).rstrip("/")
    rows = []
    for g in gigs:
        pay = (
            f"${g['pay_rate']:.0f}/hr"
            if g.get("pay_type") == "hourly"
            else f"${g['pay_rate']:.0f}"
        )
        slots_open = max(0, (g.get("slots") or 0) - (g.get("slots_filled") or 0))
        gig_url = f"{base}/gigs/{g.get('gig_id')}"
        rows.append(
            f"<li style='margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid #F3F4F6;'>"
            f"<div style='font-weight:bold;color:#030712;font-size:15px'>{g.get('title', '')}</div>"
            f"<div style='color:#4B5563;font-size:13px;margin:2px 0 6px;'>"
            f"{g.get('category', '').title()}"
            f"{' · ' + g.get('subcategory') if g.get('subcategory') else ''} · "
            f"{g.get('scheduled_date') or 'TBD'} · {pay} · {slots_open} spot{'' if slots_open == 1 else 's'} open"
            f"</div>"
            f"<a href='{gig_url}' target='_blank' style='display:inline-block;padding:8px 14px;background:#030712;color:#FFFFFF;font-size:12px;font-weight:bold;letter-spacing:.04em;text-decoration:none;text-transform:uppercase;'>"
            f"View this gig →"
            f"</a>"
            f"</li>"
        )
    rows_html = "<ul style='padding-left:0;list-style:none;margin:14px 0'>" + "".join(rows) + "</ul>"
    feed_url = f"{base}/crew"
    return (
        f"<div style='font-family:Inter,Arial,sans-serif;max-width:600px;padding:20px;background:#F9FAFB'>"
        f"<div style='background:#FFFFFF;border:1px solid #E5E7EB;padding:24px;'>"
        f"<div style='font-size:11px;letter-spacing:2px;color:#0044FF;font-weight:bold'>NEW PROJECT · HCOB NETWORK</div>"
        f"<h2 style='margin:6px 0 0 0;font-weight:900;font-size:24px;color:#030712'>{project.get('title', '')}</h2>"
        f"<div style='color:#4B5563;font-size:13px;margin-top:4px'>"
        f"{len(gigs)} gig{'' if len(gigs) == 1 else 's'} available · {(project.get('defaults') or {}).get('location') or 'Baltimore, MD'}"
        f"</div>"
        f"<div style='font-size:11px;letter-spacing:2px;color:#4B5563;margin-top:18px;font-weight:bold'>ROLES AVAILABLE</div>"
        f"{rows_html}"
        f"<table cellpadding='0' cellspacing='0' style='margin-top:8px'>"
        f"<tr><td bgcolor='#0044FF'>"
        f"<a href='{feed_url}' target='_blank' style='display:inline-block;padding:14px 28px;background:#0044FF;color:#FFFFFF;font-size:15px;font-weight:bold;letter-spacing:.04em;text-decoration:none;text-transform:uppercase;'>"
        f"Open the full feed →"
        f"</a></td></tr></table>"
        f"<p style='font-size:12px;color:#6B7280;margin-top:14px;'>"
        f"Or open this link on your phone:<br/>"
        f"<a href='{feed_url}' style='color:#0044FF;word-break:break-all;'>{feed_url}</a>"
        f"</p>"
        f"</div>"
        f"</div>"
    )


def _format_project_sms(project: dict, gigs: list, base_url: str = "") -> str:
    # Build a compact summary. Twilio accepts 1600 char multipart SMS but we
    # keep this under ~320 to land as a single message most of the time.
    base = (base_url or _resolve_public_base()).rstrip("/")
    title = project.get("title") or "Project"
    n = len(gigs)
    roles = []
    for g in gigs[:4]:
        # Use subcategory if present, otherwise the short title
        roles.append((g.get("subcategory") or g.get("title") or "").strip()[:30])
    role_str = ", ".join([r for r in roles if r])
    if len(gigs) > 4:
        role_str += f", +{len(gigs) - 4} more"
    loc = (project.get("defaults") or {}).get("location") or "Baltimore, MD"
    pays = [g.get("pay_rate") or 0 for g in gigs if g.get("pay_rate")]
    pay_line = f" Pay from ${min(pays):.0f}/hr." if pays else ""
    # For single-gig projects, deep-link straight to that gig; otherwise drop
    # them into the feed where the project-pill helps them find the right one.
    link = (
        f"{base}/gigs/{gigs[0].get('gig_id')}"
        if len(gigs) == 1 and gigs[0].get("gig_id")
        else f"{base}/crew"
    )
    return (
        f"[HCOB Project] {title} — {loc}. {n} gig{'s' if n != 1 else ''}: {role_str}."
        f"{pay_line} Tap to claim: {link}"
    )


@api.post("/projects/{project_id}/blast")
async def blast_project(
    project_id: str,
    payload: BlastIn,
    request: Request,
    admin: dict = Depends(require_admin),
):
    """Send ONE consolidated notification about a multi-gig project to every
    worker. Each linked gig is also auto-flagged as RUSH (consistent with the
    individual gig-blast endpoint) so the project's gigs float to the top of
    the feed."""
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(404, "Project not found")
    if project.get("archived"):
        raise HTTPException(400, "Cannot blast an archived project")

    # Be permissive about what counts as blastable — we want any non-terminal
    # gig that still has at least one available slot to count. Legacy gigs
    # that predate the status field have `status` missing/None, so we exclude
    # by terminal statuses rather than including by an allow-list.
    TERMINAL_STATUSES = {"closed", "cancelled", "completed", "archived", "draft"}
    all_linked = await db.gigs.find(
        {"project_id": project_id}, {"_id": 0}
    ).to_list(500)
    blastable_gigs = []
    excluded = {"terminal_status": 0, "no_slots": 0}
    for g in all_linked:
        st = (g.get("status") or "").strip().lower()
        if st in TERMINAL_STATUSES:
            excluded["terminal_status"] += 1
            continue
        slots = g.get("slots") or 0
        filled = g.get("slots_filled") or 0
        if slots > 0 and (slots - filled) <= 0:
            excluded["no_slots"] += 1
            continue
        blastable_gigs.append(g)

    if not blastable_gigs:
        # Surface diagnostic info — helps the admin understand WHY no gigs
        # qualified instead of staring at a generic error.
        total = len(all_linked)
        bits = []
        if excluded["terminal_status"]:
            bits.append(
                f"{excluded['terminal_status']} gig(s) are closed/cancelled/completed"
            )
        if excluded["no_slots"]:
            bits.append(
                f"{excluded['no_slots']} gig(s) have no available slots"
            )
        why = " · ".join(bits) if bits else "the project has no linked gigs yet"
        raise HTTPException(
            400,
            f"Nothing to blast — {why}. (Linked gigs: {total}.) "
            f"Add a gig or reopen an existing one.",
        )

    workers = await db.users.find(
        {"role": "worker"}, {"_id": 0, "password_hash": 0}
    ).to_list(1000)

    email_creds = await _resolve_email_creds() if "email" in payload.channels else None
    sms_creds = await _resolve_sms_creds() if "sms" in payload.channels else None

    counts = {"in_app": 0, "email": 0, "sms": 0, "push": 0, "email_failed": 0, "sms_failed": 0}
    subject = f"New Project: {project.get('title')}"
    base_url = _resolve_public_base(request)
    html = _format_project_email(project, blastable_gigs, base_url)
    sms_body = _format_project_sms(project, blastable_gigs, base_url)
    # Project push deep-links to the dedicated worker project view so the
    # crew can scan every role + crew chip in one tap.
    project_url = f"/crew/projects/{project_id}"
    n = len(blastable_gigs)
    push_payload = {
        "title": f"New project: {project.get('title')}",
        "body": (
            f"{n} gig{'s' if n != 1 else ''} available · "
            f"{(project.get('defaults') or {}).get('location') or 'Baltimore, MD'}"
        ),
        "tag": f"project-{project_id}",
        "url": project_url,
        "kind": "project",
        "rush": True,
    }

    notif_docs = []
    for w in workers:
        if "in_app" in payload.channels:
            notif_docs.append(
                {
                    "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
                    "user_id": w["user_id"],
                    "project_id": project_id,
                    "gig_id": None,
                    "title": subject,
                    "body": f"{len(blastable_gigs)} gigs available — {project.get('title')}",
                    "read": False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            counts["in_app"] += 1
        if "email" in payload.channels and w.get("email") and email_creds:
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
                logger.error(f"Project email send failed for {w['email']}: {e}")
                counts["email_failed"] += 1
        if "sms" in payload.channels and w.get("phone") and sms_creds:
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
                logger.error(f"Project SMS send failed for {w.get('phone')}: {e}")
                counts["sms_failed"] += 1
        if "push" in payload.channels and VAPID_PRIVATE_KEY:
            sent = await _send_push_to_user(w["user_id"], push_payload)
            counts["push"] += sent

    if notif_docs:
        await db.notifications.insert_many(notif_docs)

    # Auto-pin all blasted gigs to the top of the feed by flipping is_rush=True
    # and adding the "rush" tag (matches single-gig blast behavior).
    now_iso = datetime.now(timezone.utc).isoformat()
    for g in blastable_gigs:
        existing_tags = [t for t in (g.get("tags") or []) if t in GIG_TAG_VALUES]
        if "rush" not in existing_tags:
            existing_tags.insert(0, "rush")
        await db.gigs.update_one(
            {"gig_id": g["gig_id"]},
            {
                "$set": {
                    "last_blast_at": now_iso,
                    "blast_channels": payload.channels,
                    "is_rush": True,
                    "rush_at": now_iso,
                    "tags": existing_tags,
                },
                "$inc": {"blast_count": 1},
            },
        )

    # Track on the project doc itself.
    await db.projects.update_one(
        {"project_id": project_id},
        {
            "$set": {"last_blast_at": now_iso, "last_blast_channels": payload.channels},
            "$inc": {"blast_count": 1},
        },
    )

    # Persistent blast log — surfaces in Admin → Reports → Blasts.
    await _log_blast(
        kind="project",
        gig_id=None,
        gig_title=None,
        project_id=project_id,
        project_title=project.get("title"),
        channels=payload.channels,
        counts=counts,
        workers_targeted=len(workers),
        sent_by_id=admin["user_id"],
        sent_by_name=admin.get("name") or admin.get("email"),
        extra={"gigs_blasted": len(blastable_gigs)},
    )

    return {
        "ok": True,
        "counts": counts,
        "workers_targeted": len(workers),
        "gigs_blasted": len(blastable_gigs),
    }


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


# ============================================================================
# VA COMMISSION MARKETING PROGRAM — Phase 1
# ----------------------------------------------------------------------------
# Module enables commission-based Virtual Assistants (VAs) to submit cleaning
# leads, track their pipeline, and earn commissions. Program Manager (Mechie,
# admin role + is_program_manager=True) reviews leads and approves commissions.
# Owner (admin role + is_owner=True) does final payout sign-off.
# ============================================================================

LeadStage = Literal["new_lead", "contacted", "quoted", "booked", "completed", "paid", "lost"]
LeadServiceType = Literal["routine", "deep", "moveout", "specialty", "commercial", "unknown"]
LeadPropertySize = Literal["studio", "1br", "2br", "3br", "4br", "5br", "commercial"]
LeadSource = Literal[
    "facebook_marketplace",
    "facebook_groups",
    "craigslist",
    "direct_message",
    "referral",
    "other",
]

COMMISSION_RATES = {
    "routine": 10.0,
    "deep": 25.0,
    "moveout": 25.0,
    "specialty": 25.0,
    "commercial_pct": 0.05,
}
RECURRING_TIERS = {
    1: 15.0,
    2: 25.0,
    3: 10.0,
    4: 10.0,
    5: 10.0,
    6: 10.0,
}
RECURRING_LIFETIME_CAP = 100.0
CLEANER_REFERRAL_TIERS = {1: 20.0, 5: 30.0, 10: 50.0}
CLEANER_REFERRAL_CAP = 100.0
DUPLICATE_REOPEN_DAYS = 90  # leads completed/lost > 90 days old don't block dupes


class VARegisterDetailsIn(BaseModel):
    """Optional VA-only profile data set after signup."""
    va_phone: Optional[str] = None
    va_address: Optional[str] = None


class LeadIn(BaseModel):
    prospect_name: str = Field(min_length=2, max_length=120)
    prospect_phone: str = Field(min_length=7, max_length=40)
    prospect_email: Optional[str] = None
    prospect_address: Optional[str] = None  # used for self-referral check
    service_type: LeadServiceType
    property_size: LeadPropertySize
    preferred_datetime: Optional[str] = None  # ISO 8601 date or datetime
    source: LeadSource
    notes: Optional[str] = Field(default=None, max_length=2000)


class LeadStageIn(BaseModel):
    stage: LeadStage
    job_value: Optional[float] = None  # required when stage='paid' for commercial calc
    note: Optional[str] = None


class CommissionActionIn(BaseModel):
    """Mechie's approve / flag / reject action on a commission."""
    note: Optional[str] = None


class OwnerBulkApproveIn(BaseModel):
    """Owner bulk-approves all pm_approved commissions for a VA within a window."""
    va_user_id: str
    week_start: Optional[str] = None  # ISO date — defaults to start of current week (Mon)
    week_end: Optional[str] = None    # ISO date — defaults to end of current week (Sun)


class CommissionMarkPaidIn(BaseModel):
    payout_reference: Optional[str] = None  # check number, Venmo ref, etc.
    payout_method: Optional[Literal["cash", "venmo", "zelle", "check", "ach", "other"]] = "other"


class VAAccountAdminIn(BaseModel):
    """Program Manager creates a VA account directly."""
    email: EmailStr
    name: str
    password: str = Field(min_length=6)
    va_phone: Optional[str] = None
    va_address: Optional[str] = None
    auto_approve: Optional[bool] = True


class VAStatusActionIn(BaseModel):
    note: Optional[str] = None


class CommercialAccountIn(BaseModel):
    account_name: str = Field(min_length=2, max_length=160)
    va_user_id: str
    monthly_revenue: float = Field(ge=0)
    start_date: Optional[str] = None  # ISO date
    notes: Optional[str] = None


class CommercialAccountPatch(BaseModel):
    account_name: Optional[str] = None
    monthly_revenue: Optional[float] = None
    active: Optional[bool] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def require_va(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "va":
        raise HTTPException(403, "VA access required")
    if user.get("va_status") == "removed":
        raise HTTPException(403, "Account removed")
    return user


async def require_va_active(user: dict = Depends(get_current_user)) -> dict:
    """VA must be 'approved' to submit leads / view earnings."""
    if user.get("role") != "va":
        raise HTTPException(403, "VA access required")
    status = user.get("va_status") or "pending"
    if status != "approved":
        raise HTTPException(403, f"VA account is {status}. Wait for Program Manager approval.")
    return user


async def require_program_manager_or_owner(
    request: Request, user: dict = Depends(get_current_user)
) -> dict:
    """Mechie (Program Manager) AND any admin can manage VA accounts/leads.
    Owner = admin with is_owner=True (for final payout sign-off only).
    """
    role = user.get("role")
    if role != "admin":
        raise HTTPException(403, "Operations access required")
    if user.get("is_read_only") and request.method in ("POST", "PUT", "PATCH", "DELETE"):
        raise HTTPException(403, "Read-only admin — cannot mutate")
    return user


async def require_owner(
    request: Request, user: dict = Depends(get_current_user)
) -> dict:
    """Owner-only — final payout sign-off."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Owner access required")
    if not user.get("is_owner"):
        raise HTTPException(403, "Owner sign-off required — this user is not the Owner")
    return user


def _normalize_phone(p: Optional[str]) -> str:
    if not p:
        return ""
    return re.sub(r"[^\d]", "", p)


def _normalize_email(e: Optional[str]) -> str:
    if not e:
        return ""
    return e.lower().strip()


def _normalize_address(a: Optional[str]) -> str:
    if not a:
        return ""
    s = a.lower().strip()
    # Strip punctuation that often varies between submissions; collapse whitespace
    s = re.sub(r"[,.;:]", " ", s)
    return re.sub(r"\s+", " ", s)


def _serialize_lead(lead: dict, include_owner: bool = True) -> dict:
    out = {k: v for k, v in lead.items() if k != "_id"}
    if not include_owner:
        out.pop("va_user_id", None)
        out.pop("va_name", None)
    return out


def _serialize_commission(c: dict) -> dict:
    return {k: v for k, v in c.items() if k != "_id"}


async def _log_violation(
    va_user_id: Optional[str],
    kind: str,
    details: dict,
    flagged_by: str = "system",
) -> None:
    """Permanent violation log — cannot be deleted by any user role."""
    await db.va_violations.insert_one({
        "violation_id": f"viol_{uuid.uuid4().hex[:12]}",
        "va_user_id": va_user_id,
        "kind": kind,  # duplicate_lead, self_referral, dispute, account_removed, etc.
        "details": details,
        "flagged_by": flagged_by,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


async def _find_duplicate_lead(phone_norm: str, email_norm: str) -> Optional[dict]:
    """Return the conflicting active lead, or None if dupe window allows resubmit.
    Per scoping: allow resubmit if original is `Completed` or `Lost` > 90 days old.
    """
    q = {"$or": []}
    if phone_norm:
        q["$or"].append({"prospect_phone_norm": phone_norm})
    if email_norm:
        q["$or"].append({"prospect_email_norm": email_norm})
    if not q["$or"]:
        return None
    cur = db.va_leads.find(q)
    cutoff = datetime.now(timezone.utc) - timedelta(days=DUPLICATE_REOPEN_DAYS)
    async for d in cur:
        stage = d.get("stage")
        if stage in ("completed", "lost", "paid"):
            ts_str = d.get("stage_changed_at") or d.get("created_at") or ""
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts < cutoff:
                    continue  # eligible for resubmit
            except Exception:
                pass
        return d
    return None


async def _next_recurring_visit_count(va_user_id: str, phone_norm: str, email_norm: str) -> int:
    """Count completed/paid recurring jobs for the same client+VA — returns next visit number."""
    q = {
        "va_user_id": va_user_id,
        "stage": {"$in": ["completed", "paid"]},
        "service_type": "routine",  # only routine cleanings count as recurring
    }
    or_clauses = []
    if phone_norm:
        or_clauses.append({"prospect_phone_norm": phone_norm})
    if email_norm:
        or_clauses.append({"prospect_email_norm": email_norm})
    if or_clauses:
        q["$or"] = or_clauses
    count = await db.va_leads.count_documents(q)
    return count + 1  # next visit


async def _va_lifetime_recurring_total(va_user_id: str, phone_norm: str, email_norm: str) -> float:
    """Lifetime commission paid out / pending for this VA+client recurring chain."""
    q: dict = {"va_user_id": va_user_id, "kind": "recurring"}
    or_clauses = []
    if phone_norm:
        or_clauses.append({"client_phone_norm": phone_norm})
    if email_norm:
        or_clauses.append({"client_email_norm": email_norm})
    if or_clauses:
        q["$or"] = or_clauses
    total = 0.0
    async for c in db.commissions.find(q):
        if c.get("status") != "rejected":
            total += float(c.get("amount") or 0)
    return total


async def _calc_commission_for_lead(lead: dict, job_value: Optional[float] = None) -> dict:
    """Compute commission for a lead based on its service type.
    Returns dict with `amount`, `kind`, `visit_number`, `notes` (str)."""
    svc = lead.get("service_type")
    phone = lead.get("prospect_phone_norm") or ""
    email = lead.get("prospect_email_norm") or ""
    va = lead.get("va_user_id")

    if svc == "commercial":
        rev = float(job_value or lead.get("job_value") or 0)
        amount = round(rev * COMMISSION_RATES["commercial_pct"], 2)
        return {
            "amount": amount,
            "kind": "commercial_one_time",
            "visit_number": None,
            "notes": f"5% of ${rev:.2f} job value",
        }

    if svc == "routine":
        visit = await _next_recurring_visit_count(va, phone, email)
        if visit >= 7:
            return {"amount": 0.0, "kind": "recurring", "visit_number": visit,
                    "notes": "Visit 7+ — recurring cap reached ($0)"}
        per_visit = RECURRING_TIERS.get(visit, 0.0)
        if visit == 1:
            # first routine visit could either be a $10 routine OR a $15 recurring V1 —
            # treat first as $15 if part of recurring series. Per FRD, recurring tiers
            # supersede flat $10 for routine.
            current_paid = await _va_lifetime_recurring_total(va, phone, email)
            remaining = max(0.0, RECURRING_LIFETIME_CAP - current_paid)
            amount = min(per_visit, remaining)
            return {"amount": amount, "kind": "recurring", "visit_number": visit,
                    "notes": f"Recurring visit {visit} (${per_visit:.0f})"}
        current_paid = await _va_lifetime_recurring_total(va, phone, email)
        remaining = max(0.0, RECURRING_LIFETIME_CAP - current_paid)
        amount = min(per_visit, remaining)
        return {"amount": amount, "kind": "recurring", "visit_number": visit,
                "notes": f"Recurring visit {visit} (${per_visit:.0f}) · ${current_paid:.0f}/$100 lifetime cap"}

    if svc in ("deep", "moveout", "specialty"):
        return {"amount": COMMISSION_RATES[svc], "kind": "one_time", "visit_number": None,
                "notes": f"{svc.title()} flat $25"}

    # Unknown / fallback
    return {"amount": 0.0, "kind": "unknown", "visit_number": None,
            "notes": "Service type unknown — manual review needed"}


async def _ensure_commission_for_lead(lead: dict, target_status: str = "calculating") -> Optional[dict]:
    """Create or update a commission record for this lead. Phase 1 commission lifecycle:
       Booked → status=calculating (record created so VA sees progress)
       Paid → status=pending_approval (surfaces in PM queue, auto-calc amount)
    """
    existing = await db.commissions.find_one({"lead_id": lead["lead_id"]})
    calc = await _calc_commission_for_lead(lead, lead.get("job_value"))
    now = datetime.now(timezone.utc).isoformat()
    if existing:
        # Recompute amount if we're entering pending_approval. Once approved/paid, freeze.
        if existing.get("status") in ("approved", "paid", "owner_approved"):
            return {k: v for k, v in existing.items() if k != "_id"}
        await db.commissions.update_one(
            {"commission_id": existing["commission_id"]},
            {"$set": {
                "amount": calc["amount"],
                "kind": calc["kind"],
                "visit_number": calc["visit_number"],
                "calc_notes": calc["notes"],
                "status": target_status,
                "updated_at": now,
                # Snapshot client identifiers for cap lookups even if lead is later edited
                "client_phone_norm": lead.get("prospect_phone_norm"),
                "client_email_norm": lead.get("prospect_email_norm"),
                "job_value": lead.get("job_value"),
            }},
        )
        fresh = await db.commissions.find_one({"commission_id": existing["commission_id"]})
        return {k: v for k, v in fresh.items() if k != "_id"} if fresh else None

    doc = {
        "commission_id": f"comm_{uuid.uuid4().hex[:12]}",
        "lead_id": lead["lead_id"],
        "va_user_id": lead["va_user_id"],
        "va_name": lead.get("va_name"),
        "prospect_name": lead.get("prospect_name"),
        "service_type": lead.get("service_type"),
        "client_phone_norm": lead.get("prospect_phone_norm"),
        "client_email_norm": lead.get("prospect_email_norm"),
        "amount": calc["amount"],
        "kind": calc["kind"],  # one_time, recurring, commercial_one_time, cleaner_referral
        "visit_number": calc["visit_number"],
        "calc_notes": calc["notes"],
        "status": target_status,  # calculating, pending_approval, pm_approved, owner_approved, paid, flagged, rejected
        "pm_action_at": None,
        "pm_action_note": None,
        "owner_action_at": None,
        "paid_at": None,
        "payout_reference": None,
        "payout_method": None,
        "job_value": lead.get("job_value"),
        "created_at": now,
        "updated_at": now,
    }
    await db.commissions.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


# ---------------------------------------------------------------------------
# VA portal routes (`/api/va/*`)
# ---------------------------------------------------------------------------
@api.get("/va/me")
async def va_me(user: dict = Depends(require_va)):
    return user


@api.put("/va/me")
async def va_update_me(payload: VARegisterDetailsIn, user: dict = Depends(require_va)):
    updates = {}
    if payload.va_phone is not None:
        updates["va_phone"] = payload.va_phone.strip()
    if payload.va_address is not None:
        updates["va_address"] = payload.va_address.strip()
    if updates:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": updates})
    return await _get_user_by_id(user["user_id"])


@api.get("/va/dashboard")
async def va_dashboard(user: dict = Depends(require_va)):
    va_id = user["user_id"]
    # Active leads = pre-paid stages
    active_stages = ["new_lead", "contacted", "quoted", "booked", "completed"]
    active_count = await db.va_leads.count_documents({"va_user_id": va_id, "stage": {"$in": active_stages}})
    pending = 0.0
    approved = 0.0
    paid = 0.0
    async for c in db.commissions.find({"va_user_id": va_id}):
        amt = float(c.get("amount") or 0)
        s = c.get("status")
        if s in ("calculating", "pending_approval", "pm_approved"):
            pending += amt
        elif s == "owner_approved":
            approved += amt
        elif s == "paid":
            paid += amt
    # Leaderboard: rank by # of leads in last 30 days (relative position, no $ data shown)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}}},
        {"$group": {"_id": "$va_user_id", "leads": {"$sum": 1}}},
        {"$sort": {"leads": -1}},
    ]
    ranks = []
    async for row in db.va_leads.aggregate(pipeline):
        ranks.append(row["_id"])
    rank = (ranks.index(va_id) + 1) if va_id in ranks else None
    return {
        "va_user_id": va_id,
        "va_status": user.get("va_status"),
        "active_leads": active_count,
        "commissions_pending": round(pending, 2),
        "commissions_approved": round(approved, 2),
        "total_paid": round(paid, 2),
        "leaderboard_rank": rank,
        "leaderboard_total": len(ranks),
    }


@api.post("/va/leads")
async def va_create_lead(payload: LeadIn, request: Request, user: dict = Depends(require_va_active)):
    phone_norm = _normalize_phone(payload.prospect_phone)
    email_norm = _normalize_email(payload.prospect_email)
    if not phone_norm and not email_norm:
        raise HTTPException(400, "Phone or email required")
    addr_norm = _normalize_address(payload.prospect_address)

    # Self-referral check: prospect address must not match VA's registered address
    va_addr_norm = _normalize_address(user.get("va_address"))
    if va_addr_norm and addr_norm and va_addr_norm == addr_norm:
        await _log_violation(user["user_id"], "self_referral", {
            "prospect_name": payload.prospect_name,
            "address": payload.prospect_address,
        }, flagged_by=user["user_id"])
        raise HTTPException(400, "Self-referral blocked: this address matches your registered address.")

    # Duplicate lead check
    dupe = await _find_duplicate_lead(phone_norm, email_norm)
    if dupe:
        await _log_violation(user["user_id"], "duplicate_lead", {
            "prospect_name": payload.prospect_name,
            "phone": payload.prospect_phone,
            "email": payload.prospect_email,
            "original_lead_id": dupe.get("lead_id"),
            "original_va_user_id": dupe.get("va_user_id"),
            "original_stage": dupe.get("stage"),
        }, flagged_by=user["user_id"])
        original_va_name = dupe.get("va_name") or "another VA"
        raise HTTPException(
            status_code=409,
            detail={
                "code": "duplicate_lead",
                "message": (
                    f"This lead was already submitted by {original_va_name} "
                    f"on {dupe.get('created_at', '')[:10]} (stage: {dupe.get('stage')}). "
                    "No commission is awarded for duplicate submissions."
                ),
                "original_va_name": original_va_name,
                "original_date": dupe.get("created_at"),
                "original_stage": dupe.get("stage"),
            },
        )

    now = datetime.now(timezone.utc).isoformat()
    lead_id = f"lead_{uuid.uuid4().hex[:12]}"
    doc = {
        "lead_id": lead_id,
        "va_user_id": user["user_id"],
        "va_name": user.get("name"),
        "prospect_name": payload.prospect_name.strip(),
        "prospect_phone": payload.prospect_phone.strip(),
        "prospect_phone_norm": phone_norm,
        "prospect_email": (payload.prospect_email or "").strip(),
        "prospect_email_norm": email_norm,
        "prospect_address": (payload.prospect_address or "").strip(),
        "prospect_address_norm": addr_norm,
        "service_type": payload.service_type,
        "property_size": payload.property_size,
        "preferred_datetime": payload.preferred_datetime,
        "source": payload.source,
        "notes": (payload.notes or "").strip(),
        "stage": "new_lead",
        "stage_history": [{"stage": "new_lead", "at": now, "by": user["user_id"]}],
        "stage_changed_at": now,
        "job_value": None,
        "ownership_locked_at": now,  # timestamp ownership lock
        "created_at": now,
        "updated_at": now,
    }
    await db.va_leads.insert_one(doc)
    return _serialize_lead(doc)


@api.get("/va/leads")
async def va_list_leads(stage: Optional[str] = None, user: dict = Depends(require_va)):
    q: dict = {"va_user_id": user["user_id"]}
    if stage:
        q["stage"] = stage
    items = []
    cur = db.va_leads.find(q).sort("created_at", -1)
    async for d in cur:
        items.append(_serialize_lead(d))
    return {"items": items}


@api.get("/va/earnings")
async def va_earnings(
    month: Optional[str] = None,  # "YYYY-MM"
    status: Optional[str] = None,
    service_type: Optional[str] = None,
    user: dict = Depends(require_va),
):
    q: dict = {"va_user_id": user["user_id"]}
    if status:
        q["status"] = status
    if service_type:
        q["service_type"] = service_type
    items = []
    totals_month = 0.0
    totals_all = 0.0
    cur = db.commissions.find(q).sort("created_at", -1)
    async for d in cur:
        amt = float(d.get("amount") or 0)
        totals_all += amt
        created = d.get("created_at") or ""
        if month and created[:7] != month:
            continue
        if not month or created[:7] == month:
            totals_month += amt
        items.append(_serialize_commission(d))
    return {
        "items": items,
        "totals": {
            "this_month": round(totals_month, 2),
            "all_time": round(totals_all, 2),
        },
    }


@api.get("/va/commercial-accounts")
async def va_my_commercial_accounts(user: dict = Depends(require_va)):
    items = []
    cur = db.commercial_accounts.find({"va_user_id": user["user_id"]}).sort("created_at", -1)
    async for d in cur:
        items.append({k: v for k, v in d.items() if k != "_id"})
    return {"items": items}


# ---------------------------------------------------------------------------
# Program Manager / Ops routes (`/api/pm/*`)
# ---------------------------------------------------------------------------
@api.get("/pm/leads")
async def pm_list_leads(
    va_user_id: Optional[str] = None,
    stage: Optional[str] = None,
    service_type: Optional[str] = None,
    q: Optional[str] = None,
    admin: dict = Depends(require_program_manager_or_owner),
):
    query: dict = {}
    if va_user_id:
        query["va_user_id"] = va_user_id
    if stage:
        query["stage"] = stage
    if service_type:
        query["service_type"] = service_type
    if q:
        query["$or"] = [
            {"prospect_name": {"$regex": re.escape(q), "$options": "i"}},
            {"prospect_phone_norm": _normalize_phone(q)},
            {"prospect_email_norm": _normalize_email(q)},
        ]
    items = []
    cur = db.va_leads.find(query).sort("created_at", -1).limit(500)
    async for d in cur:
        items.append(_serialize_lead(d))
    return {"items": items}


@api.put("/pm/leads/{lead_id}/stage")
async def pm_update_lead_stage(
    lead_id: str,
    payload: LeadStageIn,
    admin: dict = Depends(require_program_manager_or_owner),
):
    lead = await db.va_leads.find_one({"lead_id": lead_id})
    if not lead:
        raise HTTPException(404, "Lead not found")
    now = datetime.now(timezone.utc).isoformat()
    history_entry = {"stage": payload.stage, "at": now, "by": admin["user_id"], "note": payload.note}
    updates = {
        "stage": payload.stage,
        "stage_changed_at": now,
        "updated_at": now,
    }
    if payload.job_value is not None:
        updates["job_value"] = float(payload.job_value)
    await db.va_leads.update_one(
        {"lead_id": lead_id},
        {"$set": updates, "$push": {"stage_history": history_entry}},
    )
    fresh = await db.va_leads.find_one({"lead_id": lead_id})

    # Commission lifecycle hooks (per scoping: 3A — create on Booked as Calculating)
    if payload.stage == "booked":
        await _ensure_commission_for_lead(fresh, target_status="calculating")
    elif payload.stage == "paid":
        # Both Completed + Paid satisfied → surface in approval queue
        await _ensure_commission_for_lead(fresh, target_status="pending_approval")
        # In-app notification to VA
        await db.notifications.insert_one({
            "notification_id": f"notif_{uuid.uuid4().hex[:10]}",
            "user_id": fresh["va_user_id"],
            "kind": "va_commission_pending",
            "title": "Commission earned",
            "body": f"Lead '{fresh.get('prospect_name')}' is paid — commission pending approval.",
            "created_at": now,
            "read": False,
        })
    elif payload.stage in ("completed",):
        # Update existing commission notes (still calculating)
        existing = await db.commissions.find_one({"lead_id": lead_id})
        if existing and existing.get("status") in ("calculating",):
            await db.commissions.update_one(
                {"commission_id": existing["commission_id"]},
                {"$set": {"status": "calculating", "updated_at": now}},
            )
    elif payload.stage == "lost":
        # Cancel any pending commission
        existing = await db.commissions.find_one({"lead_id": lead_id})
        if existing and existing.get("status") in ("calculating", "pending_approval"):
            await db.commissions.update_one(
                {"commission_id": existing["commission_id"]},
                {"$set": {"status": "rejected", "calc_notes": "Lead marked lost", "updated_at": now}},
            )
    return _serialize_lead(fresh)


@api.get("/pm/commissions")
async def pm_list_commissions(
    status: Optional[str] = None,
    va_user_id: Optional[str] = None,
    admin: dict = Depends(require_program_manager_or_owner),
):
    q: dict = {}
    if status:
        q["status"] = status
    else:
        # Default to the approval queue: pending_approval + flagged
        q["status"] = {"$in": ["pending_approval", "flagged"]}
    if va_user_id:
        q["va_user_id"] = va_user_id
    items = []
    cur = db.commissions.find(q).sort("created_at", 1)  # oldest first for FIFO review
    async for d in cur:
        items.append(_serialize_commission(d))
    return {"items": items}


@api.post("/pm/commissions/{commission_id}/approve")
async def pm_approve_commission(
    commission_id: str,
    payload: CommissionActionIn,
    admin: dict = Depends(require_program_manager_or_owner),
):
    c = await db.commissions.find_one({"commission_id": commission_id})
    if not c:
        raise HTTPException(404, "Commission not found")
    if c["status"] not in ("pending_approval", "flagged"):
        raise HTTPException(400, f"Cannot approve — current status is {c['status']}")
    now = datetime.now(timezone.utc).isoformat()
    await db.commissions.update_one(
        {"commission_id": commission_id},
        {"$set": {
            "status": "pm_approved",
            "pm_action_at": now,
            "pm_action_note": payload.note,
            "pm_action_by": admin["user_id"],
            "updated_at": now,
        }},
    )
    return _serialize_commission(await db.commissions.find_one({"commission_id": commission_id}))


@api.post("/pm/commissions/{commission_id}/flag")
async def pm_flag_commission(
    commission_id: str,
    payload: CommissionActionIn,
    admin: dict = Depends(require_program_manager_or_owner),
):
    if not (payload.note and payload.note.strip()):
        raise HTTPException(400, "Note required when flagging a commission")
    c = await db.commissions.find_one({"commission_id": commission_id})
    if not c:
        raise HTTPException(404, "Commission not found")
    now = datetime.now(timezone.utc).isoformat()
    await db.commissions.update_one(
        {"commission_id": commission_id},
        {"$set": {
            "status": "flagged",
            "pm_action_at": now,
            "pm_action_note": payload.note,
            "pm_action_by": admin["user_id"],
            "updated_at": now,
        }},
    )
    await _log_violation(c.get("va_user_id"), "commission_flagged", {
        "commission_id": commission_id,
        "note": payload.note,
    }, flagged_by=admin["user_id"])
    return _serialize_commission(await db.commissions.find_one({"commission_id": commission_id}))


@api.post("/pm/commissions/{commission_id}/reject")
async def pm_reject_commission(
    commission_id: str,
    payload: CommissionActionIn,
    admin: dict = Depends(require_program_manager_or_owner),
):
    c = await db.commissions.find_one({"commission_id": commission_id})
    if not c:
        raise HTTPException(404, "Commission not found")
    now = datetime.now(timezone.utc).isoformat()
    await db.commissions.update_one(
        {"commission_id": commission_id},
        {"$set": {
            "status": "rejected",
            "pm_action_at": now,
            "pm_action_note": payload.note,
            "pm_action_by": admin["user_id"],
            "updated_at": now,
        }},
    )
    return _serialize_commission(await db.commissions.find_one({"commission_id": commission_id}))


@api.get("/pm/vas")
async def pm_list_vas(admin: dict = Depends(require_program_manager_or_owner)):
    items = []
    cur = db.users.find({"role": "va"}, {"_id": 0, "password_hash": 0}).sort("created_at", -1)
    async for u in cur:
        va_id = u.get("user_id")
        # Aggregate stats
        leads_count = await db.va_leads.count_documents({"va_user_id": va_id})
        booked_count = await db.va_leads.count_documents({
            "va_user_id": va_id, "stage": {"$in": ["booked", "completed", "paid"]}
        })
        earnings_pipeline = [
            {"$match": {"va_user_id": va_id}},
            {"$group": {"_id": "$status", "total": {"$sum": "$amount"}}},
        ]
        by_status = {}
        async for row in db.commissions.aggregate(earnings_pipeline):
            by_status[row["_id"]] = round(row["total"], 2)
        conversion = round((booked_count / leads_count) * 100, 1) if leads_count else 0
        u["lead_count"] = leads_count
        u["booked_count"] = booked_count
        u["conversion_rate"] = conversion
        u["earnings_by_status"] = by_status
        items.append(u)
    return {"items": items}


@api.post("/pm/vas")
async def pm_create_va(payload: VAAccountAdminIn, admin: dict = Depends(require_program_manager_or_owner)):
    email = payload.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(400, "Email already registered")
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    doc = {
        "user_id": user_id,
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": payload.name,
        "role": "va",
        "va_status": "approved" if payload.auto_approve else "pending",
        "va_phone": (payload.va_phone or "").strip(),
        "va_address": (payload.va_address or "").strip(),
        "must_change_password": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "auth_provider": "local",
        "created_by": admin["user_id"],
    }
    await db.users.insert_one(doc)
    return await _get_user_by_id(user_id)


@api.post("/pm/vas/{va_user_id}/approve")
async def pm_approve_va(va_user_id: str, payload: VAStatusActionIn,
                         admin: dict = Depends(require_program_manager_or_owner)):
    u = await db.users.find_one({"user_id": va_user_id, "role": "va"})
    if not u:
        raise HTTPException(404, "VA not found")
    await db.users.update_one({"user_id": va_user_id}, {"$set": {"va_status": "approved"}})
    await db.notifications.insert_one({
        "notification_id": f"notif_{uuid.uuid4().hex[:10]}",
        "user_id": va_user_id,
        "kind": "va_approved",
        "title": "Account approved",
        "body": "Welcome to the HCOB VA Commission Program! Start submitting leads.",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read": False,
    })
    await _send_user_email(
        u, kind="va_approved",
        subject="Welcome aboard — your HCOB VA account is approved",
        body_html=(
            "<p><strong>You're approved!</strong> Your VA account is active and you can start "
            "submitting leads right now.</p>"
            "<p>Open your dashboard to submit your first lead — every lead is locked to you with a "
            "timestamp the moment you hit submit.</p>"
        ),
        cta_label="Open VA dashboard",
        cta_url=f"{_public_base()}/va",
    )
    return await _get_user_by_id(va_user_id)


@api.post("/pm/vas/{va_user_id}/suspend")
async def pm_suspend_va(va_user_id: str, payload: VAStatusActionIn,
                         admin: dict = Depends(require_program_manager_or_owner)):
    u = await db.users.find_one({"user_id": va_user_id, "role": "va"})
    if not u:
        raise HTTPException(404, "VA not found")
    await db.users.update_one({"user_id": va_user_id}, {"$set": {"va_status": "suspended"}})
    await db.sessions.delete_many({"user_id": va_user_id})  # force logout
    await _log_violation(va_user_id, "account_suspended", {"note": payload.note}, flagged_by=admin["user_id"])
    note_html = f"<p><strong>Reason from Ops:</strong> {payload.note}</p>" if payload.note else ""
    await _send_user_email(
        u, kind="va_suspended",
        subject="Your HCOB VA account has been suspended",
        body_html=(
            "<p>Your VA account has been temporarily <strong>suspended</strong> by the Program Manager.</p>"
            f"{note_html}"
            "<p>If you have questions or want to appeal, reply to this email and we'll get back to you.</p>"
        ),
    )
    return await _get_user_by_id(va_user_id)


@api.delete("/pm/vas/{va_user_id}")
async def pm_remove_va(va_user_id: str, admin: dict = Depends(require_program_manager_or_owner)):
    u = await db.users.find_one({"user_id": va_user_id, "role": "va"})
    if not u:
        raise HTTPException(404, "VA not found")
    await db.users.update_one({"user_id": va_user_id}, {"$set": {"va_status": "removed"}})
    await db.sessions.delete_many({"user_id": va_user_id})
    await _log_violation(va_user_id, "account_removed", {"removed_by": admin["user_id"]}, flagged_by=admin["user_id"])
    await _send_user_email(
        u, kind="va_removed",
        subject="Your HCOB VA account has been removed",
        body_html=(
            "<p>Your VA account has been <strong>removed</strong> from the HCOB Commission Program.</p>"
            "<p>You'll no longer be able to sign in or submit new leads. If you have a balance of "
            "approved commissions pending payout, those will still be processed.</p>"
            "<p>If this was unexpected, reply to this email.</p>"
        ),
    )
    return {"ok": True, "user_id": va_user_id}


@api.get("/pm/violations")
async def pm_list_violations(admin: dict = Depends(require_program_manager_or_owner)):
    items = []
    cur = db.va_violations.find().sort("created_at", -1).limit(500)
    async for v in cur:
        items.append({k: val for k, val in v.items() if k != "_id"})
    return {"items": items}


@api.get("/pm/commercial-accounts")
async def pm_list_commercial(admin: dict = Depends(require_program_manager_or_owner)):
    items = []
    cur = db.commercial_accounts.find().sort("created_at", -1)
    async for a in cur:
        items.append({k: v for k, v in a.items() if k != "_id"})
    return {"items": items}


@api.post("/pm/commercial-accounts")
async def pm_create_commercial(payload: CommercialAccountIn, admin: dict = Depends(require_program_manager_or_owner)):
    va = await db.users.find_one({"user_id": payload.va_user_id, "role": "va"})
    if not va:
        raise HTTPException(400, "VA not found")
    doc = {
        "account_id": f"comm_acct_{uuid.uuid4().hex[:10]}",
        "account_name": payload.account_name.strip(),
        "va_user_id": payload.va_user_id,
        "va_name": va.get("name"),
        "monthly_revenue": float(payload.monthly_revenue),
        "start_date": payload.start_date or datetime.now(timezone.utc).date().isoformat(),
        "active": True,
        "notes": payload.notes,
        "last_revenue_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": admin["user_id"],
    }
    await db.commercial_accounts.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@api.put("/pm/commercial-accounts/{account_id}")
async def pm_patch_commercial(
    account_id: str,
    payload: CommercialAccountPatch,
    admin: dict = Depends(require_program_manager_or_owner),
):
    acct = await db.commercial_accounts.find_one({"account_id": account_id})
    if not acct:
        raise HTTPException(404, "Account not found")
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if updates:
        await db.commercial_accounts.update_one({"account_id": account_id}, {"$set": updates})
    fresh = await db.commercial_accounts.find_one({"account_id": account_id})
    return {k: v for k, v in fresh.items() if k != "_id"}


@api.post("/pm/commercial-accounts/{account_id}/log-revenue")
async def pm_log_commercial_revenue(
    account_id: str,
    payload: dict = Body(...),
    admin: dict = Depends(require_program_manager_or_owner),
):
    """Log a month's revenue against a commercial account — triggers a 5% commission record."""
    acct = await db.commercial_accounts.find_one({"account_id": account_id})
    if not acct:
        raise HTTPException(404, "Account not found")
    if not acct.get("active"):
        raise HTTPException(400, "Account is inactive")
    revenue = float(payload.get("revenue") or 0)
    period = (payload.get("period") or datetime.now(timezone.utc).strftime("%Y-%m"))
    if revenue <= 0:
        raise HTTPException(400, "Revenue must be > 0")
    amount = round(revenue * 0.05, 2)
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "commission_id": f"comm_{uuid.uuid4().hex[:12]}",
        "lead_id": None,
        "commercial_account_id": account_id,
        "va_user_id": acct["va_user_id"],
        "va_name": acct.get("va_name"),
        "prospect_name": acct.get("account_name"),
        "service_type": "commercial",
        "amount": amount,
        "kind": "commercial_recurring",
        "visit_number": None,
        "calc_notes": f"5% of ${revenue:.2f} for {period}",
        "period": period,
        "status": "pending_approval",
        "job_value": revenue,
        "created_at": now,
        "updated_at": now,
    }
    await db.commissions.insert_one(doc)
    await db.commercial_accounts.update_one(
        {"account_id": account_id},
        {"$set": {"last_revenue_at": now}},
    )
    return _serialize_commission(doc)


@api.get("/pm/weekly-report")
async def pm_weekly_report(admin: dict = Depends(require_program_manager_or_owner)):
    """Auto-generated weekly snapshot — Mon..Sun UTC of current week."""
    today = datetime.now(timezone.utc).date()
    week_start_dt = today - timedelta(days=today.weekday())
    week_start = week_start_dt.isoformat()
    week_end = (week_start_dt + timedelta(days=6)).isoformat() + "T23:59:59"
    start_iso = week_start + "T00:00:00"
    leads_q = {"created_at": {"$gte": start_iso, "$lte": week_end}}
    leads_total = await db.va_leads.count_documents(leads_q)
    bookings_total = await db.va_leads.count_documents({
        **leads_q,
        "stage": {"$in": ["booked", "completed", "paid"]},
    })
    revenue = 0.0
    commission_owed = 0.0
    async for c in db.commissions.find({"created_at": {"$gte": start_iso, "$lte": week_end}}):
        if c.get("status") not in ("rejected",):
            commission_owed += float(c.get("amount") or 0)
        if c.get("status") in ("pm_approved", "owner_approved", "paid"):
            revenue += float(c.get("job_value") or 0)
    # By-VA breakdown
    by_va_pipe = [
        {"$match": leads_q},
        {"$group": {"_id": "$va_user_id", "leads": {"$sum": 1}, "va_name": {"$first": "$va_name"}}},
        {"$sort": {"leads": -1}},
        {"$limit": 10},
    ]
    by_va = []
    async for row in db.va_leads.aggregate(by_va_pipe):
        by_va.append({"va_user_id": row["_id"], "va_name": row["va_name"], "leads": row["leads"]})
    # Active commercial
    active_commercial = await db.commercial_accounts.count_documents({"active": True})
    monthly_revenue_total = 0.0
    async for a in db.commercial_accounts.find({"active": True}):
        monthly_revenue_total += float(a.get("monthly_revenue") or 0)
    # Flags this week
    flags = []
    async for v in db.va_violations.find({"created_at": {"$gte": start_iso, "$lte": week_end}}).sort("created_at", -1):
        flags.append({k: val for k, val in v.items() if k != "_id"})
    return {
        "week_start": week_start,
        "week_end": week_end[:10],
        "total_leads": leads_total,
        "total_bookings": bookings_total,
        "total_revenue": round(revenue, 2),
        "commission_owed": round(commission_owed, 2),
        "active_commercial_accounts": active_commercial,
        "commercial_monthly_revenue_total": round(monthly_revenue_total, 2),
        "top_vas": by_va,
        "flags": flags,
    }


# ---------------------------------------------------------------------------
# Owner routes (`/api/owner/*`)
# ---------------------------------------------------------------------------
@api.get("/owner/dashboard")
async def owner_dashboard(admin: dict = Depends(require_owner)):
    # Payout queue size + amount
    queue_count = 0
    queue_amount = 0.0
    async for c in db.commissions.find({"status": "pm_approved"}):
        queue_count += 1
        queue_amount += float(c.get("amount") or 0)
    # This month
    month_str = datetime.now(timezone.utc).strftime("%Y-%m")
    month_total = 0.0
    async for c in db.commissions.find({"created_at": {"$regex": f"^{month_str}"}}):
        if c.get("status") not in ("rejected",):
            month_total += float(c.get("amount") or 0)
    # Active commercial revenue
    active_commercial = await db.commercial_accounts.count_documents({"active": True})
    commercial_monthly = 0.0
    async for a in db.commercial_accounts.find({"active": True}):
        commercial_monthly += float(a.get("monthly_revenue") or 0)
    # Top VA performers — last 30 days
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    pipe = [
        {"$match": {"created_at": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$va_user_id",
            "leads": {"$sum": 1},
            "va_name": {"$first": "$va_name"},
            "booked": {"$sum": {"$cond": [{"$in": ["$stage", ["booked", "completed", "paid"]]}, 1, 0]}},
        }},
    ]
    rows = []
    async for r in db.va_leads.aggregate(pipe):
        leads = r["leads"]
        booked = r["booked"]
        rows.append({
            "va_user_id": r["_id"],
            "va_name": r["va_name"],
            "leads": leads,
            "booked": booked,
            "conversion": round((booked / leads) * 100, 1) if leads else 0,
        })
    top_by_volume = sorted(rows, key=lambda x: x["leads"], reverse=True)[:3]
    top_by_conversion = sorted(rows, key=lambda x: x["conversion"], reverse=True)[:3]
    # Alert feed — recent violations + flagged commissions
    alerts = []
    async for v in db.va_violations.find().sort("created_at", -1).limit(10):
        alerts.append({"type": "violation", **{k: val for k, val in v.items() if k != "_id"}})
    async for c in db.commissions.find({"status": "flagged"}).sort("pm_action_at", -1).limit(10):
        alerts.append({"type": "flagged_commission", **_serialize_commission(c)})
    alerts.sort(key=lambda a: a.get("created_at") or a.get("pm_action_at") or "", reverse=True)
    return {
        "payout_queue_count": queue_count,
        "payout_queue_amount": round(queue_amount, 2),
        "month_total_commissions": round(month_total, 2),
        "active_commercial_accounts": active_commercial,
        "commercial_monthly_revenue_total": round(commercial_monthly, 2),
        "top_by_volume": top_by_volume,
        "top_by_conversion": top_by_conversion,
        "alerts": alerts[:20],
    }


@api.get("/owner/payouts/queue")
async def owner_payout_queue(admin: dict = Depends(require_owner)):
    items = []
    cur = db.commissions.find({"status": "pm_approved"}).sort("pm_action_at", 1)
    async for c in cur:
        items.append(_serialize_commission(c))
    # Also group by VA for the bulk-approve UI
    groups: Dict[str, dict] = {}
    for c in items:
        va_id = c.get("va_user_id")
        if va_id not in groups:
            groups[va_id] = {
                "va_user_id": va_id,
                "va_name": c.get("va_name"),
                "items": [],
                "total": 0.0,
            }
        groups[va_id]["items"].append(c)
        groups[va_id]["total"] += float(c.get("amount") or 0)
    grouped = list(groups.values())
    for g in grouped:
        g["total"] = round(g["total"], 2)
    return {"items": items, "by_va": grouped}


@api.post("/owner/payouts/{commission_id}/approve")
async def owner_approve_payout(
    commission_id: str,
    admin: dict = Depends(require_owner),
):
    c = await db.commissions.find_one({"commission_id": commission_id})
    if not c:
        raise HTTPException(404, "Commission not found")
    if c["status"] != "pm_approved":
        raise HTTPException(400, f"Cannot sign off — current status is {c['status']}. Must be pm_approved.")
    now = datetime.now(timezone.utc).isoformat()
    await db.commissions.update_one(
        {"commission_id": commission_id},
        {"$set": {
            "status": "owner_approved",
            "owner_action_at": now,
            "owner_action_by": admin["user_id"],
            "updated_at": now,
        }},
    )
    return _serialize_commission(await db.commissions.find_one({"commission_id": commission_id}))


@api.post("/owner/payouts/bulk-approve")
async def owner_bulk_approve(
    payload: OwnerBulkApproveIn,
    admin: dict = Depends(require_owner),
):
    """One-click sign-off on all PM-approved commissions for a VA within a date window.
    Default window: current ISO week (Mon..Sun UTC)."""
    today = datetime.now(timezone.utc).date()
    default_start = today - timedelta(days=today.weekday())
    default_end = default_start + timedelta(days=6)
    week_start = payload.week_start or default_start.isoformat()
    week_end = (payload.week_end or default_end.isoformat()) + "T23:59:59"
    start_iso = week_start + ("T00:00:00" if "T" not in week_start else "")
    q = {
        "va_user_id": payload.va_user_id,
        "status": "pm_approved",
        "pm_action_at": {"$gte": start_iso, "$lte": week_end},
    }
    now = datetime.now(timezone.utc).isoformat()
    ids = []
    total = 0.0
    async for c in db.commissions.find(q):
        ids.append(c["commission_id"])
        total += float(c.get("amount") or 0)
    if not ids:
        return {"ok": True, "approved_count": 0, "total": 0.0}
    await db.commissions.update_many(
        {"commission_id": {"$in": ids}},
        {"$set": {
            "status": "owner_approved",
            "owner_action_at": now,
            "owner_action_by": admin["user_id"],
            "owner_bulk_approved": True,
            "updated_at": now,
        }},
    )
    return {"ok": True, "approved_count": len(ids), "total": round(total, 2),
            "commission_ids": ids, "week_start": week_start, "week_end": week_end[:10]}


@api.post("/owner/payouts/{commission_id}/mark-paid")
async def owner_mark_paid(
    commission_id: str,
    payload: CommissionMarkPaidIn,
    admin: dict = Depends(require_owner),
):
    c = await db.commissions.find_one({"commission_id": commission_id})
    if not c:
        raise HTTPException(404, "Commission not found")
    if c["status"] == "paid":
        # Hard guard — double-payment prevention
        raise HTTPException(400, "Commission already marked Paid — double-payment prevented")
    if c["status"] != "owner_approved":
        raise HTTPException(400, f"Cannot mark paid — current status is {c['status']}. Must be owner_approved first.")
    now = datetime.now(timezone.utc).isoformat()
    await db.commissions.update_one(
        {"commission_id": commission_id},
        {"$set": {
            "status": "paid",
            "paid_at": now,
            "payout_reference": payload.payout_reference,
            "payout_method": payload.payout_method,
            "updated_at": now,
        }},
    )
    # Notify VA
    await db.notifications.insert_one({
        "notification_id": f"notif_{uuid.uuid4().hex[:10]}",
        "user_id": c["va_user_id"],
        "kind": "va_commission_paid",
        "title": "Commission paid",
        "body": f"${c.get('amount', 0):.2f} has been paid for your lead.",
        "created_at": now,
        "read": False,
    })
    va_user = await db.users.find_one({"user_id": c["va_user_id"]})
    if va_user:
        await _send_user_email(
            va_user, kind="va_commission_paid",
            subject=f"Commission paid — ${c.get('amount', 0):.2f}",
            body_html=(
                f"<p><strong>You've been paid!</strong> Your commission for "
                f"<strong>{c.get('prospect_name')}</strong> is in.</p>"
                f"<p><strong>Amount:</strong> ${c.get('amount', 0):.2f}<br/>"
                f"<strong>Method:</strong> {payload.payout_method or 'N/A'}<br/>"
                f"<strong>Reference:</strong> {payload.payout_reference or 'N/A'}</p>"
                f"<p>Keep submitting leads — your earnings dashboard always shows the live total.</p>"
            ),
            cta_label="Open earnings dashboard",
            cta_url=f"{_public_base()}/va/earnings",
        )
    return _serialize_commission(await db.commissions.find_one({"commission_id": commission_id}))








api.include_router(messages_router)
api.include_router(push_router)
api.include_router(auth_router)
api.include_router(profile_router)
api.include_router(gigs_router)
api.include_router(admin_router)
api.include_router(reports_router)
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
