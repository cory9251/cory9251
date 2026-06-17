"""Shared VA Commission Program building blocks: deps, models, helpers, and
constants for the commission lifecycle (lead → booked → paid → commission →
pm_approved → owner_approved → paid).

Used by:
- routes/va.py — VA self-service portal
- routes/pm.py — Program Manager queue
- routes/owner.py — Owner sign-off

Kept as a single module because all three route files share the same dep
chain (require_va_active → _calc_commission_for_lead → _serialize_commission)
and splitting it further would just mean more import boilerplate.
"""
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from config import db
from auth_deps import get_current_user


# ---------------------------------------------------------------------------
# Literals + constants
# ---------------------------------------------------------------------------
LeadStage = Literal["new_lead", "contacted", "quoted", "booked", "completed", "paid", "lost"]
LeadServiceType = Literal["routine", "deep", "moveout", "specialty", "commercial", "unknown"]
LeadPropertySize = Literal["studio", "1br", "2br", "3br", "4br", "5br", "commercial"]
LeadSource = Literal[
    "facebook_marketplace",
    "facebook_groups",
    "craigslist",
    "direct_message",
    "referral",
    "other",
]

COMMISSION_RATES = {
    "routine": 10.0,
    "deep": 25.0,
    "moveout": 25.0,
    "specialty": 25.0,
    "commercial_pct": 0.05,
}
RECURRING_TIERS = {
    1: 15.0,
    2: 25.0,
    3: 10.0,
    4: 10.0,
    5: 10.0,
    6: 10.0,
}
RECURRING_LIFETIME_CAP = 100.0
CLEANER_REFERRAL_TIERS = {1: 20.0, 5: 30.0, 10: 50.0}
CLEANER_REFERRAL_CAP = 100.0
DUPLICATE_REOPEN_DAYS = 90  # leads completed/lost > 90 days old don't block dupes


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class VARegisterDetailsIn(BaseModel):
    """Optional VA-only profile data set after signup."""
    va_phone: Optional[str] = None
    va_address: Optional[str] = None


class LeadIn(BaseModel):
    prospect_name: str = Field(min_length=2, max_length=120)
    prospect_phone: str = Field(min_length=7, max_length=40)
    prospect_email: Optional[str] = None
    prospect_address: Optional[str] = None  # used for self-referral check
    service_type: LeadServiceType
    property_size: LeadPropertySize
    preferred_datetime: Optional[str] = None  # ISO 8601 date or datetime
    source: LeadSource
    notes: Optional[str] = Field(default=None, max_length=2000)


class LeadStageIn(BaseModel):
    stage: LeadStage
    job_value: Optional[float] = None  # required when stage='paid' for commercial calc
    note: Optional[str] = None


class LeadEditIn(BaseModel):
    """Partial lead edit. Admin can edit anything; VA can edit only their own
    lead while it's still in stage='new_lead' (enforced in the route)."""
    prospect_name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    prospect_phone: Optional[str] = Field(default=None, min_length=7, max_length=40)
    prospect_email: Optional[str] = None
    prospect_address: Optional[str] = None
    service_type: Optional[LeadServiceType] = None
    property_size: Optional[LeadPropertySize] = None
    preferred_datetime: Optional[str] = None
    source: Optional[LeadSource] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    job_value: Optional[float] = None  # admin only — enforced in route
    # Reassign owner — admin only — enforced in route
    va_user_id: Optional[str] = None
    # Free-text reason saved to activity log
    reason: Optional[str] = Field(default=None, max_length=500)


class LeadDeleteIn(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Batch-2 VA-success features (iter42)
# ---------------------------------------------------------------------------
class VAGoalIn(BaseModel):
    """Admin sets a monthly target for a VA. Both numbers optional — admin may
    only care about leads, or only commission. month format: 'YYYY-MM'."""
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    target_leads: Optional[int] = Field(default=None, ge=0, le=10000)
    target_commission: Optional[float] = Field(default=None, ge=0)
    note: Optional[str] = Field(default=None, max_length=500)


PitchTemplateChannel = Literal["dm", "email", "sms", "any"]


class PitchTemplateIn(BaseModel):
    """A reusable message a VA can copy when contacting prospects.
    `body` may include {prospect_name}, {service_type} tokens for client-side
    interpolation; the backend stores them as plain text."""
    title: str = Field(..., min_length=2, max_length=120)
    body: str = Field(..., min_length=4, max_length=4000)
    category: Optional[str] = Field(default=None, max_length=60)
    channel: PitchTemplateChannel = "any"


class PitchTemplatePatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=120)
    body: Optional[str] = Field(default=None, min_length=4, max_length=4000)
    category: Optional[str] = Field(default=None, max_length=60)
    channel: Optional[PitchTemplateChannel] = None
    active: Optional[bool] = None


class CoachingNoteIn(BaseModel):
    """Admin coaching note attached to a VA's profile. `is_shared=True` makes
    the note visible to the VA; private notes are admin-only."""
    text: str = Field(..., min_length=2, max_length=4000)
    is_shared: bool = False


class CoachingNotePatch(BaseModel):
    text: Optional[str] = Field(default=None, min_length=2, max_length=4000)
    is_shared: Optional[bool] = None


# Stale-lead threshold — leads that have sat in 'contacted' / 'quoted' for
# this long surface in the VA's dashboard "needs follow-up" panel.
STALE_LEAD_DAYS = 7
STALE_LEAD_STAGES = ("contacted", "quoted")


class CommissionActionIn(BaseModel):
    """PM's approve / flag / reject action on a commission."""
    note: Optional[str] = None


class OwnerBulkApproveIn(BaseModel):
    """Owner bulk-approves all pm_approved commissions for a VA within a window."""
    va_user_id: str
    week_start: Optional[str] = None
    week_end: Optional[str] = None


class CommissionMarkPaidIn(BaseModel):
    payout_reference: Optional[str] = None
    payout_method: Optional[Literal["cash", "venmo", "zelle", "check", "ach", "other"]] = "other"


class VAAccountAdminIn(BaseModel):
    """Program Manager creates a VA account directly."""
    email: EmailStr
    name: str
    password: str = Field(min_length=6)
    va_phone: Optional[str] = None
    va_address: Optional[str] = None
    auto_approve: Optional[bool] = True


class VAStatusActionIn(BaseModel):
    note: Optional[str] = None


class CommercialAccountIn(BaseModel):
    account_name: str = Field(min_length=2, max_length=160)
    va_user_id: str
    monthly_revenue: float = Field(ge=0)
    start_date: Optional[str] = None
    notes: Optional[str] = None


class CommercialAccountPatch(BaseModel):
    account_name: Optional[str] = None
    monthly_revenue: Optional[float] = None
    active: Optional[bool] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Role dependencies
# ---------------------------------------------------------------------------
async def require_va(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "va":
        raise HTTPException(403, "VA access required")
    if user.get("va_status") == "removed":
        raise HTTPException(403, "Account removed")
    return user


async def require_va_active(user: dict = Depends(get_current_user)) -> dict:
    """VA must be 'approved' to submit leads / view earnings."""
    if user.get("role") != "va":
        raise HTTPException(403, "VA access required")
    status = user.get("va_status") or "pending"
    if status != "approved":
        raise HTTPException(403, f"VA account is {status}. Wait for Program Manager approval.")
    return user


async def require_program_manager_or_owner(
    request: Request, user: dict = Depends(get_current_user)
) -> dict:
    """Mechie (Program Manager) AND any admin can manage VA accounts/leads.
    Owner = admin with is_owner=True (for final payout sign-off only)."""
    role = user.get("role")
    if role != "admin":
        raise HTTPException(403, "Operations access required")
    if user.get("is_read_only") and request.method in ("POST", "PUT", "PATCH", "DELETE"):
        raise HTTPException(403, "Read-only admin — cannot mutate")
    return user


async def require_owner(
    request: Request, user: dict = Depends(get_current_user)
) -> dict:
    """Owner-only — final payout sign-off."""
    if user.get("role") != "admin":
        raise HTTPException(403, "Owner access required")
    if not user.get("is_owner"):
        raise HTTPException(403, "Owner sign-off required — this user is not the Owner")
    return user


# ---------------------------------------------------------------------------
# Normalization + serialization helpers
# ---------------------------------------------------------------------------
def _normalize_phone(p: Optional[str]) -> str:
    if not p:
        return ""
    return re.sub(r"[^\d]", "", p)


def _normalize_email(e: Optional[str]) -> str:
    if not e:
        return ""
    return e.lower().strip()


def _normalize_address(a: Optional[str]) -> str:
    if not a:
        return ""
    s = a.lower().strip()
    s = re.sub(r"[,.;:]", " ", s)
    return re.sub(r"\s+", " ", s)


def _serialize_lead(lead: dict, include_owner: bool = True) -> dict:
    out = {k: v for k, v in lead.items() if k != "_id"}
    if not include_owner:
        out.pop("va_user_id", None)
        out.pop("va_name", None)
    return out


def _serialize_commission(c: dict) -> dict:
    return {k: v for k, v in c.items() if k != "_id"}


# ---------------------------------------------------------------------------
# Violation log + duplicate detection
# ---------------------------------------------------------------------------
async def _log_lead_activity(
    *,
    lead_id: str,
    kind: str,
    actor: dict,
    detail: dict,
) -> None:
    """Append an activity row to a lead. Visible to admin + VA owner.
    `kind` examples: 'edited', 'stage_changed', 'deleted', 'restored',
    'reassigned', 'note_added'. Never deletable — even when a lead is
    soft-deleted, its activity log survives for audit."""
    now = datetime.now(timezone.utc).isoformat()
    await db.va_lead_activity.insert_one({
        "activity_id": f"act_{uuid.uuid4().hex[:12]}",
        "lead_id": lead_id,
        "kind": kind,
        "actor_user_id": actor.get("user_id"),
        "actor_name": actor.get("name") or actor.get("email"),
        "actor_role": actor.get("role"),
        "detail": detail,
        "created_at": now,
    })


async def _log_violation(
    va_user_id: Optional[str],
    kind: str,
    details: dict,
    flagged_by: str = "system",
) -> None:
    """Permanent violation log — cannot be deleted by any user role."""
    await db.va_violations.insert_one({
        "violation_id": f"viol_{uuid.uuid4().hex[:12]}",
        "va_user_id": va_user_id,
        "kind": kind,
        "details": details,
        "flagged_by": flagged_by,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


async def _find_duplicate_lead(phone_norm: str, email_norm: str) -> Optional[dict]:
    """Return the conflicting active lead, or None if dupe window allows resubmit."""
    q: dict = {"$or": []}
    if phone_norm:
        q["$or"].append({"prospect_phone_norm": phone_norm})
    if email_norm:
        q["$or"].append({"prospect_email_norm": email_norm})
    if not q["$or"]:
        return None
    cur = db.va_leads.find(q)
    cutoff = datetime.now(timezone.utc) - timedelta(days=DUPLICATE_REOPEN_DAYS)
    async for d in cur:
        stage = d.get("stage")
        if stage in ("completed", "lost", "paid"):
            ts_str = d.get("stage_changed_at") or d.get("created_at") or ""
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts < cutoff:
                    continue  # eligible for resubmit
            except Exception:
                pass
        return d
    return None


# ---------------------------------------------------------------------------
# Commission calculation
# ---------------------------------------------------------------------------
async def _next_recurring_visit_count(va_user_id: str, phone_norm: str, email_norm: str) -> int:
    """Count completed/paid recurring jobs for the same client+VA — returns next visit number."""
    q = {
        "va_user_id": va_user_id,
        "stage": {"$in": ["completed", "paid"]},
        "service_type": "routine",
    }
    or_clauses = []
    if phone_norm:
        or_clauses.append({"prospect_phone_norm": phone_norm})
    if email_norm:
        or_clauses.append({"prospect_email_norm": email_norm})
    if or_clauses:
        q["$or"] = or_clauses
    count = await db.va_leads.count_documents(q)
    return count + 1


async def _va_lifetime_recurring_total(va_user_id: str, phone_norm: str, email_norm: str) -> float:
    """Lifetime commission paid out / pending for this VA+client recurring chain."""
    q: dict = {"va_user_id": va_user_id, "kind": "recurring"}
    or_clauses = []
    if phone_norm:
        or_clauses.append({"client_phone_norm": phone_norm})
    if email_norm:
        or_clauses.append({"client_email_norm": email_norm})
    if or_clauses:
        q["$or"] = or_clauses
    total = 0.0
    async for c in db.commissions.find(q):
        if c.get("status") != "rejected":
            total += float(c.get("amount") or 0)
    return total


async def _calc_commission_for_lead(lead: dict, job_value: Optional[float] = None) -> dict:
    """Compute commission for a lead based on its service type."""
    svc = lead.get("service_type")
    phone = lead.get("prospect_phone_norm") or ""
    email = lead.get("prospect_email_norm") or ""
    va = lead.get("va_user_id")

    if svc == "commercial":
        rev = float(job_value or lead.get("job_value") or 0)
        amount = round(rev * COMMISSION_RATES["commercial_pct"], 2)
        return {
            "amount": amount,
            "kind": "commercial_one_time",
            "visit_number": None,
            "notes": f"5% of ${rev:.2f} job value",
        }

    if svc == "routine":
        visit = await _next_recurring_visit_count(va, phone, email)
        if visit >= 7:
            return {"amount": 0.0, "kind": "recurring", "visit_number": visit,
                    "notes": "Visit 7+ — recurring cap reached ($0)"}
        per_visit = RECURRING_TIERS.get(visit, 0.0)
        if visit == 1:
            current_paid = await _va_lifetime_recurring_total(va, phone, email)
            remaining = max(0.0, RECURRING_LIFETIME_CAP - current_paid)
            amount = min(per_visit, remaining)
            return {"amount": amount, "kind": "recurring", "visit_number": visit,
                    "notes": f"Recurring visit {visit} (${per_visit:.0f})"}
        current_paid = await _va_lifetime_recurring_total(va, phone, email)
        remaining = max(0.0, RECURRING_LIFETIME_CAP - current_paid)
        amount = min(per_visit, remaining)
        return {"amount": amount, "kind": "recurring", "visit_number": visit,
                "notes": f"Recurring visit {visit} (${per_visit:.0f}) · ${current_paid:.0f}/$100 lifetime cap"}

    if svc in ("deep", "moveout", "specialty"):
        return {"amount": COMMISSION_RATES[svc], "kind": "one_time", "visit_number": None,
                "notes": f"{svc.title()} flat $25"}

    return {"amount": 0.0, "kind": "unknown", "visit_number": None,
            "notes": "Service type unknown — manual review needed"}


async def _ensure_commission_for_lead(lead: dict, target_status: str = "calculating") -> Optional[dict]:
    """Create or update a commission record for this lead. Phase 1 lifecycle:
    Booked → status=calculating (record created so VA sees progress)
    Paid → status=pending_approval (surfaces in PM queue, auto-calc amount)"""
    existing = await db.commissions.find_one({"lead_id": lead["lead_id"]})
    calc = await _calc_commission_for_lead(lead, lead.get("job_value"))
    now = datetime.now(timezone.utc).isoformat()
    if existing:
        # Recompute amount if entering pending_approval. Once approved/paid, freeze.
        if existing.get("status") in ("approved", "paid", "owner_approved"):
            return {k: v for k, v in existing.items() if k != "_id"}
        await db.commissions.update_one(
            {"commission_id": existing["commission_id"]},
            {"$set": {
                "amount": calc["amount"],
                "kind": calc["kind"],
                "visit_number": calc["visit_number"],
                "calc_notes": calc["notes"],
                "status": target_status,
                "updated_at": now,
                "client_phone_norm": lead.get("prospect_phone_norm"),
                "client_email_norm": lead.get("prospect_email_norm"),
                "job_value": lead.get("job_value"),
            }},
        )
        fresh = await db.commissions.find_one({"commission_id": existing["commission_id"]})
        return {k: v for k, v in fresh.items() if k != "_id"} if fresh else None

    doc = {
        "commission_id": f"comm_{uuid.uuid4().hex[:12]}",
        "lead_id": lead["lead_id"],
        "va_user_id": lead["va_user_id"],
        "va_name": lead.get("va_name"),
        "prospect_name": lead.get("prospect_name"),
        "service_type": lead.get("service_type"),
        "client_phone_norm": lead.get("prospect_phone_norm"),
        "client_email_norm": lead.get("prospect_email_norm"),
        "amount": calc["amount"],
        "kind": calc["kind"],
        "visit_number": calc["visit_number"],
        "calc_notes": calc["notes"],
        "status": target_status,
        "pm_action_at": None,
        "pm_action_note": None,
        "owner_action_at": None,
        "paid_at": None,
        "payout_reference": None,
        "payout_method": None,
        "job_value": lead.get("job_value"),
        "created_at": now,
        "updated_at": now,
    }
    await db.commissions.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}
