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

# ---------------------------------------------------------------------------
# Fixed Pool Model v2.0 (HCOB_Commission_Structure_v2 — supersedes all prior
# schedules). Every job generates exactly ONE commission pool (base × category
# rate), split 75/15/10 between producing agent / team lead / operations
# manager. The Company never pays beyond the pool.
# ---------------------------------------------------------------------------
BASE_CATEGORY = {
    "routine": "A",
    "deep": "B", "moveout": "B", "apartment_turnover": "B", "estate_cleanout": "B",
    "specialty": "B", "specialty_construction": "B",
    "handyman": "C", "painting": "C", "junk_removal": "C", "pressure_washing": "C",
    "carpet": "C", "landscaping": "C", "maintenance_bundle": "C",
    "commercial": "E", "specialty_medical": "E", "specialty_funeral": "E",
}
CATEGORY_LABELS = {
    "A": "Standard Cleaning",
    "B": "Premium Cleans",
    "C": "Trades & Projects",
    "D": "Recurring Accounts",
    "E": "Commercial Accounts",
    "F": "Virtual Projects",
    "G": "Virtual Retainers",
}
DEFAULT_POOL_RATES = {
    "A": {"agent": 10.0, "senior": 12.5, "elite": 15.0},
    "B": {"agent": 12.0, "senior": 15.0, "elite": 18.0},
    "C": {"agent": 12.0, "senior": 15.0, "elite": 18.0},
    "D": {"early": 15.0, "mid": 10.0, "lifetime": 5.0},  # visits 1-3 / 4-12 / 13+
    "E": {"pct": 5.0},  # % of monthly collected revenue, lifetime of account
    "F": {"agent": 12.0, "senior": 15.0, "elite": 18.0},
    "G": {"pct": 5.0},  # % of monthly retainer revenue, lifetime of retainer
}
POOL_SPLIT = {"agent": 75.0, "lead": 15.0, "ops": 10.0}  # fixed per doc §1 — not editable
TIER_THRESHOLDS = {"senior": 25, "elite": 60}  # cumulative closed + paid jobs
TEAM_LEAD_MIN_MONTHLY_JOBS = 8
TAIL_BREAK_DAYS = 90  # recurring tail ends permanently after 90 days inactive
TIERED_CATEGORIES = ("A", "B", "C", "F")  # pool base = job profit, tier-rated
REVENUE_CATEGORIES = ("E", "G")  # pool base = monthly collected revenue

CLEANER_REFERRAL_TIERS = {1: 20.0, 5: 30.0, 10: 50.0}
CLEANER_REFERRAL_CAP = 100.0
DUPLICATE_REOPEN_DAYS = 90  # leads completed/lost > 90 days old don't block dupes
DEFAULT_DIGITAL_COMMISSION_PCT = 10.0  # legacy display for VA digital pages


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
    is_recurring: bool = False  # Category D (property) / G (digital retainer)
    preferred_datetime: Optional[str] = None  # ISO 8601 date or datetime
    source: LeadSource
    notes: Optional[str] = Field(default=None, max_length=2000)


class LeadStageIn(BaseModel):
    stage: LeadStage
    job_value: Optional[float] = None  # collected revenue — pool base for Cat E/G
    job_profit: Optional[float] = None  # job profit — pool base for Cat A-D/F
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
    is_recurring: Optional[bool] = None
    job_value: Optional[float] = None  # admin only — enforced in route
    job_profit: Optional[float] = None  # admin only — enforced in route
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


class PoolRatesIn(BaseModel):
    pool_rates: dict  # {category: {tier_or_phase_or_pct: float}}


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


async def _find_duplicate_lead(
    phone_norm: str, email_norm: str, va_user_id: Optional[str] = None
) -> Optional[dict]:
    """Return the conflicting active lead, or None if dupe window allows resubmit.
    A completed/paid lead owned by the SAME VA never blocks — that's a repeat
    visit on their own client (Cat D recurring tail)."""
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
        if stage in ("completed", "paid") and va_user_id and d.get("va_user_id") == va_user_id:
            continue  # own client, job done — repeat visit is allowed
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
# Commission calculation — Fixed Pool Model v2.0
# ---------------------------------------------------------------------------
async def _get_digital_commission_pct() -> float:
    s = await db.app_settings.find_one({"_id": "global"}, {"_id": 0, "digital_commission_pct": 1})
    try:
        pct = float((s or {}).get("digital_commission_pct"))
    except (TypeError, ValueError):
        return DEFAULT_DIGITAL_COMMISSION_PCT
    return min(100.0, max(0.0, pct))


def _resolve_category(service_type: Optional[str], is_recurring: bool) -> Optional[str]:
    """Map a lead onto the seven-category service catalog (doc §4)."""
    if service_type in ("commercial", "specialty_medical", "specialty_funeral"):
        return "E"
    if service_type in DIGITAL_SERVICE_TYPES:
        return "G" if is_recurring else "F"
    if is_recurring:
        return "D"
    return BASE_CATEGORY.get(service_type)


async def _get_pool_rates() -> dict:
    """Effective pool rates: hardcoded doc defaults ← app_settings.pool_rates."""
    s = await db.app_settings.find_one({"_id": "global"}, {"_id": 0, "pool_rates": 1})
    saved = (s or {}).get("pool_rates") or {}
    rates: dict = {}
    for cat, defaults in DEFAULT_POOL_RATES.items():
        merged = dict(defaults)
        for k, v in (saved.get(cat) or {}).items():
            if k in merged:
                try:
                    merged[k] = min(100.0, max(0.0, float(v)))
                except (TypeError, ValueError):
                    pass
        rates[cat] = merged
    return rates


def _tier_for_count(paid_jobs: int) -> str:
    if paid_jobs >= TIER_THRESHOLDS["elite"]:
        return "elite"
    if paid_jobs >= TIER_THRESHOLDS["senior"]:
        return "senior"
    return "agent"


async def _va_tier(va_user_id: Optional[str]) -> dict:
    """Agent tier from cumulative closed + paid jobs. Never moves backward
    (count is cumulative). Existing pre-v2 paid leads count as credit (§10)."""
    n = 0
    if va_user_id:
        n = await db.va_leads.count_documents({
            "va_user_id": va_user_id, "stage": "paid", "deleted_at": {"$in": [None, ""]},
        })
    tier = _tier_for_count(n)
    next_tier, to_next = None, 0
    if tier == "agent":
        next_tier, to_next = "senior", TIER_THRESHOLDS["senior"] - n
    elif tier == "senior":
        next_tier, to_next = "elite", TIER_THRESHOLDS["elite"] - n
    return {"tier": tier, "paid_jobs": n, "next_tier": next_tier, "jobs_to_next": max(0, to_next)}


async def _recurring_visit_number(
    va_user_id: str, phone_norm: str, email_norm: str, exclude_lead_id: Optional[str]
) -> int:
    """Visit # in this client's recurring tail (Cat D). Legacy 'routine' leads
    count toward the chain so existing recurring clients convert at their
    current visit count (§10). A gap > TAIL_BREAK_DAYS ends the old tail
    permanently — the chain restarts at visit 1 (§6)."""
    or_client = []
    if phone_norm:
        or_client.append({"prospect_phone_norm": phone_norm})
    if email_norm:
        or_client.append({"prospect_email_norm": email_norm})
    if not or_client:
        return 1
    q = {
        "va_user_id": va_user_id,
        "stage": {"$in": ["completed", "paid"]},
        "lead_id": {"$ne": exclude_lead_id},
        "deleted_at": {"$in": [None, ""]},
        "$and": [
            {"$or": [{"is_recurring": True}, {"service_type": "routine"}]},
            {"$or": or_client},
        ],
    }
    stamps = []
    async for d in db.va_leads.find(q, {"_id": 0, "stage_changed_at": 1, "created_at": 1}):
        stamps.append(d.get("stage_changed_at") or d.get("created_at") or "")
    if not stamps:
        return 1
    try:
        ts = datetime.fromisoformat(max(stamps))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - ts > timedelta(days=TAIL_BREAK_DAYS):
            return 1
    except Exception:
        pass
    return len(stamps) + 1


async def _paid_jobs_between(va_user_id: str, start_iso: str, end_iso: str) -> int:
    return await db.va_leads.count_documents({
        "va_user_id": va_user_id,
        "stage": "paid",
        "deleted_at": {"$in": [None, ""]},
        "stage_changed_at": {"$gte": start_iso, "$lt": end_iso},
    })


async def _team_lead_status(lead_user: Optional[dict]) -> dict:
    """Auto qualification check per doc §7: approved + is_team_lead + Senior
    tier + personal production ≥ 8 paid jobs/month. Below minimum for two
    consecutive months → override pauses (retained by Company) until
    production resumes. Newly promoted leads get a grace window."""
    out = {
        "eligible": False, "reason": None, "tier": None, "production": None,
        "min_monthly": TEAM_LEAD_MIN_MONTHLY_JOBS, "grace": False,
    }
    if not lead_user or not lead_user.get("is_team_lead"):
        out["reason"] = "not_team_lead"
        return out
    if (lead_user.get("va_status") or "") != "approved":
        out["reason"] = "not_approved"
        return out
    t = await _va_tier(lead_user["user_id"])
    out["tier"] = t
    if t["tier"] == "agent":
        out["reason"] = "below_senior_tier"
        return out
    today = datetime.now(timezone.utc).date()
    cur_start = today.replace(day=1)
    m1_start = (cur_start - timedelta(days=1)).replace(day=1)
    m2_start = (m1_start - timedelta(days=1)).replace(day=1)
    uid = lead_user["user_id"]
    cur = await _paid_jobs_between(uid, cur_start.isoformat(), (today + timedelta(days=1)).isoformat())
    m1 = await _paid_jobs_between(uid, m1_start.isoformat(), cur_start.isoformat())
    m2 = await _paid_jobs_between(uid, m2_start.isoformat(), m1_start.isoformat())
    out["production"] = {"current_month": cur, "last_month": m1, "prev_month": m2}
    since = lead_user.get("team_lead_since") or ""
    out["grace"] = not since or since >= m2_start.isoformat()
    minj = TEAM_LEAD_MIN_MONTHLY_JOBS
    if m1 < minj and m2 < minj and cur < minj and not out["grace"]:
        out["reason"] = "production_paused"
        return out
    out["eligible"] = True
    return out


async def _ops_manager_user() -> Optional[dict]:
    """The Operations Manager receives 10% of every pool (doc §1)."""
    return await db.users.find_one(
        {"role": "admin", "is_program_manager": True},
        {"_id": 0, "user_id": 1, "name": 1, "email": 1},
    )


async def _calc_pool_for_lead(lead: dict) -> dict:
    """commission_pool = base × category_rate(tier). Base is job profit for
    Cat A-D/F, monthly collected revenue for Cat E/G."""
    svc = lead.get("service_type")
    cat = _resolve_category(svc, bool(lead.get("is_recurring")))
    va = lead.get("va_user_id")
    tier_info = await _va_tier(va)
    tier = tier_info["tier"]
    visit, phase = None, None
    if cat in TIERED_CATEGORIES:
        rates = await _get_pool_rates()
        rate = float(rates[cat][tier])
        base = float(lead.get("job_profit") or 0)
        detail = f"{tier} tier"
    elif cat == "D":
        rates = await _get_pool_rates()
        visit = await _recurring_visit_number(
            va, lead.get("prospect_phone_norm") or "", lead.get("prospect_email_norm") or "",
            lead.get("lead_id"),
        )
        phase = "early" if visit <= 3 else ("mid" if visit <= 12 else "lifetime")
        rate = float(rates["D"][phase])
        base = float(lead.get("job_profit") or 0)
        detail = f"visit {visit} · {phase} tail"
    elif cat in REVENUE_CATEGORIES:
        rates = await _get_pool_rates()
        rate = float(rates[cat]["pct"])
        base = float(lead.get("job_value") or lead.get("job_profit") or 0)
        detail = "monthly collected revenue"
    else:
        return {"category": None, "tier": tier, "rate": 0.0, "base": 0.0, "pool": 0.0,
                "visit_number": None, "phase": None,
                "notes": "Service type unknown — manual review needed"}
    pool = round(base * rate / 100.0, 2)
    base_label = "revenue" if cat in REVENUE_CATEGORIES else "job profit"
    notes = (f"Cat {cat} ({CATEGORY_LABELS[cat]}) — pool {rate:g}% of ${base:.2f} "
             f"{base_label} = ${pool:.2f} ({detail})")
    return {"category": cat, "tier": tier, "rate": rate, "base": base, "pool": pool,
            "visit_number": visit, "phase": phase, "notes": notes}


_FROZEN_STATUSES = ("approved", "paid", "owner_approved")


async def _upsert_pool_side(
    lead: dict, *, kind: str, recipient: Optional[dict], amount: float,
    calc: dict, target_status: str, note: str,
) -> float:
    """Idempotent upsert of the team_override / ops_share record for one lead.
    Frozen (approved/paid) records are never touched. Returns the live amount."""
    q: dict = {"lead_id": lead["lead_id"], "kind": kind}
    if kind == "team_override":
        q["level"] = 1
    existing = await db.commissions.find_one(q)
    if existing and existing.get("status") in _FROZEN_STATUSES:
        return round(float(existing.get("amount") or 0), 2)
    if amount <= 0 or not recipient:
        if existing:
            await db.commissions.delete_one({"commission_id": existing["commission_id"]})
        return 0.0
    now = datetime.now(timezone.utc).isoformat()
    base = {
        "lead_id": lead["lead_id"],
        "kind": kind,
        "level": 1 if kind == "team_override" else None,
        "engine": "pool_v2",
        "va_user_id": recipient["user_id"],
        "va_name": recipient.get("name"),
        "prospect_name": lead.get("prospect_name"),
        "service_type": lead.get("service_type"),
        "category": calc["category"],
        "pool_amount": calc["pool"],
        "pool_rate": calc["rate"],
        "amount": amount,
        "source_va_user_id": lead.get("va_user_id"),
        "source_va_name": lead.get("va_name"),
        "status": target_status,
        "calc_notes": note,
        "job_value": lead.get("job_value"),
        "job_profit": lead.get("job_profit"),
        "updated_at": now,
    }
    if existing:
        await db.commissions.update_one({"commission_id": existing["commission_id"]}, {"$set": base})
    else:
        await db.commissions.insert_one({
            "commission_id": f"comm_{uuid.uuid4().hex[:12]}",
            **base,
            "visit_number": calc.get("visit_number"),
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


async def _ensure_commission_for_lead(lead: dict, target_status: str = "calculating") -> Optional[dict]:
    """Create/refresh the pool split (agent 75% / lead 15% / ops 10%) for a
    lead. Booked → calculating; Paid → pending_approval. Frozen records never
    change. Legacy (pre-pool) commissions already past 'calculating' are
    honored at prior rates (transition rule §10)."""
    existing = await db.commissions.find_one(
        {"lead_id": lead["lead_id"], "kind": {"$nin": ["team_override", "ops_share"]}}
    )
    if existing and existing.get("status") in _FROZEN_STATUSES:
        return {k: v for k, v in existing.items() if k != "_id"}
    if (
        existing
        and existing.get("engine") != "pool_v2"
        and existing.get("status") not in (None, "calculating", "rejected")
    ):
        # Earned under the prior structure but not yet paid — honored as-is.
        return {k: v for k, v in existing.items() if k != "_id"}

    calc = await _calc_pool_for_lead(lead)
    pool = calc["pool"]
    now = datetime.now(timezone.utc).isoformat()
    agent_amount = round(pool * POOL_SPLIT["agent"] / 100.0, 2)

    # --- Team Lead 15% — only if the closer's lead passes auto-qualification.
    lead_user, lead_status = None, None
    member = await db.users.find_one(
        {"user_id": lead.get("va_user_id")}, {"_id": 0, "team_lead_id": 1}
    )
    tl_id = (member or {}).get("team_lead_id")
    if tl_id and tl_id != lead.get("va_user_id"):
        lead_user = await db.users.find_one(
            {"user_id": tl_id},
            {"_id": 0, "user_id": 1, "name": 1, "is_team_lead": 1, "va_status": 1, "team_lead_since": 1},
        )
        lead_status = await _team_lead_status(lead_user)
    lead_eligible = bool(lead_status and lead_status["eligible"])
    lead_amount = round(pool * POOL_SPLIT["lead"] / 100.0, 2) if lead_eligible else 0.0

    ops_user = await _ops_manager_user()
    ops_amount = round(pool * POOL_SPLIT["ops"] / 100.0, 2) if ops_user else 0.0

    # VERIFICATION RULE (§9): agent + lead + ops can never exceed the pool.
    if agent_amount + lead_amount + ops_amount > pool:
        agent_amount = max(0.0, round(pool - lead_amount - ops_amount, 2))

    lead_amount = await _upsert_pool_side(
        lead, kind="team_override", recipient=lead_user if lead_eligible else None,
        amount=lead_amount, calc=calc, target_status=target_status,
        note=(f"Team Lead {POOL_SPLIT['lead']:g}% of ${pool:.2f} pool — "
              f"{lead.get('va_name') or 'member'}'s job"),
    )
    ops_amount = await _upsert_pool_side(
        lead, kind="ops_share", recipient=ops_user, amount=ops_amount,
        calc=calc, target_status=target_status,
        note=(f"Operations {POOL_SPLIT['ops']:g}% of ${pool:.2f} pool — "
              f"{lead.get('va_name') or 'agent'}'s job"),
    )

    retained = 0.0
    lead_share_reason = None
    if not lead_eligible:
        lead_share_reason = (lead_status or {}).get("reason") if lead_status else "no_team_lead"
        if pool > 0:
            retained = round(pool * POOL_SPLIT["lead"] / 100.0, 2)

    agent_note = calc["notes"] + f" · Agent {POOL_SPLIT['agent']:g}% = ${agent_amount:.2f}"
    if retained:
        agent_note += f" · Lead share ${retained:.2f} retained by Company ({lead_share_reason})"

    fields = {
        "va_user_id": lead["va_user_id"],
        "va_name": lead.get("va_name"),
        "prospect_name": lead.get("prospect_name"),
        "service_type": lead.get("service_type"),
        "client_phone_norm": lead.get("prospect_phone_norm"),
        "client_email_norm": lead.get("prospect_email_norm"),
        "amount": agent_amount,
        "kind": "pool_agent",
        "engine": "pool_v2",
        "category": calc["category"],
        "tier": calc["tier"],
        "pool_amount": pool,
        "pool_rate": calc["rate"],
        "base_amount": calc["base"],
        "visit_number": calc["visit_number"],
        "tail_phase": calc["phase"],
        "calc_notes": agent_note,
        "team_lead_id": lead_user["user_id"] if lead_eligible else None,
        "lead_share": lead_amount,
        "lead_share_retained": retained,
        "lead_share_reason": lead_share_reason,
        "ops_share_amount": ops_amount,
        "status": target_status,
        "job_value": lead.get("job_value"),
        "job_profit": lead.get("job_profit"),
        "updated_at": now,
    }
    if existing:
        await db.commissions.update_one(
            {"commission_id": existing["commission_id"]}, {"$set": fields}
        )
        fresh = await db.commissions.find_one({"commission_id": existing["commission_id"]})
        return {k: v for k, v in fresh.items() if k != "_id"} if fresh else None
    doc = {
        "commission_id": f"comm_{uuid.uuid4().hex[:12]}",
        "lead_id": lead["lead_id"],
        **fields,
        "pm_action_at": None,
        "pm_action_note": None,
        "owner_action_at": None,
        "paid_at": None,
        "payout_reference": None,
        "payout_method": None,
        "created_at": now,
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
