"""Worker payment tracker — who's been paid after timesheet approval.

Approved timesheets (gig_acceptances.timesheet_approved) show up here as
payables. Marking them paid stamps paid_at/method/reference, notifies the
worker, and auto-logs a 'payroll' expense in bookkeeping (idempotent).
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth_deps import require_admin
from config import db
from routes.bookkeeping import log_worker_payout_expense

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _amount(a: dict) -> float:
    if a.get("earnings") is not None:
        return round(float(a["earnings"]), 2)
    rate = a.get("pay_rate_applied")
    if rate is None:
        return 0.0
    if (a.get("pay_type_applied") or "hourly") == "flat":
        return round(float(rate), 2)
    hours = a.get("paid_hours") if a.get("paid_hours") is not None else a.get("hours_worked")
    return round(float(rate) * float(hours or 0), 2)


class MarkPaidIn(BaseModel):
    acceptance_ids: List[str] = Field(..., min_length=1, max_length=200)
    payout_method: Optional[str] = Field(None, max_length=40)
    payout_reference: Optional[str] = Field(None, max_length=120)


@router.get("/admin/worker-payments")
async def list_worker_payments(
    status: Optional[str] = None,  # unpaid | paid | None=all
    admin: dict = Depends(require_admin),
):
    q: dict = {"timesheet_approved": True}
    if status == "unpaid":
        q["paid_at"] = None
    elif status == "paid":
        q["paid_at"] = {"$ne": None}
    accs = (
        await db.gig_acceptances.find(q, {"_id": 0})
        .sort("timesheet_approved_at", -1)
        .to_list(500)
    )
    gig_ids = list({a["gig_id"] for a in accs if a.get("gig_id")})
    gigs = {
        g["gig_id"]: g
        for g in await db.gigs.find(
            {"gig_id": {"$in": gig_ids}}, {"_id": 0, "gig_id": 1, "title": 1, "date": 1}
        ).to_list(len(gig_ids) or 1)
    }
    items = []
    unpaid_total = 0.0
    paid_total = 0.0
    workers_owed = set()
    for a in accs:
        g = gigs.get(a.get("gig_id"), {})
        amt = _amount(a)
        paid = bool(a.get("paid_at"))
        if paid:
            paid_total += amt
        else:
            unpaid_total += amt
            workers_owed.add(a.get("worker_id"))
        items.append({
            "acceptance_id": a["acceptance_id"],
            "gig_id": a.get("gig_id"),
            "gig_title": g.get("title") or "—",
            "gig_date": g.get("date"),
            "worker_id": a.get("worker_id"),
            "worker_name": a.get("worker_name") or "Worker",
            "hours_worked": a.get("hours_worked"),
            "paid_hours": a.get("paid_hours"),
            "amount": amt,
            "timesheet_approved_at": a.get("timesheet_approved_at"),
            "paid_at": a.get("paid_at"),
            "paid_by": a.get("paid_by"),
            "payout_method": a.get("payout_method"),
            "payout_reference": a.get("payout_reference"),
        })
    return {
        "items": items,
        "summary": {
            "unpaid_total": round(unpaid_total, 2),
            "unpaid_count": sum(1 for i in items if not i["paid_at"]),
            "paid_total": round(paid_total, 2),
            "workers_owed": len(workers_owed),
        },
    }


@router.post("/admin/worker-payments/mark-paid")
async def mark_worker_payments_paid(
    payload: MarkPaidIn, admin: dict = Depends(require_admin)
):
    now = _now_iso()
    paid, skipped = [], []
    for acceptance_id in payload.acceptance_ids:
        a = await db.gig_acceptances.find_one({"acceptance_id": acceptance_id})
        if not a or not a.get("timesheet_approved"):
            skipped.append({"acceptance_id": acceptance_id, "reason": "not approved"})
            continue
        if a.get("paid_at"):
            skipped.append({"acceptance_id": acceptance_id, "reason": "already paid"})
            continue
        await db.gig_acceptances.update_one(
            {"acceptance_id": acceptance_id},
            {"$set": {
                "paid_at": now,
                "paid_by": admin.get("email") or admin["user_id"],
                "payout_method": (payload.payout_method or "").strip() or None,
                "payout_reference": (payload.payout_reference or "").strip() or None,
            }},
        )
        fresh = await db.gig_acceptances.find_one({"acceptance_id": acceptance_id})
        gig = await db.gigs.find_one({"gig_id": a.get("gig_id")}, {"_id": 0, "title": 1})
        amt = _amount(fresh)
        await log_worker_payout_expense(fresh, (gig or {}).get("title") or "gig", amt)
        await db.notifications.insert_one({
            "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
            "user_id": a["worker_id"],
            "gig_id": a.get("gig_id"),
            "title": f"You've been paid: ${amt:,.2f}",
            "body": f"Payment sent for {(gig or {}).get('title') or 'your shift'}"
            + (f" via {payload.payout_method}" if payload.payout_method else "")
            + ".",
            "read": False,
            "created_at": now,
        })
        paid.append({"acceptance_id": acceptance_id, "amount": amt})
    return {"ok": True, "paid": paid, "skipped": skipped}
