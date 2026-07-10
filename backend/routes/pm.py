"""Program Manager routes (`/api/pm/*`) — lead pipeline, commission approval
queue, VA roster management, violations, commercial accounts, weekly report.

Wiring in server.py:
    from routes.pm import router as pm_router
    api.include_router(pm_router)
"""
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from config import db
from auth_deps import _get_user_by_id, hash_password
from notifications import _send_user_email, _public_base
from va_commission import (
    DIGITAL_SERVICE_TYPES,
    DigitalSettingsIn,
    AssignVAIn,
    COMMISSION_RATES,
    DEFAULT_DIGITAL_COMMISSION_PCT,
    DEFAULT_TEAM_OVERRIDE_PCT,
    _team_override_pct,
    OVERRIDABLE_FLAT_SERVICES,
    OVERRIDABLE_RATE_KEYS,
    CommissionSettingsIn,
    VACommissionOverridesIn,
    LeadFollowupIn,
    LeadContactIn,
    LeadCommentIn,
    apply_lead_followup,
    apply_lead_contact,
    apply_lead_comment,
    _resolve_commission_config,
    _get_digital_commission_pct,
    require_program_manager_or_owner,
    LeadStageIn,
    LeadEditIn,
    LeadDeleteIn,
    VAGoalIn,
    PitchTemplateIn,
    PitchTemplatePatch,
    CoachingNoteIn,
    CoachingNotePatch,
    CommissionActionIn,
    VAAccountAdminIn,
    VAStatusActionIn,
    CommercialAccountIn,
    CommercialAccountPatch,
    _normalize_phone,
    _normalize_email,
    _normalize_address,
    _log_violation,
    _log_lead_activity,
    _serialize_lead,
    _serialize_commission,
    _ensure_commission_for_lead,
)

router = APIRouter()


@router.get("/pm/leads")
async def pm_list_leads(
    va_user_id: Optional[str] = None,
    stage: Optional[str] = None,
    service_type: Optional[str] = None,
    category: Optional[str] = None,  # 'digital' | 'cleaning'
    q: Optional[str] = None,
    trash: Optional[bool] = False,  # ?trash=true → show only soft-deleted
    include_trashed: Optional[bool] = False,  # ?include_trashed=true → include trashed in result
    admin: dict = Depends(require_program_manager_or_owner),
):
    query: dict = {}
    if va_user_id:
        query["va_user_id"] = va_user_id
    if stage:
        query["stage"] = stage
    if service_type:
        query["service_type"] = service_type
    elif category == "digital":
        query["service_type"] = {"$in": sorted(DIGITAL_SERVICE_TYPES)}
    elif category == "cleaning":
        query["service_type"] = {"$nin": sorted(DIGITAL_SERVICE_TYPES)}
    if q:
        query["$or"] = [
            {"prospect_name": {"$regex": re.escape(q), "$options": "i"}},
            {"prospect_phone_norm": _normalize_phone(q)},
            {"prospect_email_norm": _normalize_email(q)},
        ]
    # Soft-delete filter (default: hide trashed).
    # `deleted_at` is set to ISO timestamp on soft delete, null otherwise.
    if trash:
        query["deleted_at"] = {"$nin": [None, ""]}
    elif not include_trashed:
        query["deleted_at"] = {"$in": [None, ""]}
    items = []
    cur = db.va_leads.find(query).sort("created_at", -1).limit(500)
    async for d in cur:
        items.append(_serialize_lead(d))
    return {"items": items}


@router.get("/pm/leads/{lead_id}")
async def pm_get_lead(
    lead_id: str,
    admin: dict = Depends(require_program_manager_or_owner),
):
    lead = await db.va_leads.find_one({"lead_id": lead_id})
    if not lead:
        raise HTTPException(404, "Lead not found")
    activity = []
    cur = db.va_lead_activity.find({"lead_id": lead_id}).sort("created_at", -1).limit(200)
    async for a in cur:
        activity.append({k: v for k, v in a.items() if k != "_id"})
    commission = await db.commissions.find_one(
        {"lead_id": lead_id, "kind": {"$ne": "team_override"}}
    )
    return {
        "lead": _serialize_lead(lead),
        "activity": activity,
        "commission": _serialize_commission(commission) if commission else None,
    }


@router.put("/pm/leads/{lead_id}/stage")
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
    updates: dict = {
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
    await _log_lead_activity(
        lead_id=lead_id,
        kind="stage_changed",
        actor=admin,
        detail={
            "from": lead.get("stage"),
            "to": payload.stage,
            "note": payload.note,
            "job_value": payload.job_value,
        },
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
        existing = await db.commissions.find_one(
            {"lead_id": lead_id, "kind": {"$ne": "team_override"}}
        )
        if existing and existing.get("status") in ("calculating",):
            await db.commissions.update_one(
                {"commission_id": existing["commission_id"]},
                {"$set": {"status": "calculating", "updated_at": now}},
            )
    elif payload.stage == "lost":
        # Reject the member commission AND any team-override tied to this lead.
        await db.commissions.update_many(
            {
                "lead_id": lead_id,
                "status": {"$in": ["calculating", "pending_approval"]},
            },
            {"$set": {"status": "rejected", "calc_notes": "Lead marked lost", "updated_at": now}},
        )

    # CRM: notify the VA on every stage move ('paid' already sends its own)
    if fresh.get("va_user_id") and payload.stage != "paid" and payload.stage != lead.get("stage"):
        await db.notifications.insert_one({
            "notification_id": f"notif_{uuid.uuid4().hex[:10]}",
            "user_id": fresh["va_user_id"],
            "kind": "lead_stage_changed",
            "title": f"Lead update: {fresh.get('prospect_name')}",
            "body": f"Your lead moved to {payload.stage.replace('_', ' ').title()}."
                    + (f" Note: {payload.note}" if payload.note else ""),
            "created_at": now,
            "read": False,
        })
    return _serialize_lead(fresh)


# ---------------------------------------------------------------------------
# Lead edit / soft-delete / restore (admin)
# ---------------------------------------------------------------------------
TRASH_AUTO_PURGE_DAYS = 30  # for future cleanup cron; UI shows "kept for N days"


@router.patch("/pm/leads/{lead_id}")
async def pm_edit_lead(
    lead_id: str,
    payload: LeadEditIn,
    admin: dict = Depends(require_program_manager_or_owner),
):
    """Admin edits any field on a lead. Activity logged. Phone/email/address
    are auto-renormalized so duplicate detection keeps working. Reassigning
    `va_user_id` also rewrites `va_name` and creates an audit row."""
    lead = await db.va_leads.find_one({"lead_id": lead_id})
    if not lead:
        raise HTTPException(404, "Lead not found")
    if lead.get("deleted_at"):
        raise HTTPException(400, "Lead is in Trash. Restore it before editing.")

    now = datetime.now(timezone.utc).isoformat()
    updates: dict = {}
    changes: dict = {}  # for activity log: field -> {from, to}

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
    if payload.estimated_budget is not None:
        _add("estimated_budget", float(payload.estimated_budget))
    if payload.job_value is not None:
        _add("job_value", float(payload.job_value))

    # Reassign owner (rare but useful when a lead was misattributed).
    if payload.va_user_id and payload.va_user_id != lead.get("va_user_id"):
        new_owner = await db.users.find_one(
            {"user_id": payload.va_user_id, "role": "va"},
            {"_id": 0, "user_id": 1, "name": 1},
        )
        if not new_owner:
            raise HTTPException(400, "Target VA not found")
        changes["va_user_id"] = {"from": lead.get("va_user_id"), "to": new_owner["user_id"]}
        changes["va_name"] = {"from": lead.get("va_name"), "to": new_owner.get("name")}
        updates["va_user_id"] = new_owner["user_id"]
        updates["va_name"] = new_owner.get("name")
        # Reassign the related commission too so it follows the new owner.
        await db.commissions.update_many(
            {"lead_id": lead_id},
            {"$set": {
                "va_user_id": new_owner["user_id"],
                "va_name": new_owner.get("name"),
                "updated_at": now,
            }},
        )

    if not changes:
        return _serialize_lead(lead)

    updates["updated_at"] = now
    await db.va_leads.update_one({"lead_id": lead_id}, {"$set": updates})
    await _log_lead_activity(
        lead_id=lead_id,
        kind="edited",
        actor=admin,
        detail={"changes": changes, "reason": payload.reason},
    )
    fresh = await db.va_leads.find_one({"lead_id": lead_id})
    return _serialize_lead(fresh)


@router.delete("/pm/leads/{lead_id}")
async def pm_delete_lead(
    lead_id: str,
    payload: LeadDeleteIn = Body(default=LeadDeleteIn()),
    admin: dict = Depends(require_program_manager_or_owner),
):
    """Soft-delete a lead. Kept in Trash for review/restore. If a commission
    is already PAID, the lead can be soft-deleted (for org hygiene) but the
    paid commission is left intact — that money was already disbursed."""
    lead = await db.va_leads.find_one({"lead_id": lead_id})
    if not lead:
        raise HTTPException(404, "Lead not found")
    if lead.get("deleted_at"):
        return _serialize_lead(lead)  # idempotent

    now = datetime.now(timezone.utc).isoformat()
    await db.va_leads.update_one(
        {"lead_id": lead_id},
        {"$set": {
            "deleted_at": now,
            "deleted_by": admin["user_id"],
            "deleted_reason": (payload.reason or "").strip() or None,
            "updated_at": now,
        }},
    )
    # Cancel any non-paid commissions tied to this lead (paid stays — already disbursed)
    await db.commissions.update_many(
        {"lead_id": lead_id, "status": {"$nin": ["paid"]}},
        {"$set": {"status": "rejected", "calc_notes": "Lead soft-deleted", "updated_at": now}},
    )
    await _log_lead_activity(
        lead_id=lead_id,
        kind="deleted",
        actor=admin,
        detail={"reason": payload.reason},
    )
    fresh = await db.va_leads.find_one({"lead_id": lead_id})
    return _serialize_lead(fresh)


@router.post("/pm/leads/{lead_id}/restore")
async def pm_restore_lead(
    lead_id: str,
    admin: dict = Depends(require_program_manager_or_owner),
):
    """Restore a soft-deleted lead. The Trash auto-purges after 30 days
    (handled by a future cleanup cron — not yet wired)."""
    lead = await db.va_leads.find_one({"lead_id": lead_id})
    if not lead:
        raise HTTPException(404, "Lead not found")
    if not lead.get("deleted_at"):
        raise HTTPException(400, "Lead is not in Trash")
    now = datetime.now(timezone.utc).isoformat()
    await db.va_leads.update_one(
        {"lead_id": lead_id},
        {"$set": {"deleted_at": None, "deleted_by": None, "deleted_reason": None, "updated_at": now}},
    )
    await _log_lead_activity(lead_id=lead_id, kind="restored", actor=admin, detail={})
    fresh = await db.va_leads.find_one({"lead_id": lead_id})
    return _serialize_lead(fresh)


# ---------------------------------------------------------------------------
# Digital services — commission rate + delivery VA assignment
# ---------------------------------------------------------------------------
@router.get("/pm/digital-settings")
async def pm_get_digital_settings(admin: dict = Depends(require_program_manager_or_owner)):
    return {"commission_pct": await _get_digital_commission_pct()}


@router.put("/pm/digital-settings")
async def pm_set_digital_settings(
    payload: DigitalSettingsIn,
    admin: dict = Depends(require_program_manager_or_owner),
):
    now = datetime.now(timezone.utc).isoformat()
    await db.app_settings.update_one(
        {"_id": "global"},
        {"$set": {
            "digital_commission_pct": float(payload.commission_pct),
            "digital_commission_updated_at": now,
            "digital_commission_updated_by": admin["user_id"],
        }},
        upsert=True,
    )
    return {"commission_pct": await _get_digital_commission_pct()}


@router.post("/pm/leads/{lead_id}/assign-va")
async def pm_assign_delivery_va(
    lead_id: str,
    payload: AssignVAIn,
    admin: dict = Depends(require_program_manager_or_owner),
):
    """Assign (or clear) the VA who will deliver this digital project."""
    lead = await db.va_leads.find_one({"lead_id": lead_id})
    if not lead:
        raise HTTPException(404, "Lead not found")
    if lead.get("deleted_at"):
        raise HTTPException(400, "Lead is in Trash")
    now = datetime.now(timezone.utc).isoformat()

    if not payload.va_user_id:
        prev = lead.get("assigned_va_name")
        await db.va_leads.update_one(
            {"lead_id": lead_id},
            {"$set": {"assigned_va_id": None, "assigned_va_name": None, "assigned_at": None, "updated_at": now}},
        )
        await _log_lead_activity(lead_id=lead_id, kind="delivery_unassigned", actor=admin, detail={"from": prev})
        fresh = await db.va_leads.find_one({"lead_id": lead_id})
        return _serialize_lead(fresh)

    va = await db.users.find_one(
        {"user_id": payload.va_user_id, "role": "va"},
        {"_id": 0, "user_id": 1, "name": 1, "va_status": 1},
    )
    if not va:
        raise HTTPException(400, "Target VA not found")
    if (va.get("va_status") or "pending") != "approved":
        raise HTTPException(400, "VA must be approved before being assigned delivery work")
    await db.va_leads.update_one(
        {"lead_id": lead_id},
        {"$set": {
            "assigned_va_id": va["user_id"],
            "assigned_va_name": va.get("name"),
            "assigned_at": now,
            "updated_at": now,
        }},
    )
    await _log_lead_activity(
        lead_id=lead_id,
        kind="delivery_assigned",
        actor=admin,
        detail={"from": lead.get("assigned_va_name"), "to": va.get("name")},
    )
    await db.notifications.insert_one({
        "notification_id": f"notif_{uuid.uuid4().hex[:10]}",
        "user_id": va["user_id"],
        "kind": "va_delivery_assigned",
        "title": "New delivery project",
        "body": f"You've been assigned to deliver '{lead.get('prospect_name')}' — {str(lead.get('service_type') or '').replace('_', ' ')}.",
        "created_at": now,
        "read": False,
    })
    fresh = await db.va_leads.find_one({"lead_id": lead_id})
    return _serialize_lead(fresh)


# ---------------------------------------------------------------------------
# Commission rate control — global defaults + per-VA overrides
# ---------------------------------------------------------------------------
async def _commission_settings_payload() -> dict:
    cfg = await _resolve_commission_config(None)
    return {
        "rates": cfg["rates"],
        "commercial_pct": cfg["commercial_pct"],
        "digital_pct": cfg["digital_pct"],
        "team_override_pct": await _team_override_pct(),
        "defaults": {
            "rates": {k: v for k, v in COMMISSION_RATES.items() if k != "commercial_pct"},
            "commercial_pct": COMMISSION_RATES["commercial_pct"] * 100.0,
            "digital_pct": DEFAULT_DIGITAL_COMMISSION_PCT,
            "team_override_pct": DEFAULT_TEAM_OVERRIDE_PCT,
        },
    }


@router.get("/pm/commission-settings")
async def pm_get_commission_settings(admin: dict = Depends(require_program_manager_or_owner)):
    return await _commission_settings_payload()


@router.put("/pm/commission-settings")
async def pm_set_commission_settings(
    payload: CommissionSettingsIn,
    admin: dict = Depends(require_program_manager_or_owner),
):
    updates: dict = {}
    if payload.rates is not None:
        clean: dict = {}
        for k, v in payload.rates.items():
            if k not in OVERRIDABLE_FLAT_SERVICES:
                raise HTTPException(400, f"Unknown service rate '{k}'")
            try:
                fv = float(v)
            except (TypeError, ValueError):
                raise HTTPException(400, f"Rate for '{k}' must be a number")
            if fv < 0 or fv > 10000:
                raise HTTPException(400, f"Rate for '{k}' out of range")
            clean[k] = fv
        updates["commission_rates"] = clean
    if payload.commercial_pct is not None:
        updates["commercial_pct"] = float(payload.commercial_pct)
    if payload.digital_pct is not None:
        updates["digital_commission_pct"] = float(payload.digital_pct)
    if payload.team_override_pct is not None:
        updates["team_override_pct"] = float(payload.team_override_pct)
    if updates:
        updates["commission_settings_updated_at"] = datetime.now(timezone.utc).isoformat()
        updates["commission_settings_updated_by"] = admin["user_id"]
        await db.app_settings.update_one({"_id": "global"}, {"$set": updates}, upsert=True)
    return await _commission_settings_payload()


@router.get("/pm/vas/{va_user_id}/commission-overrides")
async def pm_get_va_commission_overrides(
    va_user_id: str,
    admin: dict = Depends(require_program_manager_or_owner),
):
    va = await db.users.find_one(
        {"user_id": va_user_id, "role": "va"},
        {"_id": 0, "user_id": 1, "name": 1, "commission_overrides": 1},
    )
    if not va:
        raise HTTPException(404, "VA not found")
    cfg = await _resolve_commission_config(va_user_id)
    return {
        "va_user_id": va_user_id,
        "va_name": va.get("name"),
        "overrides": va.get("commission_overrides") or {},
        "effective": {"rates": cfg["rates"], "commercial_pct": cfg["commercial_pct"], "digital_pct": cfg["digital_pct"]},
        "globals": await _commission_settings_payload(),
    }


@router.put("/pm/vas/{va_user_id}/commission-overrides")
async def pm_set_va_commission_overrides(
    va_user_id: str,
    payload: VACommissionOverridesIn,
    admin: dict = Depends(require_program_manager_or_owner),
):
    va = await db.users.find_one({"user_id": va_user_id, "role": "va"}, {"_id": 0, "user_id": 1})
    if not va:
        raise HTTPException(404, "VA not found")
    clean: dict = {}
    for k, v in (payload.overrides or {}).items():
        if k not in OVERRIDABLE_RATE_KEYS:
            raise HTTPException(400, f"Unknown rate key '{k}'")
        try:
            fv = float(v)
        except (TypeError, ValueError):
            raise HTTPException(400, f"Override '{k}' must be a number")
        if k in ("commercial_pct", "digital_pct"):
            if fv < 0 or fv > 100:
                raise HTTPException(400, f"'{k}' must be between 0 and 100")
        elif fv < 0 or fv > 10000:
            raise HTTPException(400, f"'{k}' out of range")
        clean[k] = fv
    await db.users.update_one(
        {"user_id": va_user_id},
        {"$set": {"commission_overrides": clean, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    cfg = await _resolve_commission_config(va_user_id)
    return {
        "va_user_id": va_user_id,
        "overrides": clean,
        "effective": {"rates": cfg["rates"], "commercial_pct": cfg["commercial_pct"], "digital_pct": cfg["digital_pct"]},
    }


# ---------------------------------------------------------------------------
# VA Teams — single-level lead/downline with SPLIT override commissions.
# Feature is opt-in per VA via the is_team_lead toggle.
# ---------------------------------------------------------------------------
class TeamLeadToggleIn(BaseModel):
    is_team_lead: bool


class TeamAssignIn(BaseModel):
    team_lead_id: Optional[str] = None  # None = remove from any team


@router.put("/pm/vas/{va_user_id}/team-lead")
async def pm_toggle_team_lead(
    va_user_id: str,
    payload: TeamLeadToggleIn,
    admin: dict = Depends(require_program_manager_or_owner),
):
    va = await db.users.find_one(
        {"user_id": va_user_id, "role": "va"}, {"_id": 0, "user_id": 1, "team_lead_id": 1}
    )
    if not va:
        raise HTTPException(404, "VA not found")
    # Single level: a VA who is someone's member can't also lead a team.
    if payload.is_team_lead and va.get("team_lead_id"):
        raise HTTPException(400, "Remove this VA from their current team before making them a team lead")
    updates = {"is_team_lead": payload.is_team_lead, "updated_at": datetime.now(timezone.utc).isoformat()}
    await db.users.update_one({"user_id": va_user_id}, {"$set": updates})
    if not payload.is_team_lead:
        # Detach any members that reported to this (now former) lead.
        await db.users.update_many(
            {"team_lead_id": va_user_id}, {"$set": {"team_lead_id": None}}
        )
    return {"ok": True, "is_team_lead": payload.is_team_lead}


@router.put("/pm/vas/{va_user_id}/team")
async def pm_assign_team(
    va_user_id: str,
    payload: TeamAssignIn,
    admin: dict = Depends(require_program_manager_or_owner),
):
    member = await db.users.find_one(
        {"user_id": va_user_id, "role": "va"}, {"_id": 0, "user_id": 1, "is_team_lead": 1}
    )
    if not member:
        raise HTTPException(404, "VA not found")
    if payload.team_lead_id:
        if payload.team_lead_id == va_user_id:
            raise HTTPException(400, "A VA can't be on their own team")
        if member.get("is_team_lead"):
            raise HTTPException(400, "A team lead can't also be a member of another team (single level only)")
        lead = await db.users.find_one(
            {"user_id": payload.team_lead_id, "role": "va"},
            {"_id": 0, "is_team_lead": 1, "va_status": 1},
        )
        if not lead or not lead.get("is_team_lead"):
            raise HTTPException(400, "Target is not a team lead")
    await db.users.update_one(
        {"user_id": va_user_id},
        {"$set": {"team_lead_id": payload.team_lead_id, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True, "team_lead_id": payload.team_lead_id}


async def _override_earnings(team_lead_id: str) -> dict:
    by_status: dict = {}
    async for row in db.commissions.aggregate([
        {"$match": {"va_user_id": team_lead_id, "kind": "team_override"}},
        {"$group": {"_id": "$status", "total": {"$sum": "$amount"}}},
    ]):
        by_status[row["_id"]] = round(row["total"], 2)
    total = round(sum(v for k, v in by_status.items() if k != "rejected"), 2)
    return {"by_status": by_status, "total": total}


@router.get("/pm/teams")
async def pm_list_teams(admin: dict = Depends(require_program_manager_or_owner)):
    leads = await db.users.find(
        {"role": "va", "is_team_lead": True},
        {"_id": 0, "user_id": 1, "name": 1, "email": 1, "va_status": 1},
    ).sort("name", 1).to_list(200)
    all_vas = await db.users.find(
        {"role": "va"},
        {"_id": 0, "user_id": 1, "name": 1, "email": 1, "va_status": 1, "is_team_lead": 1, "team_lead_id": 1},
    ).sort("name", 1).to_list(1000)
    members_by_lead: dict = {}
    for v in all_vas:
        if v.get("team_lead_id"):
            members_by_lead.setdefault(v["team_lead_id"], []).append(v)
    teams = []
    for l in leads:
        earn = await _override_earnings(l["user_id"])
        teams.append({
            **l,
            "members": members_by_lead.get(l["user_id"], []),
            "member_count": len(members_by_lead.get(l["user_id"], [])),
            "override_earnings": earn,
        })
    # VAs eligible to be added as members: approved, not a lead, not already on a team.
    assignable = [
        v for v in all_vas
        if not v.get("is_team_lead") and not v.get("team_lead_id")
        and (v.get("va_status") or "") == "approved"
    ]
    return {
        "teams": teams,
        "assignable_vas": assignable,
        "team_override_pct": await _team_override_pct(),
    }


# ---------------------------------------------------------------------------
# CRM: follow-ups / contact log / comments (admin side)
# ---------------------------------------------------------------------------
async def _pm_lead_or_400(lead_id: str) -> dict:
    lead = await db.va_leads.find_one({"lead_id": lead_id})
    if not lead:
        raise HTTPException(404, "Lead not found")
    if lead.get("deleted_at"):
        raise HTTPException(400, "Lead is in Trash")
    return lead


@router.post("/pm/leads/{lead_id}/followup")
async def pm_set_followup(lead_id: str, payload: LeadFollowupIn, admin: dict = Depends(require_program_manager_or_owner)):
    lead = await _pm_lead_or_400(lead_id)
    fresh = await apply_lead_followup(lead, payload, admin)
    return _serialize_lead(fresh)


@router.post("/pm/leads/{lead_id}/contacts")
async def pm_log_contact(lead_id: str, payload: LeadContactIn, admin: dict = Depends(require_program_manager_or_owner)):
    lead = await _pm_lead_or_400(lead_id)
    fresh = await apply_lead_contact(lead, payload, admin)
    return _serialize_lead(fresh)


@router.post("/pm/leads/{lead_id}/comments")
async def pm_post_comment(lead_id: str, payload: LeadCommentIn, admin: dict = Depends(require_program_manager_or_owner)):
    lead = await _pm_lead_or_400(lead_id)
    fresh = await apply_lead_comment(lead, payload, admin)
    return _serialize_lead(fresh)


@router.get("/pm/commissions")
async def pm_list_commissions(
    status: Optional[str] = None,
    va_user_id: Optional[str] = None,
    admin: dict = Depends(require_program_manager_or_owner),
):
    q: dict = {}
    if status:
        q["status"] = status
    else:
        q["status"] = {"$in": ["pending_approval", "flagged"]}
    if va_user_id:
        q["va_user_id"] = va_user_id
    items = []
    cur = db.commissions.find(q).sort("created_at", 1)
    async for d in cur:
        items.append(_serialize_commission(d))
    return {"items": items}


@router.post("/pm/commissions/{commission_id}/approve")
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


@router.post("/pm/commissions/{commission_id}/flag")
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


@router.post("/pm/commissions/{commission_id}/reject")
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


@router.get("/pm/vas")
async def pm_list_vas(admin: dict = Depends(require_program_manager_or_owner)):
    items = []
    cur = db.users.find({"role": "va"}, {"_id": 0, "password_hash": 0}).sort("created_at", -1)
    async for u in cur:
        va_id = u.get("user_id")
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


@router.post("/pm/vas")
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


@router.post("/pm/vas/{va_user_id}/approve")
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


@router.post("/pm/vas/{va_user_id}/suspend")
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


@router.delete("/pm/vas/{va_user_id}")
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


@router.get("/pm/violations")
async def pm_list_violations(admin: dict = Depends(require_program_manager_or_owner)):
    items = []
    cur = db.va_violations.find().sort("created_at", -1).limit(500)
    async for v in cur:
        items.append({k: val for k, val in v.items() if k != "_id"})
    return {"items": items}


@router.get("/pm/commercial-accounts")
async def pm_list_commercial(admin: dict = Depends(require_program_manager_or_owner)):
    items = []
    cur = db.commercial_accounts.find().sort("created_at", -1)
    async for a in cur:
        items.append({k: v for k, v in a.items() if k != "_id"})
    return {"items": items}


@router.post("/pm/commercial-accounts")
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


@router.put("/pm/commercial-accounts/{account_id}")
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


@router.post("/pm/commercial-accounts/{account_id}/log-revenue")
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


@router.get("/pm/weekly-report")
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
    by_va_pipe = [
        {"$match": leads_q},
        {"$group": {"_id": "$va_user_id", "leads": {"$sum": 1}, "va_name": {"$first": "$va_name"}}},
        {"$sort": {"leads": -1}},
        {"$limit": 10},
    ]
    by_va = []
    async for row in db.va_leads.aggregate(by_va_pipe):
        by_va.append({"va_user_id": row["_id"], "va_name": row["va_name"], "leads": row["leads"]})
    active_commercial = await db.commercial_accounts.count_documents({"active": True})
    monthly_revenue_total = 0.0
    async for a in db.commercial_accounts.find({"active": True}):
        monthly_revenue_total += float(a.get("monthly_revenue") or 0)
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
# Analytics — drives the dedicated VA analytics page.
#   * velocity: commission dollar trend by calendar month (last 6 months)
#   * funnel:   per-VA conversion through the lead stages
#   * leaks:    leads stuck more than `leak_days` in a non-terminal stage,
#               sorted oldest-first so Mechie can break the log-jam
# ---------------------------------------------------------------------------
@router.get("/pm/analytics")
async def pm_analytics(
    months: int = 6,
    leak_days: int = 7,
    admin: dict = Depends(require_program_manager_or_owner),
):
    months = max(1, min(int(months), 12))
    leak_days = max(1, min(int(leak_days), 60))
    now = datetime.now(timezone.utc)
    # Anchor each month bucket on the 1st (UTC) for consistent labelling.
    # e.g. months=6 + today=2026-06-15 → buckets 2026-01..2026-06.
    buckets: list = []
    for i in range(months - 1, -1, -1):
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1
        buckets.append(f"{year:04d}-{month:02d}")
    earliest = buckets[0] + "-01T00:00:00"

    # ---- velocity ----------------------------------------------------------
    # Group commissions by created month, separately summing paid / approved
    # / pending so the chart shows the buckets stacked.
    velocity_pipe = [
        {"$match": {"created_at": {"$gte": earliest}}},
        {"$project": {
            "period": {"$substr": ["$created_at", 0, 7]},
            "amount": {"$ifNull": ["$amount", 0]},
            "status": 1,
        }},
        {"$group": {
            "_id": "$period",
            "paid":         {"$sum": {"$cond": [{"$eq": ["$status", "paid"]},                    "$amount", 0]}},
            "owner_approved":{"$sum": {"$cond": [{"$eq": ["$status", "owner_approved"]},         "$amount", 0]}},
            "pm_approved":  {"$sum": {"$cond": [{"$eq": ["$status", "pm_approved"]},             "$amount", 0]}},
            "pending":      {"$sum": {"$cond": [{"$in": ["$status", ["calculating", "pending_approval", "flagged"]]}, "$amount", 0]}},
            "rejected":     {"$sum": {"$cond": [{"$eq": ["$status", "rejected"]},                "$amount", 0]}},
            "count":        {"$sum": 1},
        }},
    ]
    by_period: dict = {}
    async for row in db.commissions.aggregate(velocity_pipe):
        by_period[row["_id"]] = row
    velocity = []
    for p in buckets:
        row = by_period.get(p) or {}
        paid = float(row.get("paid") or 0)
        owner_approved = float(row.get("owner_approved") or 0)
        pm_approved = float(row.get("pm_approved") or 0)
        pending = float(row.get("pending") or 0)
        rejected = float(row.get("rejected") or 0)
        velocity.append({
            "period": p,
            "paid": round(paid, 2),
            "owner_approved": round(owner_approved, 2),
            "pm_approved": round(pm_approved, 2),
            "pending": round(pending, 2),
            "rejected": round(rejected, 2),
            "total": round(paid + owner_approved + pm_approved + pending, 2),
            "count": int(row.get("count") or 0),
        })

    # ---- funnel -----------------------------------------------------------
    # For each VA: lead count broken down by *furthest stage reached*. Funnel
    # stages are progressive — if a lead is at `paid`, it was also booked,
    # quoted, contacted, etc. We compute the funnel by counting each stage
    # threshold (count of leads whose stage is at-or-past stage X).
    funnel_pipe = [
        {"$group": {
            "_id": "$va_user_id",
            "va_name": {"$first": "$va_name"},
            "stages": {"$push": "$stage"},
            "leads": {"$sum": 1},
            "lost": {"$sum": {"$cond": [{"$eq": ["$stage", "lost"]}, 1, 0]}},
        }},
    ]

    # "At-or-past" ordering for the funnel pyramid
    STAGE_ORDER = ["new_lead", "contacted", "quoted", "booked", "completed", "paid"]
    funnel = []
    async for row in db.va_leads.aggregate(funnel_pipe):
        stages = row.get("stages") or []
        # Count for each threshold: lead is "at_or_past" stage X if its stage
        # index >= X's index. Lost leads are tracked separately — they never
        # reach `paid` even if they were quoted at some point.
        counts = {}
        for idx, stage_name in enumerate(STAGE_ORDER):
            counts[stage_name] = sum(
                1 for s in stages
                if s in STAGE_ORDER and STAGE_ORDER.index(s) >= idx
            )
        leads = int(row.get("leads") or 0)
        paid_n = counts.get("paid", 0)
        funnel.append({
            "va_user_id": row["_id"],
            "va_name": row.get("va_name"),
            "leads": leads,
            "contacted": counts.get("contacted", 0),
            "quoted": counts.get("quoted", 0),
            "booked": counts.get("booked", 0),
            "completed": counts.get("completed", 0),
            "paid": paid_n,
            "lost": int(row.get("lost") or 0),
            "conversion": round((paid_n / leads) * 100, 1) if leads else 0,
        })
    funnel.sort(key=lambda r: (-r["leads"], -r["conversion"]))

    # ---- leaks ------------------------------------------------------------
    # Leads stuck in a non-terminal stage for > leak_days. Use the most-recent
    # stage transition timestamp so a lead that was contacted today doesn't
    # show up even if it was created 30 days ago.
    cutoff = (now - timedelta(days=leak_days)).isoformat()
    NON_TERMINAL = ["new_lead", "contacted", "quoted", "booked"]
    leak_cursor = db.va_leads.find(
        {
            "stage": {"$in": NON_TERMINAL},
            "stage_changed_at": {"$lt": cutoff},
        },
        {
            "_id": 0,
            "lead_id": 1,
            "va_user_id": 1,
            "va_name": 1,
            "prospect_name": 1,
            "stage": 1,
            "service_type": 1,
            "stage_changed_at": 1,
            "created_at": 1,
        },
    ).sort("stage_changed_at", 1).limit(50)
    leaks = []
    async for d in leak_cursor:
        last = d.get("stage_changed_at") or d.get("created_at") or ""
        try:
            ts = datetime.fromisoformat(last.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            days_stuck = int((now - ts).total_seconds() / 86400)
        except Exception:
            days_stuck = leak_days
        leaks.append({
            **d,
            "days_stuck": days_stuck,
        })

    return {
        "velocity": velocity,
        "funnel": funnel,
        "leaks": leaks,
        "params": {"months": months, "leak_days": leak_days},
    }


# ---------------------------------------------------------------------------
# Iter 42 — VA-success endpoints (goals, templates, coaching notes)
# ---------------------------------------------------------------------------
@router.get("/pm/va-goals/{va_user_id}")
async def pm_get_va_goals(
    va_user_id: str,
    months: Optional[int] = 12,
    admin: dict = Depends(require_program_manager_or_owner),
):
    """All goals for a VA, newest first. `months` caps how many rows."""
    items = []
    cur = db.va_goals.find({"va_user_id": va_user_id}).sort("month", -1).limit(max(1, int(months or 12)))
    async for g in cur:
        items.append({
            "month": g["month"],
            "target_leads": g.get("target_leads"),
            "target_commission": g.get("target_commission"),
            "note": g.get("note"),
            "set_by": g.get("set_by"),
            "set_at": g.get("set_at"),
        })
    return {"items": items}


@router.post("/pm/va-goals/{va_user_id}")
async def pm_set_va_goal(
    va_user_id: str,
    payload: VAGoalIn,
    admin: dict = Depends(require_program_manager_or_owner),
):
    """Upsert (set or replace) the goal for `va_user_id` for `payload.month`.
    If both target_leads and target_commission are None, the goal row is
    deleted instead (cleaner than leaving an empty target)."""
    va = await db.users.find_one({"user_id": va_user_id, "role": "va"})
    if not va:
        raise HTTPException(404, "VA not found")

    if payload.target_leads is None and payload.target_commission is None:
        await db.va_goals.delete_one({"va_user_id": va_user_id, "month": payload.month})
        return {"ok": True, "deleted": True}

    now = datetime.now(timezone.utc).isoformat()
    await db.va_goals.update_one(
        {"va_user_id": va_user_id, "month": payload.month},
        {"$set": {
            "va_user_id": va_user_id,
            "month": payload.month,
            "target_leads": payload.target_leads,
            "target_commission": payload.target_commission,
            "note": payload.note,
            "set_by": admin["user_id"],
            "set_by_name": admin.get("name") or admin.get("email"),
            "set_at": now,
        }},
        upsert=True,
    )
    return {"ok": True}


# ---- Pitch templates -------------------------------------------------------
@router.get("/pm/templates")
async def pm_list_templates(
    include_archived: Optional[bool] = False,
    admin: dict = Depends(require_program_manager_or_owner),
):
    q: dict = {"deleted_at": {"$in": [None, ""]}}
    if not include_archived:
        q["active"] = True
    items = []
    cur = db.pitch_templates.find(q).sort("created_at", -1).limit(500)
    async for t in cur:
        items.append({
            "template_id": t["template_id"],
            "title": t["title"],
            "body": t["body"],
            "category": t.get("category"),
            "channel": t.get("channel") or "any",
            "active": bool(t.get("active", True)),
            "created_at": t.get("created_at"),
            "created_by_name": t.get("created_by_name"),
        })
    return {"items": items}


@router.post("/pm/templates")
async def pm_create_template(
    payload: PitchTemplateIn,
    admin: dict = Depends(require_program_manager_or_owner),
):
    now = datetime.now(timezone.utc).isoformat()
    tid = f"tpl_{uuid.uuid4().hex[:12]}"
    doc = {
        "template_id": tid,
        "title": payload.title.strip(),
        "body": payload.body.strip(),
        "category": (payload.category or "").strip() or None,
        "channel": payload.channel,
        "active": True,
        "created_at": now,
        "created_by": admin["user_id"],
        "created_by_name": admin.get("name") or admin.get("email"),
        "updated_at": now,
        "deleted_at": None,
    }
    await db.pitch_templates.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.patch("/pm/templates/{template_id}")
async def pm_update_template(
    template_id: str,
    payload: PitchTemplatePatch,
    admin: dict = Depends(require_program_manager_or_owner),
):
    tpl = await db.pitch_templates.find_one({"template_id": template_id})
    if not tpl:
        raise HTTPException(404, "Template not found")
    updates: dict = {}
    if payload.title is not None:
        updates["title"] = payload.title.strip()
    if payload.body is not None:
        updates["body"] = payload.body.strip()
    if payload.category is not None:
        updates["category"] = payload.category.strip() or None
    if payload.channel is not None:
        updates["channel"] = payload.channel
    if payload.active is not None:
        updates["active"] = bool(payload.active)
    if not updates:
        return {k: v for k, v in tpl.items() if k != "_id"}
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.pitch_templates.update_one({"template_id": template_id}, {"$set": updates})
    fresh = await db.pitch_templates.find_one({"template_id": template_id})
    return {k: v for k, v in fresh.items() if k != "_id"}


@router.delete("/pm/templates/{template_id}")
async def pm_delete_template(
    template_id: str,
    admin: dict = Depends(require_program_manager_or_owner),
):
    """Soft-delete. Hidden from list endpoints; never re-listed even with
    include_archived (use archive via active=false for that)."""
    tpl = await db.pitch_templates.find_one({"template_id": template_id})
    if not tpl:
        raise HTTPException(404, "Template not found")
    now = datetime.now(timezone.utc).isoformat()
    await db.pitch_templates.update_one(
        {"template_id": template_id},
        {"$set": {"deleted_at": now, "active": False}},
    )
    return {"ok": True}


# ---- Coaching notes --------------------------------------------------------
@router.get("/pm/coaching-notes/{va_user_id}")
async def pm_list_coaching_notes(
    va_user_id: str,
    admin: dict = Depends(require_program_manager_or_owner),
):
    """Admin sees ALL notes (shared + private). VA endpoint /va/coaching-notes
    only returns shared."""
    items = []
    cur = db.va_coaching_notes.find({
        "va_user_id": va_user_id,
        "deleted_at": {"$in": [None, ""]},
    }).sort("created_at", -1).limit(500)
    async for n in cur:
        items.append({
            "note_id": n["note_id"],
            "text": n["text"],
            "is_shared": bool(n.get("is_shared")),
            "author_user_id": n.get("author_user_id"),
            "author_name": n.get("author_name"),
            "created_at": n["created_at"],
            "updated_at": n.get("updated_at"),
        })
    return {"items": items}


@router.post("/pm/coaching-notes/{va_user_id}")
async def pm_create_coaching_note(
    va_user_id: str,
    payload: CoachingNoteIn,
    admin: dict = Depends(require_program_manager_or_owner),
):
    va = await db.users.find_one({"user_id": va_user_id, "role": "va"})
    if not va:
        raise HTTPException(404, "VA not found")
    now = datetime.now(timezone.utc).isoformat()
    nid = f"cn_{uuid.uuid4().hex[:12]}"
    doc = {
        "note_id": nid,
        "va_user_id": va_user_id,
        "text": payload.text.strip(),
        "is_shared": bool(payload.is_shared),
        "author_user_id": admin["user_id"],
        "author_name": admin.get("name") or admin.get("email"),
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    await db.va_coaching_notes.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


@router.patch("/pm/coaching-notes/{note_id}")
async def pm_update_coaching_note(
    note_id: str,
    payload: CoachingNotePatch,
    admin: dict = Depends(require_program_manager_or_owner),
):
    note = await db.va_coaching_notes.find_one({"note_id": note_id})
    if not note:
        raise HTTPException(404, "Note not found")
    updates: dict = {}
    if payload.text is not None:
        updates["text"] = payload.text.strip()
    if payload.is_shared is not None:
        updates["is_shared"] = bool(payload.is_shared)
    if not updates:
        return {k: v for k, v in note.items() if k != "_id"}
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.va_coaching_notes.update_one({"note_id": note_id}, {"$set": updates})
    fresh = await db.va_coaching_notes.find_one({"note_id": note_id})
    return {k: v for k, v in fresh.items() if k != "_id"}


@router.delete("/pm/coaching-notes/{note_id}")
async def pm_delete_coaching_note(
    note_id: str,
    admin: dict = Depends(require_program_manager_or_owner),
):
    note = await db.va_coaching_notes.find_one({"note_id": note_id})
    if not note:
        raise HTTPException(404, "Note not found")
    await db.va_coaching_notes.update_one(
        {"note_id": note_id},
        {"$set": {"deleted_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True}


# ---- Per-VA detail (admin) ------------------------------------------------
@router.get("/pm/vas/{va_user_id}/detail")
async def pm_va_detail(
    va_user_id: str,
    admin: dict = Depends(require_program_manager_or_owner),
):
    """Single-page summary for the admin VA detail screen: profile + current
    month goal/progress + paid-count + conversion + active lead count."""
    va = await db.users.find_one({"user_id": va_user_id, "role": "va"})
    if not va:
        raise HTTPException(404, "VA not found")
    not_deleted = {"deleted_at": {"$in": [None, ""]}}

    active_stages = ["new_lead", "contacted", "quoted", "booked", "completed"]
    active_count = await db.va_leads.count_documents({
        "va_user_id": va_user_id, "stage": {"$in": active_stages}, **not_deleted,
    })
    total_lifetime = await db.va_leads.count_documents({"va_user_id": va_user_id, **not_deleted})
    converted = await db.va_leads.count_documents({
        "va_user_id": va_user_id,
        "stage": {"$in": ["booked", "completed", "paid"]},
        **not_deleted,
    })
    conversion = round((converted / total_lifetime) * 100, 1) if total_lifetime > 0 else 0.0

    paid = 0.0
    paid_count = 0
    async for c in db.commissions.find({"va_user_id": va_user_id, "status": "paid"}):
        paid += float(c.get("amount") or 0)
        paid_count += 1

    month = datetime.now(timezone.utc).strftime("%Y-%m")
    goal_doc = await db.va_goals.find_one(
        {"va_user_id": va_user_id, "month": month}, {"_id": 0}
    )
    month_iso = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    mtd_leads = await db.va_leads.count_documents({
        "va_user_id": va_user_id,
        "created_at": {"$gte": month_iso},
        **not_deleted,
    })
    mtd_commission = 0.0
    async for c in db.commissions.find({
        "va_user_id": va_user_id,
        "status": "paid",
        "paid_at": {"$gte": month_iso},
    }):
        mtd_commission += float(c.get("amount") or 0)

    return {
        "va": {
            "user_id": va.get("user_id"),
            "name": va.get("name"),
            "email": va.get("email"),
            "phone": va.get("phone"),
            "va_status": va.get("va_status"),
            "created_at": va.get("created_at"),
        },
        "stats": {
            "active_leads": active_count,
            "total_lifetime_leads": total_lifetime,
            "conversion_rate": conversion,
            "total_paid": round(paid, 2),
            "paid_count": paid_count,
        },
        "month_goal": {
            "month": month,
            "target_leads": (goal_doc or {}).get("target_leads"),
            "target_commission": (goal_doc or {}).get("target_commission"),
            "note": (goal_doc or {}).get("note"),
            "mtd_leads": mtd_leads,
            "mtd_commission": round(mtd_commission, 2),
        },
    }

