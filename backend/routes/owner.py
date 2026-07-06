"""Owner routes (`/api/owner/*`) — payout queue, sign-off, bulk approve,
mark paid. The Owner is the only role that can convert `pm_approved`
commissions to `owner_approved` / `paid`. Hard guard against double-pay.

Wiring in server.py:
    from routes.owner import router as owner_router
    api.include_router(owner_router)
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException

from config import db
from notifications import _send_user_email, _public_base
from routes.bookkeeping import log_commission_payroll_expense
from va_commission import (
    require_owner,
    OwnerBulkApproveIn,
    CommissionMarkPaidIn,
    _serialize_commission,
)

router = APIRouter()


@router.get("/owner/dashboard")
async def owner_dashboard(admin: dict = Depends(require_owner)):
    # Payout queue size + amount
    queue_count = 0
    queue_amount = 0.0
    async for c in db.commissions.find({"status": "pm_approved"}):
        queue_count += 1
        queue_amount += float(c.get("amount") or 0)
    # This month
    month_str = datetime.now(timezone.utc).strftime("%Y-%m")
    month_total = 0.0
    async for c in db.commissions.find({"created_at": {"$regex": f"^{month_str}"}}):
        if c.get("status") not in ("rejected",):
            month_total += float(c.get("amount") or 0)
    # Active commercial revenue
    active_commercial = await db.commercial_accounts.count_documents({"active": True})
    commercial_monthly = 0.0
    async for a in db.commercial_accounts.find({"active": True}):
        commercial_monthly += float(a.get("monthly_revenue") or 0)
    # Top VA performers — last 30 days
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    pipe = [
        {"$match": {"created_at": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$va_user_id",
            "leads": {"$sum": 1},
            "va_name": {"$first": "$va_name"},
            "booked": {"$sum": {"$cond": [{"$in": ["$stage", ["booked", "completed", "paid"]]}, 1, 0]}},
        }},
    ]
    rows = []
    async for r in db.va_leads.aggregate(pipe):
        leads = r["leads"]
        booked = r["booked"]
        rows.append({
            "va_user_id": r["_id"],
            "va_name": r["va_name"],
            "leads": leads,
            "booked": booked,
            "conversion": round((booked / leads) * 100, 1) if leads else 0,
        })
    top_by_volume = sorted(rows, key=lambda x: x["leads"], reverse=True)[:3]
    top_by_conversion = sorted(rows, key=lambda x: x["conversion"], reverse=True)[:3]
    # Alert feed — recent violations + flagged commissions
    alerts = []
    async for v in db.va_violations.find().sort("created_at", -1).limit(10):
        alerts.append({"type": "violation", **{k: val for k, val in v.items() if k != "_id"}})
    async for c in db.commissions.find({"status": "flagged"}).sort("pm_action_at", -1).limit(10):
        alerts.append({"type": "flagged_commission", **_serialize_commission(c)})
    alerts.sort(key=lambda a: a.get("created_at") or a.get("pm_action_at") or "", reverse=True)
    return {
        "payout_queue_count": queue_count,
        "payout_queue_amount": round(queue_amount, 2),
        "month_total_commissions": round(month_total, 2),
        "active_commercial_accounts": active_commercial,
        "commercial_monthly_revenue_total": round(commercial_monthly, 2),
        "top_by_volume": top_by_volume,
        "top_by_conversion": top_by_conversion,
        "alerts": alerts[:20],
    }


@router.get("/owner/payouts/queue")
async def owner_payout_queue(admin: dict = Depends(require_owner)):
    items = []
    cur = db.commissions.find({"status": "pm_approved"}).sort("pm_action_at", 1)
    async for c in cur:
        items.append(_serialize_commission(c))
    # Also group by VA for the bulk-approve UI
    groups: Dict[str, dict] = {}
    for c in items:
        va_id = c.get("va_user_id")
        if va_id not in groups:
            groups[va_id] = {
                "va_user_id": va_id,
                "va_name": c.get("va_name"),
                "items": [],
                "total": 0.0,
            }
        groups[va_id]["items"].append(c)
        groups[va_id]["total"] += float(c.get("amount") or 0)
    grouped = list(groups.values())
    for g in grouped:
        g["total"] = round(g["total"], 2)
    return {"items": items, "by_va": grouped}


@router.post("/owner/payouts/{commission_id}/approve")
async def owner_approve_payout(
    commission_id: str,
    admin: dict = Depends(require_owner),
):
    c = await db.commissions.find_one({"commission_id": commission_id})
    if not c:
        raise HTTPException(404, "Commission not found")
    if c["status"] != "pm_approved":
        raise HTTPException(400, f"Cannot sign off — current status is {c['status']}. Must be pm_approved.")
    now = datetime.now(timezone.utc).isoformat()
    await db.commissions.update_one(
        {"commission_id": commission_id},
        {"$set": {
            "status": "owner_approved",
            "owner_action_at": now,
            "owner_action_by": admin["user_id"],
            "updated_at": now,
        }},
    )
    return _serialize_commission(await db.commissions.find_one({"commission_id": commission_id}))


@router.post("/owner/payouts/bulk-approve")
async def owner_bulk_approve(
    payload: OwnerBulkApproveIn,
    admin: dict = Depends(require_owner),
):
    """One-click sign-off on all PM-approved commissions for a VA within a date window.
    Default window: current ISO week (Mon..Sun UTC)."""
    today = datetime.now(timezone.utc).date()
    default_start = today - timedelta(days=today.weekday())
    default_end = default_start + timedelta(days=6)
    week_start = payload.week_start or default_start.isoformat()
    week_end = (payload.week_end or default_end.isoformat()) + "T23:59:59"
    start_iso = week_start + ("T00:00:00" if "T" not in week_start else "")
    q = {
        "va_user_id": payload.va_user_id,
        "status": "pm_approved",
        "pm_action_at": {"$gte": start_iso, "$lte": week_end},
    }
    now = datetime.now(timezone.utc).isoformat()
    ids = []
    total = 0.0
    async for c in db.commissions.find(q):
        ids.append(c["commission_id"])
        total += float(c.get("amount") or 0)
    if not ids:
        return {"ok": True, "approved_count": 0, "total": 0.0}
    await db.commissions.update_many(
        {"commission_id": {"$in": ids}},
        {"$set": {
            "status": "owner_approved",
            "owner_action_at": now,
            "owner_action_by": admin["user_id"],
            "owner_bulk_approved": True,
            "updated_at": now,
        }},
    )
    return {"ok": True, "approved_count": len(ids), "total": round(total, 2),
            "commission_ids": ids, "week_start": week_start, "week_end": week_end[:10]}


@router.post("/owner/payouts/{commission_id}/mark-paid")
async def owner_mark_paid(
    commission_id: str,
    payload: CommissionMarkPaidIn,
    admin: dict = Depends(require_owner),
):
    c = await db.commissions.find_one({"commission_id": commission_id})
    if not c:
        raise HTTPException(404, "Commission not found")
    if c["status"] == "paid":
        # Hard guard — double-payment prevention
        raise HTTPException(400, "Commission already marked Paid — double-payment prevented")
    if c["status"] != "owner_approved":
        raise HTTPException(400, f"Cannot mark paid — current status is {c['status']}. Must be owner_approved first.")
    now = datetime.now(timezone.utc).isoformat()
    await db.commissions.update_one(
        {"commission_id": commission_id},
        {"$set": {
            "status": "paid",
            "paid_at": now,
            "payout_reference": payload.payout_reference,
            "payout_method": payload.payout_method,
            "updated_at": now,
        }},
    )
    fresh = await db.commissions.find_one({"commission_id": commission_id})
    # Auto-log this payout as a 'payroll' expense in the bookkeeping ledger.
    await log_commission_payroll_expense(fresh)
    # Notify VA
    await db.notifications.insert_one({
        "notification_id": f"notif_{uuid.uuid4().hex[:10]}",
        "user_id": c["va_user_id"],
        "kind": "va_commission_paid",
        "title": "Commission paid",
        "body": f"${c.get('amount', 0):.2f} has been paid for your lead.",
        "created_at": now,
        "read": False,
    })
    va_user = await db.users.find_one({"user_id": c["va_user_id"]})
    if va_user:
        await _send_user_email(
            va_user, kind="va_commission_paid",
            subject=f"Commission paid — ${c.get('amount', 0):.2f}",
            body_html=(
                f"<p><strong>You've been paid!</strong> Your commission for "
                f"<strong>{c.get('prospect_name')}</strong> is in.</p>"
                f"<p><strong>Amount:</strong> ${c.get('amount', 0):.2f}<br/>"
                f"<strong>Method:</strong> {payload.payout_method or 'N/A'}<br/>"
                f"<strong>Reference:</strong> {payload.payout_reference or 'N/A'}</p>"
                f"<p>Keep submitting leads — your earnings dashboard always shows the live total.</p>"
            ),
            cta_label="Open earnings dashboard",
            cta_url=f"{_public_base()}/va/earnings",
        )
    return _serialize_commission(await db.commissions.find_one({"commission_id": commission_id}))
