"""Customer ↔ Contractor 2-Way Messenger.

A customer (no account, no login) gets a magic-link URL from an admin and
can chat with the approved contractors on their assignment in real-time.
Contractors see and reply from inside the existing app.

Architecture
------------
  customer_threads   : one per (gig × customer) pairing
                       carries the token, customer name/email, status
  customer_messages  : append-only, ordered by created_at
                       sender_type ∈ {customer, contractor, admin}

Access model
------------
  • Admin: creates threads, closes threads, reads any thread (full PII)
  • Contractor (approved on gig): reads + writes (sees customer first name
    only — no phone, no email)
  • Customer: reads + writes via `?token=...` magic link, no login
    (sees contractor first names only)

Auto-close
----------
  Threads auto-close when the underlying gig is marked completed. Calls
  that hit a closed thread return 410 Gone on writes; reads still work
  so the conversation history isn't lost.

Notifications
-------------
  • Customer → contractor msg : email every approved contractor on the gig
                                (graceful when Resend isn't configured)
  • Contractor/admin → customer msg : email customer at their address
                                      with a deep-link back to /c/<token>
"""
import asyncio
import secrets
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from auth_deps import get_current_user, require_admin
from config import db, logger
from notifications import (
    _public_base,
    _resolve_email_creds,
    _send_email_sync,
    _send_user_email,
)

router = APIRouter()


# ----- Helpers --------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_token() -> str:
    """URL-safe random 24-byte token (~32 chars) for the customer magic link."""
    return secrets.token_urlsafe(24)


def _first_name(full: Optional[str]) -> str:
    if not full:
        return "—"
    return full.strip().split(" ")[0] or "—"


async def _gig_or_404(gig_id: str) -> dict:
    gig = await db.gigs.find_one(
        {"gig_id": gig_id},
        {"_id": 0, "gig_id": 1, "title": 1, "status": 1, "category": 1},
    )
    if not gig:
        raise HTTPException(404, "Assignment not found")
    return gig


async def _approved_contractor_ids_for_gig(gig_id: str) -> list[str]:
    """worker_ids actively approved/clocking-in/completed on this gig."""
    rows = await db.gig_acceptances.find(
        {
            "gig_id": gig_id,
            "status": {"$in": ["accepted", "on_the_clock", "completed", "backup"]},
        },
        {"_id": 0, "worker_id": 1},
    ).to_list(length=2000)
    return list({r["worker_id"] for r in rows if r.get("worker_id")})


async def _thread_contractor_ids(thread: dict) -> list[str]:
    """Resolve the active contractor list for any thread.
       • gig-scoped → derived live from gig_acceptances
       • project-scoped → admin-curated `participant_contractor_ids`
    """
    if thread.get("scope_type") == "project":
        return list(thread.get("participant_contractor_ids") or [])
    return await _approved_contractor_ids_for_gig(thread["gig_id"])


async def _approved_contractor_ids_for_project(project_id: str) -> list[str]:
    """All worker_ids that have/had an accepted-style acceptance on ANY
    gig in the project. Used to populate the participant picker."""
    gigs = await db.gigs.find(
        {"project_id": project_id}, {"_id": 0, "gig_id": 1}
    ).to_list(length=500)
    gig_ids = [g["gig_id"] for g in gigs]
    if not gig_ids:
        return []
    rows = await db.gig_acceptances.find(
        {
            "gig_id": {"$in": gig_ids},
            "status": {"$in": ["accepted", "on_the_clock", "completed", "backup", "requested"]},
        },
        {"_id": 0, "worker_id": 1},
    ).to_list(length=4000)
    return list({r["worker_id"] for r in rows if r.get("worker_id")})


async def _contractor_participants(thread: dict) -> list[dict]:
    """Hydrated first-name-only participant list for the customer view."""
    ids = await _thread_contractor_ids(thread)
    if not ids:
        return []
    docs = await db.users.find(
        {"user_id": {"$in": ids}},
        {"_id": 0, "user_id": 1, "name": 1, "avatar_path": 1},
    ).to_list(length=2000)
    return [
        {
            "user_id": d["user_id"],
            "first_name": _first_name(d.get("name")),
            "avatar_path": d.get("avatar_path"),
        }
        for d in docs
    ]


async def _is_thread_active(thread: dict) -> tuple[bool, Optional[str]]:
    """Return (is_active, reason_if_not).

    Gig-scoped: auto-flip to closed when the backing gig is `completed`.
    Project-scoped: never auto-close (per-user choice — projects are
    long-lived; admin manually closes via /close)."""
    if thread.get("status") == "closed":
        return False, thread.get("closed_reason") or "Thread is closed"
    if thread.get("scope_type") == "project":
        return True, None
    gig = await db.gigs.find_one(
        {"gig_id": thread["gig_id"]}, {"_id": 0, "status": 1}
    )
    if gig and gig.get("status") == "completed":
        await db.customer_threads.update_one(
            {"thread_id": thread["thread_id"]},
            {"$set": {
                "status": "closed",
                "closed_at": _now_iso(),
                "closed_reason": "Assignment marked completed",
            }},
        )
        return False, "Assignment marked completed — chat closed"
    return True, None


def _serialize_thread(t: dict, *, viewer: str) -> dict:
    """`viewer` ∈ {admin, contractor, customer}.
    Strips customer PII for contractor view per the privacy default."""
    scope = t.get("scope_type") or "gig"
    out = {
        "thread_id": t["thread_id"],
        "scope_type": scope,
        "gig_id": t.get("gig_id"),
        "project_id": t.get("project_id"),
        # Display title — gig title for gig threads, project title for project threads.
        "gig_title": t.get("gig_title"),
        "project_title": t.get("project_title"),
        "title": t.get("project_title") if scope == "project" else t.get("gig_title"),
        "customer_name": t.get("customer_name"),
        "customer_first_name": _first_name(t.get("customer_name")),
        "status": t.get("status") or "active",
        "created_at": t.get("created_at"),
        "last_message_at": t.get("last_message_at"),
        "last_message_preview": t.get("last_message_preview"),
        "closed_at": t.get("closed_at"),
        "closed_reason": t.get("closed_reason"),
    }
    if viewer == "admin":
        out["customer_email"] = t.get("customer_email")
        out["token"] = t.get("token")
        out["customer_link"] = f"{_public_base()}/c/{t.get('token')}"
        out["created_by"] = t.get("created_by")
        if scope == "project":
            out["participant_contractor_ids"] = t.get("participant_contractor_ids") or []
    elif viewer == "contractor":
        # Contractor sees first-name only — no email, no token.
        out.pop("customer_name", None)
    # Customer doesn't need the customer fields back to themselves
    if viewer == "customer":
        out.pop("customer_email", None)
    return out


def _serialize_message(m: dict, *, viewer: str) -> dict:
    out = {
        "message_id": m["message_id"],
        "thread_id": m["thread_id"],
        "sender_type": m["sender_type"],
        "sender_name": m.get("sender_name"),
        "sender_first_name": _first_name(m.get("sender_name")),
        "text": m.get("text") or "",
        "created_at": m.get("created_at"),
    }
    if viewer == "admin":
        out["sender_user_id"] = m.get("sender_user_id")
    return out


async def _record_message(
    thread: dict,
    *,
    sender_type: str,
    sender_name: str,
    text: str,
    sender_user_id: Optional[str] = None,
) -> dict:
    now = _now_iso()
    mid = f"cmsg_{uuid.uuid4().hex[:14]}"
    doc = {
        "message_id": mid,
        "thread_id": thread["thread_id"],
        "scope_type": thread.get("scope_type") or "gig",
        "gig_id": thread.get("gig_id"),
        "project_id": thread.get("project_id"),
        "sender_type": sender_type,
        "sender_user_id": sender_user_id,
        "sender_name": sender_name,
        "text": text,
        "created_at": now,
    }
    await db.customer_messages.insert_one(doc)
    preview = text[:140]
    await db.customer_threads.update_one(
        {"thread_id": thread["thread_id"]},
        {"$set": {
            "last_message_at": now,
            "last_message_preview": preview,
            "last_message_sender_type": sender_type,
            "updated_at": now,
        }},
    )
    return doc


# ----- Email notifications --------------------------------------------------
async def _email_contractors_new_customer_msg(
    thread: dict, customer_name: str, text: str
) -> None:
    """Fire when the customer sends a message — notify every approved
    contractor on the gig (or project participants for project threads)
    + the admin who created the thread. Background-task safe."""
    ids = await _thread_contractor_ids(thread)
    creator_id = thread.get("created_by")
    if creator_id and creator_id not in ids:
        ids.append(creator_id)
    if not ids:
        return
    users = await db.users.find(
        {"user_id": {"$in": ids}},
        {"_id": 0, "user_id": 1, "email": 1, "name": 1},
    ).to_list(length=2000)
    snippet = (text or "")[:300]
    is_project = thread.get("scope_type") == "project"
    title = (
        thread.get("project_title") if is_project else thread.get("gig_title")
    ) or ("your project" if is_project else "your assignment")
    subject = f"💬 New message from {customer_name} — {title}"
    body_html = f"""
      <p style="margin:0 0 12px;font-size:15px;line-height:1.6;color:#030712">
        <strong>{customer_name}</strong> just sent a message about
        <em>{title}</em>:
      </p>
      <blockquote style="margin:12px 0;padding:12px 14px;border-left:3px solid #0044FF;
                          background:#F5F8FF;color:#030712;font-size:14px;line-height:1.6">
        {snippet.replace(chr(10), '<br/>')}
      </blockquote>
      <p style="margin:0;color:#6B7280;font-size:13px">
        Reply from your dashboard on HCOB Network.
      </p>
    """
    if is_project:
        cta_url = f"{_public_base()}/crew/projects/{thread['project_id']}"
        cta_label = "Open project"
    else:
        cta_url = f"{_public_base()}/crew/assignments/{thread['gig_id']}"
        cta_label = "Open assignment"
    for u in users:
        if not u.get("email"):
            continue
        try:
            await _send_user_email(
                u,
                kind="customer_chat_new_message",
                subject=subject,
                body_html=body_html,
                cta_label=cta_label,
                cta_url=cta_url,
            )
        except Exception as e:
            logger.error(f"customer chat email to {u.get('email')} failed: {e}")


async def _email_customer_new_reply(
    thread: dict, sender_first_name: str, text: str
) -> None:
    """Fire when admin/contractor sends → notify the customer at their
    email with a deep-link back to the same magic-link page."""
    email = thread.get("customer_email")
    if not email:
        return
    creds = await _resolve_email_creds()
    if not creds.get("api_key") or not creds.get("sender"):
        logger.warning(
            f"[customer_chat] no Resend creds — skipped customer email for {thread.get('thread_id')}"
        )
        return
    snippet = (text or "")[:300]
    is_project = thread.get("scope_type") == "project"
    context_label = (
        thread.get("project_title") if is_project else thread.get("gig_title")
    ) or "with HCOB"
    context_word = "project" if is_project else "assignment"
    subject = f"💬 New reply from {sender_first_name} — HCOB Network"
    base = _public_base()
    link = f"{base}/c/{thread.get('token')}"
    html = f"""
    <div style="font-family:system-ui,-apple-system,sans-serif;max-width:560px;margin:0 auto;padding:24px">
      <div style="background:#030712;color:#fff;padding:18px 22px;font-weight:900;letter-spacing:-0.02em;font-size:22px">HCOB Network</div>
      <div style="padding:24px 22px;border:1px solid #E5E7EB;border-top:0">
        <h2 style="margin:0 0 12px 0;font-size:18px;color:#030712">New message from {sender_first_name}</h2>
        <p style="margin:0 0 12px;color:#4B5563;line-height:1.55;font-size:14px">
          Regarding your {context_word} <em>{context_label}</em>:
        </p>
        <blockquote style="margin:12px 0;padding:12px 14px;border-left:3px solid #0044FF;
                            background:#F5F8FF;color:#030712;font-size:14px;line-height:1.6">
          {snippet.replace(chr(10), '<br/>')}
        </blockquote>
        <p style="margin:24px 0">
          <a href="{link}" style="background:#0044FF;color:#fff;text-decoration:none;padding:14px 22px;
                                   font-weight:700;display:inline-block">Open chat</a>
        </p>
        <p style="color:#9CA3AF;font-size:11px;margin-top:24px;border-top:1px solid #E5E7EB;padding-top:14px">
          You're getting this because an HCOB Network team member shared a private chat link with you.
          If this wasn't expected, ignore this email — no action required.
        </p>
      </div>
    </div>
    """
    try:
        await asyncio.to_thread(
            _send_email_sync,
            creds["api_key"], creds["sender"], email, subject, html,
        )
        await db.email_logs.insert_one({
            "log_id": f"em_{uuid.uuid4().hex[:12]}",
            "email": email,
            "kind": "customer_chat_reply",
            "subject": subject,
            "sent_at": _now_iso(),
        })
    except Exception as e:
        logger.error(f"customer chat reply email to {email} failed: {e}")


# ----- Pydantic -------------------------------------------------------------
class CreateCustomerThreadIn(BaseModel):
    gig_id: str = Field(..., min_length=4)
    customer_name: str = Field(..., min_length=1, max_length=120)
    customer_email: Optional[EmailStr] = None


class SendMessageIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)


class CloseThreadIn(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=200)


# ----- Admin endpoints ------------------------------------------------------
@router.post("/admin/customer-threads")
async def admin_create_customer_thread(
    payload: CreateCustomerThreadIn,
    admin: dict = Depends(require_admin),
):
    """Create a new customer↔contractor chat thread bound to a gig.
    Idempotent per (gig, customer_email): if a thread already exists for
    the same gig + email, we return the existing one (so a re-click
    doesn't spawn duplicate links)."""
    gig = await _gig_or_404(payload.gig_id)
    if payload.customer_email:
        existing = await db.customer_threads.find_one({
            "scope_type": {"$in": ["gig", None]},
            "gig_id": payload.gig_id,
            "customer_email": payload.customer_email,
        })
        if existing:
            return _serialize_thread(existing, viewer="admin")
    tid = f"cthr_{uuid.uuid4().hex[:12]}"
    token = _new_token()
    now = _now_iso()
    doc = {
        "thread_id": tid,
        "scope_type": "gig",
        "gig_id": payload.gig_id,
        "gig_title": gig.get("title"),
        "customer_name": payload.customer_name.strip(),
        "customer_email": payload.customer_email,
        "token": token,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "created_by": admin["user_id"],
        "created_by_name": admin.get("name") or admin.get("email"),
        "last_message_at": None,
        "last_message_preview": None,
        "closed_at": None,
        "closed_reason": None,
    }
    await db.customer_threads.insert_one(doc)
    logger.info(
        f"customer_thread created: {tid} gig={payload.gig_id} by={admin['user_id']}"
    )
    return _serialize_thread(doc, viewer="admin")


@router.get("/admin/gigs/{gig_id}/customer-threads")
async def admin_list_threads_for_gig(
    gig_id: str, admin: dict = Depends(require_admin)
):
    await _gig_or_404(gig_id)
    items: list[dict] = []
    async for t in db.customer_threads.find({
        "gig_id": gig_id,
        "scope_type": {"$in": ["gig", None]},
    }).sort("created_at", -1):
        items.append(_serialize_thread(t, viewer="admin"))
    return {"items": items}


@router.get("/admin/customer-threads/{thread_id}")
async def admin_get_thread(thread_id: str, admin: dict = Depends(require_admin)):
    t = await db.customer_threads.find_one({"thread_id": thread_id})
    if not t:
        raise HTTPException(404, "Thread not found")
    # Auto-flip closed if gig done — keep status accurate before returning
    await _is_thread_active(t)
    t = await db.customer_threads.find_one({"thread_id": thread_id})
    contractors = await _contractor_participants(t)
    out = _serialize_thread(t, viewer="admin")
    out["contractors"] = contractors
    return out


@router.get("/admin/customer-threads/{thread_id}/messages")
async def admin_list_messages(
    thread_id: str, admin: dict = Depends(require_admin)
):
    t = await db.customer_threads.find_one({"thread_id": thread_id})
    if not t:
        raise HTTPException(404, "Thread not found")
    msgs = await db.customer_messages.find(
        {"thread_id": thread_id}
    ).sort("created_at", 1).to_list(length=500)
    return [_serialize_message(m, viewer="admin") for m in msgs]


@router.post("/admin/customer-threads/{thread_id}/messages")
async def admin_send_message(
    thread_id: str,
    payload: SendMessageIn,
    background_tasks: BackgroundTasks,
    admin: dict = Depends(require_admin),
):
    t = await db.customer_threads.find_one({"thread_id": thread_id})
    if not t:
        raise HTTPException(404, "Thread not found")
    active, reason = await _is_thread_active(t)
    if not active:
        raise HTTPException(410, reason or "Thread is closed")
    msg = await _record_message(
        t,
        sender_type="admin",
        sender_name=admin.get("name") or admin.get("email") or "HCOB Team",
        text=payload.text.strip(),
        sender_user_id=admin["user_id"],
    )
    background_tasks.add_task(
        _email_customer_new_reply, t, _first_name(msg["sender_name"]), msg["text"]
    )
    return _serialize_message(msg, viewer="admin")


@router.post("/admin/customer-threads/{thread_id}/close")
async def admin_close_thread(
    thread_id: str,
    payload: CloseThreadIn = CloseThreadIn(),
    admin: dict = Depends(require_admin),
):
    t = await db.customer_threads.find_one({"thread_id": thread_id})
    if not t:
        raise HTTPException(404, "Thread not found")
    await db.customer_threads.update_one(
        {"thread_id": thread_id},
        {"$set": {
            "status": "closed",
            "closed_at": _now_iso(),
            "closed_reason": (payload.reason or "Closed by admin").strip(),
            "closed_by": admin["user_id"],
        }},
    )
    fresh = await db.customer_threads.find_one({"thread_id": thread_id})
    return _serialize_thread(fresh, viewer="admin")


@router.post("/admin/customer-threads/{thread_id}/reopen")
async def admin_reopen_thread(
    thread_id: str, admin: dict = Depends(require_admin)
):
    t = await db.customer_threads.find_one({"thread_id": thread_id})
    if not t:
        raise HTTPException(404, "Thread not found")
    # Gig-scoped: can't reopen if the underlying gig is still completed
    if t.get("scope_type") != "project" and t.get("gig_id"):
        gig = await db.gigs.find_one({"gig_id": t["gig_id"]}, {"_id": 0, "status": 1})
        if gig and gig.get("status") == "completed":
            raise HTTPException(
                400,
                "Can't reopen — the assignment is marked completed. Reopen the assignment first.",
            )
    await db.customer_threads.update_one(
        {"thread_id": thread_id},
        {"$set": {"status": "active"},
         "$unset": {"closed_at": "", "closed_reason": "", "closed_by": ""}},
    )
    fresh = await db.customer_threads.find_one({"thread_id": thread_id})
    return _serialize_thread(fresh, viewer="admin")


# ----- Admin: Project-scoped threads ---------------------------------------
class CreateProjectThreadIn(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=120)
    customer_email: Optional[EmailStr] = None
    # Explicit contractor picks (per user choice 1c — admin controls who's in)
    contractor_ids: list[str] = Field(default_factory=list, max_length=200)


class UpdateParticipantsIn(BaseModel):
    contractor_ids: list[str] = Field(..., max_length=200)


async def _project_or_404(project_id: str) -> dict:
    p = await db.projects.find_one(
        {"project_id": project_id},
        {"_id": 0, "project_id": 1, "title": 1, "archived": 1},
    )
    if not p:
        raise HTTPException(404, "Project not found")
    return p


@router.post("/admin/projects/{project_id}/customer-threads")
async def admin_create_project_thread(
    project_id: str,
    payload: CreateProjectThreadIn,
    admin: dict = Depends(require_admin),
):
    """Create a project-wide customer↔crew chat. Admin curates the
    participant list explicitly (so e.g. the customer doesn't end up in
    a thread with a contractor that was kicked off the project).

    Idempotent per (project, customer_email)."""
    project = await _project_or_404(project_id)
    if payload.customer_email:
        existing = await db.customer_threads.find_one({
            "scope_type": "project",
            "project_id": project_id,
            "customer_email": payload.customer_email,
        })
        if existing:
            return _serialize_thread(existing, viewer="admin")
    tid = f"cthr_{uuid.uuid4().hex[:12]}"
    token = _new_token()
    now = _now_iso()
    # Sanitize the contractor list — dedupe and drop anything that isn't
    # actually a worker.
    ids = list({cid for cid in payload.contractor_ids if cid})
    if ids:
        valid = await db.users.find(
            {"user_id": {"$in": ids}, "role": "worker"},
            {"_id": 0, "user_id": 1},
        ).to_list(length=2000)
        ids = [v["user_id"] for v in valid]
    doc = {
        "thread_id": tid,
        "scope_type": "project",
        "project_id": project_id,
        "project_title": project.get("title"),
        "gig_id": None,
        "participant_contractor_ids": ids,
        "customer_name": payload.customer_name.strip(),
        "customer_email": payload.customer_email,
        "token": token,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "created_by": admin["user_id"],
        "created_by_name": admin.get("name") or admin.get("email"),
        "last_message_at": None,
        "last_message_preview": None,
        "closed_at": None,
        "closed_reason": None,
    }
    await db.customer_threads.insert_one(doc)
    logger.info(
        f"customer_thread created (project): {tid} project={project_id} "
        f"participants={len(ids)} by={admin['user_id']}"
    )
    return _serialize_thread(doc, viewer="admin")


@router.get("/admin/projects/{project_id}/customer-threads")
async def admin_list_project_threads(
    project_id: str, admin: dict = Depends(require_admin)
):
    await _project_or_404(project_id)
    items: list[dict] = []
    async for t in db.customer_threads.find({
        "scope_type": "project",
        "project_id": project_id,
    }).sort("created_at", -1):
        items.append(_serialize_thread(t, viewer="admin"))
    return {"items": items}


@router.patch("/admin/customer-threads/{thread_id}/participants")
async def admin_update_participants(
    thread_id: str,
    payload: UpdateParticipantsIn,
    admin: dict = Depends(require_admin),
):
    """Add/remove contractors on a project-scoped thread without recreating
    it. Gig-scoped threads can't be edited — their participant list is
    derived from gig_acceptances."""
    t = await db.customer_threads.find_one({"thread_id": thread_id})
    if not t:
        raise HTTPException(404, "Thread not found")
    if t.get("scope_type") != "project":
        raise HTTPException(
            400,
            "Only project chats have an editable participant list. Per-gig chats use the gig roster automatically.",
        )
    ids = list({cid for cid in payload.contractor_ids if cid})
    if ids:
        valid = await db.users.find(
            {"user_id": {"$in": ids}, "role": "worker"},
            {"_id": 0, "user_id": 1},
        ).to_list(length=2000)
        ids = [v["user_id"] for v in valid]
    await db.customer_threads.update_one(
        {"thread_id": thread_id},
        {"$set": {
            "participant_contractor_ids": ids,
            "updated_at": _now_iso(),
        }},
    )
    fresh = await db.customer_threads.find_one({"thread_id": thread_id})
    out = _serialize_thread(fresh, viewer="admin")
    out["contractors"] = await _contractor_participants(fresh)
    return out


# ----- Contractor endpoints -------------------------------------------------
async def _require_approved_contractor(user: dict, thread: dict) -> None:
    """Gate contractor access to a thread.
       gig scope     → must be approved on the gig via gig_acceptances
       project scope → must be in participant_contractor_ids
    Admins always pass."""
    if user.get("role") == "admin":
        return
    if user.get("role") != "worker":
        raise HTTPException(403, "Only contractors on this chat can view it")
    if thread.get("scope_type") == "project":
        if user["user_id"] not in (thread.get("participant_contractor_ids") or []):
            raise HTTPException(403, "You're not a participant on this project chat")
        return
    ok = await db.gig_acceptances.find_one({
        "gig_id": thread.get("gig_id"),
        "worker_id": user["user_id"],
        "status": {"$in": ["accepted", "on_the_clock", "completed", "backup"]},
    })
    if not ok:
        raise HTTPException(403, "You must be approved on this assignment to access the customer chat")


@router.get("/crew/gigs/{gig_id}/customer-threads")
async def crew_list_threads_for_gig(
    gig_id: str, user: dict = Depends(get_current_user)
):
    """Approved contractors on the gig see (PII-stripped):
       1. Per-gig customer chats for this gig
       2. Project-scoped customer chats where the gig's parent project
          includes them as a participant
    Unified into a single panel so contractors see all relevant chats in
    one place."""
    # Permission: must be approved on this gig (admins also allowed)
    if user.get("role") != "admin":
        if user.get("role") != "worker":
            raise HTTPException(403, "Not allowed")
        ok = await db.gig_acceptances.find_one({
            "gig_id": gig_id,
            "worker_id": user["user_id"],
            "status": {"$in": ["accepted", "on_the_clock", "completed", "backup"]},
        })
        if not ok:
            raise HTTPException(403, "You must be approved on this assignment to access customer chats")

    items: list[dict] = []
    # Gig-scoped threads for this gig
    async for t in db.customer_threads.find({
        "gig_id": gig_id,
        "scope_type": {"$in": ["gig", None]},
    }).sort("created_at", -1):
        items.append(_serialize_thread(t, viewer="contractor"))

    # Project-scoped threads for this gig's parent project (if any)
    gig = await db.gigs.find_one({"gig_id": gig_id}, {"_id": 0, "project_id": 1})
    if gig and gig.get("project_id"):
        worker_id = user.get("user_id")
        q = {"scope_type": "project", "project_id": gig["project_id"]}
        # Workers only see threads they're a participant on; admin sees all.
        if user.get("role") != "admin":
            q["participant_contractor_ids"] = worker_id
        async for t in db.customer_threads.find(q).sort("created_at", -1):
            items.append(_serialize_thread(t, viewer="contractor"))

    return {"items": items}


@router.get("/crew/projects/{project_id}/customer-threads")
async def crew_list_threads_for_project(
    project_id: str, user: dict = Depends(get_current_user)
):
    """Worker-facing list of project-scoped customer chats they're a
    participant on. Used by the worker project view page."""
    if user.get("role") not in ("admin", "worker"):
        raise HTTPException(403, "Not allowed")
    q = {"scope_type": "project", "project_id": project_id}
    if user.get("role") != "admin":
        q["participant_contractor_ids"] = user["user_id"]
    items: list[dict] = []
    async for t in db.customer_threads.find(q).sort("created_at", -1):
        items.append(_serialize_thread(t, viewer="contractor"))
    return {"items": items}


@router.get("/crew/customer-threads/{thread_id}/messages")
async def crew_list_messages(
    thread_id: str, user: dict = Depends(get_current_user)
):
    t = await db.customer_threads.find_one({"thread_id": thread_id})
    if not t:
        raise HTTPException(404, "Thread not found")
    await _require_approved_contractor(user, t)
    msgs = await db.customer_messages.find(
        {"thread_id": thread_id}
    ).sort("created_at", 1).to_list(length=500)
    return [_serialize_message(m, viewer="contractor") for m in msgs]


@router.post("/crew/customer-threads/{thread_id}/messages")
async def crew_send_message(
    thread_id: str,
    payload: SendMessageIn,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    t = await db.customer_threads.find_one({"thread_id": thread_id})
    if not t:
        raise HTTPException(404, "Thread not found")
    await _require_approved_contractor(user, t)
    active, reason = await _is_thread_active(t)
    if not active:
        raise HTTPException(410, reason or "Thread is closed")
    msg = await _record_message(
        t,
        sender_type="contractor",
        sender_name=user.get("name") or user.get("email") or "Contractor",
        text=payload.text.strip(),
        sender_user_id=user["user_id"],
    )
    background_tasks.add_task(
        _email_customer_new_reply, t, _first_name(msg["sender_name"]), msg["text"]
    )
    return _serialize_message(msg, viewer="contractor")


# ----- Customer (public, token-auth) endpoints ------------------------------
async def _thread_by_token_or_404(token: str) -> dict:
    if not token or len(token) < 16:
        raise HTTPException(404, "Chat not found")
    t = await db.customer_threads.find_one({"token": token})
    if not t:
        raise HTTPException(404, "Chat not found")
    return t


@router.get("/customer/threads/{token}")
async def customer_get_thread(token: str):
    """Customer opens the magic link — returns thread metadata + contractor
    first names so they know who's on the chat."""
    t = await _thread_by_token_or_404(token)
    # Refresh active/closed state.
    await _is_thread_active(t)
    t = await db.customer_threads.find_one({"token": token})
    contractors = await _contractor_participants(t)
    out = _serialize_thread(t, viewer="customer")
    out["contractors"] = contractors
    return out


@router.get("/customer/threads/{token}/messages")
async def customer_list_messages(token: str):
    t = await _thread_by_token_or_404(token)
    msgs = await db.customer_messages.find(
        {"thread_id": t["thread_id"]}
    ).sort("created_at", 1).to_list(length=500)
    return [_serialize_message(m, viewer="customer") for m in msgs]


@router.post("/customer/threads/{token}/messages")
async def customer_send_message(
    token: str,
    payload: SendMessageIn,
    background_tasks: BackgroundTasks,
):
    t = await _thread_by_token_or_404(token)
    active, reason = await _is_thread_active(t)
    if not active:
        raise HTTPException(410, reason or "This chat has ended")
    msg = await _record_message(
        t,
        sender_type="customer",
        sender_name=t.get("customer_name") or "Customer",
        text=payload.text.strip(),
        sender_user_id=None,
    )
    background_tasks.add_task(
        _email_contractors_new_customer_msg, t, msg["sender_name"], msg["text"]
    )
    return _serialize_message(msg, viewer="customer")
