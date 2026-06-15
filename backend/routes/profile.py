"""Profile / file upload / file ACL download routes.

Wiring in server.py:
    from routes.profile import router as profile_router, _upload_user_image
    api.include_router(profile_router)
The `_upload_user_image` helper is re-exported because admin-side worker
ID upload (still in server.py) reuses it.
"""
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response as FastAPIResponse
from pydantic import BaseModel

from config import db, APP_NAME
from auth_deps import get_current_user, _get_user_by_id
from storage import put_object, get_object, _ext_from
from constants import (
    WORKER_SKILLS,
    SKILL_LABELS,
    AVAILABILITY_OPTIONS,
    EXPERIENCE_OPTIONS,
    TSHIRT_SIZES,
    REQUIRED_PROFILE_FIELDS,
)
from models import ProfileUpdateIn

router = APIRouter()


@router.get("/profile/options")
async def profile_options(user: dict = Depends(get_current_user)):
    """Static lookup data the profile form needs to render its dropdowns &
    checkboxes. Lives on the backend so the frontend stays in sync with what
    skills the platform supports."""
    return {
        "skills": [{"value": s, "label": SKILL_LABELS[s]} for s in WORKER_SKILLS],
        "availability": AVAILABILITY_OPTIONS,
        "experience_levels": EXPERIENCE_OPTIONS,
        "tshirt_sizes": TSHIRT_SIZES,
        "required_fields": REQUIRED_PROFILE_FIELDS,
    }


@router.put("/profile")
async def update_profile(payload: ProfileUpdateIn, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}

    # Validate enum-ish fields. For multi-select chip fields we silently drop
    # values we don't recognize rather than 400 — keeps saves working even when
    # legacy free-text data is still on the record.
    if "skills" in updates:
        updates["skills"] = [s for s in updates["skills"] if s in WORKER_SKILLS]
    if "availability" in updates:
        updates["availability"] = [a for a in updates["availability"] if a in AVAILABILITY_OPTIONS]
    if "experience_level" in updates and updates["experience_level"] and updates["experience_level"] not in EXPERIENCE_OPTIONS:
        raise HTTPException(400, f"experience_level must be one of {EXPERIENCE_OPTIONS}")
    if "tshirt_size" in updates and updates["tshirt_size"] and updates["tshirt_size"] not in TSHIRT_SIZES:
        raise HTTPException(400, f"tshirt_size must be one of {TSHIRT_SIZES}")
    if "zip_code" in updates and updates["zip_code"]:
        z = updates["zip_code"].strip()
        if not (z.isdigit() and len(z) == 5):
            raise HTTPException(400, "zip_code must be a 5-digit US ZIP code")
        updates["zip_code"] = z

    if updates:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": updates})
    return await _get_user_by_id(user["user_id"])


async def _upload_user_image(user_id: str, kind: str, file: UploadFile) -> str:
    ext = _ext_from(file.filename or "", file.content_type or "")
    path = f"{APP_NAME}/users/{user_id}/{kind}/{uuid.uuid4().hex}.{ext}"
    data = await file.read()
    result = await asyncio.to_thread(
        put_object, path, data, file.content_type or "application/octet-stream"
    )
    await db.files.insert_one(
        {
            "file_id": str(uuid.uuid4()),
            "storage_path": result["path"],
            "original_filename": file.filename,
            "content_type": file.content_type,
            "size": result.get("size"),
            "owner_id": user_id,
            "kind": kind,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return result["path"]


@router.post("/profile/avatar")
async def upload_avatar(
    file: UploadFile = File(...), user: dict = Depends(get_current_user)
):
    path = await _upload_user_image(user["user_id"], "avatar", file)
    await db.users.update_one(
        {"user_id": user["user_id"]}, {"$set": {"avatar_path": path}}
    )
    return {"avatar_path": path}


@router.post("/profile/id")
async def upload_id(
    file: UploadFile = File(...), user: dict = Depends(get_current_user)
):
    path = await _upload_user_image(user["user_id"], "id", file)
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"id_image_path": path, "id_verified": False}},
    )
    return {"id_image_path": path}


# ----- Available Now -------------------------------------------------------
class AvailabilityIn(BaseModel):
    available: bool
    hours: Optional[int] = None  # how long to stay available; default = until midnight (site TZ)


@router.put("/me/availability")
async def set_availability(
    payload: AvailabilityIn, user: dict = Depends(get_current_user)
):
    """Worker self-service: flip the 'I'm available now' switch.

    When `available=True`, sets `available_until` to either:
      - `hours` from now (1..24), OR
      - end-of-day at the site's TZ (default America/New_York) if `hours` is None.

    When `available=False`, clears the flag immediately.

    Admins can filter `/api/admin/workers?available_now=true` to find who is
    actually reachable for same-day RUSH gigs.
    """
    if user.get("role") != "worker":
        raise HTTPException(403, "Only workers can set availability")

    if not payload.available:
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"available_now": False, "available_until": None}},
        )
        return {"available_now": False, "available_until": None}

    now = datetime.now(timezone.utc)
    if payload.hours and 1 <= int(payload.hours) <= 24:
        until = now + timedelta(hours=int(payload.hours))
    else:
        # End-of-day at the site TZ (default America/New_York — HCOB HQ).
        try:
            import os
            from zoneinfo import ZoneInfo
            site_tz = ZoneInfo(os.environ.get("HCOB_SITE_TZ", "America/New_York"))
            local_now = now.astimezone(site_tz)
            eod_local = local_now.replace(hour=23, minute=59, second=59, microsecond=0)
            # If we're already past EOD (rare), fall back to +8h.
            if eod_local <= local_now:
                eod_local = local_now + timedelta(hours=8)
            until = eod_local.astimezone(timezone.utc)
        except Exception:
            until = now + timedelta(hours=8)

    await db.users.update_one(
        {"user_id": user["user_id"]},
        {
            "$set": {
                "available_now": True,
                "available_until": until.isoformat(),
                "available_set_at": now.isoformat(),
            }
        },
    )
    return {"available_now": True, "available_until": until.isoformat()}


@router.get("/files/{path:path}")
async def download_file(
    path: str,
    request: Request,
    auth: Optional[str] = Query(None),
):
    # Auth via cookie OR ?auth= query token (for <img src>)
    token = request.cookies.get("session_token") or auth
    if not token:
        raise HTTPException(401, "Not authenticated")
    session = await db.sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(401, "Invalid session")

    record = await db.files.find_one({"storage_path": path}, {"_id": 0})
    if not record:
        raise HTTPException(404, "File not found")

    requester = await _get_user_by_id(session["user_id"])
    if not requester:
        raise HTTPException(401, "User not found")
    # Owners can always view their own files. Admins can view any file.
    allowed = (
        record["owner_id"] == requester["user_id"]
        or requester.get("role") == "admin"
    )
    # Message attachments: any participant of the thread containing the
    # message that references this attachment may view it.
    if not allowed and record.get("kind") == "message_attachment":
        msg = await db.messages.find_one(
            {"attachments.path": path}, {"_id": 0, "thread_id": 1}
        )
        if msg:
            thread = await db.threads.find_one(
                {"thread_id": msg["thread_id"]},
                {"_id": 0, "participant_ids": 1},
            )
            if thread and requester["user_id"] in (thread.get("participant_ids") or []):
                allowed = True
    if not allowed:
        raise HTTPException(403, "Forbidden")

    data, content_type = await asyncio.to_thread(get_object, path)
    return FastAPIResponse(
        content=data, media_type=record.get("content_type") or content_type
    )
