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


async def _approved_contractor_ids(gig_id: str) -> list[str]:
    """worker_ids actively approved/clocking-in/completed on this gig."""
    rows = await db.gig_acceptances.find(
        {
            "gig_id": gig_id,
            "status": {"$in": ["accepted", "on_the_clock", "completed", "backup"]},
        },
        {"_id": 0, "worker_id": 1},
    ).to_list(length=2000)
    return list({r["worker_id"] for r in rows if r.get("worker_id")})


async def _contractor_participants(gig_id: str) -> list[dict]:
    """Hydrated first-name-only participant list for the customer view."""
    ids = await _approved_contractor_ids(gig_id)
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
    """Return (is_active, reason_if_not). Auto-flip to closed when the
    backing gig has been marked completed — keeps the source of truth in
    the gig lifecycle, not a parallel close timer."""
    if thread.get("status") == "closed":
        return False, thread.get("closed_reason") or "Thread is closed"
    gig = await db.gigs.find_one(
        {"gig_id": thread["gig_id"]}, {"_id": 0, "status": 1}
    )
    if gig and gig.get("status") == "completed":
        # Auto-close on next access. We mutate the doc here so subsequent
        # checks short-circuit on the cheap field-check above.
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
    out = {
        "thread_id": t["thread_id"],
        "gig_id": t["gig_id"],
        "gig_title": t.get("gig_title"),
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
        "gig_id": thread["gig_id"],
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
    contractor on the gig (and the admin who created the thread).
    Background-task safe."""
    ids = await _approved_contractor_ids(thread["gig_id"])
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
    subject = f"💬 New message from {customer_name} — {thread.get('gig_title') or 'your assignment'}"
    body_html = f"""
      <p style="margin:0 0 12px;font-size:15px;line-height:1.6;color:#030712">
        <strong>{customer_name}</strong> just sent a message about
        <em>{thread.get('gig_title') or 'your assignment'}</em>:
      </p>
      <blockquote style="margin:12px 0;padding:12px 14px;border-left:3px solid #0044FF;
                          background:#F5F8FF;color:#030712;font-size:14px;line-height:1.6">
        {snippet.replace(chr(10), '<br/>')}
      </blockquote>
      <p style="margin:0;color:#6B7280;font-size:13px">
        Reply from the assignment page on HCOB Network.
      </p>
    """
    cta_url = f"{_public_base()}/crew/assignments/{thread['gig_id']}"
    for u in users:
        if not u.get("email"):
            continue
        try:
            await _send_user_email(
                u,
                kind="customer_chat_new_message",
                subject=subject,
                body_html=body_html,
                cta_label="Open assignment",
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
    subject = f"💬 New reply from {sender_first_name} — HCOB Network"
    base = _public_base()
    link = f"{base}/c/{thread.get('token')}"
    html = f"""
    <div style="font-family:system-ui,-apple-system,sans-serif;max-width:560px;margin:0 auto;padding:24px">
      <div style="background:#030712;color:#fff;padding:18px 22px;font-weight:900;letter-spacing:-0.02em;font-size:22px">HCOB Network</div>
      <div style="padding:24px 22px;border:1px solid #E5E7EB;border-top:0">
        <h2 style="margin:0 0 12px 0;font-size:18px;color:#030712">New message from {sender_first_name}</h2>
        <p style="margin:0 0 12px;color:#4B5563;line-height:1.55;font-size:14px">
          Regarding your assignment <em>{thread.get('gig_title') or 'with HCOB'}</em>:
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
    async for t in db.customer_threads.find({"gig_id": gig_id}).sort("created_at", -1):
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
    contractors = await _contractor_participants(t["gig_id"])
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


# ----- Contractor endpoints -------------------------------------------------
async def _require_approved_contractor(user: dict, gig_id: str) -> None:
    if user.get("role") == "admin":
        return
    if user.get("role") != "worker":
        raise HTTPException(403, "Only contractors on this assignment can view the customer chat")
    ok = await db.gig_acceptances.find_one({
        "gig_id": gig_id,
        "worker_id": user["user_id"],
        "status": {"$in": ["accepted", "on_the_clock", "completed", "backup"]},
    })
    if not ok:
        raise HTTPException(403, "You must be approved on this assignment to access the customer chat")


@router.get("/crew/gigs/{gig_id}/customer-threads")
async def crew_list_threads_for_gig(
    gig_id: str, user: dict = Depends(get_current_user)
):
    """Approved contractors on the gig can see the (PII-stripped) list of
    customer chats for that gig."""
    await _require_approved_contractor(user, gig_id)
    items: list[dict] = []
    async for t in db.customer_threads.find({"gig_id": gig_id}).sort("created_at", -1):
        items.append(_serialize_thread(t, viewer="contractor"))
    return {"items": items}


@router.get("/crew/customer-threads/{thread_id}/messages")
async def crew_list_messages(
    thread_id: str, user: dict = Depends(get_current_user)
):
    t = await db.customer_threads.find_one({"thread_id": thread_id})
    if not t:
        raise HTTPException(404, "Thread not found")
    await _require_approved_contractor(user, t["gig_id"])
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
    await _require_approved_contractor(user, t["gig_id"])
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
    contractors = await _contractor_participants(t["gig_id"])
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
