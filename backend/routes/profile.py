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

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response as FastAPIResponse
from pydantic import BaseModel

from config import db, APP_NAME
from auth_deps import get_current_user, _get_user_by_id
from storage import put_object, get_object, validate_upload
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
async def update_profile(payload: ProfileUpdateIn, request: Request, user: dict = Depends(get_current_user)):
    # We use `exclude_none=True` because the legacy semantic is "omitted=keep,
    # null=keep". For payout we need a way to *explicitly clear* — the
    # frontend sends `payout_method: ""` which the validator turns into
    # None, which `exclude_none` would drop. We detect the clear-intent by
    # peeking at the raw request body.
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    try:
        raw_body = await request.json()
    except Exception:
        raw_body = {}
    payout_clear_intent = (
        isinstance(raw_body, dict)
        and "payout_method" in raw_body
        and (raw_body.get("payout_method") in ("", None))
    )

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

    # Payout: clear handle if method is cleared, and vice versa, so we never
    # store an orphan "zelle but no number" record.
    if payout_clear_intent:
        updates["payout_method"] = None
        updates["payout_handle"] = None
    if "payout_handle" in updates and updates["payout_handle"] is not None:
        updates["payout_handle"] = updates["payout_handle"].strip()
        if updates["payout_handle"] == "":
            updates["payout_handle"] = None
    if updates.get("payout_method") and not updates.get("payout_handle"):
        # Allow saving method without handle? No — they go together. Reject so
        # the worker has to enter the identifier before saving.
        # If they already had a handle on file and only updated the method
        # (handle not in payload), the existing handle stays — only enforce
        # when both fields are in this payload.
        if "payout_handle" in updates or (isinstance(raw_body, dict) and "payout_handle" in raw_body):
            raise HTTPException(400, "Payout handle (phone/email/$username) is required when payout method is set.")
    if updates.get("payout_method"):
        updates["payout_updated_at"] = datetime.now(timezone.utc).isoformat()

    if updates:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": updates})
    return await _get_user_by_id(user["user_id"])


MAX_IMAGE_BYTES = 10 * 1024 * 1024


async def _upload_user_image(user_id: str, kind: str, file: UploadFile) -> str:
    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(400, "Image too large (max 10MB)")
    ext, content_type = validate_upload(data, file.filename or "")
    path = f"{APP_NAME}/users/{user_id}/{kind}/{uuid.uuid4().hex}.{ext}"
    result = await asyncio.to_thread(put_object, path, data, content_type)
    await db.files.insert_one(
        {
            "file_id": str(uuid.uuid4()),
            "storage_path": result["path"],
            "original_filename": file.filename,
            "content_type": content_type,
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


# Only these render inline in the browser; everything else is forced to
# download so a smuggled HTML/SVG can never execute in our origin.
_INLINE_SAFE_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf",
}


@router.get("/files/{path:path}")
async def download_file(
    path: str,
    requester: dict = Depends(get_current_user),
):
    # Auth via httpOnly cookie (browser sends it automatically for <img src>)
    # or Authorization header. Tokens are never accepted in the query string.
    record = await db.files.find_one({"storage_path": path}, {"_id": 0})
    if not record:
        raise HTTPException(404, "File not found")

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
    media_type = record.get("content_type") or content_type or "application/octet-stream"
    headers = {"X-Content-Type-Options": "nosniff"}
    if media_type in _INLINE_SAFE_TYPES:
        headers["Content-Disposition"] = "inline"
    else:
        media_type = "application/octet-stream"
        fname = (record.get("original_filename") or "download").replace('"', "").replace("\n", "")
        headers["Content-Disposition"] = f'attachment; filename="{fname}"'
    return FastAPIResponse(content=data, media_type=media_type, headers=headers)
