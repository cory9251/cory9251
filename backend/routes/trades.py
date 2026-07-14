"""Specialist trades (FRD Addendum A) — equipment checklists, photo proof,
verification queue, admin-configurable trade definitions, and metrics.

Wiring in server.py:
    from routes.trades import router as trades_router, seed_trade_definitions
    api.include_router(trades_router)
"""
import re
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from config import db, logger, APP_NAME
from auth_deps import get_current_user, require_admin, _get_user_by_id
from storage import put_object, validate_upload
from constants import (
    SPECIALIST_TRADES,
    TRADE_LABELS,
    LICENSED_TRADES,
    GENERAL_SKILLS,
    WORK_ATTRIBUTES,
    WORK_CLASSES,
    EXPERIENCE_OPTIONS,
)
from worker_taxonomy import sync_user_skills, trade_is_active, _parse_iso

router = APIRouter()

MAX_TRADE_PHOTOS = 6
MAX_PHOTO_BYTES = 10 * 1024 * 1024

OWNERSHIP_LANGUAGE = (
    "Check only equipment you personally own and bring to jobs. Network policy: "
    "contractors supply their own tools and equipment unless a job states otherwise."
)


async def _notify(user_id: str, title: str, body: str) -> None:
    await db.notifications.insert_one({
        "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "title": title,
        "body": body,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


async def _notify_admins(title: str, body: str) -> None:
    admins = await db.users.find({"role": "admin"}, {"_id": 0, "user_id": 1}).to_list(50)
    for a in admins:
        await _notify(a["user_id"], title, body)


# ============================================================================
# Launch-set trade definitions (FRD §5) — admin-editable after seed
# ============================================================================
def _item(key, label, detail_label=None, photo_required=False):
    return {"key": key, "label": label, "detail_label": detail_label, "photo_required": photo_required}


LAUNCH_TRADES = [
    {"trade_id": "painting", "label": "Painting", "licensed": False, "sort": 1,
     "photo_hint": "Full kit photo; sprayer photo if claimed",
     "checklist": [
         _item("brushes_rollers", "Brushes & rollers"),
         _item("sprayer", "Paint sprayer", "Make/model", True),
         _item("ladders", "Ladders", "Heights"),
         _item("drop_cloths", "Drop cloths & masking"),
         _item("supplies", "Own supplies (primer, caulk, patching)"),
     ]},
    {"trade_id": "landscaping", "label": "Landscaping", "licensed": False, "sort": 2,
     "photo_hint": "Equipment photo(s); trailer photo if claimed",
     "checklist": [
         _item("mower", "Mower", "Type (push / ride)"),
         _item("trimmer", "String trimmer"),
         _item("blower", "Blower"),
         _item("hedge_tools", "Hedge tools"),
         _item("trailer", "Trailer or hauling capability", None, True),
     ]},
    {"trade_id": "carpet_cleaning", "label": "Carpet Cleaning", "licensed": False, "sort": 3,
     "photo_hint": "Machine photo REQUIRED — no photo, no claim",
     "checklist": [
         _item("machine", "Extraction machine", "Type (portable / truck-mount) + make/model", True),
         _item("wand_hoses", "Wand & hoses"),
         _item("chemicals", "Chemicals / solutions"),
         _item("spotter", "Spotter"),
     ]},
    {"trade_id": "pressure_washing", "label": "Pressure Washing", "licensed": False, "sort": 4,
     "photo_hint": "Machine photo REQUIRED",
     "checklist": [
         _item("washer", "Pressure washer", "PSI + make/model", True),
         _item("surface_cleaner", "Surface cleaner attachment"),
         _item("hoses_nozzles", "Hoses & nozzles"),
         _item("water_tank", "Water tank (if any)"),
     ]},
    {"trade_id": "carpentry", "label": "Carpentry", "licensed": False, "sort": 5,
     "photo_hint": "Kit photo; portfolio photos encouraged",
     "checklist": [
         _item("saws", "Saws", "Types"),
         _item("drills", "Drills & drivers"),
         _item("measuring", "Levels, squares, measuring"),
         _item("work_vehicle", "Work vehicle capability"),
     ]},
    {"trade_id": "handyman", "label": "Handyman", "licensed": False, "sort": 6,
     "photo_hint": "Kit photo",
     "checklist": [
         _item("hand_tools", "Core hand-tool kit"),
         _item("drill_driver", "Drill / driver"),
         _item("ladder", "Ladder"),
         _item("consumables", "Multi-trade consumables"),
     ]},
    {"trade_id": "junk_removal", "label": "Junk Removal / Hauling", "licensed": False, "sort": 7,
     "photo_hint": "Vehicle/trailer photo REQUIRED",
     "checklist": [
         _item("truck_trailer", "Truck or trailer", None, True),
         _item("dollies_straps", "Dollies & straps"),
         _item("tarps", "Tarps"),
     ]},
    {"trade_id": "plumbing", "label": "Plumbing (Licensed)", "licensed": True, "sort": 8,
     "photo_hint": "License upload REQUIRED; DLLR lookup by admin",
     "checklist": [
         _item("tools", "Standard plumbing tool kit (attestation)"),
     ]},
    {"trade_id": "electrical", "label": "Electrical (Licensed)", "licensed": True, "sort": 9,
     "photo_hint": "License upload REQUIRED; DLLR lookup by admin",
     "checklist": [
         _item("tools", "Standard electrical tool kit (attestation)"),
     ]},
]


async def seed_trade_definitions() -> None:
    now = datetime.now(timezone.utc).isoformat()
    for t in LAUNCH_TRADES:
        await db.trade_definitions.update_one(
            {"trade_id": t["trade_id"]},
            {"$setOnInsert": {**t, "active": True, "created_at": now, "created_by": "seed"}},
            upsert=True,
        )


async def _get_def(trade_id: str) -> Optional[dict]:
    return await db.trade_definitions.find_one({"trade_id": trade_id}, {"_id": 0})


def claim_completeness_errors(claim: dict, tdef: dict) -> List[str]:
    """FRD §5 gate — a claim can't go to review until these all pass."""
    errs: List[str] = []
    checklist = claim.get("checklist") or {}
    checked = [k for k, v in checklist.items() if v]
    if not checked:
        errs.append("Check at least one equipment item you own")
    items = {i["key"]: i for i in (tdef.get("checklist") or [])}
    details = claim.get("detail_fields") or {}
    for k in checked:
        it = items.get(k)
        if it and it.get("detail_label") and not str(details.get(k) or "").strip():
            errs.append(f"\u201c{it['label']}\u201d needs details ({it['detail_label']})")
    if tdef.get("licensed") and not str(claim.get("license_number") or "").strip():
        errs.append("License number is required")
    if not (claim.get("photos") or []):
        errs.append("License upload is required" if tdef.get("licensed") else "At least one equipment photo is required")
    if not claim.get("experience"):
        errs.append("Select your experience level for this trade")
    return errs


# ============================================================================
# Shared — trade definitions for any logged-in user
# ============================================================================
@router.get("/trades/definitions")
async def list_trade_definitions(user: dict = Depends(get_current_user)):
    defs = await db.trade_definitions.find({"active": True}, {"_id": 0}).sort("sort", 1).to_list(100)
    return {"trades": defs, "ownership_language": OWNERSHIP_LANGUAGE}


# ============================================================================
# Worker — questionnaire (classes / general skills / attributes)
# ============================================================================
class QuestionnaireIn(BaseModel):
    work_classes: Optional[List[str]] = None
    general_skills: Optional[List[str]] = None
    general_experience: Optional[str] = None
    work_attributes: Optional[List[str]] = None
    bilingual_languages: Optional[str] = None


def _require_worker(user: dict) -> None:
    if user.get("role") != "worker":
        raise HTTPException(403, "Worker account required")


@router.put("/profile/questionnaire")
async def update_questionnaire(payload: QuestionnaireIn, user: dict = Depends(get_current_user)):
    _require_worker(user)
    updates: dict = {"questionnaire_version": 2}
    if payload.work_classes is not None:
        updates["work_classes"] = [c for c in payload.work_classes if c in WORK_CLASSES]
    if payload.general_skills is not None:
        gs = [s for s in payload.general_skills if s in GENERAL_SKILLS]
        if ("driving" in gs or "delivery" in gs) and not (user.get("has_car") or user.get("has_truck")):
            raise HTTPException(400, "Driving/delivery requires a car or truck — declare your vehicle first")
        updates["general_skills"] = gs
    if payload.general_experience is not None:
        if payload.general_experience and payload.general_experience not in EXPERIENCE_OPTIONS:
            raise HTTPException(400, f"general_experience must be one of {EXPERIENCE_OPTIONS}")
        updates["general_experience"] = payload.general_experience or None
    if payload.work_attributes is not None:
        updates["work_attributes"] = [a for a in payload.work_attributes if a in WORK_ATTRIBUTES]
    if payload.bilingual_languages is not None:
        updates["bilingual_languages"] = payload.bilingual_languages.strip()[:120] or None
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": updates})
    await sync_user_skills(user["user_id"])
    return await _get_user_by_id(user["user_id"])


# ============================================================================
# Worker — specialist trade claims
# ============================================================================
class TradeClaimIn(BaseModel):
    checklist: Optional[Dict[str, bool]] = None
    detail_fields: Optional[Dict[str, str]] = None
    experience: Optional[str] = None
    license_number: Optional[str] = None


def _find_claim(user: dict, trade_id: str) -> Optional[dict]:
    for c in user.get("specialist_trades") or []:
        if c.get("trade") == trade_id:
            return c
    return None


async def _fresh_user(user_id: str) -> dict:
    return await db.users.find_one({"user_id": user_id}, {"_id": 0})


@router.get("/profile/trades")
async def my_trade_claims(user: dict = Depends(get_current_user)):
    _require_worker(user)
    claims = user.get("specialist_trades") or []
    defs = {d["trade_id"]: d for d in await db.trade_definitions.find({}, {"_id": 0}).to_list(100)}
    out = []
    for c in claims:
        tdef = defs.get(c.get("trade")) or {}
        out.append({**c, "label": tdef.get("label") or TRADE_LABELS.get(c.get("trade"), c.get("trade")),
                    "completeness_errors": claim_completeness_errors(c, tdef),
                    "active_for_dispatch": trade_is_active(c)})
    return {"claims": out}


@router.put("/profile/trades/{trade_id}")
async def upsert_trade_claim(trade_id: str, payload: TradeClaimIn, user: dict = Depends(get_current_user)):
    _require_worker(user)
    tdef = await _get_def(trade_id)
    if not tdef or not tdef.get("active"):
        raise HTTPException(404, "Unknown trade")
    if payload.experience and payload.experience not in EXPERIENCE_OPTIONS:
        raise HTTPException(400, f"experience must be one of {EXPERIENCE_OPTIONS}")
    fresh = await _fresh_user(user["user_id"])
    claim = _find_claim(fresh, trade_id)
    now_iso = datetime.now(timezone.utc).isoformat()
    if not claim:
        claim = {
            "trade": trade_id, "status": "incomplete", "experience": None,
            "checklist": {}, "detail_fields": {}, "photos": [],
            "license_number": None, "admin_note": None, "claimed_at": now_iso,
            "submitted_at": None, "verified_at": None, "verified_by": None,
            "grace_until": None,
        }
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$push": {"specialist_trades": claim},
             "$addToSet": {"work_classes": "specialist"}},
        )
    valid_keys = {i["key"] for i in (tdef.get("checklist") or [])}
    sets = {}
    if payload.checklist is not None:
        sets["specialist_trades.$.checklist"] = {k: bool(v) for k, v in payload.checklist.items() if k in valid_keys}
    if payload.detail_fields is not None:
        sets["specialist_trades.$.detail_fields"] = {k: str(v)[:200] for k, v in payload.detail_fields.items() if k in valid_keys}
    if payload.experience is not None:
        sets["specialist_trades.$.experience"] = payload.experience or None
    if payload.license_number is not None:
        sets["specialist_trades.$.license_number"] = payload.license_number.strip()[:60] or None
    # Editing a returned claim re-opens it for resubmission.
    if claim.get("status") == "returned" and sets:
        sets["specialist_trades.$.status"] = "incomplete"
    if sets:
        await db.users.update_one(
            {"user_id": user["user_id"], "specialist_trades.trade": trade_id},
            {"$set": sets},
        )
    fresh = await _fresh_user(user["user_id"])
    c = _find_claim(fresh, trade_id)
    return {**c, "completeness_errors": claim_completeness_errors(c, tdef)}


@router.delete("/profile/trades/{trade_id}")
async def remove_trade_claim(trade_id: str, user: dict = Depends(get_current_user)):
    _require_worker(user)
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$pull": {"specialist_trades": {"trade": trade_id}}},
    )
    fresh = await _fresh_user(user["user_id"])
    if not (fresh.get("specialist_trades") or []):
        await db.users.update_one(
            {"user_id": user["user_id"]}, {"$pull": {"work_classes": "specialist"}}
        )
    await sync_user_skills(user["user_id"])
    return {"ok": True}


@router.post("/profile/trades/{trade_id}/photos")
async def upload_trade_photo(trade_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    _require_worker(user)
    tdef = await _get_def(trade_id)
    if not tdef:
        raise HTTPException(404, "Unknown trade")
    fresh = await _fresh_user(user["user_id"])
    claim = _find_claim(fresh, trade_id)
    if not claim:
        # Auto-create the claim shell so photo-first flows work.
        await upsert_trade_claim(trade_id, TradeClaimIn(), user)
        fresh = await _fresh_user(user["user_id"])
        claim = _find_claim(fresh, trade_id)
    if len(claim.get("photos") or []) >= MAX_TRADE_PHOTOS:
        raise HTTPException(400, f"Max {MAX_TRADE_PHOTOS} photos per trade")
    data = await file.read()
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(400, "File too large (max 10MB)")
    ext, ct = validate_upload(data, file.filename or "", allow_pdf=tdef.get("licensed", False))
    path = f"{APP_NAME}/trades/{user['user_id']}/{trade_id}/{uuid.uuid4().hex}.{ext}"
    result = await asyncio.to_thread(put_object, path, data, ct)
    await db.files.insert_one({
        "file_id": str(uuid.uuid4()),
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": ct,
        "size": result.get("size"),
        "owner_id": user["user_id"],
        "kind": "trade_photo",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.users.update_one(
        {"user_id": user["user_id"], "specialist_trades.trade": trade_id},
        {"$push": {"specialist_trades.$.photos": result["path"]}},
    )
    return {"path": result["path"]}


@router.delete("/profile/trades/{trade_id}/photos")
async def remove_trade_photo(trade_id: str, path: str = Query(...), user: dict = Depends(get_current_user)):
    _require_worker(user)
    await db.users.update_one(
        {"user_id": user["user_id"], "specialist_trades.trade": trade_id},
        {"$pull": {"specialist_trades.$.photos": path}},
    )
    return {"ok": True}


@router.post("/profile/trades/{trade_id}/submit")
async def submit_trade_claim(trade_id: str, user: dict = Depends(get_current_user)):
    _require_worker(user)
    tdef = await _get_def(trade_id)
    if not tdef:
        raise HTTPException(404, "Unknown trade")
    fresh = await _fresh_user(user["user_id"])
    claim = _find_claim(fresh, trade_id)
    if not claim:
        raise HTTPException(404, "You haven't claimed this trade")
    if claim.get("status") in ("pending", "verified"):
        return {**claim, "completeness_errors": []}
    errs = claim_completeness_errors(claim, tdef)
    if errs:
        raise HTTPException(400, "Complete the checklist first: " + "; ".join(errs))
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.users.update_one(
        {"user_id": user["user_id"], "specialist_trades.trade": trade_id},
        {"$set": {"specialist_trades.$.status": "pending",
                  "specialist_trades.$.submitted_at": now_iso,
                  "specialist_trades.$.admin_note": None}},
    )
    await _notify_admins(
        f"Specialist claim: {tdef['label']}",
        f"{fresh.get('name') or fresh.get('email')} submitted equipment proof for {tdef['label']}. Review it in Ops → Trades.",
    )
    fresh = await _fresh_user(user["user_id"])
    return {**_find_claim(fresh, trade_id), "completeness_errors": []}


# ============================================================================
# Admin — trade manager (FRD §8, no-code checklist edits)
# ============================================================================
class ChecklistItemIn(BaseModel):
    key: Optional[str] = None
    label: str
    detail_label: Optional[str] = None
    photo_required: bool = False


class TradeDefIn(BaseModel):
    label: str
    licensed: bool = False
    active: bool = True
    photo_hint: Optional[str] = None
    checklist: List[ChecklistItemIn] = []


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.strip().lower()).strip("_")[:40]


def _clean_checklist(items: List[ChecklistItemIn]) -> List[dict]:
    out, seen = [], set()
    for it in items:
        key = _slug(it.key or it.label)
        if not key or key in seen:
            key = f"{key or 'item'}_{len(out)}"
        seen.add(key)
        out.append({"key": key, "label": it.label.strip()[:120],
                    "detail_label": (it.detail_label or "").strip()[:120] or None,
                    "photo_required": bool(it.photo_required)})
    return out


@router.get("/admin/trades")
async def admin_list_trades(admin: dict = Depends(require_admin)):
    defs = await db.trade_definitions.find({}, {"_id": 0}).sort("sort", 1).to_list(200)
    return {"trades": defs}


@router.post("/admin/trades")
async def admin_create_trade(payload: TradeDefIn, admin: dict = Depends(require_admin)):
    trade_id = _slug(payload.label)
    if not trade_id:
        raise HTTPException(400, "Trade name required")
    if await _get_def(trade_id):
        raise HTTPException(400, "A trade with this name already exists")
    count = await db.trade_definitions.count_documents({})
    doc = {
        "trade_id": trade_id,
        "label": payload.label.strip()[:80],
        "licensed": payload.licensed,
        "active": payload.active,
        "photo_hint": (payload.photo_hint or "").strip()[:200] or None,
        "checklist": _clean_checklist(payload.checklist),
        "sort": count + 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": admin["email"],
    }
    await db.trade_definitions.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.put("/admin/trades/{trade_id}")
async def admin_update_trade(trade_id: str, payload: TradeDefIn, admin: dict = Depends(require_admin)):
    tdef = await _get_def(trade_id)
    if not tdef:
        raise HTTPException(404, "Trade not found")
    await db.trade_definitions.update_one(
        {"trade_id": trade_id},
        {"$set": {
            "label": payload.label.strip()[:80],
            "licensed": payload.licensed,
            "active": payload.active,
            "photo_hint": (payload.photo_hint or "").strip()[:200] or None,
            "checklist": _clean_checklist(payload.checklist),
        }},
    )
    return await _get_def(trade_id)


@router.delete("/admin/trades/{trade_id}")
async def admin_delete_trade(trade_id: str, admin: dict = Depends(require_admin)):
    claim_count = await db.users.count_documents({"specialist_trades.trade": trade_id})
    if claim_count:
        raise HTTPException(400, f"{claim_count} workers have claims on this trade — deactivate it instead")
    await db.trade_definitions.delete_one({"trade_id": trade_id})
    return {"ok": True}


# ============================================================================
# Admin — verification review queue (FRD §8 review screen)
# ============================================================================
@router.get("/admin/trade-claims")
async def admin_list_claims(
    status: Optional[str] = Query("pending"),
    trade: Optional[str] = Query(None),
    admin: dict = Depends(require_admin),
):
    q: dict = {"role": "worker", "specialist_trades.0": {"$exists": True}}
    users = await db.users.find(
        q, {"_id": 0, "user_id": 1, "name": 1, "email": 1, "phone": 1, "zip_code": 1,
            "avatar_path": 1, "specialist_trades": 1}
    ).to_list(2000)
    defs = {d["trade_id"]: d for d in await db.trade_definitions.find({}, {"_id": 0}).to_list(200)}
    out = []
    for u in users:
        for c in u.get("specialist_trades") or []:
            if status and status != "all" and c.get("status") != status:
                continue
            if trade and c.get("trade") != trade:
                continue
            tdef = defs.get(c.get("trade")) or {}
            out.append({
                **c,
                "label": tdef.get("label") or TRADE_LABELS.get(c.get("trade"), c.get("trade")),
                "licensed": bool(tdef.get("licensed")),
                "checklist_items": tdef.get("checklist") or [],
                "completeness_errors": claim_completeness_errors(c, tdef),
                "worker": {"user_id": u["user_id"], "name": u.get("name"), "email": u.get("email"),
                           "phone": u.get("phone"), "zip_code": u.get("zip_code"),
                           "avatar_path": u.get("avatar_path")},
            })
    out.sort(key=lambda c: c.get("submitted_at") or c.get("claimed_at") or "", reverse=True)
    return {"claims": out}


class ReturnIn(BaseModel):
    note: Optional[str] = None


@router.post("/admin/trade-claims/{user_id}/{trade_id}/verify")
async def admin_verify_claim(user_id: str, trade_id: str, admin: dict = Depends(require_admin)):
    tdef = await _get_def(trade_id)
    now_iso = datetime.now(timezone.utc).isoformat()
    res = await db.users.update_one(
        {"user_id": user_id, "specialist_trades.trade": trade_id},
        {"$set": {"specialist_trades.$.status": "verified",
                  "specialist_trades.$.verified_at": now_iso,
                  "specialist_trades.$.verified_by": admin["email"],
                  "specialist_trades.$.grace_until": None,
                  "specialist_trades.$.admin_note": None}},
    )
    if not res.matched_count:
        raise HTTPException(404, "Claim not found")
    await sync_user_skills(user_id)
    label = (tdef or {}).get("label") or trade_id
    await _notify(
        user_id,
        f"You're verified: {label}",
        f"HCOB verified your {label} equipment. You'll now get first access to {label} jobs at specialist rates.",
    )
    return {"ok": True}


@router.post("/admin/trade-claims/{user_id}/{trade_id}/return")
async def admin_return_claim(user_id: str, trade_id: str, payload: ReturnIn, admin: dict = Depends(require_admin)):
    tdef = await _get_def(trade_id)
    note = (payload.note or "").strip()[:500] or None
    res = await db.users.update_one(
        {"user_id": user_id, "specialist_trades.trade": trade_id},
        {"$set": {"specialist_trades.$.status": "returned",
                  "specialist_trades.$.admin_note": note}},
    )
    if not res.matched_count:
        raise HTTPException(404, "Claim not found")
    await sync_user_skills(user_id)
    label = (tdef or {}).get("label") or trade_id
    await _notify(
        user_id,
        f"Action needed: {label} verification",
        note or f"HCOB needs more info on your {label} equipment. Update your checklist and resubmit.",
    )
    return {"ok": True}


class GraceIn(BaseModel):
    days: int = 30


@router.post("/admin/trade-claims/{user_id}/{trade_id}/grace")
async def admin_extend_grace(user_id: str, trade_id: str, payload: GraceIn, admin: dict = Depends(require_admin)):
    days = max(1, min(int(payload.days or 30), 365))
    until = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    res = await db.users.update_one(
        {"user_id": user_id, "specialist_trades.trade": trade_id},
        {"$set": {"specialist_trades.$.grace_until": until}},
    )
    if not res.matched_count:
        raise HTTPException(404, "Claim not found")
    await sync_user_skills(user_id)
    return {"ok": True, "grace_until": until}


# ============================================================================
# Admin — metrics (FRD §8)
# ============================================================================
@router.get("/admin/trades/metrics")
async def admin_trade_metrics(admin: dict = Depends(require_admin)):
    users = await db.users.find(
        {"role": "worker", "specialist_trades.0": {"$exists": True}},
        {"_id": 0, "specialist_trades": 1},
    ).to_list(5000)
    defs = await db.trade_definitions.find({}, {"_id": 0, "trade_id": 1, "label": 1}).sort("sort", 1).to_list(200)
    by_trade: Dict[str, dict] = {d["trade_id"]: {"trade": d["trade_id"], "label": d["label"],
                                                 "total": 0, "incomplete": 0, "pending": 0,
                                                 "verified": 0, "returned": 0, "turnaround_days": []}
                                 for d in defs}
    total_specialists = 0
    verified_specialists = 0
    for u in users:
        has_verified = False
        for c in u.get("specialist_trades") or []:
            t = by_trade.setdefault(c.get("trade"), {"trade": c.get("trade"), "label": c.get("trade"),
                                                     "total": 0, "incomplete": 0, "pending": 0,
                                                     "verified": 0, "returned": 0, "turnaround_days": []})
            t["total"] += 1
            st = c.get("status") or "incomplete"
            if st in t:
                t[st] += 1
            if st == "verified":
                has_verified = True
                sub, ver = _parse_iso(c.get("submitted_at")), _parse_iso(c.get("verified_at"))
                if sub and ver and ver >= sub:
                    t["turnaround_days"].append((ver - sub).total_seconds() / 86400)
        total_specialists += 1
        if has_verified:
            verified_specialists += 1
    rows = []
    for t in by_trade.values():
        td = t.pop("turnaround_days")
        t["avg_turnaround_days"] = round(sum(td) / len(td), 1) if td else None
        t["pct_verified"] = round(100 * t["verified"] / t["total"]) if t["total"] else 0
        rows.append(t)
    return {
        "trades": rows,
        "total_specialists": total_specialists,
        "verified_specialists": verified_specialists,
        "pct_roster_verified": round(100 * verified_specialists / total_specialists) if total_specialists else 0,
    }
