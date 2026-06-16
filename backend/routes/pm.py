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

from config import db
from auth_deps import _get_user_by_id, hash_password
from notifications import _send_user_email, _public_base
from va_commission import (
    require_program_manager_or_owner,
    LeadStageIn,
    CommissionActionIn,
    VAAccountAdminIn,
    VAStatusActionIn,
    CommercialAccountIn,
    CommercialAccountPatch,
    _normalize_phone,
    _normalize_email,
    _log_violation,
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
    q: Optional[str] = None,
    admin: dict = Depends(require_program_manager_or_owner),
):
    query: dict = {}
    if va_user_id:
        query["va_user_id"] = va_user_id
    if stage:
        query["stage"] = stage
    if service_type:
        query["service_type"] = service_type
    if q:
        query["$or"] = [
            {"prospect_name": {"$regex": re.escape(q), "$options": "i"}},
            {"prospect_phone_norm": _normalize_phone(q)},
            {"prospect_email_norm": _normalize_email(q)},
        ]
    items = []
    cur = db.va_leads.find(query).sort("created_at", -1).limit(500)
    async for d in cur:
        items.append(_serialize_lead(d))
    return {"items": items}


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
        existing = await db.commissions.find_one({"lead_id": lead_id})
        if existing and existing.get("status") in ("calculating",):
            await db.commissions.update_one(
                {"commission_id": existing["commission_id"]},
                {"$set": {"status": "calculating", "updated_at": now}},
            )
    elif payload.stage == "lost":
        existing = await db.commissions.find_one({"lead_id": lead_id})
        if existing and existing.get("status") in ("calculating", "pending_approval"):
            await db.commissions.update_one(
                {"commission_id": existing["commission_id"]},
                {"$set": {"status": "rejected", "calc_notes": "Lead marked lost", "updated_at": now}},
            )
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
