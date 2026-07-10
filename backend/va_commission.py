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
LeadServiceType = Literal[
    # Residential cleaning
    "routine",
    "deep",
    "moveout",
    "apartment_turnover",
    "carpet",
    # Property services
    "junk_removal",
    "estate_cleanout",
    "pressure_washing",
    "landscaping",
    "handyman",
    "painting",
    "maintenance_bundle",
    # Commercial / specialty
    "commercial",
    "specialty_medical",
    "specialty_funeral",
    "specialty_construction",
    "specialty",  # legacy bucket — kept so existing leads stay valid
    "unknown",
    # Digital / remote services — commission is a % of project value
    "product_sourcing",
    "web_development",
    "app_development",
    "social_media_marketing",
    "seo_content",
    "graphic_design",
    "digital_other",
]

DIGITAL_SERVICE_TYPES = frozenset({
    "product_sourcing",
    "web_development",
    "app_development",
    "social_media_marketing",
    "seo_content",
    "graphic_design",
    "digital_other",
})
LeadPropertySize = Literal["studio", "1br", "2br", "3br", "4br", "5br", "commercial"]
LeadSource = Literal[
    "facebook_marketplace",
    "facebook_groups",
    "craigslist",
    "nextdoor",
    "linkedin",
    "reddit",
    "google_maps",
    "cold_email",
    "listing_marketplace",  # Yelp / Thumbtack / Angi / HomeAdvisor
    "direct_message",
    "referral",
    "other",
]

# Commission rate buckets. New service types map to existing buckets so we
# don't have to rewrite commission logic — each non-commercial residential
# service falls into "routine" ($10 baseline) or "deep" ($25 premium) bucket.
COMMISSION_RATES = {
    "routine": 10.0,
    "deep": 25.0,
    "moveout": 25.0,
    "apartment_turnover": 25.0,
    "carpet": 25.0,
    "junk_removal": 10.0,
    "estate_cleanout": 25.0,
    "pressure_washing": 10.0,
    "landscaping": 10.0,
    "handyman": 10.0,
    "painting": 25.0,
    "maintenance_bundle": 25.0,
    "specialty": 25.0,
    "specialty_medical": 25.0,
    "specialty_funeral": 25.0,
    "specialty_construction": 25.0,
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
DEFAULT_DIGITAL_COMMISSION_PCT = 10.0  # % of project value; admin-editable via app_settings
DEFAULT_TEAM_OVERRIDE_PCT = 10.0  # % of a downline member's commission the team lead earns (SPLIT)
DEFAULT_TEAM_OVERRIDE_L2_PCT = 5.0  # L2: % the lead's own lead earns on a grandchild commission (SPLIT)

OVERRIDABLE_FLAT_SERVICES = [k for k in COMMISSION_RATES if k != "commercial_pct"]
OVERRIDABLE_RATE_KEYS = set(OVERRIDABLE_FLAT_SERVICES) | {"commercial_pct", "digital_pct"}


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
    property_size: Optional[LeadPropertySize] = None  # required for non-digital (route-enforced)
    estimated_budget: Optional[float] = Field(default=None, ge=0)  # digital leads
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
    estimated_budget: Optional[float] = Field(default=None, ge=0)
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


class DigitalSettingsIn(BaseModel):
    commission_pct: float = Field(ge=0, le=100)


class AssignVAIn(BaseModel):
    va_user_id: Optional[str] = None  # None/'' clears the delivery assignment


class CommissionSettingsIn(BaseModel):
    rates: Optional[dict] = None  # {service: flat $ amount}
    commercial_pct: Optional[float] = Field(default=None, ge=0, le=100)
    digital_pct: Optional[float] = Field(default=None, ge=0, le=100)
    team_override_pct: Optional[float] = Field(default=None, ge=0, le=100)
    team_override_l2_pct: Optional[float] = Field(default=None, ge=0, le=100)


class VACommissionOverridesIn(BaseModel):
    overrides: dict = Field(default_factory=dict)  # full replace; omit keys to clear


class LeadFollowupIn(BaseModel):
    due_at: Optional[str] = None  # ISO date; None/empty clears
    note: Optional[str] = Field(default=None, max_length=300)


class LeadContactIn(BaseModel):
    method: Literal["call", "text", "email", "in_person", "other"]
    outcome: str = Field(min_length=1, max_length=500)


class LeadCommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


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


async def block_unapproved_va(user: dict = Depends(get_current_user)) -> dict:
    """Allow everyone EXCEPT VAs whose status is not 'approved'. Apply to
    cross-role endpoints (e.g. messaging) that pending/suspended VAs should
    not have access to until the Program Manager approves them. Admins, owners,
    customers, workers, and approved VAs all pass through unchanged."""
    if user.get("role") == "va":
        status = user.get("va_status") or "pending"
        if status != "approved":
            raise HTTPException(
                403,
                f"VA account is {status}. This feature unlocks once your Program Manager approves you.",
            )
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


async def _get_digital_commission_pct() -> float:
    s = await db.app_settings.find_one({"_id": "global"}, {"_id": 0, "digital_commission_pct": 1})
    try:
        pct = float((s or {}).get("digital_commission_pct"))
    except (TypeError, ValueError):
        return DEFAULT_DIGITAL_COMMISSION_PCT
    return min(100.0, max(0.0, pct))


async def _team_override_pct() -> float:
    s = await db.app_settings.find_one({"_id": "global"}, {"_id": 0, "team_override_pct": 1})
    try:
        pct = float((s or {}).get("team_override_pct"))
    except (TypeError, ValueError):
        return DEFAULT_TEAM_OVERRIDE_PCT
    return min(100.0, max(0.0, pct))


async def _team_override_l2_pct() -> float:
    s = await db.app_settings.find_one({"_id": "global"}, {"_id": 0, "team_override_l2_pct": 1})
    try:
        pct = float((s or {}).get("team_override_l2_pct"))
    except (TypeError, ValueError):
        return DEFAULT_TEAM_OVERRIDE_L2_PCT
    return min(100.0, max(0.0, pct))


async def _eligible_lead(va_id: Optional[str]) -> Optional[dict]:
    """Return the VA doc if they can receive overrides (active team lead)."""
    if not va_id:
        return None
    u = await db.users.find_one(
        {"user_id": va_id},
        {"_id": 0, "user_id": 1, "name": 1, "is_team_lead": 1, "va_status": 1, "team_lead_id": 1},
    )
    if not u or not u.get("is_team_lead") or (u.get("va_status") or "") != "approved":
        return None
    return u


async def _upsert_override(lead: dict, recipient: dict, level: int, gross: float, pct: float, member_id: str, target_status: str) -> float:
    """Create/refresh the `team_override` commission for one upline recipient at
    a given level. Idempotent by (lead_id, kind, level). Frozen once approved/paid
    — returns the frozen amount so the closer's split stays consistent. Returns
    the amount deducted from the closer for this level."""
    existing = await db.commissions.find_one(
        {"lead_id": lead["lead_id"], "kind": "team_override", "level": level}
    )
    if existing and existing.get("status") in ("approved", "paid", "owner_approved"):
        return round(float(existing.get("amount") or 0), 2)
    if pct <= 0 or not recipient:
        if existing:
            await db.commissions.delete_one({"commission_id": existing["commission_id"]})
        return 0.0
    amount = round(gross * pct / 100.0, 2)
    now = datetime.now(timezone.utc).isoformat()
    base = {
        "lead_id": lead["lead_id"],
        "kind": "team_override",
        "level": level,
        "va_user_id": recipient["user_id"],
        "va_name": recipient.get("name"),
        "prospect_name": lead.get("prospect_name"),
        "service_type": lead.get("service_type"),
        "amount": amount,
        "override_rate": pct,
        "source_va_user_id": member_id,
        "source_va_name": lead.get("va_name"),
        "status": target_status,
        "calc_notes": f"Team override L{level} — {pct:.1f}% of {lead.get('va_name') or 'member'}'s commission (${gross:.2f})",
        "job_value": lead.get("job_value"),
        "updated_at": now,
    }
    if existing:
        await db.commissions.update_one({"commission_id": existing["commission_id"]}, {"$set": base})
    else:
        await db.commissions.insert_one({
            "commission_id": f"comm_{uuid.uuid4().hex[:12]}",
            **base,
            "visit_number": None,
            "client_phone_norm": None,
            "client_email_norm": None,
            "pm_action_at": None,
            "pm_action_note": None,
            "owner_action_at": None,
            "paid_at": None,
            "payout_reference": None,
            "payout_method": None,
            "created_at": now,
        })
    return amount


async def _apply_team_override(lead: dict, gross_amount: float, target_status: str) -> tuple:
    """Up to TWO levels of SPLIT override, both deducted from the closing VA.
    L1 → the closer's direct team lead; L2 → that lead's own team lead.
    Returns (member_net_amount, override_info|None)."""
    member_id = lead.get("va_user_id")
    if not member_id or gross_amount <= 0:
        return gross_amount, None
    member = await db.users.find_one({"user_id": member_id}, {"_id": 0, "team_lead_id": 1})
    l1 = await _eligible_lead((member or {}).get("team_lead_id"))
    if not l1 or l1["user_id"] == member_id:
        # No upline — clean up any stale overrides and pay the closer in full.
        await db.commissions.delete_many({"lead_id": lead["lead_id"], "kind": "team_override"})
        return gross_amount, None

    l1_pct = await _team_override_pct()
    l1_amount = await _upsert_override(lead, l1, 1, gross_amount, l1_pct, member_id, target_status)

    # Level 2 — the direct lead's own lead (hard cap at 2 levels).
    l2 = await _eligible_lead(l1.get("team_lead_id"))
    if l2 and l2["user_id"] not in (member_id, l1["user_id"]):
        l2_pct = await _team_override_l2_pct()
        l2_amount = await _upsert_override(lead, l2, 2, gross_amount, l2_pct, member_id, target_status)
    else:
        l2_amount = 0.0
        stale = await db.commissions.find_one({"lead_id": lead["lead_id"], "kind": "team_override", "level": 2})
        if stale and stale.get("status") not in ("approved", "paid", "owner_approved"):
            await db.commissions.delete_one({"commission_id": stale["commission_id"]})

    member_net = round(gross_amount - l1_amount - l2_amount, 2)
    return member_net, {
        "team_lead_id": l1["user_id"],
        "override_amount": round(l1_amount + l2_amount, 2),
        "override_rate": l1_pct,
    }


async def _resolve_commission_config(va_user_id: Optional[str]) -> dict:
    """Effective rates: hardcoded defaults ← app_settings globals ← per-VA overrides."""
    s = await db.app_settings.find_one(
        {"_id": "global"},
        {"_id": 0, "commission_rates": 1, "commercial_pct": 1, "digital_commission_pct": 1},
    ) or {}
    rates = {k: float(v) for k, v in COMMISSION_RATES.items() if k != "commercial_pct"}
    for k, v in (s.get("commission_rates") or {}).items():
        if k in rates:
            try:
                rates[k] = float(v)
            except (TypeError, ValueError):
                pass
    try:
        commercial_pct = float(s.get("commercial_pct"))
    except (TypeError, ValueError):
        commercial_pct = COMMISSION_RATES["commercial_pct"] * 100.0
    digital_pct = await _get_digital_commission_pct()

    overrides: dict = {}
    if va_user_id:
        u = await db.users.find_one({"user_id": va_user_id}, {"_id": 0, "commission_overrides": 1})
        overrides = (u or {}).get("commission_overrides") or {}
    for k, v in overrides.items():
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if k == "commercial_pct":
            commercial_pct = fv
        elif k == "digital_pct":
            digital_pct = fv
        elif k in rates:
            rates[k] = fv
    return {"rates": rates, "commercial_pct": commercial_pct, "digital_pct": digital_pct, "overrides": overrides}


async def _calc_commission_for_lead(lead: dict, job_value: Optional[float] = None) -> dict:
    """Compute commission for a lead based on its service type."""
    svc = lead.get("service_type")
    phone = lead.get("prospect_phone_norm") or ""
    email = lead.get("prospect_email_norm") or ""
    va = lead.get("va_user_id")
    cfg = await _resolve_commission_config(va)

    if svc in DIGITAL_SERVICE_TYPES:
        pct = cfg["digital_pct"]
        rev = float(job_value or lead.get("job_value") or 0)
        amount = round(rev * pct / 100.0, 2)
        return {
            "amount": amount,
            "kind": "digital_pct",
            "visit_number": None,
            "notes": f"{pct:g}% of ${rev:.2f} project value ({str(svc).replace('_', ' ')})",
        }

    if svc in ("commercial", "specialty_medical", "specialty_funeral", "specialty_construction", "maintenance_bundle"):
        # All commercial-like services pay the 5% revenue cut. Specialty
        # sub-types (medical/funeral/construction) and maintenance bundles
        # are by nature commercial deals.
        rev = float(job_value or lead.get("job_value") or 0)
        pct = cfg["commercial_pct"]
        amount = round(rev * pct / 100.0, 2)
        return {
            "amount": amount,
            "kind": "commercial_one_time",
            "visit_number": None,
            "notes": f"{pct:g}% of ${rev:.2f} job value ({svc})",
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

    # Flat one-time payouts. Bucketed at either $10 or $25 per the
    # COMMISSION_RATES table at the top of this file.
    if svc in cfg["rates"]:
        amt = cfg["rates"][svc]
        return {"amount": amt, "kind": "one_time", "visit_number": None,
                "notes": f"{svc.replace('_', ' ').title()} flat ${amt:.0f}"}

    return {"amount": 0.0, "kind": "unknown", "visit_number": None,
            "notes": "Service type unknown — manual review needed"}


async def _ensure_commission_for_lead(lead: dict, target_status: str = "calculating") -> Optional[dict]:
    """Create or update a commission record for this lead. Phase 1 lifecycle:
    Booked → status=calculating (record created so VA sees progress)
    Paid → status=pending_approval (surfaces in PM queue, auto-calc amount)"""
    existing = await db.commissions.find_one(
        {"lead_id": lead["lead_id"], "kind": {"$ne": "team_override"}}
    )
    calc = await _calc_commission_for_lead(lead, lead.get("job_value"))
    now = datetime.now(timezone.utc).isoformat()
    # Team override (single-level, SPLIT): net the member, spin up the lead's cut.
    member_amount, override_info = await _apply_team_override(lead, calc["amount"], target_status)
    override_fields = {
        "team_lead_id": (override_info or {}).get("team_lead_id"),
        "override_amount": (override_info or {}).get("override_amount", 0.0),
        "override_rate": (override_info or {}).get("override_rate"),
    }
    if existing:
        # Recompute amount if entering pending_approval. Once approved/paid, freeze.
        if existing.get("status") in ("approved", "paid", "owner_approved"):
            return {k: v for k, v in existing.items() if k != "_id"}
        await db.commissions.update_one(
            {"commission_id": existing["commission_id"]},
            {"$set": {
                "amount": member_amount,
                "kind": calc["kind"],
                "visit_number": calc["visit_number"],
                "calc_notes": calc["notes"],
                "status": target_status,
                "updated_at": now,
                "client_phone_norm": lead.get("prospect_phone_norm"),
                "client_email_norm": lead.get("prospect_email_norm"),
                "job_value": lead.get("job_value"),
                **override_fields,
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
        "amount": member_amount,
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
        **override_fields,
    }
    await db.commissions.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


# ---------------------------------------------------------------------------
# CRM helpers — follow-ups / contact log / comments (shared by pm.py + va.py)
# ---------------------------------------------------------------------------
async def apply_lead_followup(lead: dict, payload: "LeadFollowupIn", actor: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    await db.va_leads.update_one(
        {"lead_id": lead["lead_id"]},
        {"$set": {
            "next_followup_at": payload.due_at or None,
            "followup_note": (payload.note or "").strip() or None,
            "updated_at": now,
        }},
    )
    await _log_lead_activity(
        lead_id=lead["lead_id"], kind="followup_set", actor=actor,
        detail={"due_at": payload.due_at or None, "note": (payload.note or "").strip() or None},
    )
    return await db.va_leads.find_one({"lead_id": lead["lead_id"]})


async def apply_lead_contact(lead: dict, payload: "LeadContactIn", actor: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    await db.va_leads.update_one(
        {"lead_id": lead["lead_id"]},
        {"$set": {"last_contact_at": now, "updated_at": now}, "$inc": {"contact_count": 1}},
    )
    await _log_lead_activity(
        lead_id=lead["lead_id"], kind="contact_logged", actor=actor,
        detail={"method": payload.method, "outcome": payload.outcome.strip()},
    )
    return await db.va_leads.find_one({"lead_id": lead["lead_id"]})


async def apply_lead_comment(lead: dict, payload: "LeadCommentIn", actor: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    await db.va_leads.update_one(
        {"lead_id": lead["lead_id"]},
        {"$set": {"updated_at": now}, "$inc": {"comment_count": 1}},
    )
    await _log_lead_activity(
        lead_id=lead["lead_id"], kind="comment", actor=actor,
        detail={"text": payload.text.strip()},
    )
    if actor.get("role") != "va" and lead.get("va_user_id"):
        await db.notifications.insert_one({
            "notification_id": f"notif_{uuid.uuid4().hex[:10]}",
            "user_id": lead["va_user_id"],
            "kind": "lead_comment",
            "title": f"New comment on '{lead.get('prospect_name')}'",
            "body": payload.text.strip()[:140],
            "created_at": now,
            "read": False,
        })
    return await db.va_leads.find_one({"lead_id": lead["lead_id"]})
