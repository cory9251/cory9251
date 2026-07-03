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
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from auth_deps import get_current_user, require_admin
from config import db, logger
from notifications import (
    _public_base,
    _resolve_sms_creds,
    _send_sms_sync,
    _send_user_email,
    notify_admins,
)

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


# ----- Status update notifications ----------------------------------------
# Templates for the email we send the REFERRING worker every time their
# referral's status changes. Keeps them informed + motivated through the
# pipeline. Tone: short, professional, HCOB-branded.
#
# `sms_text` is provided only for milestone statuses ('paid' and
# 'commission_released') — the moments the worker actually cares enough
# for a phone buzz. Everything else is email-only.
_STATUS_NOTIFICATIONS: dict[str, dict] = {
    "under_review": {
        "subject": "Your referral is under review",
        "intro": (
            "Mechie is taking a look at your referral now. We'll let you "
            "know as soon as it moves to the next step."
        ),
    },
    "quoted": {
        "subject": "We've quoted your referral",
        "intro": (
            "Good news — we sent a quote to the customer you referred. "
            "If they accept, your commission is one step closer."
        ),
    },
    "scheduled": {
        "subject": "Your referral is scheduled",
        "intro": (
            "The customer accepted and the job is on the calendar. "
            "Almost there — commission accrues when the invoice is paid."
        ),
    },
    "in_progress": {
        "subject": "Work has started on your referral",
        "intro": "Crews are on site now. We'll let you know when it wraps.",
    },
    "completed": {
        "subject": "Work complete on your referral",
        "intro": (
            "The job is done. Invoice goes out next — your commission "
            "becomes eligible the moment it's paid."
        ),
    },
    "invoiced": {
        "subject": "Invoice sent on your referral",
        "intro": (
            "We invoiced the customer. As soon as they pay, your "
            "commission flips to eligible."
        ),
    },
    "paid": {
        "subject": "Invoice paid — your commission is eligible",
        "intro": (
            "The customer paid! Your commission is now eligible and will "
            "be released on the next payout cycle."
        ),
        "sms_text": (
            "HCOB Network: Your referral invoice is PAID. Commission "
            "${commission} is now eligible for payout."
        ),
    },
    "commission_released": {
        "subject": "Your referral commission has been paid out",
        "intro": (
            "Your commission has been released. Check your preferred "
            "payout channel — funds are on the way."
        ),
        "sms_text": (
            "HCOB Network: Commission ${commission} on your referral "
            "has been released. Thanks for the lead."
        ),
    },
    "void": {
        "subject": "Your referral was voided",
        "intro": (
            "Heads up — this referral was closed without a commission. "
            "Check the admin notes for details, and keep them coming."
        ),
    },
    "self_fulfilled": {
        "subject": "Referral closed (self-fulfilled)",
        "intro": (
            "Per program rules, commission isn't paid when the referring "
            "contractor takes the job themselves. The lead has been "
            "closed accordingly."
        ),
    },
}


def _build_status_email_html(
    referral: dict,
    new_status: str,
    intro: str,
    admin_notes: Optional[str],
) -> str:
    """Render the status-update email body. The `_email_layout` wrapper adds
    the HCOB header + CTA + footer; we only supply the inner HTML."""
    address = referral.get("property_address") or "—"
    category = (referral.get("service_category") or "").replace("_", " ").title()
    quoted = referral.get("quoted_amount")
    commission = referral.get("commission_amount")
    quoted_line = (
        f'<tr><td style="padding:4px 0;color:#6B7280;width:160px">Quoted amount</td>'
        f'<td style="padding:4px 0;font-weight:600;color:#030712">${quoted:,.0f}</td></tr>'
        if quoted else ""
    )
    commission_line = (
        f'<tr><td style="padding:4px 0;color:#6B7280">Your commission</td>'
        f'<td style="padding:4px 0;font-weight:700;color:#059669">${commission:,.0f}</td></tr>'
        if commission else ""
    )
    notes_block = ""
    if admin_notes:
        notes_block = (
            f'<div style="margin-top:16px;padding:12px;background:#FFFBEB;'
            f'border-left:3px solid #F59E0B;color:#92400E;font-size:13px">'
            f'<strong>Admin note:</strong> {admin_notes}</div>'
        )
    status_label = new_status.replace("_", " ").upper()
    return f"""
      <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#030712">
        {intro}
      </p>
      <table style="width:100%;border-collapse:collapse;font-size:13px;
                    border:1px solid #E5E7EB;padding:12px;margin:16px 0">
        <tr><td style="padding:4px 0;color:#6B7280">Status</td>
            <td style="padding:4px 0;font-weight:700;color:#0044FF">{status_label}</td></tr>
        <tr><td style="padding:4px 0;color:#6B7280">Address</td>
            <td style="padding:4px 0;color:#030712">{address}</td></tr>
        <tr><td style="padding:4px 0;color:#6B7280">Service</td>
            <td style="padding:4px 0;color:#030712">{category}</td></tr>
        {quoted_line}
        {commission_line}
      </table>
      {notes_block}
    """


async def _record_referral_notification(
    referral_id: str,
    referrer_id: str,
    new_status: str,
    *,
    channels_attempted: list[str],
    email_sent: bool,
    sms_sent: bool,
    skipped_reason: Optional[str] = None,
) -> None:
    """Audit log every status-update notification attempt. Lets the worker
    UI show 'Mechie pinged you on 2026-02-05' AND lets tests assert
    behavior without mocking Resend/Twilio."""
    try:
        await db.referral_notifications.insert_one({
            "notification_id": f"rn_{uuid.uuid4().hex[:12]}",
            "referral_id": referral_id,
            "referrer_id": referrer_id,
            "status": new_status,
            "channels_attempted": channels_attempted,
            "email_sent": email_sent,
            "sms_sent": sms_sent,
            "skipped_reason": skipped_reason,
            "created_at": _now_iso(),
        })
    except Exception as e:
        logger.error(f"failed to record referral notification: {e}")


async def _send_referral_status_notification(
    referral_id: str,
    new_status: str,
) -> None:
    """Background task — email (always) + SMS (milestone events only)
    fired to the referring contractor whenever a status update lands.

    Status transitions defined in `_STATUS_NOTIFICATIONS` get a template;
    everything else is silently skipped (e.g. raw 'submitted' which is
    self-triggered by the worker)."""
    template = _STATUS_NOTIFICATIONS.get(new_status)
    if not template:
        return
    referral = await db.referral_leads.find_one({"referral_id": referral_id})
    if not referral:
        return
    referrer_id = referral.get("referring_contractor_id")
    if not referrer_id:
        return
    user = await db.users.find_one({"user_id": referrer_id})
    if not user:
        await _record_referral_notification(
            referral_id, referrer_id, new_status,
            channels_attempted=[], email_sent=False, sms_sent=False,
            skipped_reason="user_not_found",
        )
        return

    channels: list[str] = []
    html = _build_status_email_html(
        referral, new_status, template["intro"], referral.get("admin_notes")
    )
    cta_url = f"{_public_base()}/crew/referrals"

    # ---- Email (always, when template exists) -----------------------------
    email_sent = False
    if user.get("email"):
        channels.append("email")
        try:
            email_sent = await _send_user_email(
                user,
                kind=f"referral_status_{new_status}",
                subject=template["subject"],
                body_html=html,
                cta_label="Open my referrals",
                cta_url=cta_url,
            )
        except Exception as e:
            logger.exception(f"referral status email failed: {e}")

    # ---- SMS (milestone statuses only: paid + commission_released) --------
    sms_sent = False
    sms_template = template.get("sms_text")
    if sms_template and user.get("phone"):
        channels.append("sms")
        try:
            creds = await _resolve_sms_creds()
            if creds.get("sid") and creds.get("token") and creds.get("from_"):
                commission = referral.get("commission_amount") or 0
                sms_body = sms_template.format(commission=int(commission))
                await asyncio.to_thread(
                    _send_sms_sync,
                    creds["sid"], creds["token"], creds["from_"],
                    user["phone"], sms_body,
                )
                sms_sent = True
            else:
                logger.warning(
                    f"[referral/{new_status}] no Twilio creds — sms skipped for {referrer_id}"
                )
        except Exception as e:
            logger.exception(f"referral status sms failed: {e}")

    await _record_referral_notification(
        referral_id, referrer_id, new_status,
        channels_attempted=channels,
        email_sent=email_sent,
        sms_sent=sms_sent,
    )


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
    await notify_admins(
        f"New contractor referral: {payload.property_address.strip()}",
        f"{user.get('name') or 'A contractor'} spotted a {payload.service_category.replace('_', ' ')} lead",
        url="/ops/referrals",
    )
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


# ----- Commission rate settings -------------------------------------------
# NOTE: must be registered BEFORE /admin/referrals/{referral_id} or FastAPI
# matches "settings" as a referral_id and returns 404.
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
    background_tasks: BackgroundTasks,
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

    # Fire referrer notification (email + SMS for milestone statuses) AFTER
    # the doc is updated so the email reads from the new state.
    # Run in the background so the admin's PATCH returns instantly.
    if new_status and new_status != existing.get("status"):
        background_tasks.add_task(
            _send_referral_status_notification, referral_id, new_status,
        )

    return _serialize(fresh)
