"""VA portal routes (`/api/va/*`) — self-service dashboard, lead submission,
earnings, and commercial account list. Lead+commission lifecycle helpers live
in `va_commission.py`.

Wiring in server.py:
    from routes.va import router as va_router
    api.include_router(va_router)
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from config import db
from auth_deps import _get_user_by_id
from va_commission import (
    require_va,
    require_va_active,
    VARegisterDetailsIn,
    LeadIn,
    LeadEditIn,
    LeadDeleteIn,
    _normalize_phone,
    _normalize_email,
    _normalize_address,
    _log_violation,
    _log_lead_activity,
    _find_duplicate_lead,
    _serialize_lead,
    _serialize_commission,
)

router = APIRouter()


@router.get("/va/me")
async def va_me(user: dict = Depends(require_va)):
    return user


@router.put("/va/me")
async def va_update_me(payload: VARegisterDetailsIn, user: dict = Depends(require_va)):
    updates = {}
    if payload.va_phone is not None:
        updates["va_phone"] = payload.va_phone.strip()
    if payload.va_address is not None:
        updates["va_address"] = payload.va_address.strip()
    if updates:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": updates})
    return await _get_user_by_id(user["user_id"])


@router.get("/va/dashboard")
async def va_dashboard(user: dict = Depends(require_va)):
    va_id = user["user_id"]
    active_stages = ["new_lead", "contacted", "quoted", "booked", "completed"]
    active_count = await db.va_leads.count_documents(
        {"va_user_id": va_id, "stage": {"$in": active_stages}}
    )
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


@router.post("/va/leads")
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
        "ownership_locked_at": now,
        "created_at": now,
        "updated_at": now,
    }
    await db.va_leads.insert_one(doc)
    return _serialize_lead(doc)


@router.get("/va/leads")
async def va_list_leads(stage: Optional[str] = None, user: dict = Depends(require_va)):
    q: dict = {"va_user_id": user["user_id"], "deleted_at": {"$in": [None, ""]}}
    if stage:
        q["stage"] = stage
    items = []
    cur = db.va_leads.find(q).sort("created_at", -1)
    async for d in cur:
        items.append(_serialize_lead(d))
    return {"items": items}


@router.get("/va/leads/{lead_id}")
async def va_get_lead(lead_id: str, user: dict = Depends(require_va)):
    """VAs see their own lead detail + activity timeline. Other VAs' leads are 404."""
    lead = await db.va_leads.find_one({"lead_id": lead_id, "va_user_id": user["user_id"]})
    if not lead:
        raise HTTPException(404, "Lead not found")
    activity = []
    cur = db.va_lead_activity.find({"lead_id": lead_id}).sort("created_at", -1).limit(200)
    async for a in cur:
        activity.append({k: v for k, v in a.items() if k != "_id"})
    commission = await db.commissions.find_one({"lead_id": lead_id})
    return {
        "lead": _serialize_lead(lead),
        "activity": activity,
        "commission": _serialize_commission(commission) if commission else None,
    }


@router.patch("/va/leads/{lead_id}")
async def va_edit_lead(
    lead_id: str,
    payload: LeadEditIn,
    user: dict = Depends(require_va_active),
):
    """VA can edit their own lead ONLY while it's still in stage='new_lead'.
    Once admin has touched the pipeline (contacted/quoted/etc.), the lead is
    locked for VAs and must be edited by an admin."""
    lead = await db.va_leads.find_one({"lead_id": lead_id, "va_user_id": user["user_id"]})
    if not lead:
        raise HTTPException(404, "Lead not found")
    if lead.get("deleted_at"):
        raise HTTPException(400, "Lead is deleted")
    if lead.get("stage") != "new_lead":
        raise HTTPException(
            403,
            "This lead has already been picked up by admin. Ask your Program Manager to edit it.",
        )
    # VAs cannot reassign owner or set job_value — those are admin-only.
    if payload.va_user_id or payload.job_value is not None:
        raise HTTPException(403, "Only admins can change ownership or job value")

    now = datetime.now(timezone.utc).isoformat()
    updates: dict = {}
    changes: dict = {}

    def _add(field: str, new_val):
        old_val = lead.get(field)
        if new_val is not None and new_val != old_val:
            updates[field] = new_val
            changes[field] = {"from": old_val, "to": new_val}

    if payload.prospect_name is not None:
        _add("prospect_name", payload.prospect_name.strip())
    if payload.prospect_phone is not None:
        phone = payload.prospect_phone.strip()
        _add("prospect_phone", phone)
        updates["prospect_phone_norm"] = _normalize_phone(phone)
    if payload.prospect_email is not None:
        em = payload.prospect_email.strip()
        _add("prospect_email", em)
        updates["prospect_email_norm"] = _normalize_email(em)
    if payload.prospect_address is not None:
        ad = payload.prospect_address.strip()
        _add("prospect_address", ad)
        updates["prospect_address_norm"] = _normalize_address(ad)
    if payload.service_type is not None:
        _add("service_type", payload.service_type)
    if payload.property_size is not None:
        _add("property_size", payload.property_size)
    if payload.preferred_datetime is not None:
        _add("preferred_datetime", payload.preferred_datetime)
    if payload.source is not None:
        _add("source", payload.source)
    if payload.notes is not None:
        _add("notes", payload.notes.strip())

    if not changes:
        return _serialize_lead(lead)

    updates["updated_at"] = now
    await db.va_leads.update_one({"lead_id": lead_id}, {"$set": updates})
    await _log_lead_activity(
        lead_id=lead_id,
        kind="edited",
        actor=user,
        detail={"changes": changes, "reason": payload.reason},
    )
    fresh = await db.va_leads.find_one({"lead_id": lead_id})
    return _serialize_lead(fresh)


@router.delete("/va/leads/{lead_id}")
async def va_delete_lead(
    lead_id: str,
    payload: LeadDeleteIn = Body(default=LeadDeleteIn()),
    user: dict = Depends(require_va_active),
):
    """VA can soft-delete their own lead ONLY while it's still in stage='new_lead'.
    Once it moves past 'new_lead' (or any commission has been generated), only
    an admin can delete it."""
    lead = await db.va_leads.find_one({"lead_id": lead_id, "va_user_id": user["user_id"]})
    if not lead:
        raise HTTPException(404, "Lead not found")
    if lead.get("deleted_at"):
        return _serialize_lead(lead)  # idempotent
    if lead.get("stage") != "new_lead":
        raise HTTPException(
            403,
            "This lead has already been picked up by admin. Ask your Program Manager to delete it.",
        )
    # Extra safety: if a commission exists, block (commissions only exist post-'booked').
    existing_commission = await db.commissions.find_one({"lead_id": lead_id})
    if existing_commission:
        raise HTTPException(403, "Cannot delete — a commission has been generated. Contact admin.")

    now = datetime.now(timezone.utc).isoformat()
    await db.va_leads.update_one(
        {"lead_id": lead_id},
        {"$set": {
            "deleted_at": now,
            "deleted_by": user["user_id"],
            "deleted_reason": (payload.reason or "").strip() or None,
            "updated_at": now,
        }},
    )
    await _log_lead_activity(
        lead_id=lead_id,
        kind="deleted",
        actor=user,
        detail={"reason": payload.reason},
    )
    fresh = await db.va_leads.find_one({"lead_id": lead_id})
    return _serialize_lead(fresh)


@router.get("/va/earnings")
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


@router.get("/va/commercial-accounts")
async def va_my_commercial_accounts(user: dict = Depends(require_va)):
    items = []
    cur = db.commercial_accounts.find({"va_user_id": user["user_id"]}).sort("created_at", -1)
    async for d in cur:
        items.append({k: v for k, v in d.items() if k != "_id"})
    return {"items": items}
