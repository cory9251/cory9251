"""Read-only Partner API for external apps (PalletTrack).

Auth: shared API key via `X-API-Key` header (or `Authorization: Bearer <key>`).
Scope: only gigs whose title matches PARTNER_SHIFT_TITLE_FILTER (case-insensitive
substring, e.g. "recycling plant"). shift_name == gig title.
"""
import os
import re
import secrets
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from config import db

router = APIRouter(prefix="/partner", tags=["partner"])

PARTNER_API_KEY = os.environ.get("PARTNER_API_KEY", "")
SHIFT_TITLE_FILTER = os.environ.get("PARTNER_SHIFT_TITLE_FILTER", "recycling plant")


def _require_partner_key(x_api_key: Optional[str], authorization: Optional[str]):
    supplied = x_api_key or ""
    if not supplied and authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    if not PARTNER_API_KEY or not supplied or not secrets.compare_digest(supplied, PARTNER_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing partner API key")


def _shift_title_query() -> dict:
    return {"title": {"$regex": re.escape(SHIFT_TITLE_FILTER), "$options": "i"}}


async def _matching_gigs() -> dict:
    """Return {gig_id: gig} for all gigs matching the partner shift filter."""
    cursor = db.gigs.find(_shift_title_query(), {"_id": 0})
    return {g["gig_id"]: g async for g in cursor}


async def _users_by_ids(worker_ids: set) -> dict:
    cursor = db.users.find({"user_id": {"$in": list(worker_ids)}}, {"_id": 0})
    return {u["user_id"]: u async for u in cursor}


ACTIVE_ACC_STATUSES = {"cancelled", "removed", "no_show", "declined"}


@router.get("/workers")
async def partner_workers(
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    """All workers assigned to matching shifts, with the shift names they work."""
    _require_partner_key(x_api_key, authorization)
    gigs = await _matching_gigs()
    if not gigs:
        return {"workers": [], "shift_filter": SHIFT_TITLE_FILTER}

    accs = await db.gig_acceptances.find(
        {"gig_id": {"$in": list(gigs.keys())}, "status": {"$nin": list(ACTIVE_ACC_STATUSES)}},
        {"_id": 0},
    ).to_list(length=None)

    shifts_by_worker: dict = {}
    for a in accs:
        gig = gigs.get(a["gig_id"])
        if not gig:
            continue
        shifts_by_worker.setdefault(a["worker_id"], set()).add(gig.get("title") or "")

    users = await _users_by_ids(set(shifts_by_worker.keys()))
    workers = []
    for wid, titles in shifts_by_worker.items():
        u = users.get(wid)
        if not u:
            continue
        workers.append({
            "worker_id": wid,
            "name": u.get("name"),
            "email": u.get("email"),
            "phone": u.get("phone"),
            "shift_names": sorted(t for t in titles if t),
        })
    workers.sort(key=lambda w: (w.get("name") or "").lower())
    return {"workers": workers, "count": len(workers), "shift_filter": SHIFT_TITLE_FILTER}


@router.get("/shifts/active")
async def partner_active_shifts(
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    """Workers currently clocked in (clock_in set, no clock_out) on matching shifts."""
    _require_partner_key(x_api_key, authorization)
    gigs = await _matching_gigs()
    if not gigs:
        return {"active_shifts": [], "count": 0, "shift_filter": SHIFT_TITLE_FILTER}

    accs = await db.gig_acceptances.find(
        {
            "gig_id": {"$in": list(gigs.keys())},
            "clock_in_at": {"$ne": None},
            "$or": [{"clock_out_at": None}, {"clock_out_at": {"$exists": False}}],
        },
        {"_id": 0},
    ).to_list(length=None)

    users = await _users_by_ids({a["worker_id"] for a in accs})
    rows = []
    for a in accs:
        gig = gigs[a["gig_id"]]
        u = users.get(a["worker_id"], {})
        rows.append({
            "worker_id": a["worker_id"],
            "worker_name": u.get("name"),
            "worker_email": u.get("email"),
            "shift_name": gig.get("title"),
            "gig_id": gig.get("gig_id"),
            "scheduled_date": gig.get("scheduled_date"),
            "location": gig.get("location"),
            "clock_in_at": a.get("clock_in_at"),
        })
    rows.sort(key=lambda r: r.get("clock_in_at") or "")
    return {"active_shifts": rows, "count": len(rows), "shift_filter": SHIFT_TITLE_FILTER}


@router.get("/shifts/hours")
async def partner_shift_hours(
    start_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD (inclusive)"),
    end_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD (inclusive)"),
    worker_email: Optional[str] = Query(default=None),
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
):
    """Completed shift hours (clocked out) on matching shifts, newest first."""
    _require_partner_key(x_api_key, authorization)
    gigs = await _matching_gigs()
    if not gigs:
        return {"shifts": [], "count": 0, "total_hours": 0, "shift_filter": SHIFT_TITLE_FILTER}

    q: dict = {"gig_id": {"$in": list(gigs.keys())}, "clock_out_at": {"$ne": None}}
    if start_date:
        q["clock_in_at"] = {"$gte": start_date}
    if end_date:
        q.setdefault("clock_in_at", {})["$lte"] = end_date + "T23:59:59.999999+00:00"
    accs = await db.gig_acceptances.find(q, {"_id": 0}).to_list(length=None)

    users = await _users_by_ids({a["worker_id"] for a in accs})
    rows = []
    for a in accs:
        u = users.get(a["worker_id"], {})
        if worker_email and (u.get("email") or "").lower() != worker_email.lower():
            continue
        gig = gigs[a["gig_id"]]
        rows.append({
            "worker_id": a["worker_id"],
            "worker_name": u.get("name"),
            "worker_email": u.get("email"),
            "shift_name": gig.get("title"),
            "gig_id": gig.get("gig_id"),
            "scheduled_date": gig.get("scheduled_date"),
            "location": gig.get("location"),
            "clock_in_at": a.get("clock_in_at"),
            "clock_out_at": a.get("clock_out_at"),
            "hours_worked": a.get("hours_worked"),
            "paid_hours": a.get("paid_hours", a.get("hours_worked")),
            "break_minutes": a.get("break_minutes"),
            "status": a.get("status"),
        })
    rows.sort(key=lambda r: r.get("clock_in_at") or "", reverse=True)
    total = round(sum(r["hours_worked"] or 0 for r in rows), 2)
    return {"shifts": rows, "count": len(rows), "total_hours": total, "shift_filter": SHIFT_TITLE_FILTER}
