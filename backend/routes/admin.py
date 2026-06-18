"""Admin routes — workers management, requests queue, stats, pay defaults,
timesheets (approve / edit / unapprove + per-acceptance pay override).

Wiring in server.py:
    from routes.admin import router as admin_router
    api.include_router(admin_router)

Helpers `_set_worker_status`, `_completed_gigs_by_worker_and_category`, and
`_parse_admin_dt` are local to this module — not re-exported.
Local Pydantic models (AdminProfileUpdateIn / AdminGigNoteIn / WorkerMessageIn /
AcceptanceRoleIn / AdminCreateIn / AdminRoleUpdateIn) live here because they
are only referenced by admin routes.
"""
import os
import re
import uuid
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from config import db, logger
from auth_deps import (
    hash_password,
    require_admin,
    _get_user_by_id,
    _profile_missing_fields,
    _worker_approval_blockers,
    _worker_is_fully_active,
    _worker_rating_stats,
)
from constants import (
    WORKER_SKILLS,
    SKILL_LABELS,
    AVAILABILITY_OPTIONS,
    EXPERIENCE_OPTIONS,
    TSHIRT_SIZES,
    GIG_CATEGORY_TO_SKILLS,
)
from models import (
    GigCategory,
    ProfileUpdateIn,
    WorkerStatusIn,
    WorkerPayIn,
    AcceptancePayIn,
    AdminResetPasswordIn,
    TimesheetApproveIn,
    TimesheetEditIn,
    AcceptanceNoShowIn,
    AcceptanceMarkCompletedIn,
)
from notifications import _send_user_email, _public_base, is_blast_disabled, BLAST_COOLDOWN_SECONDS
from va_commission import require_owner
from routes.gigs import (
    _resolve_pay,
    _resolve_break_minutes,
    _compute_paid_hours,
    _compute_earnings,
    _effective_status,
)
from routes.profile import _upload_user_image

router = APIRouter()


@router.get("/admin/workers")
async def list_workers(
    status: Optional[str] = Query(None),
    skills: Optional[str] = Query(None, description="Comma-separated skill values"),
    availability: Optional[str] = Query(None, description="Comma-separated availability values"),
    zip_code: Optional[str] = Query(None, description="Exact 5-digit ZIP"),
    zip_prefix: Optional[str] = Query(None, description="First N digits of ZIP for 'nearby' filter"),
    vehicle: Optional[str] = Query(None, description="one of: any, car, truck, cdl"),
    profile_complete: Optional[bool] = Query(None),
    min_rating: Optional[float] = Query(None, ge=0, le=5, description="Hide workers below this avg rating"),
    available_now: Optional[bool] = Query(None, description="Only workers who flipped the 'I'm available now' switch"),
    search: Optional[str] = Query(None, description="Free-text search across name/email/phone"),
    admin: dict = Depends(require_admin),
):
    # Build the MongoDB filter. CRITICAL: every "this OR that" filter (status
    # back-compat, vehicle 'any', free-text search) needs its OWN $or block —
    # writing them all into a single $or key would just append disjuncts, which
    # is why the search box was returning every worker before. We collect each
    # disjunctive filter as a separate list and AND them all together at the
    # bottom.
    query: dict = {"role": "worker"}
    or_blocks: list[list[dict]] = []

    if status == "pending":
        query["worker_status"] = "pending"
    elif status == "approved":
        # Treat missing field as approved for back-compat
        or_blocks.append([
            {"worker_status": "approved"},
            {"worker_status": {"$exists": False}},
        ])
    elif status in ("rejected", "suspended"):
        query["worker_status"] = status

    if skills:
        skill_list = [s.strip() for s in skills.split(",") if s.strip()]
        if skill_list:
            query["skills"] = {"$in": skill_list}
    if availability:
        av_list = [a.strip() for a in availability.split(",") if a.strip()]
        if av_list:
            query["availability"] = {"$in": av_list}
    if zip_code:
        query["zip_code"] = zip_code.strip()
    elif zip_prefix:
        # ZIP starts-with for a "nearby" filter (no geocoding required)
        prefix = zip_prefix.strip()
        if prefix:
            query["zip_code"] = {"$regex": f"^{re.escape(prefix)}"}

    if vehicle == "car":
        query["has_car"] = True
    elif vehicle == "truck":
        query["has_truck"] = True
    elif vehicle == "cdl":
        query["has_cdl"] = True
    elif vehicle == "any":
        or_blocks.append([
            {"has_car": True}, {"has_truck": True}, {"has_cdl": True}
        ])

    if search:
        s = re.escape(search.strip())
        if s:
            or_blocks.append([
                {"name": {"$regex": s, "$options": "i"}},
                {"email": {"$regex": s, "$options": "i"}},
                {"phone": {"$regex": s, "$options": "i"}},
            ])

    # Collapse the disjunctive blocks: 0 blocks → no $or; 1 block → top-level
    # $or; 2+ blocks → wrap in $and so each block is independently required.
    if len(or_blocks) == 1:
        query["$or"] = or_blocks[0]
    elif len(or_blocks) > 1:
        query["$and"] = [{"$or": ob} for ob in or_blocks]

    workers = await db.users.find(
        query, {"_id": 0, "password_hash": 0}
    ).sort("created_at", -1).to_list(1000)

    # Re-evaluate "available_now" with auto-expiry semantics. A worker is
    # actually available if both `available_now=True` AND `available_until`
    # is in the future. We return both fields to the client so they can show
    # countdowns / status pills.
    now_utc = datetime.now(timezone.utc)
    for w in workers:
        if w.get("available_now"):
            until = w.get("available_until")
            try:
                until_dt = datetime.fromisoformat(str(until).replace("Z", "+00:00")) if until else None
            except Exception:
                until_dt = None
            if not until_dt or until_dt < now_utc:
                w["available_now"] = False
                w["available_until"] = None
        else:
            w["available_now"] = bool(w.get("available_now"))
            w.setdefault("available_until", None)

    # Enrich with computed profile_complete + missing + rating stats
    for w in workers:
        miss = _profile_missing_fields(w)
        w["profile_complete"] = len(miss) == 0
        w["profile_missing_fields"] = miss
        w["approval_blockers"] = _worker_approval_blockers(w)
        w["fully_active"] = _worker_is_fully_active(w)
        stats = await _worker_rating_stats(w["user_id"])
        w.update(stats)

    if profile_complete is True:
        workers = [w for w in workers if w["profile_complete"]]
    elif profile_complete is False:
        workers = [w for w in workers if not w["profile_complete"]]

    if min_rating is not None:
        # Only include workers WITH a rating and at or above threshold. If
        # they have no rating yet, exclude — matches admin intent of "show me
        # 4-star+ workers."
        workers = [w for w in workers if (w.get("rating_avg") or 0) >= min_rating]

    if available_now is True:
        workers = [w for w in workers if w.get("available_now")]
    elif available_now is False:
        workers = [w for w in workers if not w.get("available_now")]

    return workers


@router.get("/admin/workers/match")
async def match_workers_for_gig(
    category: Optional[GigCategory] = Query(None),
    zip_code: Optional[str] = Query(None, description="Gig ZIP — matched against worker zip_code"),
    zip_prefix_length: int = Query(3, ge=1, le=5),
    availability: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    admin: dict = Depends(require_admin),
):
    """Suggest workers for a gig admin is about to create.

    Scoring:
    - +3 skills overlap (any skill in GIG_CATEGORY_TO_SKILLS[category])
    - +3 exact zip match, +1 same zip prefix (default first 3 digits ~ SCF area)
    - +1 ID verified, +1 availability overlap, +1 has any vehicle
    - +1 per 3 completed gigs in this category (capped at +5) — proven track record
    - profile_complete is required (returns []  when no candidate matches)
    """
    cand = await db.users.find(
        {"role": "worker"}, {"_id": 0, "password_hash": 0}
    ).to_list(2000)

    target_skills: List[str] = (
        GIG_CATEGORY_TO_SKILLS.get(category, []) if category else []
    )
    avail_list = [a.strip() for a in (availability or "").split(",") if a.strip()]
    zip_pref = (zip_code or "")[:zip_prefix_length] if zip_code else ""

    # Pre-compute completed-by-category for every worker so we can bump
    # experienced candidates higher. Single Mongo query, in-memory bucket.
    completed_by_category = await _completed_gigs_by_worker_and_category()

    matches: List[dict] = []
    for w in cand:
        if _effective_status(w) in ("rejected", "suspended"):
            continue
        miss = _profile_missing_fields(w)
        if miss:
            continue
        score = 0
        reasons: List[str] = []

        worker_skills = w.get("skills") or []
        skill_overlap = [s for s in worker_skills if s in target_skills]
        if target_skills:
            if skill_overlap:
                score += 3
                reasons.append(
                    f"skills: {', '.join(SKILL_LABELS.get(s, s) for s in skill_overlap)}"
                )
            else:
                continue  # require skill match if category given

        wzip = (w.get("zip_code") or "").strip()
        if zip_code and wzip == zip_code:
            score += 3
            reasons.append(f"same ZIP {zip_code}")
        elif zip_pref and wzip.startswith(zip_pref):
            score += 1
            reasons.append(f"nearby ZIP ({wzip})")

        if avail_list:
            wav = w.get("availability") or []
            if any(a in wav for a in avail_list):
                score += 1
                reasons.append("availability matches")

        if w.get("id_verified"):
            score += 1
        if w.get("has_car") or w.get("has_truck") or w.get("has_cdl"):
            score += 1
            reasons.append("has vehicle")

        # Category track-record — +1 per 3 completed, capped at +5
        cat_done = (
            completed_by_category.get(w["user_id"], {}).get(category, 0)
            if category else 0
        )
        if cat_done > 0:
            score += min(5, cat_done // 3 + 1)
            reasons.append(
                f"{cat_done} {category} gig{'s' if cat_done != 1 else ''} done"
            )

        if score == 0:
            continue
        matches.append({
            "user_id": w["user_id"],
            "name": w.get("name"),
            "email": w.get("email"),
            "phone": w.get("phone"),
            "zip_code": wzip,
            "skills": worker_skills,
            "id_verified": bool(w.get("id_verified")),
            "category_completed_count": cat_done,
            "score": score,
            "reasons": reasons,
        })

    matches.sort(key=lambda m: m["score"], reverse=True)
    return matches[:limit]


async def _completed_gigs_by_worker_and_category() -> dict:
    """Build a {worker_id: {category: count}} dict of completed gigs (i.e.
    acceptances that have been clocked out). One aggregate scan — caller can
    cache the result for the duration of a request."""
    accs = await db.gig_acceptances.find(
        {"clock_out_at": {"$ne": None}}, {"_id": 0, "worker_id": 1, "gig_id": 1}
    ).to_list(50000)
    if not accs:
        return {}
    gig_ids = list({a["gig_id"] for a in accs})
    gigs = await db.gigs.find(
        {"gig_id": {"$in": gig_ids}}, {"_id": 0, "gig_id": 1, "category": 1}
    ).to_list(50000)
    cat_by_gig = {g["gig_id"]: g.get("category") for g in gigs}
    out: dict = {}
    for a in accs:
        cat = cat_by_gig.get(a["gig_id"])
        if not cat:
            continue
        out.setdefault(a["worker_id"], {})
        out[a["worker_id"]][cat] = out[a["worker_id"]].get(cat, 0) + 1
    return out


@router.get("/admin/workers/{user_id}")
async def get_worker(user_id: str, admin: dict = Depends(require_admin)):
    w = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    if not w:
        raise HTTPException(404, "Worker not found")
    accepted = await db.gig_acceptances.find(
        {"worker_id": user_id}, {"_id": 0}
    ).sort("accepted_at", -1).to_list(500)
    if accepted:
        gig_ids = list({a["gig_id"] for a in accepted})
        gigs = await db.gigs.find(
            {"gig_id": {"$in": gig_ids}},
            {"_id": 0},
        ).to_list(500)
        gmap = {g["gig_id"]: g for g in gigs}
        for a in accepted:
            g = gmap.get(a["gig_id"]) or {}
            a["gig_title"] = g.get("title")
            a["gig_category"] = g.get("category")
            a["gig_scheduled_date"] = g.get("scheduled_date")
            a["gig_pay_rate"] = g.get("pay_rate")
            a["gig_pay_type"] = g.get("pay_type")
            # If never clocked out, project resolved pay so admin can see what
            # the worker WOULD earn at current rate.
            if a.get("earnings") is None:
                pay = _resolve_pay(a, w, g)
                a["pay_rate_effective"] = pay["pay_rate"]
                a["pay_type_effective"] = pay["pay_type"]
                br = _resolve_break_minutes(a, g)
                a["break_minutes_effective"] = br
                a["paid_hours"] = _compute_paid_hours(a.get("hours_worked"), br)
                a["projected_earnings"] = _compute_earnings(
                    pay["pay_rate"], pay["pay_type"], a.get("hours_worked"), br
                )
            else:
                br = _resolve_break_minutes(a, g)
                a["break_minutes_effective"] = br
                a["paid_hours"] = _compute_paid_hours(a.get("hours_worked"), br)
    w["accepted_gigs"] = accepted
    # Attach rating aggregates so the WorkerDetail header can render stars.
    w.update(await _worker_rating_stats(user_id))
    # Mirror enrichment from list endpoint so detail page badges are truthful
    miss = _profile_missing_fields(w)
    w["profile_complete"] = len(miss) == 0
    w["profile_missing_fields"] = miss
    w["approval_blockers"] = _worker_approval_blockers(w)
    w["fully_active"] = _worker_is_fully_active(w)
    return w


@router.get("/admin/requests")
async def list_pending_requests(
    search: Optional[str] = Query(None, description="Free-text — worker name/email/phone or gig title/location"),
    admin: dict = Depends(require_admin),
):
    """Return ALL pending gig requests across the platform, flat, sorted oldest
    first. Enriched with gig and worker fields so admin can decide inline.

    Optional `search` is case-insensitive and matches against the enriched
    worker + gig fields. Filtering is done in-memory after enrichment so admin
    can search across both sides in one go."""
    rows = await db.gig_acceptances.find(
        {"status": "requested"}, {"_id": 0}
    ).sort("requested_at", 1).to_list(1000)
    if not rows:
        return []
    gig_ids = list({r["gig_id"] for r in rows})
    worker_ids = list({r["worker_id"] for r in rows})
    gigs = await db.gigs.find(
        {"gig_id": {"$in": gig_ids}},
        {
            "_id": 0,
            "gig_id": 1,
            "title": 1,
            "category": 1,
            "subcategory": 1,
            "location": 1,
            "scheduled_date": 1,
            "scheduled_at": 1,
            "pay_rate": 1,
            "pay_type": 1,
            "slots": 1,
            "slots_filled": 1,
            "status": 1,
        },
    ).to_list(1000)
    gmap = {g["gig_id"]: g for g in gigs}
    workers = await db.users.find(
        {"user_id": {"$in": worker_ids}}, {"_id": 0, "password_hash": 0}
    ).to_list(1000)
    wmap = {w["user_id"]: w for w in workers}
    for r in rows:
        g = gmap.get(r["gig_id"]) or {}
        w = wmap.get(r["worker_id"]) or {}
        r["gig"] = g
        r["worker_name"] = w.get("name")
        r["worker_email"] = w.get("email")
        r["worker_phone"] = w.get("phone")
        r["worker_id_verified"] = w.get("id_verified", False)
        r["worker_status"] = w.get("worker_status", "approved")

    if search:
        q = search.strip().lower()
        if q:
            rows = [
                r for r in rows
                if q in (r.get("worker_name") or "").lower()
                or q in (r.get("worker_email") or "").lower()
                or q in (r.get("worker_phone") or "").lower()
                or q in ((r.get("gig") or {}).get("title") or "").lower()
                or q in ((r.get("gig") or {}).get("location") or "").lower()
            ]
    return rows


class AdminProfileUpdateIn(BaseModel):
    """All fields are optional — admin sends only what's changing. Mirrors
    ProfileUpdateIn + admin-only fields (worker_status, id_verified, email)."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    bio: Optional[str] = None
    skills: Optional[List[str]] = None
    zip_code: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    date_of_birth: Optional[str] = None
    has_car: Optional[bool] = None
    has_truck: Optional[bool] = None
    has_cdl: Optional[bool] = None
    experience_level: Optional[str] = None
    availability: Optional[List[str]] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    tshirt_size: Optional[str] = None
    # Admin-only overrides
    worker_status: Optional[str] = None
    id_verified: Optional[bool] = None
    # Admin sticky-note (internal — workers never see this)
    admin_note: Optional[str] = None


class AdminGigNoteIn(BaseModel):
    """Per-gig private admin note about a worker on a specific acceptance.
    Separate from the rating note — used for ops context like 'arrived late'
    or 'client requested this worker again'."""
    note: Optional[str] = None


class WorkerMessageIn(BaseModel):
    """One-way message from admin → worker. Surfaces in /me/notifications and
    on the worker's gig detail page when gig_id is set."""
    body: str
    title: Optional[str] = None
    gig_id: Optional[str] = None


# Per-gig role for a worker. `manager` gets a badge + sees the crew's contact
# info (next iteration); `worker` is the default.
GIG_ROLES = ["worker", "manager", "lead", "trainer"]
GIG_ROLE_LABELS = {
    "worker": "Worker",
    "manager": "Manager",
    "lead": "Lead",
    "trainer": "Trainer",
}


class AcceptanceRoleIn(BaseModel):
    role: str


class AdminCreateIn(BaseModel):
    """Create a new admin user from Settings → Admin users."""
    name: str
    email: str
    password: str
    is_read_only: Optional[bool] = False


class AdminRoleUpdateIn(BaseModel):
    """Toggle read-only or promote/demote between admin↔worker."""
    is_read_only: Optional[bool] = None
    promote_to_admin: Optional[bool] = None
    demote_to_worker: Optional[bool] = None


@router.post("/admin/workers/{user_id}/verify-id")
async def verify_worker_id(user_id: str, admin: dict = Depends(require_admin)):
    await db.users.update_one(
        {"user_id": user_id}, {"$set": {"id_verified": True}}
    )
    return {"ok": True}


@router.put("/admin/workers/{user_id}/profile")
async def admin_update_worker_profile(
    user_id: str,
    payload: AdminProfileUpdateIn,
    admin: dict = Depends(require_admin),
):
    """Admin override editor — set any field on a worker's profile. Validates
    enum-ish fields identically to the worker self-serve endpoint. Used when
    a worker can't update their own profile (system glitch, missing info,
    etc)."""
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(404, "Worker not found")
    if user.get("role") == "admin":
        raise HTTPException(400, "Use the admin self-service flow to edit an admin")

    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}

    # Validate enum-ish fields (same rules as PUT /profile — silently drop
    # unknown skill/availability values so legacy/free-text data doesn't break
    # admin saves).
    if "skills" in updates:
        updates["skills"] = [s for s in updates["skills"] if s in WORKER_SKILLS]
    if "availability" in updates:
        updates["availability"] = [a for a in updates["availability"] if a in AVAILABILITY_OPTIONS]
    if "experience_level" in updates and updates["experience_level"] and updates["experience_level"] not in EXPERIENCE_OPTIONS:
        raise HTTPException(400, f"experience_level must be one of {EXPERIENCE_OPTIONS}")
    if "tshirt_size" in updates and updates["tshirt_size"] and updates["tshirt_size"] not in TSHIRT_SIZES:
        raise HTTPException(400, f"tshirt_size must be one of {TSHIRT_SIZES}")
    if "zip_code" in updates and updates["zip_code"]:
        z = updates["zip_code"].strip()
        if not (z.isdigit() and len(z) == 5):
            raise HTTPException(400, "zip_code must be a 5-digit US ZIP code")
        updates["zip_code"] = z
    if "worker_status" in updates and updates["worker_status"] not in (
        "approved", "pending", "rejected", "suspended"
    ):
        raise HTTPException(400, "worker_status must be approved|pending|rejected|suspended")
    if "worker_status" in updates and updates["worker_status"] == "approved":
        # Same gate as _set_worker_status — keep the two write paths in sync.
        # Apply prospective updates first so admins can fix profile/id_verified
        # in the SAME PATCH call without needing two round trips.
        merged = {**user, **updates}
        blockers = _worker_approval_blockers(merged)
        if blockers:
            raise HTTPException(
                400,
                "Cannot approve worker yet — "
                + "; ".join(blockers)
                + ". Complete profile + verify ID before approving.",
            )
    if "email" in updates and updates["email"]:
        new_email = updates["email"].strip().lower()
        if "@" not in new_email or "." not in new_email:
            raise HTTPException(400, "Invalid email")
        # Make sure no other user has that email
        existing = await db.users.find_one(
            {"email": new_email, "user_id": {"$ne": user_id}}
        )
        if existing:
            raise HTTPException(400, "That email is already in use by another account")
        updates["email"] = new_email

    if updates:
        # If status changed, also stamp the audit-ish fields & kill sessions for
        # rejected/suspended so the worker doesn't keep using the app.
        if "worker_status" in updates:
            updates["worker_status_at"] = datetime.now(timezone.utc).isoformat()
            updates["worker_status_by"] = admin["email"]
        await db.users.update_one({"user_id": user_id}, {"$set": updates})
        if updates.get("worker_status") in ("rejected", "suspended"):
            await db.sessions.delete_many({"user_id": user_id})

    logger.info(
        f"Admin {admin['email']} edited worker {user.get('email')} profile: "
        f"{list(updates.keys())}"
    )
    # Enrich the response so the frontend's WorkerDetail page sees truthful
    # approval state immediately after save (no stale badge between save and
    # the next list refetch).
    fresh = await _get_user_by_id(user_id)
    if fresh:
        miss = _profile_missing_fields(fresh)
        fresh["profile_complete"] = len(miss) == 0
        fresh["profile_missing_fields"] = miss
        fresh["approval_blockers"] = _worker_approval_blockers(fresh)
        fresh["fully_active"] = _worker_is_fully_active(fresh)
    return fresh


@router.post("/admin/workers/{user_id}/id-upload")
async def admin_upload_worker_id(
    user_id: str,
    file: UploadFile = File(...),
    admin: dict = Depends(require_admin),
):
    """Upload an ID image on behalf of a worker (e.g. they emailed a photo
    instead of uploading in the app). The ID lands UNverified — admin must
    still hit the Verify button afterwards if it's accepted."""
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(404, "Worker not found")
    if user.get("role") != "worker":
        raise HTTPException(400, "Only worker IDs can be uploaded this way")
    path = await _upload_user_image(user_id, "id", file)
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"id_image_path": path, "id_verified": False}},
    )
    logger.info(f"Admin {admin['email']} uploaded ID for worker {user.get('email')}")
    return {"id_image_path": path}


async def _set_worker_status(
    user_id: str, status: str, admin: dict, kill_sessions: bool = False
) -> dict:
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(404, "Worker not found")
    if user.get("role") == "admin":
        raise HTTPException(400, "Cannot change status of an admin user")
    # Gate: workers can't be 'approved' until ID is on file + verified AND
    # the required profile fields are filled in. Keeps the badge truthful and
    # mirrors the gates enforced at /gigs/accept.
    if status == "approved":
        blockers = _worker_approval_blockers(user)
        if blockers:
            raise HTTPException(
                400,
                "Cannot approve worker yet — "
                + "; ".join(blockers)
                + ". Complete profile + verify ID before approving.",
            )
    await db.users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "worker_status": status,
                "worker_status_at": datetime.now(timezone.utc).isoformat(),
                "worker_status_by": admin["email"],
            }
        },
    )
    if kill_sessions:
        await db.sessions.delete_many({"user_id": user_id})
    logger.info(f"Admin {admin['email']} set worker {user.get('email')} status -> {status}")
    return {"ok": True, "worker_status": status}


@router.post("/admin/workers/{user_id}/approve")
async def approve_worker(
    user_id: str, _: WorkerStatusIn = WorkerStatusIn(), admin: dict = Depends(require_admin)
):
    return await _set_worker_status(user_id, "approved", admin)


@router.post("/admin/workers/{user_id}/reject")
async def reject_worker(
    user_id: str, _: WorkerStatusIn = WorkerStatusIn(), admin: dict = Depends(require_admin)
):
    # Rejection invalidates active sessions
    return await _set_worker_status(user_id, "rejected", admin, kill_sessions=True)


@router.post("/admin/workers/{user_id}/suspend")
async def suspend_worker(
    user_id: str, _: WorkerStatusIn = WorkerStatusIn(), admin: dict = Depends(require_admin)
):
    return await _set_worker_status(user_id, "suspended", admin, kill_sessions=True)


@router.post("/admin/workers/{user_id}/reinstate")
async def reinstate_worker(
    user_id: str, _: WorkerStatusIn = WorkerStatusIn(), admin: dict = Depends(require_admin)
):
    return await _set_worker_status(user_id, "approved", admin)


@router.post("/admin/workers/{user_id}/reset-password")
async def admin_reset_password(
    user_id: str,
    payload: AdminResetPasswordIn,
    admin: dict = Depends(require_admin),
):
    """Set a new password for a worker. Invalidates all of their sessions."""
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(404, "Worker not found")
    if user.get("role") == "admin":
        raise HTTPException(
            400,
            "To reset an admin password, use POST /admin/users/{id}/reset-password (Owner only)",
        )

    new_password = (payload.new_password or "").strip()
    if not new_password:
        # Generate an easy-to-share temp password
        new_password = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10]
    elif len(new_password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"password_hash": hash_password(new_password)}},
    )
    # Force re-login by killing all of their sessions
    await db.sessions.delete_many({"user_id": user_id})
    logger.info(f"Admin {admin['email']} reset password for {user.get('email')}")
    return {"ok": True, "new_password": new_password}


@router.post("/admin/users/{user_id}/reset-password")
async def owner_reset_any_password(
    user_id: str,
    payload: AdminResetPasswordIn,
    admin: dict = Depends(require_admin),
):
    """Reset ANY user's password — including other admins/VAs. Owner-only when target is admin."""
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(404, "User not found")

    # Only the Owner can force-reset other admin accounts. Workers/VAs are fine
    # for any admin to reset.
    if user.get("role") == "admin" and not admin.get("is_owner"):
        raise HTTPException(403, "Owner sign-off required to reset another admin's password")

    # Owners CAN reset their own password through this endpoint, but a self-reset
    # without the current password should go through /auth/change-password. Block
    # self-resets here to avoid foot-guns.
    if user_id == admin["user_id"]:
        raise HTTPException(
            400,
            "Use /auth/change-password to change your own password (requires current password)",
        )

    new_password = (payload.new_password or "").strip()
    if not new_password:
        new_password = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10]
    elif len(new_password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "password_hash": hash_password(new_password),
            "must_change_password": True,  # force them to change on next login
        }},
    )
    await db.sessions.delete_many({"user_id": user_id})
    logger.info(
        f"Owner {admin['email']} (is_owner={admin.get('is_owner')}) force-reset password for "
        f"{user.get('email')} (role={user.get('role')})"
    )
    # Email the user their new credentials
    await _send_user_email(
        user, kind="password_reset_by_admin",
        subject="Your HCOB password was reset",
        body_html=(
            "<p>HCOB Operations just <strong>reset your password</strong>.</p>"
            "<p>Your new temporary password is:</p>"
            f"<p style='background:#F9FAFB;padding:14px;font-family:monospace;font-size:18px;border:1px solid #E5E7EB'>{new_password}</p>"
            "<p>You'll be prompted to change this on your next login. If you didn't expect this email, "
            "reply immediately so we can investigate.</p>"
        ),
        cta_label="Sign in now",
        cta_url=f"{_public_base()}/login",
    )
    return {
        "ok": True,
        "user_id": user_id,
        "email": user.get("email"),
        "name": user.get("name"),
        "new_password": new_password,
    }



@router.delete("/admin/workers/{user_id}")
async def delete_worker(user_id: str, admin: dict = Depends(require_admin)):
    """Delete a worker and cascade clean their acceptances, sessions, files."""
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(404, "Worker not found")
    if user.get("role") == "admin":
        raise HTTPException(400, "Cannot delete an admin from this endpoint")

    # Free up gig slots for any open acceptances
    acceptances = await db.gig_acceptances.find({"worker_id": user_id}).to_list(1000)
    for a in acceptances:
        gig = await db.gigs.find_one({"gig_id": a["gig_id"]})
        if not gig:
            continue
        new_filled = max(0, (gig.get("slots_filled") or 0) - 1)
        new_status = (
            "open" if new_filled < gig.get("slots", 1) else gig.get("status", "open")
        )
        await db.gigs.update_one(
            {"gig_id": a["gig_id"]},
            {"$set": {"slots_filled": new_filled, "status": new_status}},
        )

    await db.gig_acceptances.delete_many({"worker_id": user_id})
    await db.sessions.delete_many({"user_id": user_id})
    await db.notifications.delete_many({"user_id": user_id})
    await db.files.delete_many({"owner_id": user_id})
    await db.users.delete_one({"user_id": user_id})
    logger.info(f"Admin {admin['email']} deleted worker {user.get('email')}")
    return {"ok": True}




@router.get("/admin/stats")
async def admin_stats(admin: dict = Depends(require_admin)):
    total_workers = await db.users.count_documents({"role": "worker"})
    open_gigs = await db.gigs.count_documents({"status": "open"})
    filled_gigs = await db.gigs.count_documents({"status": "filled"})
    total_gigs = await db.gigs.count_documents({})
    total_acceptances = await db.gig_acceptances.count_documents({})
    pending_id = await db.users.count_documents(
        {"role": "worker", "id_image_path": {"$ne": None}, "id_verified": False}
    )
    pending_approval = await db.users.count_documents(
        {"role": "worker", "worker_status": "pending"}
    )
    pending_requests = await db.gig_acceptances.count_documents(
        {"status": "requested"}
    )
    # "Available now" — workers who flipped the switch AND haven't expired.
    now_iso = datetime.now(timezone.utc).isoformat()
    available_now = await db.users.count_documents(
        {
            "role": "worker",
            "available_now": True,
            "available_until": {"$gt": now_iso},
        }
    )
    return {
        "total_workers": total_workers,
        "open_gigs": open_gigs,
        "filled_gigs": filled_gigs,
        "total_gigs": total_gigs,
        "total_acceptances": total_acceptances,
        "pending_id_verification": pending_id,
        "pending_approval": pending_approval,
        "pending_requests": pending_requests,
        "available_now": available_now,
    }




@router.put("/admin/workers/{user_id}/pay")
async def set_worker_default_pay(
    user_id: str, payload: WorkerPayIn, admin: dict = Depends(require_admin)
):
    """Admin sets a worker's default pay rate / type (used as a fallback when a
    gig-specific override is not set)."""
    worker = await db.users.find_one({"user_id": user_id})
    if not worker or worker.get("role") != "worker":
        raise HTTPException(404, "Worker not found")

    set_ops: dict = {}
    unset_ops: dict = {}
    if payload.clear_rate:
        unset_ops["default_pay_rate"] = ""
    elif payload.default_pay_rate is not None:
        if payload.default_pay_rate < 0:
            raise HTTPException(400, "pay rate must be >= 0")
        set_ops["default_pay_rate"] = float(payload.default_pay_rate)
    if payload.clear_type:
        unset_ops["default_pay_type"] = ""
    elif payload.default_pay_type is not None:
        set_ops["default_pay_type"] = payload.default_pay_type

    if not set_ops and not unset_ops:
        return {"ok": True, "changed": 0}

    ops: dict = {}
    if set_ops:
        ops["$set"] = set_ops
    if unset_ops:
        ops["$unset"] = unset_ops
    await db.users.update_one({"user_id": user_id}, ops)
    logger.info(f"Admin {admin['email']} set pay for worker {user_id}: {set_ops or unset_ops}")
    return {"ok": True, "default_pay_rate": set_ops.get("default_pay_rate"), "default_pay_type": set_ops.get("default_pay_type")}


@router.put("/gigs/{gig_id}/acceptances/{acceptance_id}/pay")
async def set_acceptance_pay_override(
    gig_id: str,
    acceptance_id: str,
    payload: AcceptancePayIn,
    admin: dict = Depends(require_admin),
):
    """Admin overrides pay rate/type for a single worker on a single gig.

    Useful when one worker earns differently from the posted gig rate (e.g.
    performance, seniority). If the acceptance is already completed (clocked
    out), this also recomputes the snapshotted earnings."""
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Acceptance not found")

    set_ops: dict = {}
    unset_ops: dict = {}
    if payload.clear_rate:
        unset_ops["pay_rate_override"] = ""
    elif payload.pay_rate_override is not None:
        if payload.pay_rate_override < 0:
            raise HTTPException(400, "pay rate must be >= 0")
        set_ops["pay_rate_override"] = float(payload.pay_rate_override)
    if payload.clear_type:
        unset_ops["pay_type_override"] = ""
    elif payload.pay_type_override is not None:
        set_ops["pay_type_override"] = payload.pay_type_override

    if not set_ops and not unset_ops:
        return {"ok": True, "changed": 0}

    ops: dict = {}
    if set_ops:
        ops["$set"] = set_ops
    if unset_ops:
        ops["$unset"] = unset_ops
    await db.gig_acceptances.update_one({"acceptance_id": acceptance_id}, ops)

    # Recompute earnings if already clocked out
    refreshed = await db.gig_acceptances.find_one({"acceptance_id": acceptance_id})
    if refreshed and refreshed.get("clock_out_at"):
        gig = await db.gigs.find_one({"gig_id": gig_id})
        worker = await db.users.find_one({"user_id": refreshed["worker_id"]})
        pay = _resolve_pay(refreshed, worker, gig)
        br = _resolve_break_minutes(refreshed, gig)
        new_paid = _compute_paid_hours(refreshed.get("hours_worked"), br)
        new_earnings = _compute_earnings(pay["pay_rate"], pay["pay_type"], refreshed.get("hours_worked"), br)
        await db.gig_acceptances.update_one(
            {"acceptance_id": acceptance_id},
            {
                "$set": {
                    "pay_rate_applied": pay["pay_rate"],
                    "pay_type_applied": pay["pay_type"],
                    "pay_rate_source": pay["pay_rate_source"],
                    "pay_type_source": pay["pay_type_source"],
                    "break_minutes_applied": br,
                    "paid_hours": new_paid,
                    "earnings": new_earnings,
                    # Override invalidates a prior approval — admin should re-approve
                    "timesheet_approved": False,
                    "timesheet_approved_at": None,
                    "timesheet_approved_by": None,
                }
            },
        )
    logger.info(f"Admin {admin['email']} set per-gig pay override on acceptance {acceptance_id}")
    return {"ok": True}


@router.post("/gigs/{gig_id}/acceptances/{acceptance_id}/approve-timesheet")
async def approve_timesheet(
    gig_id: str,
    acceptance_id: str,
    payload: TimesheetApproveIn,
    admin: dict = Depends(require_admin),
):
    """Admin approves the worker's clocked timesheet — releases earnings to the
    worker's earnings view. Optionally allows correcting hours_worked / earnings
    (e.g. worker forgot to clock out)."""
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Acceptance not found")
    if not acceptance.get("clock_out_at"):
        raise HTTPException(400, "Worker hasn't clocked out yet — cannot approve timesheet")

    set_ops: dict = {
        "timesheet_approved": True,
        "timesheet_approved_at": datetime.now(timezone.utc).isoformat(),
        "timesheet_approved_by": admin["email"],
    }
    if payload.note:
        set_ops["timesheet_note"] = payload.note

    # Per-worker break override (minutes) — when present, replaces the gig default
    if payload.break_minutes is not None:
        if payload.break_minutes < 0:
            raise HTTPException(400, "break_minutes must be >= 0")
        set_ops["break_minutes"] = int(payload.break_minutes)

    # Optional admin corrections (e.g. trim hours, set earnings manually)
    if payload.hours_worked is not None:
        if payload.hours_worked < 0:
            raise HTTPException(400, "hours_worked must be >= 0")
        set_ops["hours_worked"] = round(float(payload.hours_worked), 2)
    if payload.earnings is not None:
        if payload.earnings < 0:
            raise HTTPException(400, "earnings must be >= 0")
        set_ops["earnings"] = round(float(payload.earnings), 2)
        set_ops["earnings_manual_override"] = True
    elif payload.hours_worked is not None or payload.break_minutes is not None:
        # Recompute earnings whenever hours OR break changed.
        rate = acceptance.get("pay_rate_applied")
        ptype = acceptance.get("pay_type_applied")
        gig = await db.gigs.find_one({"gig_id": gig_id})
        # Fallback to a fresh resolution if not snapshotted yet
        if rate is None or ptype is None:
            worker = await db.users.find_one({"user_id": acceptance["worker_id"]})
            pay = _resolve_pay(acceptance, worker, gig)
            rate, ptype = pay["pay_rate"], pay["pay_type"]
            set_ops["pay_rate_applied"] = rate
            set_ops["pay_type_applied"] = ptype
        effective_hours = set_ops.get("hours_worked", acceptance.get("hours_worked"))
        # Use the new break if provided, else fall back to existing resolution
        effective_break = (
            set_ops.get("break_minutes")
            if "break_minutes" in set_ops
            else _resolve_break_minutes(acceptance, gig)
        )
        set_ops["break_minutes_applied"] = effective_break
        set_ops["paid_hours"] = _compute_paid_hours(effective_hours, effective_break)
        set_ops["earnings"] = _compute_earnings(rate, ptype, effective_hours, effective_break)

    await db.gig_acceptances.update_one(
        {"acceptance_id": acceptance_id}, {"$set": set_ops}
    )

    # Notify worker that their timesheet was approved + earnings now visible
    gig = await db.gigs.find_one({"gig_id": gig_id}, {"_id": 0, "title": 1})
    refreshed = await db.gig_acceptances.find_one({"acceptance_id": acceptance_id}, {"_id": 0})
    earned = refreshed.get("earnings") if refreshed else None
    await db.notifications.insert_one(
        {
            "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
            "user_id": acceptance["worker_id"],
            "gig_id": gig_id,
            "title": f"Timesheet approved: {gig.get('title') if gig else 'gig'}",
            "body": f"You earned ${earned:.2f} for this gig." if earned is not None else "Your timesheet was approved.",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    logger.info(f"Admin {admin['email']} approved timesheet {acceptance_id}")
    return {"ok": True, "earnings": earned, "timesheet_approved": True}


@router.post("/gigs/{gig_id}/acceptances/{acceptance_id}/unapprove-timesheet")
async def unapprove_timesheet(
    gig_id: str,
    acceptance_id: str,
    admin: dict = Depends(require_admin),
):
    """Reverse a prior timesheet approval (e.g. if a dispute is raised)."""
    res = await db.gig_acceptances.update_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id},
        {
            "$set": {
                "timesheet_approved": False,
                "timesheet_approved_at": None,
                "timesheet_approved_by": None,
            }
        },
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Acceptance not found")
    return {"ok": True}


def _parse_admin_dt(value: str) -> datetime:
    """Parse a datetime string from the admin UI. Accepts ISO 8601 with or
    without timezone (treats naive as UTC) and the `YYYY-MM-DDTHH:MM` shape
    that `<input type=datetime-local>` emits."""
    raw = value.strip()
    if not raw:
        raise HTTPException(400, "Empty datetime value")
    # Handle trailing Z
    raw = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        raise HTTPException(400, f"Invalid datetime: {value}")
    if dt.tzinfo is None:
        # datetime-local from the admin's browser is in their local time, but
        # we don't know the offset. Treat as UTC — the admin form will preview
        # the value back to them so they can correct if needed.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@router.put("/gigs/{gig_id}/acceptances/{acceptance_id}/timesheet")
async def edit_acceptance_timesheet(
    gig_id: str,
    acceptance_id: str,
    payload: TimesheetEditIn,
    admin: dict = Depends(require_admin),
):
    """Admin sets / edits / clears clock-in & clock-out times for an acceptance.

    Recomputes `hours_worked` + `earnings` whenever both times are present.
    Any edit resets `timesheet_approved=false` so the admin must re-approve.
    Status is kept in sync: completed if clocked out, accepted if clocked back in only.
    """
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Acceptance not found")

    # Allow editing only for workers who were actually approved/clocked-in/completed
    if acceptance.get("status") == "requested":
        raise HTTPException(
            400, "Approve the worker for this gig before editing their timesheet"
        )

    new_in: Optional[datetime] = None
    new_out: Optional[datetime] = None
    if payload.clock_in_at is not None:
        new_in = _parse_admin_dt(payload.clock_in_at)
    elif acceptance.get("clock_in_at"):
        new_in = _parse_admin_dt(acceptance["clock_in_at"])

    if payload.clear_clock_out:
        new_out = None
    elif payload.clock_out_at is not None:
        new_out = _parse_admin_dt(payload.clock_out_at)
    elif acceptance.get("clock_out_at") and not payload.clear_clock_out:
        new_out = _parse_admin_dt(acceptance["clock_out_at"])

    # Validation
    if new_in is None and new_out is not None:
        raise HTTPException(400, "Cannot set a clock-out time without a clock-in time")
    if new_in and new_out and new_out <= new_in:
        raise HTTPException(400, "Clock-out must be after clock-in")

    set_ops: dict = {
        "timesheet_approved": False,
        "timesheet_approved_at": None,
        "timesheet_approved_by": None,
        "timesheet_edited_at": datetime.now(timezone.utc).isoformat(),
        "timesheet_edited_by": admin["email"],
    }
    unset_ops: dict = {}

    if payload.admin_note is not None:
        note_clean = payload.admin_note.strip()
        if note_clean:
            set_ops["admin_note"] = note_clean
            set_ops["admin_note_at"] = datetime.now(timezone.utc).isoformat()
            set_ops["admin_note_by"] = admin["email"]
        else:
            unset_ops["admin_note"] = ""
            unset_ops["admin_note_at"] = ""
            unset_ops["admin_note_by"] = ""

    if new_in is None:
        unset_ops["clock_in_at"] = ""
        unset_ops["hours_worked"] = ""
        unset_ops["paid_hours"] = ""
        unset_ops["break_minutes_applied"] = ""
        unset_ops["earnings"] = ""
        set_ops["status"] = "accepted"
    else:
        set_ops["clock_in_at"] = new_in.isoformat()

    if new_out is None:
        unset_ops["clock_out_at"] = ""
        unset_ops["hours_worked"] = ""
        unset_ops["paid_hours"] = ""
        unset_ops["break_minutes_applied"] = ""
        unset_ops["earnings"] = ""
        if new_in is not None:
            set_ops["status"] = "clocked_in"
    else:
        set_ops["clock_out_at"] = new_out.isoformat()
        hours = round((new_out - new_in).total_seconds() / 3600.0, 2)
        set_ops["hours_worked"] = hours

        # Recompute earnings using the resolved pay (which respects per-gig
        # override → worker default → gig posted precedence)
        gig = await db.gigs.find_one({"gig_id": gig_id})
        worker = await db.users.find_one({"user_id": acceptance["worker_id"]})
        pay = _resolve_pay(acceptance, worker, gig)

        # Per-worker break override (minutes) — if provided, apply now so we
        # can include it in the recompute below
        if payload.break_minutes is not None:
            if payload.break_minutes < 0:
                raise HTTPException(400, "break_minutes must be >= 0")
            set_ops["break_minutes"] = int(payload.break_minutes)
            effective_break = int(payload.break_minutes)
        else:
            effective_break = _resolve_break_minutes(acceptance, gig)

        set_ops["pay_rate_applied"] = pay["pay_rate"]
        set_ops["pay_type_applied"] = pay["pay_type"]
        set_ops["pay_rate_source"] = pay["pay_rate_source"]
        set_ops["pay_type_source"] = pay["pay_type_source"]
        set_ops["break_minutes_applied"] = effective_break
        set_ops["paid_hours"] = _compute_paid_hours(hours, effective_break)
        set_ops["earnings"] = _compute_earnings(pay["pay_rate"], pay["pay_type"], hours, effective_break)
        set_ops["earnings_manual_override"] = False
        set_ops["status"] = "completed"

    ops: dict = {"$set": set_ops}
    if unset_ops:
        ops["$unset"] = unset_ops
    await db.gig_acceptances.update_one({"acceptance_id": acceptance_id}, ops)

    logger.info(
        f"Admin {admin['email']} edited timesheet {acceptance_id}: "
        f"in={set_ops.get('clock_in_at')} out={set_ops.get('clock_out_at')}"
    )
    refreshed = await db.gig_acceptances.find_one({"acceptance_id": acceptance_id}, {"_id": 0})
    return {
        "ok": True,
        "clock_in_at": refreshed.get("clock_in_at"),
        "clock_out_at": refreshed.get("clock_out_at"),
        "hours_worked": refreshed.get("hours_worked"),
        "earnings": refreshed.get("earnings"),
        "status": refreshed.get("status"),
    }


@router.post("/gigs/{gig_id}/acceptances/{acceptance_id}/no-show")
async def mark_acceptance_no_show(
    gig_id: str,
    acceptance_id: str,
    payload: AcceptanceNoShowIn,
    admin: dict = Depends(require_admin),
):
    """Admin marks a worker as a no-show for this acceptance. Records the
    reason + admin email + timestamp for the audit log. Clears any clock
    times (worker wasn't there). The 'first no-show = auto-delete' rule
    runs elsewhere — this endpoint only flips the status."""
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Acceptance not found")
    if acceptance.get("status") == "requested":
        raise HTTPException(
            400, "Approve the worker before marking them as a no-show"
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    set_ops: dict = {
        "status": "no_show",
        "no_show_at": now_iso,
        "no_show_by": admin["email"],
        "no_show_reason": payload.reason.strip(),
        # Reset timesheet so it doesn't accidentally appear in earnings
        "timesheet_approved": False,
        "timesheet_approved_at": None,
        "timesheet_approved_by": None,
    }
    if payload.admin_note:
        note_clean = payload.admin_note.strip()
        if note_clean:
            set_ops["admin_note"] = note_clean
            set_ops["admin_note_at"] = now_iso
            set_ops["admin_note_by"] = admin["email"]

    unset_ops = {
        "clock_in_at": "",
        "clock_out_at": "",
        "hours_worked": "",
        "paid_hours": "",
        "earnings": "",
    }
    await db.gig_acceptances.update_one(
        {"acceptance_id": acceptance_id}, {"$set": set_ops, "$unset": unset_ops}
    )

    logger.info(
        f"Admin {admin['email']} marked acceptance {acceptance_id} as no_show "
        f"— reason: {payload.reason[:80]}"
    )

    # Notify the worker (no email — this is a sensitive event, in-app only)
    gig = await db.gigs.find_one({"gig_id": gig_id}, {"title": 1})
    await db.notifications.insert_one(
        {
            "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
            "user_id": acceptance["worker_id"],
            "gig_id": gig_id,
            "title": f"Marked no-show: {gig.get('title') if gig else 'gig'}",
            "body": f"HCOB marked you as a no-show. Reason: {payload.reason.strip()}",
            "read": False,
            "created_at": now_iso,
        }
    )

    return {"ok": True, "status": "no_show"}


@router.post("/gigs/{gig_id}/acceptances/{acceptance_id}/mark-completed")
async def mark_acceptance_completed(
    gig_id: str,
    acceptance_id: str,
    payload: AcceptanceMarkCompletedIn,
    admin: dict = Depends(require_admin),
):
    """Admin force-marks an acceptance as completed (worker forgot to clock in
    or out but did finish). If clock_in_at / clock_out_at are passed, use
    those. Otherwise fall back to the gig's scheduled_at + duration_hours.

    Recomputes earnings via the standard pay-resolution pipeline."""
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Acceptance not found")
    if acceptance.get("status") == "requested":
        raise HTTPException(
            400, "Approve the worker before marking the gig completed"
        )

    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")

    # Resolve clock-in: payload → existing → gig scheduled_at
    in_str = payload.clock_in_at or acceptance.get("clock_in_at") or gig.get("scheduled_at")
    if not in_str:
        raise HTTPException(
            400, "Cannot mark completed without a clock-in time. Set scheduled_at on the gig or pass clock_in_at."
        )
    new_in = _parse_admin_dt(in_str)

    # Resolve clock-out: payload → existing → scheduled_at + duration_hours
    out_str = payload.clock_out_at or acceptance.get("clock_out_at")
    if out_str:
        new_out = _parse_admin_dt(out_str)
    else:
        duration_h = float(gig.get("duration_hours") or 0)
        if duration_h <= 0:
            raise HTTPException(
                400, "Gig has no duration_hours — pass clock_out_at explicitly."
            )
        from datetime import timedelta
        new_out = new_in + timedelta(hours=duration_h)

    if new_out <= new_in:
        raise HTTPException(400, "Clock-out must be after clock-in")

    worker = await db.users.find_one({"user_id": acceptance["worker_id"]})
    pay = _resolve_pay(acceptance, worker, gig)
    hours = round((new_out - new_in).total_seconds() / 3600.0, 2)
    effective_break = _resolve_break_minutes(acceptance, gig)

    now_iso = datetime.now(timezone.utc).isoformat()
    set_ops: dict = {
        "status": "completed",
        "clock_in_at": new_in.isoformat(),
        "clock_out_at": new_out.isoformat(),
        "hours_worked": hours,
        "pay_rate_applied": pay["pay_rate"],
        "pay_type_applied": pay["pay_type"],
        "pay_rate_source": pay["pay_rate_source"],
        "pay_type_source": pay["pay_type_source"],
        "break_minutes_applied": effective_break,
        "paid_hours": _compute_paid_hours(hours, effective_break),
        "earnings": _compute_earnings(pay["pay_rate"], pay["pay_type"], hours, effective_break),
        "earnings_manual_override": False,
        "timesheet_approved": False,
        "timesheet_approved_at": None,
        "timesheet_approved_by": None,
        "timesheet_edited_at": now_iso,
        "timesheet_edited_by": admin["email"],
        "marked_completed_at": now_iso,
        "marked_completed_by": admin["email"],
    }
    if payload.admin_note:
        note_clean = payload.admin_note.strip()
        if note_clean:
            set_ops["admin_note"] = note_clean
            set_ops["admin_note_at"] = now_iso
            set_ops["admin_note_by"] = admin["email"]

    await db.gig_acceptances.update_one(
        {"acceptance_id": acceptance_id}, {"$set": set_ops}
    )

    logger.info(
        f"Admin {admin['email']} force-completed acceptance {acceptance_id} "
        f"(hours={hours}, earnings={set_ops['earnings']})"
    )

    refreshed = await db.gig_acceptances.find_one({"acceptance_id": acceptance_id}, {"_id": 0})
    return {
        "ok": True,
        "status": refreshed.get("status"),
        "clock_in_at": refreshed.get("clock_in_at"),
        "clock_out_at": refreshed.get("clock_out_at"),
        "hours_worked": refreshed.get("hours_worked"),
        "earnings": refreshed.get("earnings"),
    }



# ---------------------------------------------------------------------------
# Blast safety (kill switch + audit) — Feb-2026 SEV1 follow-up
# ---------------------------------------------------------------------------
class BlastKillSwitchIn(BaseModel):
    enabled: bool


@router.get("/admin/blast-kill-switch")
async def get_blast_kill_switch(admin: dict = Depends(require_admin)):
    """Return whether blasts are currently disabled and why (env vs DB)."""
    env_on = (os.environ.get("BLAST_KILL_SWITCH") or "").strip().lower() in (
        "1", "true", "yes", "on"
    )
    s = await db.app_settings.find_one(
        {"_id": "global"}, {"_id": 0, "blast_kill_switch": 1, "blast_kill_switch_at": 1, "blast_kill_switch_by": 1}
    ) or {}
    return {
        "enabled": bool(env_on or s.get("blast_kill_switch")),
        "source": "env" if env_on else ("db" if s.get("blast_kill_switch") else "off"),
        "toggled_at": s.get("blast_kill_switch_at"),
        "toggled_by": s.get("blast_kill_switch_by"),
        "cooldown_seconds": BLAST_COOLDOWN_SECONDS,
    }


@router.post("/admin/blast-kill-switch")
async def set_blast_kill_switch(
    payload: BlastKillSwitchIn,
    owner: dict = Depends(require_owner),
):
    """Owner-only: flip the global blast kill switch. When enabled, every
    /blast endpoint returns 503 and in-flight background fan-outs exit early.
    Note: env var `BLAST_KILL_SWITCH` still overrides the DB toggle."""
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.app_settings.update_one(
        {"_id": "global"},
        {"$set": {
            "blast_kill_switch": bool(payload.enabled),
            "blast_kill_switch_at": now_iso,
            "blast_kill_switch_by": owner.get("email") or owner.get("user_id"),
        }},
        upsert=True,
    )
    logger.warning(
        f"[BLAST_KILL_SWITCH] {'ENABLED' if payload.enabled else 'DISABLED'} "
        f"by {owner.get('email')}"
    )
    return {"ok": True, "enabled": bool(payload.enabled)}


@router.get("/admin/blast-audit")
async def blast_audit(
    gig_id: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    hours: int = Query(72, ge=1, le=24 * 30),
    admin: dict = Depends(require_admin),
):
    """Diagnostic — show the recent `blast_logs` rows (filterable by gig or
    project) plus a summary of the `email_logs` collection so an Owner can
    audit exactly what was sent in production during an incident."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    q: dict = {"sent_at": {"$gte": cutoff}}
    if gig_id:
        q["gig_id"] = gig_id
    if project_id:
        q["project_id"] = project_id

    blasts = await db.blast_logs.find(q, {"_id": 0}).sort("sent_at", -1).to_list(500)

    # Surface per-blast unique-recipient counts to spot anomalies
    for b in blasts:
        b["unique_emails_sent"] = len(b.get("sent_emails") or [])
        b["unique_phones_sent"] = len(b.get("sent_phones") or [])

    # Email log summary in the window (catches event/digest emails too)
    email_summary = await db.email_logs.aggregate([
        {"$match": {"sent_at": {"$gte": cutoff}}},
        {"$group": {"_id": "$email", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 50},
    ]).to_list(50)
    total_emails = sum(r["count"] for r in email_summary)

    return {
        "window_hours": hours,
        "blasts": blasts,
        "blast_count": len(blasts),
        "top_email_recipients": [
            {"email": r["_id"], "count": r["count"]} for r in email_summary
        ],
        "total_event_emails": total_emails,
    }

