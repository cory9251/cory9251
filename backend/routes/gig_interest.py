"""FRD Addendum B — the Interest flow, gig views, and gig photo uploads.

Specialist projects with an open variable (pay range or TBD date) take
"I'm Interested" instead of a claim. Interests land in the ops queue attached
to the gig. Views are deduped per worker per gig for conversion metrics.

Wiring in server.py:
    from routes.gig_interest import router as gig_interest_router
    api.include_router(gig_interest_router)
"""
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from config import db, APP_NAME
from auth_deps import get_current_user, require_admin, _profile_missing_fields
from storage import put_object, validate_upload

router = APIRouter()

MAX_GIG_PHOTO_BYTES = 10 * 1024 * 1024


async def _notify(user_id: str, title: str, body: str) -> None:
    await db.notifications.insert_one({
        "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "title": title,
        "body": body,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


# ============================================================================
# Worker — I'm Interested
# ============================================================================
class InterestIn(BaseModel):
    note: Optional[str] = Field(None, max_length=300)
    availability: Optional[str] = Field(None, max_length=200)


@router.post("/gigs/{gig_id}/interest")
async def express_interest(gig_id: str, payload: InterestIn, user: dict = Depends(get_current_user)):
    if user.get("role") != "worker":
        raise HTTPException(403, "Only workers can express interest")
    status = user.get("worker_status") or "approved"
    if status in ("rejected", "suspended"):
        raise HTTPException(403, "Your account is not authorized")
    if not user.get("id_verified"):
        raise HTTPException(403, "Verify your ID before raising your hand for gigs")
    if _profile_missing_fields(user):
        raise HTTPException(403, "Complete your profile before raising your hand for gigs")
    gig = await db.gigs.find_one({"gig_id": gig_id}, {"_id": 0})
    if not gig:
        raise HTTPException(404, "Gig not found")
    if gig.get("status") not in ("open", "coming_soon"):
        raise HTTPException(400, "This gig is no longer taking interest")

    now_iso = datetime.now(timezone.utc).isoformat()
    existing = await db.gig_interests.find_one(
        {"gig_id": gig_id, "worker_id": user["user_id"]}, {"_id": 0}
    )
    note = (payload.note or "").strip() or None
    availability = (payload.availability or "").strip() or None
    if existing:
        await db.gig_interests.update_one(
            {"gig_id": gig_id, "worker_id": user["user_id"]},
            {"$set": {"note": note, "availability": availability,
                      "status": "open", "updated_at": now_iso}},
        )
        doc = {**existing, "note": note, "availability": availability, "status": "open"}
        return doc
    doc = {
        "interest_id": f"int_{uuid.uuid4().hex[:12]}",
        "gig_id": gig_id,
        "worker_id": user["user_id"],
        "note": note,
        "availability": availability,
        "status": "open",
        "created_at": now_iso,
    }
    await db.gig_interests.insert_one(dict(doc))
    await db.gigs.update_one({"gig_id": gig_id}, {"$inc": {"interest_count": 1}})
    admins = await db.users.find({"role": "admin"}, {"_id": 0, "user_id": 1}).to_list(50)
    for a in admins:
        await _notify(
            a["user_id"],
            f"Interest: {gig.get('title')}",
            f"{user.get('name') or user.get('email')} raised their hand"
            + (f' — "{note}"' if note else "")
            + (f" · Available: {availability}" if availability else ""),
        )
    return doc


@router.delete("/gigs/{gig_id}/interest")
async def withdraw_interest(gig_id: str, user: dict = Depends(get_current_user)):
    res = await db.gig_interests.delete_one(
        {"gig_id": gig_id, "worker_id": user["user_id"]}
    )
    if res.deleted_count:
        await db.gigs.update_one({"gig_id": gig_id}, {"$inc": {"interest_count": -1}})
    return {"ok": True}


# ============================================================================
# Worker — view tracking (deduped per worker per gig; conversion metrics)
# ============================================================================
@router.post("/gigs/{gig_id}/view")
async def track_gig_view(gig_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "worker":
        return {"ok": True}
    res = await db.gig_views.update_one(
        {"gig_id": gig_id, "worker_id": user["user_id"]},
        {"$setOnInsert": {
            "gig_id": gig_id,
            "worker_id": user["user_id"],
            "first_viewed_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    if res.upserted_id is not None:
        await db.gigs.update_one({"gig_id": gig_id}, {"$inc": {"view_count": 1}})
    return {"ok": True}


# ============================================================================
# Admin — per-gig interest queue (enriched)
# ============================================================================
@router.get("/admin/gigs/{gig_id}/interests")
async def admin_gig_interests(gig_id: str, admin: dict = Depends(require_admin)):
    rows = await db.gig_interests.find({"gig_id": gig_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    if not rows:
        return {"interests": []}
    wids = list({r["worker_id"] for r in rows})
    workers = await db.users.find(
        {"user_id": {"$in": wids}},
        {"_id": 0, "user_id": 1, "name": 1, "email": 1, "phone": 1, "zip_code": 1,
         "avatar_path": 1, "certified_badges": 1, "specialist_trades": 1, "rating_avg": 1},
    ).to_list(500)
    wmap = {w["user_id"]: w for w in workers}
    # Past completions per worker (one aggregate pass).
    pipeline = [
        {"$match": {"worker_id": {"$in": wids}, "status": "completed"}},
        {"$group": {"_id": "$worker_id", "n": {"$sum": 1}}},
    ]
    comp = {c["_id"]: c["n"] async for c in db.gig_acceptances.aggregate(pipeline)}
    out = []
    for r in rows:
        w = wmap.get(r["worker_id"]) or {}
        verified_trades = [
            t.get("trade") for t in (w.get("specialist_trades") or [])
            if t.get("status") == "verified"
        ]
        out.append({
            **r,
            "worker": {
                "user_id": r["worker_id"],
                "name": w.get("name"),
                "email": w.get("email"),
                "phone": w.get("phone"),
                "zip_code": w.get("zip_code"),
                "avatar_path": w.get("avatar_path"),
                "badge_count": len(w.get("certified_badges") or []),
                "verified_trades": verified_trades,
                "completions": comp.get(r["worker_id"], 0),
                "rating_avg": w.get("rating_avg"),
            },
        })
    return {"interests": out}


# ============================================================================
# Admin — gig photo upload (staged before create; served to all logged-in users)
# ============================================================================
@router.post("/admin/gig-photos")
async def upload_gig_photo(file: UploadFile = File(...), admin: dict = Depends(require_admin)):
    data = await file.read()
    if len(data) > MAX_GIG_PHOTO_BYTES:
        raise HTTPException(400, "File too large (max 10MB)")
    ext, ct = validate_upload(data, file.filename or "")
    path = f"{APP_NAME}/gigs/{uuid.uuid4().hex}.{ext}"
    result = await asyncio.to_thread(put_object, path, data, ct)
    await db.files.insert_one({
        "file_id": str(uuid.uuid4()),
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": ct,
        "size": result.get("size"),
        "owner_id": admin["user_id"],
        "kind": "gig_photo",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"path": result["path"]}
