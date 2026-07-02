"""VA portal routes (`/api/va/*`) — self-service dashboard, lead submission,
earnings, and commercial account list. Lead+commission lifecycle helpers live
in `va_commission.py`.

Wiring in server.py:
    from routes.va import router as va_router
    api.include_router(va_router)
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from config import db
from auth_deps import _get_user_by_id
from va_commission import (
    DIGITAL_SERVICE_TYPES,
    _get_digital_commission_pct,
    LeadFollowupIn,
    LeadContactIn,
    LeadCommentIn,
    apply_lead_followup,
    apply_lead_contact,
    apply_lead_comment,
    require_va,
    require_va_active,
    VARegisterDetailsIn,
    LeadIn,
    LeadEditIn,
    LeadDeleteIn,
    CoachingNoteIn,
    STALE_LEAD_DAYS,
    STALE_LEAD_STAGES,
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
    """Single-call dashboard payload. Internally fans out the independent
    aggregate queries with asyncio.gather() so total latency ≈ slowest single
    query, not sum of all of them. Commission cursors aren't parallelized
    inside (they share the same cursor pattern) — see comments below."""
    va_id = user["user_id"]
    now = datetime.now(timezone.utc)
    active_stages = ["new_lead", "contacted", "quoted", "booked", "completed"]
    not_deleted = {"deleted_at": {"$in": [None, ""]}}
    cutoff_30 = (now - timedelta(days=30)).isoformat()
    stale_cutoff = (now - timedelta(days=STALE_LEAD_DAYS)).isoformat()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_iso = month_start.isoformat()
    month = now.strftime("%Y-%m")

    # ---- Helpers run in parallel -------------------------------------------
    async def _active_count():
        return await db.va_leads.count_documents(
            {"va_user_id": va_id, "stage": {"$in": active_stages}, **not_deleted}
        )

    async def _commission_totals():
        pending = approved = paid = 0.0
        paid_count = 0
        async for c in db.commissions.find({"va_user_id": va_id}):
            amt = float(c.get("amount") or 0)
            s = c.get("status")
            if s in ("calculating", "pending_approval", "pm_approved"):
                pending += amt
            elif s == "owner_approved":
                approved += amt
            elif s == "paid":
                paid += amt
                paid_count += 1
        return pending, approved, paid, paid_count

    async def _leaderboard_rank():
        pipeline = [
            {"$match": {"created_at": {"$gte": cutoff_30}, **not_deleted}},
            {"$group": {"_id": "$va_user_id", "leads": {"$sum": 1}}},
            {"$sort": {"leads": -1}},
        ]
        ranks = []
        async for row in db.va_leads.aggregate(pipeline):
            ranks.append(row["_id"])
        return ranks

    async def _lifetime_counts():
        total = await db.va_leads.count_documents({"va_user_id": va_id, **not_deleted})
        converted = await db.va_leads.count_documents({
            "va_user_id": va_id,
            "stage": {"$in": ["booked", "completed", "paid"]},
            **not_deleted,
        })
        return total, converted

    async def _stale_count():
        return await db.va_leads.count_documents({
            "va_user_id": va_id,
            "stage": {"$in": list(STALE_LEAD_STAGES)},
            "updated_at": {"$lt": stale_cutoff},
            **not_deleted,
        })

    async def _goal_and_mtd():
        goal_doc = await db.va_goals.find_one(
            {"va_user_id": va_id, "month": month}, {"_id": 0}
        )
        mtd_leads = await db.va_leads.count_documents({
            "va_user_id": va_id,
            "created_at": {"$gte": month_iso},
            **not_deleted,
        })
        mtd_commission = 0.0
        async for c in db.commissions.find({
            "va_user_id": va_id,
            "status": "paid",
            "paid_at": {"$gte": month_iso},
        }):
            mtd_commission += float(c.get("amount") or 0)
        return goal_doc, mtd_leads, mtd_commission

    async def _shared_notes():
        notes = []
        cur = db.va_coaching_notes.find(
            {"va_user_id": va_id, "is_shared": True, "deleted_at": {"$in": [None, ""]}}
        ).sort("created_at", -1).limit(5)
        async for n in cur:
            notes.append({
                "note_id": n["note_id"],
                "text": n["text"],
                "author_name": n.get("author_name"),
                "created_at": n["created_at"],
            })
        return notes

    (
        active_count,
        commission_tuple,
        ranks,
        lifetime_tuple,
        stale_count,
        goal_tuple,
        notes,
    ) = await asyncio.gather(
        _active_count(),
        _commission_totals(),
        _leaderboard_rank(),
        _lifetime_counts(),
        _stale_count(),
        _goal_and_mtd(),
        _shared_notes(),
    )

    pending, approved, paid, paid_count = commission_tuple
    total_lifetime, converted = lifetime_tuple
    goal_doc, mtd_leads, mtd_commission = goal_tuple

    rank = (ranks.index(va_id) + 1) if va_id in ranks else None
    conversion = round((converted / total_lifetime) * 100, 1) if total_lifetime > 0 else 0.0

    # ---- Tier ladder ------------------------------------------------------
    # Five tiers based on MONTHLY commission earnings. These are the same
    # for every VA — easy to grasp at a glance ("I made it to Star this
    # month"). Admin-editable rungs is P3 — for now they're hardcoded so
    # the feature ships without a settings page.
    TIER_LADDER = [
        {"key": "hustler", "label": "Hustler",   "min": 0,     "next_min": 500},
        {"key": "pro",     "label": "Pro",       "min": 500,   "next_min": 1500},
        {"key": "star",    "label": "Star",      "min": 1500,  "next_min": 3000},
        {"key": "elite",   "label": "Elite",     "min": 3000,  "next_min": 6000},
        {"key": "legend",  "label": "Legend",    "min": 6000,  "next_min": None},
    ]
    mtd_amount = round(mtd_commission, 2)
    current_tier = TIER_LADDER[0]
    for t in TIER_LADDER:
        if mtd_amount >= t["min"]:
            current_tier = t
        else:
            break
    next_tier = None
    progress_pct = 100  # legend caps out
    needed_to_next = 0
    if current_tier["next_min"] is not None:
        next_tier = next(
            (t for t in TIER_LADDER if t["min"] == current_tier["next_min"]),
            None,
        )
        span = current_tier["next_min"] - current_tier["min"]
        progress = mtd_amount - current_tier["min"]
        progress_pct = max(0, min(100, round((progress / span) * 100, 1))) if span > 0 else 100
        needed_to_next = max(0.0, round(current_tier["next_min"] - mtd_amount, 2))

    tier_payload = {
        "current": {"key": current_tier["key"], "label": current_tier["label"]},
        "next": (
            {"key": next_tier["key"], "label": next_tier["label"], "at_amount": current_tier["next_min"]}
            if next_tier
            else None
        ),
        "progress_pct": progress_pct,
        "amount_needed_to_next": needed_to_next,
        "ladder": [
            {"key": t["key"], "label": t["label"], "min": t["min"]} for t in TIER_LADDER
        ],
    }

    goal_payload = None
    if goal_doc:
        goal_payload = {
            "month": goal_doc["month"],
            "target_leads": goal_doc.get("target_leads"),
            "target_commission": goal_doc.get("target_commission"),
            "note": goal_doc.get("note"),
            "mtd_leads": mtd_leads,
            "mtd_commission": round(mtd_commission, 2),
        }

    return {
        "va_user_id": va_id,
        "va_status": user.get("va_status"),
        "active_leads": active_count,
        "commissions_pending": round(pending, 2),
        "commissions_approved": round(approved, 2),
        "total_paid": round(paid, 2),
        "paid_count": paid_count,
        "mtd_commission": mtd_amount,
        "tier": tier_payload,
        "conversion_rate": conversion,
        "stale_leads_count": stale_count,
        "leaderboard_rank": rank,
        "leaderboard_total": len(ranks),
        "goal": goal_payload,
        "shared_notes": notes,
    }


@router.get("/va/stale-leads")
async def va_stale_leads(user: dict = Depends(require_va)):
    """Leads in contacted/quoted stages that haven't been updated in 7+ days.
    Surfaced as a 'needs follow-up' nudge on the VA dashboard."""
    va_id = user["user_id"]
    cutoff = (datetime.now(timezone.utc) - timedelta(days=STALE_LEAD_DAYS)).isoformat()
    items = []
    cur = db.va_leads.find({
        "va_user_id": va_id,
        "stage": {"$in": list(STALE_LEAD_STAGES)},
        "updated_at": {"$lt": cutoff},
        "deleted_at": {"$in": [None, ""]},
    }).sort("updated_at", 1).limit(50)
    async for d in cur:
        items.append(_serialize_lead(d))
    return {"items": items, "threshold_days": STALE_LEAD_DAYS}


@router.get("/va/leaderboard")
async def va_leaderboard(
    period: Optional[str] = "month",
    user: dict = Depends(require_va),
):
    """Ranked list of VAs by activity. period: 'month' (default) | 'week' | 'all'.
    Earnings are masked for everyone except the requesting VA's own row."""
    va_id = user["user_id"]
    now = datetime.now(timezone.utc)
    if period == "week":
        cutoff = (now - timedelta(days=7)).isoformat()
    elif period == "all":
        cutoff = "1970-01-01T00:00:00+00:00"
    else:
        cutoff = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

    # Aggregate leads per VA
    pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}, "deleted_at": {"$in": [None, ""]}}},
        {"$group": {
            "_id": "$va_user_id",
            "leads": {"$sum": 1},
            "booked": {"$sum": {"$cond": [{"$in": ["$stage", ["booked", "completed", "paid"]]}, 1, 0]}},
        }},
        {"$sort": {"leads": -1, "booked": -1}},
        {"$limit": 50},
    ]
    rows: list = []
    async for r in db.va_leads.aggregate(pipeline):
        rows.append(r)
    # Resolve VA names
    va_ids = [r["_id"] for r in rows if r["_id"]]
    name_map: dict = {}
    async for u in db.users.find(
        {"user_id": {"$in": va_ids}}, {"_id": 0, "user_id": 1, "name": 1}
    ):
        name_map[u["user_id"]] = u.get("name")

    items = []
    for idx, r in enumerate(rows):
        is_self = r["_id"] == va_id
        items.append({
            "rank": idx + 1,
            "va_user_id": r["_id"],
            "va_name": name_map.get(r["_id"]) or "—",
            "leads": r["leads"],
            "booked": r["booked"],
            "conversion": round((r["booked"] / r["leads"]) * 100, 1) if r["leads"] else 0,
            "is_self": is_self,
        })
    return {"items": items, "period": period}


@router.get("/va/templates")
async def va_list_templates(user: dict = Depends(require_va)):
    """Read-only pitch templates library for VAs."""
    items = []
    cur = db.pitch_templates.find(
        {"active": True, "deleted_at": {"$in": [None, ""]}}
    ).sort("created_at", -1).limit(200)
    async for t in cur:
        items.append({
            "template_id": t["template_id"],
            "title": t["title"],
            "body": t["body"],
            "category": t.get("category"),
            "channel": t.get("channel") or "any",
        })
    return {"items": items}


@router.get("/va/coaching-notes")
async def va_list_coaching_notes(user: dict = Depends(require_va)):
    """VAs only see notes their PM explicitly shared with them."""
    va_id = user["user_id"]
    items = []
    cur = db.va_coaching_notes.find({
        "va_user_id": va_id,
        "is_shared": True,
        "deleted_at": {"$in": [None, ""]},
    }).sort("created_at", -1).limit(200)
    async for n in cur:
        items.append({
            "note_id": n["note_id"],
            "text": n["text"],
            "author_name": n.get("author_name"),
            "created_at": n["created_at"],
        })
    return {"items": items}


@router.get("/va/goals")
async def va_get_goals(
    months: Optional[int] = 6,
    user: dict = Depends(require_va),
):
    """Last N months of goals (default 6) so VA can see trend / past targets."""
    va_id = user["user_id"]
    items = []
    cur = db.va_goals.find({"va_user_id": va_id}).sort("month", -1).limit(max(1, int(months or 6)))
    async for g in cur:
        items.append({
            "month": g["month"],
            "target_leads": g.get("target_leads"),
            "target_commission": g.get("target_commission"),
            "note": g.get("note"),
        })
    return {"items": items}


@router.post("/va/leads")
async def va_create_lead(payload: LeadIn, request: Request, user: dict = Depends(require_va_active)):
    phone_norm = _normalize_phone(payload.prospect_phone)
    email_norm = _normalize_email(payload.prospect_email)
    if not phone_norm and not email_norm:
        raise HTTPException(400, "Phone or email required")
    addr_norm = _normalize_address(payload.prospect_address)

    is_digital = payload.service_type in DIGITAL_SERVICE_TYPES
    if not is_digital and not payload.property_size:
        raise HTTPException(400, "Property size is required for this service type")

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
        "estimated_budget": payload.estimated_budget,
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
async def va_list_leads(stage: Optional[str] = None, user: dict = Depends(require_va_active)):
    q: dict = {"va_user_id": user["user_id"], "deleted_at": {"$in": [None, ""]}}
    if stage:
        q["stage"] = stage
    items = []
    cur = db.va_leads.find(q).sort("created_at", -1)
    async for d in cur:
        items.append(_serialize_lead(d))
    return {"items": items}


@router.get("/va/leads/{lead_id}")
async def va_get_lead(lead_id: str, user: dict = Depends(require_va_active)):
    """VAs see their own lead detail (or one assigned to them for delivery)."""
    lead = await db.va_leads.find_one({
        "lead_id": lead_id,
        "$or": [{"va_user_id": user["user_id"]}, {"assigned_va_id": user["user_id"]}],
    })
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
    if payload.estimated_budget is not None:
        _add("estimated_budget", float(payload.estimated_budget))

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


# Stages a VA can move their own lead through. Hard stages (booked,
# completed, paid, lost) require admin verification because commissions
# attach when a lead is marked "booked" — VAs can't be allowed to
# self-mark their own leads as booked or we lose commission integrity.
VA_PIPELINE_STAGES = ("new_lead", "contacted", "quoted")


@router.patch("/va/leads/{lead_id}/notes")
async def va_update_lead_notes(
    lead_id: str,
    payload: dict = Body(...),
    user: dict = Depends(require_va_active),
):
    """Append (or replace) the VA's notes on their own lead. Works at any
    stage — even after the lead has moved past 'new_lead' — because the
    notes field is opaque to commissions and doesn't affect lead routing.

    Body shape:
      {"notes": "...new full notes string..."}
    """
    new_notes = (payload or {}).get("notes")
    if new_notes is None:
        raise HTTPException(400, "notes (string) required")
    new_notes = str(new_notes).strip()
    if len(new_notes) > 4000:
        raise HTTPException(400, "notes must be 4000 characters or fewer")
    lead = await db.va_leads.find_one({"lead_id": lead_id, "va_user_id": user["user_id"]})
    if not lead:
        raise HTTPException(404, "Lead not found")
    if lead.get("deleted_at"):
        raise HTTPException(400, "Lead is deleted")
    now = datetime.now(timezone.utc).isoformat()
    await db.va_leads.update_one(
        {"lead_id": lead_id},
        {"$set": {"notes": new_notes, "updated_at": now}},
    )
    await _log_lead_activity(
        lead_id=lead_id,
        kind="notes_updated",
        actor=user,
        detail={"length": len(new_notes)},
    )
    fresh = await db.va_leads.find_one({"lead_id": lead_id})
    return _serialize_lead(fresh)


@router.patch("/va/leads/{lead_id}/stage")
async def va_move_lead_stage(
    lead_id: str,
    payload: dict = Body(...),
    user: dict = Depends(require_va_active),
):
    """VA-driven stage move within the soft pipeline (new → contacted → quoted).
    For hard outcomes (booked / completed / lost) the admin/PM has to flip
    the stage so commissions can be audited."""
    new_stage = (payload or {}).get("stage", "").strip().lower()
    if new_stage not in VA_PIPELINE_STAGES:
        raise HTTPException(
            400,
            f"VAs can only move leads between {', '.join(VA_PIPELINE_STAGES)}. "
            "Bookings, closes, and losses are set by your Program Manager.",
        )
    lead = await db.va_leads.find_one({"lead_id": lead_id, "va_user_id": user["user_id"]})
    if not lead:
        raise HTTPException(404, "Lead not found")
    if lead.get("deleted_at"):
        raise HTTPException(400, "Lead is deleted")
    current = lead.get("stage") or "new_lead"
    # Once admin has flipped it past quoted, the VA can't drag it back.
    if current not in VA_PIPELINE_STAGES:
        raise HTTPException(
            403,
            "This lead is in an admin-controlled stage. Ask your Program Manager to move it.",
        )
    if current == new_stage:
        return _serialize_lead(lead)
    now = datetime.now(timezone.utc).isoformat()
    await db.va_leads.update_one(
        {"lead_id": lead_id},
        {
            "$set": {
                "stage": new_stage,
                "stage_changed_at": now,
                "updated_at": now,
            },
            "$push": {
                "stage_history": {"stage": new_stage, "at": now, "by": user["user_id"]},
            },
        },
    )
    await _log_lead_activity(
        lead_id=lead_id,
        kind="stage_moved",
        actor=user,
        detail={"from": current, "to": new_stage},
    )
    fresh = await db.va_leads.find_one({"lead_id": lead_id})
    return _serialize_lead(fresh)


# SLA (response-time) windows in hours — how long a lead can sit in each
# pipeline stage before it's flagged "hot" (80%) then "stale" (100%).
# Tuned to HCOB's actual workflow:
#   - new_lead (24h): VA must do first outreach within 24 hours
#   - contacted (48h): VA stays in convo to gather the brief for Ops
#   - quoted = "Sent to Ops" (120h / 5 days): VA hands the lead to Ops
#     for the actual quote. SLA here is "the prospect is going cold while
#     Ops drafts the quote — nudge them, keep it warm". 5 days gives Ops
#     room to quote without the timer screaming.
VA_LEAD_SLA_HOURS = {
    "new_lead": 24,
    "contacted": 48,
    "quoted": 120,
}


def _lead_sla_status(lead: dict) -> dict:
    """Compute SLA state for a lead card based on stage + stage_changed_at.

    Returns:
      - hours_in_stage:   float | None
      - sla_hours:        int | None      (None when stage has no SLA, e.g. booked)
      - sla_state:        "ok" | "hot" (>=80%) | "stale" (>=100%) | None
      - sla_due_at_iso:   ISO string for the deadline (UI countdown)
    """
    stage = (lead.get("stage") or "").lower()
    sla = VA_LEAD_SLA_HOURS.get(stage)
    if not sla:
        return {"hours_in_stage": None, "sla_hours": None, "sla_state": None, "sla_due_at_iso": None}
    anchor = lead.get("stage_changed_at") or lead.get("created_at")
    if not anchor:
        return {"hours_in_stage": None, "sla_hours": sla, "sla_state": None, "sla_due_at_iso": None}
    try:
        anchor_dt = datetime.fromisoformat(str(anchor).replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return {"hours_in_stage": None, "sla_hours": sla, "sla_state": None, "sla_due_at_iso": None}
    now = datetime.now(timezone.utc)
    hours = max(0.0, (now - anchor_dt).total_seconds() / 3600.0)
    pct = hours / sla
    state = "stale" if pct >= 1.0 else ("hot" if pct >= 0.8 else "ok")
    due = (anchor_dt + timedelta(hours=sla)).isoformat()
    return {
        "hours_in_stage": round(hours, 1),
        "sla_hours": sla,
        "sla_state": state,
        "sla_due_at_iso": due,
    }


@router.get("/va/pipeline")
async def va_pipeline_board(user: dict = Depends(require_va_active)):
    """Kanban board payload — every non-deleted lead the VA owns, decorated
    with SLA timing. Frontend groups by `stage` into columns. Cheap to call
    on focus/refresh; UI polls every 30s for SLA tick."""
    not_deleted = {"deleted_at": {"$in": [None, ""]}}
    cur = db.va_leads.find({"va_user_id": user["user_id"], **not_deleted}).sort("stage_changed_at", -1)
    items: list[dict] = []
    async for lead in cur:
        card = _serialize_lead(lead)
        card.update(_lead_sla_status(lead))
        items.append(card)
    return {
        "items": items,
        "stages_va_can_move": list(VA_PIPELINE_STAGES),
        "sla_hours": VA_LEAD_SLA_HOURS,
    }


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
    user: dict = Depends(require_va_active),
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
async def va_my_commercial_accounts(user: dict = Depends(require_va_active)):
    items = []
    cur = db.commercial_accounts.find({"va_user_id": user["user_id"]}).sort("created_at", -1)
    async for d in cur:
        items.append({k: v for k, v in d.items() if k != "_id"})
    return {"items": items}


@router.get("/va/digital-settings")
async def va_digital_settings(user: dict = Depends(require_va)):
    """Current digital-services commission rate + accepted service types."""
    return {
        "commission_pct": await _get_digital_commission_pct(),
        "service_types": sorted(DIGITAL_SERVICE_TYPES),
    }


@router.get("/va/projects")
async def va_delivery_projects(user: dict = Depends(require_va_active)):
    """Digital leads assigned to this VA for delivery."""
    items = []
    cur = db.va_leads.find({
        "assigned_va_id": user["user_id"],
        "deleted_at": {"$in": [None, ""]},
    }).sort("stage_changed_at", -1)
    async for d in cur:
        items.append(_serialize_lead(d))
    return {"items": items, "commission_pct": await _get_digital_commission_pct()}


# ---------------------------------------------------------------------------
# CRM: follow-ups / contact log / comments (VA side — owner or delivery VA)
# ---------------------------------------------------------------------------
async def _va_crm_lead_or_404(lead_id: str, user: dict) -> dict:
    lead = await db.va_leads.find_one({
        "lead_id": lead_id,
        "$or": [{"va_user_id": user["user_id"]}, {"assigned_va_id": user["user_id"]}],
    })
    if not lead or lead.get("deleted_at"):
        raise HTTPException(404, "Lead not found")
    return lead


@router.post("/va/leads/{lead_id}/followup")
async def va_set_followup(lead_id: str, payload: LeadFollowupIn, user: dict = Depends(require_va_active)):
    lead = await _va_crm_lead_or_404(lead_id, user)
    fresh = await apply_lead_followup(lead, payload, user)
    return _serialize_lead(fresh)


@router.post("/va/leads/{lead_id}/contacts")
async def va_log_contact(lead_id: str, payload: LeadContactIn, user: dict = Depends(require_va_active)):
    lead = await _va_crm_lead_or_404(lead_id, user)
    fresh = await apply_lead_contact(lead, payload, user)
    return _serialize_lead(fresh)


@router.post("/va/leads/{lead_id}/comments")
async def va_post_comment(lead_id: str, payload: LeadCommentIn, user: dict = Depends(require_va_active)):
    lead = await _va_crm_lead_or_404(lead_id, user)
    fresh = await apply_lead_comment(lead, payload, user)
    return _serialize_lead(fresh)
