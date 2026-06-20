"""HCOB Network — Contractor Referral Program.

Workers refer leads they spot in the wild (carpet cleaning, junk hauling,
painting, etc.) — anywhere, anytime. Mechie/Admin vets, quotes, assigns,
and once the invoice is marked paid the system credits the referring
contractor a 10% commission (admin-configurable rate).

Status lifecycle (`status` field):
    submitted → under_review → quoted → scheduled → in_progress
              → completed → invoiced → paid → commission_released
    (or → void at any point)

Commission status (`commission_status`):
    pending  — quoted but not yet paid
    eligible — invoice marked paid, owed to the worker
    paid     — actually disbursed on the next payout cycle
    void     — never matures (self-fulfilled, void, etc.)

Scope notes (per Cory's spec, deviating from the FRD):
  - source_job is OPTIONAL — workers can refer from anywhere, not just an
    active assignment site. Submission is first-class, always-available.
  - No 24h-window enforcement, no source-job validation.
  - Self-fulfillment: worker declares intent upfront ("for myself" vs
    "for someone else"). We ALSO auto-flip to self_fulfilled if the
    assigned worker == referring worker, even if intent was "another".
"""
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from auth_deps import get_current_user, require_admin
from config import db, logger

router = APIRouter()

# ----- Constants -----------------------------------------------------------
DEFAULT_COMMISSION_RATE = 0.10  # 10% — admin can override via Settings

WORKER_INTENTS = ("for_another", "for_self")

STATUS_FLOW = (
    "submitted",
    "under_review",
    "quoted",
    "scheduled",
    "in_progress",
    "completed",
    "invoiced",
    "paid",
    "commission_released",
)
TERMINAL_STATUSES = ("void", "self_fulfilled", "commission_released")

ALL_STATUSES = STATUS_FLOW + ("void", "self_fulfilled")

# Categories shown in the submit form. Easy to extend; kept narrow on
# purpose so Mechie isn't drowning in noise from day one.
SERVICE_CATEGORIES = [
    "carpet_cleaning",
    "junk_removal",
    "painting",
    "handyman",
    "landscaping",
    "moving",
    "window_cleaning",
    "pressure_washing",
    "pest_control",
    "appliance_repair",
    "commercial_account",  # Multi-service, recurring — high-value tag
    "other",
]


# ----- Helpers -------------------------------------------------------------
async def _commission_rate() -> float:
    """Pull rate from app_settings; fall back to default."""
    doc = await db.app_settings.find_one({"_id": "referral_program"})
    if doc and isinstance(doc.get("commission_rate"), (int, float)):
        return float(doc["commission_rate"])
    return DEFAULT_COMMISSION_RATE


def _serialize(r: dict) -> dict:
    out = {k: v for k, v in (r or {}).items() if k != "_id"}
    return out


def _calc_commission(quoted_amount: Optional[float], rate: float) -> float:
    if not quoted_amount or quoted_amount <= 0:
        return 0.0
    # Round to nearest dollar per FRD §6
    return round(quoted_amount * rate)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ----- Pydantic ------------------------------------------------------------
class SubmitReferralIn(BaseModel):
    property_address: str = Field(..., min_length=4, max_length=300)
    opportunity_description: str = Field(..., min_length=4, max_length=2000)
    service_category: str = Field(..., min_length=2, max_length=60)
    intent: Literal["for_another", "for_self"] = "for_another"
    photos: list[str] = Field(default_factory=list, max_length=10)
    source_assignment_id: Optional[str] = None  # optional context — gig_id
    contact_name: Optional[str] = Field(default=None, max_length=120)
    contact_phone: Optional[str] = Field(default=None, max_length=40)
    contact_email: Optional[str] = Field(default=None, max_length=200)


class AdminUpdateReferralIn(BaseModel):
    status: Optional[str] = None
    quoted_amount: Optional[float] = Field(default=None, ge=0)
    assigned_contractor_id: Optional[str] = None
    linked_invoice_id: Optional[str] = None
    admin_notes: Optional[str] = Field(default=None, max_length=2000)


# ----- Worker endpoints ----------------------------------------------------
def _require_approved_worker(user: dict) -> None:
    if user.get("role") != "worker":
        raise HTTPException(403, "Only workers can submit referrals.")
    if user.get("worker_status") != "approved":
        raise HTTPException(
            403,
            "Only approved workers can submit referrals. Finish your profile and ID first.",
        )


@router.post("/worker/referrals")
async def submit_referral(
    payload: SubmitReferralIn,
    user: dict = Depends(get_current_user),
):
    """Create a new referral lead. Intent ('for myself' / 'for another') is
    captured upfront so Mechie sees the signal in the inbox — and so we
    never accidentally credit a commission for a job the referrer wanted
    to take themselves."""
    _require_approved_worker(user)
    if payload.service_category not in SERVICE_CATEGORIES:
        raise HTTPException(400, f"service_category must be one of {SERVICE_CATEGORIES}")
    now = _now_iso()
    rid = f"ref_{uuid.uuid4().hex[:12]}"
    doc = {
        "referral_id": rid,
        "referring_contractor_id": user["user_id"],
        "referring_contractor_name": user.get("name"),
        "source_assignment_id": payload.source_assignment_id or None,
        "property_address": payload.property_address.strip(),
        "opportunity_description": payload.opportunity_description.strip(),
        "service_category": payload.service_category,
        "intent": payload.intent,
        "photos": list(payload.photos or []),
        "contact": {
            "name": (payload.contact_name or "").strip() or None,
            "phone": (payload.contact_phone or "").strip() or None,
            "email": (payload.contact_email or "").strip() or None,
        },
        "submission_timestamp": now,
        "created_at": now,
        "updated_at": now,
        "status": "submitted",
        "status_history": [{"status": "submitted", "at": now, "by": user["user_id"]}],
        "quoted_amount": None,
        "assigned_contractor_id": None,
        "linked_invoice_id": None,
        "commission_amount": None,
        "commission_status": "pending",
        "commission_paid_date": None,
        "admin_notes": None,
        "void_reason": None,
    }
    await db.referral_leads.insert_one(doc)
    logger.info(
        f"referral submitted: {rid} by {user['user_id']} ({user.get('name')}) "
        f"intent={payload.intent} category={payload.service_category}"
    )
    return _serialize(doc)


@router.get("/worker/referrals")
async def my_referrals(user: dict = Depends(get_current_user)):
    if user.get("role") != "worker":
        raise HTTPException(403, "Workers only.")
    items: list[dict] = []
    async for r in db.referral_leads.find(
        {"referring_contractor_id": user["user_id"]}
    ).sort("created_at", -1):
        items.append(_serialize(r))
    # Roll-up of total earned + pending so the worker has a "what am I owed" answer
    eligible = sum((r.get("commission_amount") or 0) for r in items if r.get("commission_status") == "eligible")
    paid = sum((r.get("commission_amount") or 0) for r in items if r.get("commission_status") == "paid")
    pending = sum((r.get("commission_amount") or 0) for r in items if r.get("commission_status") == "pending")
    return {
        "items": items,
        "totals": {
            "commission_pending": round(pending, 2),
            "commission_eligible": round(eligible, 2),
            "commission_paid": round(paid, 2),
        },
        "service_categories": SERVICE_CATEGORIES,
    }


@router.get("/worker/referrals/{referral_id}")
async def get_my_referral(referral_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "worker":
        raise HTTPException(403)
    r = await db.referral_leads.find_one({
        "referral_id": referral_id,
        "referring_contractor_id": user["user_id"],
    })
    if not r:
        raise HTTPException(404, "Referral not found")
    return _serialize(r)


# ----- Admin endpoints -----------------------------------------------------
@router.get("/admin/referrals")
async def admin_list_referrals(
    status: Optional[str] = None,
    admin: dict = Depends(require_admin),
):
    q: dict = {}
    if status and status in ALL_STATUSES:
        q["status"] = status
    items: list[dict] = []
    async for r in db.referral_leads.find(q).sort("created_at", -1):
        items.append(_serialize(r))
    # Counts grouped by status — drives the "5 pending review" pills
    counts: dict[str, int] = {}
    async for r in db.referral_leads.find({}, {"status": 1}):
        s = r.get("status") or "submitted"
        counts[s] = counts.get(s, 0) + 1
    return {"items": items, "counts": counts, "all_statuses": list(ALL_STATUSES)}


@router.get("/admin/referrals/{referral_id}")
async def admin_get_referral(referral_id: str, admin: dict = Depends(require_admin)):
    r = await db.referral_leads.find_one({"referral_id": referral_id})
    if not r:
        raise HTTPException(404, "Referral not found")
    return _serialize(r)


@router.patch("/admin/referrals/{referral_id}")
async def admin_update_referral(
    referral_id: str,
    payload: AdminUpdateReferralIn,
    admin: dict = Depends(require_admin),
):
    """Mechie/Admin vets, quotes, assigns. Side effects:
      - assigning the referring contractor → status flips to 'self_fulfilled'
        and commission goes void (FRD §7).
      - moving status to 'paid' → commission_status flips to 'eligible' and
        commission_amount is computed from quoted_amount × rate.
      - moving status to 'commission_released' → commission_status='paid'.
    """
    existing = await db.referral_leads.find_one({"referral_id": referral_id})
    if not existing:
        raise HTTPException(404, "Referral not found")
    updates: dict = {}
    if payload.quoted_amount is not None:
        updates["quoted_amount"] = float(payload.quoted_amount)
    if payload.assigned_contractor_id is not None:
        updates["assigned_contractor_id"] = payload.assigned_contractor_id or None
    if payload.linked_invoice_id is not None:
        updates["linked_invoice_id"] = payload.linked_invoice_id or None
    if payload.admin_notes is not None:
        updates["admin_notes"] = payload.admin_notes

    new_status = payload.status
    if new_status:
        if new_status not in ALL_STATUSES:
            raise HTTPException(400, f"Unknown status {new_status}")

    # Self-fulfillment auto-detect — if we're assigning the referrer to
    # their own lead, force status to 'self_fulfilled' and void the commission.
    referrer_id = existing["referring_contractor_id"]
    assigned_id = (
        updates.get("assigned_contractor_id")
        if "assigned_contractor_id" in updates
        else existing.get("assigned_contractor_id")
    )
    if assigned_id and assigned_id == referrer_id:
        new_status = "self_fulfilled"
        updates["commission_amount"] = 0
        updates["commission_status"] = "void"
        updates["void_reason"] = "Self-fulfilled — referring contractor took the job"

    # Commission accrual triggers
    if new_status == "paid":
        rate = await _commission_rate()
        q_amount = updates.get("quoted_amount") or existing.get("quoted_amount") or 0
        comm = _calc_commission(q_amount, rate)
        updates["commission_amount"] = comm
        updates["commission_status"] = "eligible" if comm > 0 else "void"
    elif new_status == "commission_released":
        # Mark actually-paid-out
        if (existing.get("commission_status") or "pending") not in ("eligible", "paid"):
            # Allow if commission is eligible OR already paid (idempotent)
            raise HTTPException(
                400,
                "Cannot release commission until status moves past 'paid' (invoice paid).",
            )
        updates["commission_status"] = "paid"
        updates["commission_paid_date"] = _now_iso()
    elif new_status == "void":
        updates["commission_status"] = "void"
        updates["void_reason"] = payload.admin_notes or "Voided by admin"

    if new_status:
        updates["status"] = new_status

    updates["updated_at"] = _now_iso()
    push: dict = {}
    if new_status and new_status != existing.get("status"):
        push["status_history"] = {
            "status": new_status,
            "at": updates["updated_at"],
            "by": admin["user_id"],
        }

    mongo_update: dict = {"$set": updates}
    if push:
        mongo_update["$push"] = push
    await db.referral_leads.update_one({"referral_id": referral_id}, mongo_update)
    fresh = await db.referral_leads.find_one({"referral_id": referral_id})
    return _serialize(fresh)


# ----- Commission rate settings -------------------------------------------
class RateUpdateIn(BaseModel):
    commission_rate: float = Field(..., ge=0, le=1)


@router.get("/admin/referrals/settings")
async def get_settings(admin: dict = Depends(require_admin)):
    rate = await _commission_rate()
    return {"commission_rate": rate}


@router.put("/admin/referrals/settings")
async def update_settings(payload: RateUpdateIn, admin: dict = Depends(require_admin)):
    await db.app_settings.update_one(
        {"_id": "referral_program"},
        {
            "$set": {
                "commission_rate": float(payload.commission_rate),
                "updated_at": _now_iso(),
                "updated_by": admin["user_id"],
            }
        },
        upsert=True,
    )
    return {"commission_rate": float(payload.commission_rate)}
