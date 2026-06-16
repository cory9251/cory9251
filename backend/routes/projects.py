"""Projects routes (`/api/projects/*`) — bundle 2+ gigs that share a job
site so crews can coordinate. Includes project CRUD, worker-view (with PII
gating), notes, gig linking, and consolidated blast (with background
fan-out for email/sms/push to avoid the Cloudflare 100s cap).

Wiring in server.py:
    from routes.projects import router as projects_router
    api.include_router(projects_router)
"""
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request

from config import db, VAPID_PRIVATE_KEY
from auth_deps import get_current_user, require_admin
from constants import GIG_TAG_VALUES
from models import (
    BlastIn,
    LinkGigToProjectIn,
    ProjectIn,
    ProjectNoteIn,
    ProjectPatch,
)
from notifications import (
    _resolve_public_base,
    _log_blast,
    fanout_blast_channels,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _serialize_project(p: dict) -> dict:
    """Strip Mongo's _id and return the safe view."""
    out = {k: v for k, v in p.items() if k != "_id"}
    out.setdefault("defaults", {})
    out.setdefault("notes", [])
    out.setdefault("archived", False)
    return out


def _apply_project_defaults_to_gig(gig_payload: dict, defaults: dict) -> dict:
    """Pre-fill the optional fields on a new gig from the project defaults.
    Only fills fields that are empty/None on the gig payload — never
    overwrites explicit values."""
    if not defaults:
        return gig_payload
    merged = dict(gig_payload)
    for key in ("location", "address_line", "scheduled_date", "scheduled_at",
                "payment_timeline", "payment_timeline_note", "contact_phone"):
        if defaults.get(key) and not merged.get(key):
            merged[key] = defaults[key]
    return merged


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
    # Compact summary — kept under ~320 chars so most carriers deliver as 1 segment.
    base = (base_url or _resolve_public_base()).rstrip("/")
    title = project.get("title") or "Project"
    n = len(gigs)
    roles = []
    for g in gigs[:4]:
        roles.append((g.get("subcategory") or g.get("title") or "").strip()[:30])
    role_str = ", ".join([r for r in roles if r])
    if len(gigs) > 4:
        role_str += f", +{len(gigs) - 4} more"
    loc = (project.get("defaults") or {}).get("location") or "Baltimore, MD"
    pays = [g.get("pay_rate") or 0 for g in gigs if g.get("pay_rate")]
    pay_line = f" Pay from ${min(pays):.0f}/hr." if pays else ""
    link = (
        f"{base}/gigs/{gigs[0].get('gig_id')}"
        if len(gigs) == 1 and gigs[0].get("gig_id")
        else f"{base}/crew"
    )
    return (
        f"[HCOB Project] {title} — {loc}. {n} gig{'s' if n != 1 else ''}: {role_str}."
        f"{pay_line} Tap to claim: {link}"
    )


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------
@router.post("/projects")
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


@router.get("/projects")
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
    gigs = await db.gigs.find(
        {"project_id": {"$in": pids}},
        {"_id": 0, "gig_id": 1, "project_id": 1, "status": 1, "slots": 1, "slots_filled": 1, "scheduled_at": 1},
    ).to_list(2000)
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


@router.get("/projects/{project_id}")
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


@router.put("/projects/{project_id}")
async def update_project(project_id: str, payload: ProjectPatch, admin: dict = Depends(require_admin)):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return await get_project(project_id, admin)
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    updates["updated_by"] = admin["email"]
    r = await db.projects.update_one({"project_id": project_id}, {"$set": updates})
    if r.matched_count == 0:
        raise HTTPException(404, "Project not found")
    return await get_project(project_id, admin)


@router.delete("/projects/{project_id}")
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


# ---------------------------------------------------------------------------
# Worker-facing project view (PII gated)
# ---------------------------------------------------------------------------
@router.get("/projects/{project_id}/worker-view")
async def get_project_worker_view(
    project_id: str, user: dict = Depends(get_current_user)
):
    """Read-only project view for workers. Project structure (title, gigs,
    roles, slots) is visible to ANY logged-in worker so they can shop the
    feed. Crew identity (first names + roles per gig) is only revealed once
    the requesting worker is APPROVED on at least one project gig."""
    if user.get("role") not in ("worker", "admin"):
        raise HTTPException(403, "Workers and admins only")

    proj = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not proj or proj.get("archived"):
        raise HTTPException(404, "Project not found")

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

    approved_statuses = {"accepted", "on_the_clock", "clocked_in", "completed"}
    crew_visible = (
        user.get("role") == "admin"
        or any(a.get("status") in approved_statuses for a in my_acceptances)
    )

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
            crew_by_gig.setdefault(a["gig_id"], []).append({
                "first_name": first,
                "gig_role": a.get("gig_role") or "worker",
                "is_me": a["worker_id"] == user.get("user_id"),
                "status": a.get("status"),
            })

    safe_gigs = []
    my_gig_titles = []
    for g in gigs:
        mine = my_acc_by_gig.get(g["gig_id"])
        slots_open = max(0, (g.get("slots") or 0) - (g.get("slots_filled") or 0))
        is_approved_here = mine and mine.get("status") in approved_statuses
        safe_gigs.append({
            "gig_id": g["gig_id"],
            "title": g.get("title"),
            "category": g.get("category"),
            "subcategory": g.get("subcategory"),
            "description_snippet": (g.get("description") or "")[:200],
            "scheduled_date": g.get("scheduled_date"),
            "scheduled_at": g.get("scheduled_at"),
            "scheduled_local": g.get("scheduled_local"),
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
            "approved_crew": crew_by_gig.get(g["gig_id"], []) if crew_visible else None,
            "approved_count": (
                len(crew_by_gig.get(g["gig_id"], []))
                if crew_visible
                else g.get("slots_filled") or 0
            ),
        })
        if is_approved_here:
            my_gig_titles.append(g.get("title"))

    dates = [g.get("scheduled_at") for g in gigs if g.get("scheduled_at")]
    window = {"start": min(dates), "end": max(dates)} if dates else None

    return {
        "project_id": project_id,
        "title": proj.get("title"),
        "description": proj.get("description") or "",
        "scheduled_window": window,
        "linked_gigs": safe_gigs,
        "crew_visible": crew_visible,
        "my_gigs": my_gig_titles,
    }


# ---------------------------------------------------------------------------
# Project notes
# ---------------------------------------------------------------------------
@router.post("/projects/{project_id}/notes")
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


@router.delete("/projects/{project_id}/notes/{note_id}")
async def delete_project_note(project_id: str, note_id: str, admin: dict = Depends(require_admin)):
    r = await db.projects.update_one(
        {"project_id": project_id},
        {"$pull": {"notes": {"note_id": note_id}}},
    )
    if r.modified_count == 0:
        raise HTTPException(404, "Note not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Gig ↔ project linking
# ---------------------------------------------------------------------------
@router.post("/gigs/{gig_id}/link-to-project")
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
        d = proj.get("defaults") or {}
        for key in ("location", "address_line", "scheduled_date", "scheduled_at",
                    "payment_timeline", "payment_timeline_note", "contact_phone"):
            if d.get(key) is not None:
                updates[key] = d[key]
    await db.gigs.update_one({"gig_id": gig_id}, {"$set": updates})
    return {"ok": True, "project_id": payload.project_id}


@router.delete("/gigs/{gig_id}/project")
async def unlink_gig_from_project(gig_id: str, admin: dict = Depends(require_admin)):
    r = await db.gigs.update_one({"gig_id": gig_id}, {"$set": {"project_id": None}})
    if r.matched_count == 0:
        raise HTTPException(404, "Gig not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Project blast — consolidated notification, background fan-out
# ---------------------------------------------------------------------------
@router.post("/projects/{project_id}/blast")
async def blast_project(
    project_id: str,
    payload: BlastIn,
    request: Request,
    background_tasks: BackgroundTasks,
    admin: dict = Depends(require_admin),
):
    """Send ONE consolidated notification about a multi-gig project to every
    active worker. Each linked gig is also auto-flagged as RUSH."""
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(404, "Project not found")
    if project.get("archived"):
        raise HTTPException(400, "Cannot blast an archived project")

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
        total = len(all_linked)
        bits = []
        if excluded["terminal_status"]:
            bits.append(f"{excluded['terminal_status']} gig(s) are closed/cancelled/completed")
        if excluded["no_slots"]:
            bits.append(f"{excluded['no_slots']} gig(s) have no available slots")
        why = " · ".join(bits) if bits else "the project has no linked gigs yet"
        raise HTTPException(
            400,
            f"Nothing to blast — {why}. (Linked gigs: {total}.) "
            f"Add a gig or reopen an existing one.",
        )

    # Only blast to workers who can actually claim the gigs (active roster).
    workers = await db.users.find(
        {
            "role": "worker",
            "$or": [
                {"worker_status": {"$in": ["approved", "active", None]}},
                {"worker_status": {"$exists": False}},
            ],
        },
        {"_id": 0, "password_hash": 0},
    ).to_list(5000)

    counts = {"in_app": 0, "email": 0, "sms": 0, "push": 0, "email_failed": 0, "sms_failed": 0}
    subject = f"New Project: {project.get('title')}"
    base_url = _resolve_public_base(request)
    html = _format_project_email(project, blastable_gigs, base_url)
    sms_body = _format_project_sms(project, blastable_gigs, base_url)
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

    # ---- In-app notifications (FAST: 1 batched insert) ----------------------
    if "in_app" in payload.channels:
        now_iso = datetime.now(timezone.utc).isoformat()
        notif_docs = [
            {
                "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
                "user_id": w["user_id"],
                "project_id": project_id,
                "gig_id": None,
                "title": subject,
                "body": f"{len(blastable_gigs)} gigs available — {project.get('title')}",
                "read": False,
                "created_at": now_iso,
            }
            for w in workers
        ]
        if notif_docs:
            await db.notifications.insert_many(notif_docs)
            counts["in_app"] = len(notif_docs)

    counts["email"] = (
        sum(1 for w in workers if w.get("email")) if "email" in payload.channels else 0
    )
    counts["sms"] = (
        sum(1 for w in workers if w.get("phone")) if "sms" in payload.channels else 0
    )
    counts["push"] = len(workers) if "push" in payload.channels and VAPID_PRIVATE_KEY else 0

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

    await db.projects.update_one(
        {"project_id": project_id},
        {
            "$set": {"last_blast_at": now_iso, "last_blast_channels": payload.channels},
            "$inc": {"blast_count": 1},
        },
    )

    blast_log_id = await _log_blast(
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

    queued = any(c in payload.channels for c in ("email", "sms", "push"))
    if queued:
        background_tasks.add_task(
            fanout_blast_channels,
            workers=workers,
            channels=payload.channels,
            subject=subject,
            html=html,
            sms_body=sms_body,
            push_payload=push_payload,
            blast_log_id=blast_log_id,
        )

    return {
        "ok": True,
        "counts": counts,
        "workers_targeted": len(workers),
        "gigs_blasted": len(blastable_gigs),
        "queued": queued,
        "blast_id": blast_log_id,
    }
