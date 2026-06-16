"""In-app messenger — DMs + per-gig group chats.

Polling-based delivery (no websockets). See server.py for the wiring:
    from routes.messages import router as messages_router, _message_digest_runner
    api.include_router(messages_router)
    # in on_startup:  asyncio.create_task(_message_digest_runner())
"""
import os
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from config import db, logger, APP_NAME
from auth_deps import get_current_user
from storage import put_object, _ext_from
from notifications import (
    _send_user_email,
    _public_base,
    _resolve_email_creds,
    _resolve_sms_creds,
    _send_email_sync,
    _send_sms_sync,
    is_blast_disabled,
)
from models import MessageSendIn, OpenDMIn

router = APIRouter()

# ============================================================================
# In-App Messenger — DMs + Per-Gig Group Chats
# ============================================================================
# Architecture
#   threads        : type=dm | gig_group; deterministic thread IDs for both
#   messages       : append-only, ordered by created_at
#   thread_reads   : per-user last-read pointer (for unread counts)
#   files          : message_attachment kind; ACL extended in /files/{path}
# Polling-based delivery — clients hit /unread-count + the thread messages
# endpoint on a timer. No websockets.
# Email digest task runs every 5 min and notifies users about unread
# messages older than MESSAGE_DIGEST_DELAY_MIN.


# Statuses that count as "this worker is/was on the roster" for permission
# checks. Includes historical (completed) and backup so that a worker who
# shared a gig in the past can still DM their old coworker.
WORKER_ON_GIG_STATUSES = ["accepted", "on_the_clock", "completed", "backup"]


async def _workers_share_a_gig(user_a_id: str, user_b_id: str) -> bool:
    """True if user_a and user_b have both ever been approved on the same gig."""
    if user_a_id == user_b_id:
        return False
    my_gigs = await db.gig_acceptances.distinct(
        "gig_id",
        {"worker_id": user_a_id, "status": {"$in": WORKER_ON_GIG_STATUSES}},
    )
    if not my_gigs:
        return False
    shared = await db.gig_acceptances.count_documents({
        "gig_id": {"$in": my_gigs},
        "worker_id": user_b_id,
        "status": {"$in": WORKER_ON_GIG_STATUSES},
    })
    return shared > 0


async def _coworker_ids(user_id: str) -> list:
    """All worker_ids who share at least one ever-approved gig with this user."""
    my_gigs = await db.gig_acceptances.distinct(
        "gig_id",
        {"worker_id": user_id, "status": {"$in": WORKER_ON_GIG_STATUSES}},
    )
    if not my_gigs:
        return []
    ids = await db.gig_acceptances.distinct(
        "worker_id",
        {
            "gig_id": {"$in": my_gigs},
            "worker_id": {"$ne": user_id},
            "status": {"$in": WORKER_ON_GIG_STATUSES},
        },
    )
    return list(ids)


def _dm_thread_id(user_a_id: str, user_b_id: str) -> str:
    """Deterministic ID for a 1:1 DM — same regardless of who opens it."""
    a, b = sorted([user_a_id, user_b_id])
    return f"dm_{a}__{b}"


def _gig_thread_id(gig_id: str) -> str:
    return f"gig_{gig_id}"


async def _gig_group_participants(gig_id: str) -> list:
    """Approved workers on the gig + every admin in the system."""
    workers = await db.gig_acceptances.find(
        {
            "gig_id": gig_id,
            "status": {"$in": ["accepted", "on_the_clock", "completed", "backup"]},
        },
        {"_id": 0, "worker_id": 1},
    ).to_list(length=10000)
    worker_ids = list({w["worker_id"] for w in workers if w.get("worker_id")})
    admins = await db.users.find(
        {"role": "admin"}, {"_id": 0, "user_id": 1}
    ).to_list(length=1000)
    admin_ids = [a["user_id"] for a in admins if a.get("user_id")]
    return sorted(set(worker_ids + admin_ids))


async def _get_or_create_dm_thread(user_a_id: str, user_b_id: str) -> dict:
    if user_a_id == user_b_id:
        raise HTTPException(400, "Can't DM yourself")
    tid = _dm_thread_id(user_a_id, user_b_id)
    existing = await db.threads.find_one({"thread_id": tid}, {"_id": 0})
    if existing:
        return existing
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "thread_id": tid,
        "type": "dm",
        "gig_id": None,
        "gig_title": None,
        "participant_ids": sorted([user_a_id, user_b_id]),
        "created_at": now,
        "updated_at": now,
        "last_message_at": None,
        "last_message_text": None,
        "last_message_sender_id": None,
    }
    await db.threads.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


async def _get_or_create_gig_thread(gig_id: str) -> dict:
    gig = await db.gigs.find_one({"gig_id": gig_id}, {"_id": 0, "title": 1, "gig_id": 1})
    if not gig:
        raise HTTPException(404, "Gig not found")
    tid = _gig_thread_id(gig_id)
    parts = await _gig_group_participants(gig_id)
    existing = await db.threads.find_one({"thread_id": tid}, {"_id": 0})
    if existing:
        # Keep participant list fresh — workers approved/removed since last visit
        if set(existing.get("participant_ids", [])) != set(parts):
            await db.threads.update_one(
                {"thread_id": tid},
                {"$set": {"participant_ids": parts}},
            )
            existing["participant_ids"] = parts
        if existing.get("gig_title") != gig.get("title"):
            await db.threads.update_one(
                {"thread_id": tid},
                {"$set": {"gig_title": gig.get("title")}},
            )
            existing["gig_title"] = gig.get("title")
        return existing
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "thread_id": tid,
        "type": "gig_group",
        "gig_id": gig_id,
        "gig_title": gig.get("title"),
        "participant_ids": parts,
        "created_at": now,
        "updated_at": now,
        "last_message_at": None,
        "last_message_text": None,
        "last_message_sender_id": None,
    }
    await db.threads.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


async def _ensure_participant(thread: dict, user: dict) -> None:
    parts = thread.get("participant_ids", []) or []
    if user["user_id"] in parts:
        return
    # Admins can always view any thread (moderation/oversight)
    if user.get("role") == "admin":
        return
    # Refresh participants for gig groups (in case worker was just approved)
    if thread.get("type") == "gig_group" and thread.get("gig_id"):
        fresh = await _gig_group_participants(thread["gig_id"])
        if user["user_id"] in fresh:
            await db.threads.update_one(
                {"thread_id": thread["thread_id"]},
                {"$set": {"participant_ids": fresh}},
            )
            return
    raise HTTPException(403, "You don't have access to this thread")


async def _unread_count_for_user_in_thread(thread: dict, user_id: str) -> int:
    """Count messages in thread not sent by user and not yet read."""
    read = await db.thread_reads.find_one(
        {"thread_id": thread["thread_id"], "user_id": user_id}, {"_id": 0}
    )
    last_read = (read or {}).get("last_read_at") or "1970-01-01T00:00:00+00:00"
    return await db.messages.count_documents({
        "thread_id": thread["thread_id"],
        "sender_id": {"$ne": user_id},
        "created_at": {"$gt": last_read},
        "deleted": {"$ne": True},
    })


async def _participants_summary(user_ids: list) -> list:
    """Lightweight participant cards (name, role, avatar) for the thread UI."""
    if not user_ids:
        return []
    docs = await db.users.find(
        {"user_id": {"$in": user_ids}},
        {
            "_id": 0, "user_id": 1, "name": 1, "email": 1,
            "role": 1, "avatar_path": 1,
        },
    ).to_list(length=1000)
    out = []
    for d in docs:
        full = d.get("name") or d.get("email") or "Unknown"
        out.append({
            "user_id": d["user_id"],
            "name": full,
            "first_name": (full.split(" ")[0] if full else "Unknown"),
            "role": d.get("role"),
            "avatar_path": d.get("avatar_path"),
        })
    return out


async def _serialize_thread(thread: dict, user_id: str) -> dict:
    out = {k: v for k, v in thread.items() if k != "_id"}
    out["unread_count"] = await _unread_count_for_user_in_thread(thread, user_id)
    out["participants"] = await _participants_summary(thread.get("participant_ids", []) or [])
    if thread.get("type") == "dm":
        other_ids = [
            p for p in (thread.get("participant_ids") or []) if p != user_id
        ]
        out["other_user"] = next(
            (p for p in out["participants"] if p["user_id"] in other_ids), None
        )
    return out


def _serialize_message(msg: dict) -> dict:
    return {
        "message_id": msg["message_id"],
        "thread_id": msg["thread_id"],
        "sender_id": msg["sender_id"],
        "sender_name": msg.get("sender_name") or "Unknown",
        "sender_role": msg.get("sender_role"),
        "text": msg.get("text") or "",
        "attachments": msg.get("attachments") or [],
        "created_at": msg.get("created_at"),
    }


# ---- Models ----------------------------------------------------------------
# MessageSendIn and OpenDMIn are imported from models.py (single source of truth).


# ---- Endpoints -------------------------------------------------------------
@router.get("/messages/threads")
async def list_my_threads(user: dict = Depends(get_current_user)):
    """Threads I'm a participant of. Admins see every thread (oversight)."""
    if user.get("role") == "admin":
        q = {}
    else:
        q = {"participant_ids": user["user_id"]}
    cur = db.threads.find(q, {"_id": 0}).sort(
        [("last_message_at", -1), ("updated_at", -1)]
    )
    out = []
    async for t in cur:
        out.append(await _serialize_thread(t, user["user_id"]))
    return out


@router.get("/messages/unread-count")
async def messages_unread_count(user: dict = Depends(get_current_user)):
    """Global unread badge count across all my threads. Polled by the navbar."""
    if user.get("role") == "admin":
        q = {}
    else:
        q = {"participant_ids": user["user_id"]}
    threads = await db.threads.find(q, {"_id": 0}).to_list(length=2000)
    total = 0
    for t in threads:
        total += await _unread_count_for_user_in_thread(t, user["user_id"])
    return {"count": total}


@router.post("/messages/threads/dm")
async def open_dm(payload: OpenDMIn, user: dict = Depends(get_current_user)):
    """Open or create a DM with another user.
    Role gating:
      - Admins can DM anyone
      - Workers can DM admins, OR other workers they've shared a gig with
        (any gig where both have ever been approved)
      - VAs can DM admins only
    """
    target = await db.users.find_one({"user_id": payload.user_id}, {"_id": 0})
    if not target:
        raise HTTPException(404, "User not found")
    if user.get("role") == "worker":
        if target.get("role") == "admin":
            pass  # workers can always DM admins
        elif target.get("role") == "worker":
            if target.get("worker_status") != "approved":
                raise HTTPException(403, "That worker is not active")
            shared = await _workers_share_a_gig(user["user_id"], target["user_id"])
            if not shared:
                raise HTTPException(
                    403,
                    "You can only DM workers you've shared a gig with",
                )
        else:
            raise HTTPException(
                403, "Workers can only DM admins or coworkers from a shared gig"
            )
    elif user.get("role") == "va":
        if target.get("role") != "admin":
            raise HTTPException(403, "VAs can only DM admins")
    thread = await _get_or_create_dm_thread(user["user_id"], target["user_id"])
    return await _serialize_thread(thread, user["user_id"])


@router.get("/messages/threads/gig/{gig_id}")
async def open_gig_thread(gig_id: str, user: dict = Depends(get_current_user)):
    """Get or create the gig group thread. Approved-on-gig workers + admins."""
    if user.get("role") != "admin":
        ok = await db.gig_acceptances.find_one({
            "gig_id": gig_id,
            "worker_id": user["user_id"],
            "status": {"$in": ["accepted", "on_the_clock", "completed", "backup"]},
        })
        if not ok:
            raise HTTPException(403, "You must be approved on this gig to access the group chat")
    thread = await _get_or_create_gig_thread(gig_id)
    return await _serialize_thread(thread, user["user_id"])


@router.get("/messages/threads/{thread_id}")
async def get_thread(thread_id: str, user: dict = Depends(get_current_user)):
    thread = await db.threads.find_one({"thread_id": thread_id}, {"_id": 0})
    if not thread:
        raise HTTPException(404, "Thread not found")
    await _ensure_participant(thread, user)
    return await _serialize_thread(thread, user["user_id"])


@router.get("/messages/threads/{thread_id}/messages")
async def list_thread_messages(
    thread_id: str,
    limit: int = Query(default=50, le=200),
    before: Optional[str] = Query(default=None, description="created_at < this ISO ts"),
    user: dict = Depends(get_current_user),
):
    thread = await db.threads.find_one({"thread_id": thread_id}, {"_id": 0})
    if not thread:
        raise HTTPException(404, "Thread not found")
    await _ensure_participant(thread, user)
    q = {"thread_id": thread_id, "deleted": {"$ne": True}}
    if before:
        q["created_at"] = {"$lt": before}
    cur = db.messages.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    docs = await cur.to_list(length=limit)
    docs.reverse()  # client expects ascending order
    return [_serialize_message(m) for m in docs]


@router.post("/messages/threads/{thread_id}/messages")
async def send_message(
    thread_id: str,
    payload: MessageSendIn,
    user: dict = Depends(get_current_user),
):
    thread = await db.threads.find_one({"thread_id": thread_id}, {"_id": 0})
    if not thread:
        raise HTTPException(404, "Thread not found")
    await _ensure_participant(thread, user)

    text = (payload.text or "").strip()
    attachments_in = payload.attachment_paths or []
    if not text and not attachments_in:
        raise HTTPException(400, "Empty message (no text and no attachments)")

    # Validate attachments: must be a message_attachment owned by the sender.
    attachments = []
    for path in attachments_in:
        rec = await db.files.find_one(
            {"storage_path": path, "owner_id": user["user_id"], "kind": "message_attachment"},
            {"_id": 0},
        )
        if not rec:
            raise HTTPException(400, f"Attachment not found or not yours: {path}")
        attachments.append({
            "path": path,
            "content_type": rec.get("content_type"),
            "size": rec.get("size"),
        })

    now = datetime.now(timezone.utc).isoformat()
    msg_id = f"msg_{uuid.uuid4().hex[:14]}"
    doc = {
        "message_id": msg_id,
        "thread_id": thread_id,
        "sender_id": user["user_id"],
        "sender_name": user.get("name") or user.get("email"),
        "sender_role": user.get("role"),
        "text": text,
        "attachments": attachments,
        "created_at": now,
        "deleted": False,
    }
    await db.messages.insert_one(doc)

    preview = text if text else f"📎 {len(attachments)} attachment{'s' if len(attachments) != 1 else ''}"
    await db.threads.update_one(
        {"thread_id": thread_id},
        {"$set": {
            "last_message_at": now,
            "last_message_text": preview[:140],
            "last_message_sender_id": user["user_id"],
            "updated_at": now,
        }},
    )
    # Auto-mark sender as read so the new message doesn't count against them.
    await db.thread_reads.update_one(
        {"thread_id": thread_id, "user_id": user["user_id"]},
        {"$set": {"last_read_message_id": msg_id, "last_read_at": now}},
        upsert=True,
    )

    # ---- Optional companion delivery (email / SMS) -------------------------
    # Only admin/owner/pm may request extra channels. Workers/VAs setting
    # channels is silently ignored (in-app only).
    requested_channels = [c for c in (payload.channels or []) if c in ("email", "sms")]
    companion_dispatched = []
    if requested_channels and user.get("role") in ("admin", "owner", "pm"):
        # Respect the kill switch — a runaway DM-flooder would be just as bad.
        if not await is_blast_disabled() and thread.get("type") == "dm":
            # Fire-and-forget so a slow Resend / Twilio call doesn't block
            # the HTTP response. Errors are logged inside the helper.
            asyncio.create_task(
                _deliver_dm_companion(
                    thread=thread,
                    sender=user,
                    text=text,
                    channels=requested_channels,
                )
            )
            companion_dispatched = requested_channels

    response = _serialize_message(doc)
    # Surface what we actually attempted so the UI can confirm
    # ('Sent via in-app, email' vs 'Sent via in-app').
    response["companion_channels"] = companion_dispatched
    return response


async def _deliver_dm_companion(
    *, thread: dict, sender: dict, text: str, channels: list
):
    """Send the same DM body as email and/or SMS to the recipient.

    Only used on DM threads (not gig groups — those have too many recipients
    and should use the blast endpoint instead).
    Recipient = the participant that is NOT the sender.
    Failures are logged + swallowed; in-app delivery already succeeded."""
    if thread.get("type") != "dm":
        return
    participants = thread.get("participant_ids") or []
    other_id = next((p for p in participants if p != sender["user_id"]), None)
    if not other_id:
        return
    recipient = await db.users.find_one(
        {"user_id": other_id},
        {"_id": 0, "user_id": 1, "email": 1, "phone": 1, "name": 1},
    )
    if not recipient:
        return

    sender_name = sender.get("name") or sender.get("email") or "HCOB"
    snippet = (text or "")[:600]

    if "email" in channels and recipient.get("email"):
        try:
            creds = await _resolve_email_creds()
            if creds and creds.get("api_key"):
                base = _public_base()
                deep_link = f"{base}/messages?thread={thread['thread_id']}"
                subject = f"New message from {sender_name}"
                html = (
                    f"<p><strong>{sender_name}</strong> sent you a message:</p>"
                    f"<blockquote style='border-left:3px solid #0044FF;padding-left:12px;color:#222;'>"
                    f"{snippet.replace(chr(10), '<br/>')}</blockquote>"
                    f"<p><a href='{deep_link}' style='color:#0044FF;font-weight:600;'>Open conversation →</a></p>"
                )
                await asyncio.to_thread(
                    _send_email_sync,
                    creds["api_key"],
                    creds["sender"],
                    recipient["email"],
                    subject,
                    html,
                )
        except Exception as e:
            logger.error(f"DM companion email failed for {recipient.get('email')}: {e}")

    if "sms" in channels and recipient.get("phone"):
        try:
            creds = await _resolve_sms_creds()
            if creds and creds.get("sid") and creds.get("token") and creds.get("from_"):
                body = f"{sender_name}: {snippet[:300]}"
                await asyncio.to_thread(
                    _send_sms_sync,
                    creds["sid"],
                    creds["token"],
                    creds["from_"],
                    recipient["phone"],
                    body,
                )
        except Exception as e:
            logger.error(f"DM companion sms failed for {recipient.get('phone')}: {e}")


@router.post("/messages/threads/{thread_id}/read")
async def mark_thread_read(thread_id: str, user: dict = Depends(get_current_user)):
    thread = await db.threads.find_one({"thread_id": thread_id}, {"_id": 0})
    if not thread:
        raise HTTPException(404, "Thread not found")
    await _ensure_participant(thread, user)
    last = await db.messages.find_one(
        {"thread_id": thread_id, "deleted": {"$ne": True}},
        {"_id": 0, "message_id": 1, "created_at": 1},
        sort=[("created_at", -1)],
    )
    now = datetime.now(timezone.utc).isoformat()
    await db.thread_reads.update_one(
        {"thread_id": thread_id, "user_id": user["user_id"]},
        {"$set": {
            "last_read_message_id": (last or {}).get("message_id"),
            "last_read_at": (last or {}).get("created_at") or now,
        }},
        upsert=True,
    )
    return {"ok": True}


@router.post("/messages/attachments")
async def upload_message_attachment(
    file: UploadFile = File(...), user: dict = Depends(get_current_user)
):
    """Upload an image attachment. Returns the storage path which the client
    then passes in attachment_paths on send_message."""
    if file.content_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        raise HTTPException(400, "Only images supported (jpg, png, webp, gif)")
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(400, "Attachment too large (max 10MB)")
    ext = _ext_from(file.filename or "", file.content_type or "")
    path = f"{APP_NAME}/messages/{user['user_id']}/{uuid.uuid4().hex}.{ext}"
    result = await asyncio.to_thread(
        put_object, path, data, file.content_type or "application/octet-stream"
    )
    await db.files.insert_one({
        "file_id": str(uuid.uuid4()),
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": file.content_type,
        "size": result.get("size"),
        "owner_id": user["user_id"],
        "kind": "message_attachment",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {
        "path": result["path"],
        "size": result.get("size"),
        "content_type": file.content_type,
    }


@router.get("/messages/eligible-users")
async def messages_eligible_users(
    q: Optional[str] = Query(default=None),
    user: dict = Depends(get_current_user),
):
    """Users I'm allowed to start a new DM with. Used by the New Message dialog.
    Workers see: every admin + every coworker (someone they've shared a gig with).
    """
    if user.get("role") == "admin":
        match: dict = {}
    elif user.get("role") == "worker":
        coworker_ids = await _coworker_ids(user["user_id"])
        if coworker_ids:
            match = {
                "$or": [
                    {"role": "admin"},
                    {
                        "role": "worker",
                        "worker_status": "approved",
                        "user_id": {"$in": coworker_ids},
                    },
                ]
            }
        else:
            # No coworkers yet — only admins are reachable.
            match = {"role": "admin"}
    elif user.get("role") == "va":
        match = {"role": "admin"}
    else:
        match = {"role": "admin"}
    docs = await db.users.find(
        match,
        {
            "_id": 0, "user_id": 1, "name": 1, "email": 1,
            "role": 1, "avatar_path": 1,
            "is_owner": 1, "is_program_manager": 1,
        },
    ).sort("name", 1).to_list(length=500)
    me = user["user_id"]
    qn = (q or "").strip().lower()
    out = []
    for d in docs:
        if d["user_id"] == me:
            continue
        name = d.get("name") or d.get("email") or ""
        if qn and qn not in name.lower() and qn not in (d.get("email") or "").lower():
            continue
        out.append({
            "user_id": d["user_id"],
            "name": name,
            "email": d.get("email"),
            "role": d.get("role"),
            "avatar_path": d.get("avatar_path"),
            "is_owner": bool(d.get("is_owner")),
            "is_program_manager": bool(d.get("is_program_manager")),
        })
    return out


# ---- Email digest task -----------------------------------------------------
MESSAGE_DIGEST_DELAY_MIN = int(os.environ.get("MESSAGE_DIGEST_DELAY_MIN", "15"))
MESSAGE_DIGEST_CHECK_INTERVAL_SEC = int(os.environ.get("MESSAGE_DIGEST_CHECK_INTERVAL_SEC", "300"))


async def _send_message_digest_pass():
    """One pass through all threads — for any user with unread messages older
    than MESSAGE_DIGEST_DELAY_MIN AND for which we haven't yet emailed the
    current head message, fire a single rolled-up email."""
    cutoff = (
        datetime.now(timezone.utc) - timedelta(minutes=MESSAGE_DIGEST_DELAY_MIN)
    ).isoformat()
    threads = await db.threads.find(
        {"last_message_at": {"$lt": cutoff, "$ne": None}},
        {"_id": 0},
    ).to_list(length=2000)

    per_user: dict = {}
    for t in threads:
        for uid in t.get("participant_ids", []) or []:
            if t.get("last_message_sender_id") == uid:
                continue
            unread = await _unread_count_for_user_in_thread(t, uid)
            if unread <= 0:
                continue
            ptr = await db.message_digest_state.find_one(
                {"user_id": uid, "thread_id": t["thread_id"]}, {"_id": 0}
            )
            last_digested_at = (ptr or {}).get("last_digested_at")
            if last_digested_at and last_digested_at >= t["last_message_at"]:
                continue
            per_user.setdefault(uid, []).append((t, unread))

    sent_count = 0
    for uid, items in per_user.items():
        user = await db.users.find_one({"user_id": uid}, {"_id": 0})
        if not user or not user.get("email"):
            continue
        total_unread = sum(c for _, c in items)
        lines = []
        for t, unread in items[:5]:
            sender_id = t.get("last_message_sender_id")
            sender = None
            if sender_id:
                sender = await db.users.find_one(
                    {"user_id": sender_id}, {"_id": 0, "name": 1, "email": 1}
                )
            sender_name = (sender or {}).get("name") or (sender or {}).get("email") or "Someone"
            label = t.get("gig_title") or sender_name
            preview = (t.get("last_message_text") or "")[:120]
            lines.append(
                "<p style='margin:8px 0;padding:12px;background:#FFFBEB;border-left:3px solid #030712;'>"
                f"<strong>{sender_name}</strong> · {label}"
                f"<br><span style='color:#525252;font-size:14px;'>{preview}</span>"
                f"<br><span style='font-size:12px;color:#737373;'>{unread} unread message{'s' if unread != 1 else ''}</span>"
                "</p>"
            )
        body_html = "<p>You have unread messages on HCOB Network.</p>" + "".join(lines)
        portal = "ops" if user.get("role") == "admin" else (
            "va" if user.get("role") == "va" else "crew"
        )
        ok = await _send_user_email(
            user,
            kind="message_digest",
            subject=f"📬 {total_unread} unread message{'s' if total_unread != 1 else ''} on HCOB Network",
            body_html=body_html,
            cta_label="Open messages",
            cta_url=f"{_public_base()}/{portal}/messages",
        )
        if ok:
            now = datetime.now(timezone.utc).isoformat()
            for t, _ in items:
                await db.message_digest_state.update_one(
                    {"user_id": uid, "thread_id": t["thread_id"]},
                    {"$set": {"last_digested_at": now}},
                    upsert=True,
                )
            sent_count += 1
    if sent_count:
        logger.info(f"[message digest] sent {sent_count} digest email(s)")


async def _message_digest_runner():
    """Long-running coroutine — kicked off in on_startup."""
    await asyncio.sleep(30)
    while True:
        try:
            await _send_message_digest_pass()
        except Exception as e:
            logger.exception(f"[message digest] pass failed: {e}")
        await asyncio.sleep(MESSAGE_DIGEST_CHECK_INTERVAL_SEC)
