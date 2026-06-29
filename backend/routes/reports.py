"""Reports routes — workers/gigs/activity/earnings/blasts reports +
timesheet detail + CSV + Google Sheets export + /me/earnings worker view.

Wiring in server.py:
    from routes.reports import router as reports_router
    api.include_router(reports_router)

Helpers `_build_workers_report`, `_build_gigs_report`, `_build_activity_report`,
`_build_earnings_report`, `_build_blasts_report`, `_build_timesheet_rows`,
`_dispatch_report`, `_params_from_query`, `_gigs_cols`, `_activity_cols`,
`_fmt_dt_for_csv`, `_csv_escape`, `REPORT_TYPES` are all module-local.
"""
import re
import csv
import io
import asyncio
import json
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response as FastAPIResponse, PlainTextResponse  # noqa: F401

from config import db, logger
from auth_deps import require_admin, get_current_user, _profile_missing_fields
from notifications import _get_settings_doc
from routes.gigs import (
    _resolve_pay,
    _resolve_break_minutes,
    _compute_paid_hours,
    _compute_earnings,
)

router = APIRouter()


async def _build_workers_report(
    skills: Optional[str],
    zip_code: Optional[str],
    zip_prefix: Optional[str],
    status: Optional[str],
    profile_status: Optional[str],
    include_pii: bool,
) -> tuple[List[dict], List[dict]]:
    """Roster report: every worker + work stats. Optional PII columns when
    include_pii=True (DOB, full address, emergency contact). Filters mirror
    /admin/workers."""
    query: dict = {"role": "worker"}
    if status in ("approved", "pending", "rejected", "suspended"):
        if status == "approved":
            query["$or"] = [
                {"worker_status": "approved"},
                {"worker_status": {"$exists": False}},
            ]
        else:
            query["worker_status"] = status
    if skills:
        skill_list = [s.strip() for s in skills.split(",") if s.strip()]
        if skill_list:
            query["skills"] = {"$in": skill_list}
    if zip_code:
        query["zip_code"] = zip_code.strip()
    elif zip_prefix:
        query["zip_code"] = {"$regex": f"^{re.escape(zip_prefix.strip())}"}

    workers = await db.users.find(
        query, {"_id": 0, "password_hash": 0}
    ).sort("created_at", -1).to_list(2000)

    # Pre-load all acceptances grouped by worker (only need finished ones for stats)
    user_ids = [w["user_id"] for w in workers]
    accs = []
    if user_ids:
        accs = await db.gig_acceptances.find(
            {"worker_id": {"$in": user_ids}}, {"_id": 0}
        ).to_list(20000)
    acc_by_worker: dict = {}
    for a in accs:
        acc_by_worker.setdefault(a["worker_id"], []).append(a)

    rows: List[dict] = []
    for w in workers:
        missing = _profile_missing_fields(w)
        complete = len(missing) == 0
        if profile_status == "complete" and not complete:
            continue
        if profile_status == "incomplete" and complete:
            continue
        accs_w = acc_by_worker.get(w["user_id"], [])
        completed = [a for a in accs_w if a.get("clock_out_at")]
        approved_earnings = sum(
            float(a.get("earnings") or 0)
            for a in completed
            if a.get("timesheet_approved")
        )
        total_hours = sum(float(a.get("hours_worked") or 0) for a in completed)

        row: dict = {
            "user_id": w["user_id"],
            "name": w.get("name") or "",
            "email": w.get("email") or "",
            "phone": w.get("phone") or "",
            "zip_code": w.get("zip_code") or "",
            "city": w.get("city") or "",
            "state": w.get("state") or "",
            "skills": ", ".join(w.get("skills") or []),
            "availability": ", ".join(w.get("availability") or []),
            "vehicle": ", ".join(
                v for v, present in [
                    ("car", w.get("has_car")),
                    ("truck", w.get("has_truck")),
                    ("cdl", w.get("has_cdl")),
                ] if present
            ),
            "experience_level": w.get("experience_level") or "",
            "tshirt_size": w.get("tshirt_size") or "",
            "id_verified": "yes" if w.get("id_verified") else "no",
            "profile_complete": "yes" if complete else "no",
            "worker_status": w.get("worker_status") or "approved",
            "joined_date": (w.get("created_at") or "")[:10],
            "jobs_completed": len(completed),
            "total_hours": round(total_hours, 2),
            "total_earned": round(approved_earnings, 2),
        }
        if include_pii:
            row["date_of_birth"] = w.get("date_of_birth") or ""
            row["address"] = w.get("address") or ""
            row["emergency_contact_name"] = w.get("emergency_contact_name") or ""
            row["emergency_contact_phone"] = w.get("emergency_contact_phone") or ""
            row["bio"] = w.get("bio") or ""
        rows.append(row)

    cols = [
        {"key": "name", "label": "Name"},
        {"key": "email", "label": "Email"},
        {"key": "phone", "label": "Phone"},
        {"key": "zip_code", "label": "ZIP"},
        {"key": "city", "label": "City"},
        {"key": "state", "label": "State"},
        {"key": "skills", "label": "Skills"},
        {"key": "availability", "label": "Availability"},
        {"key": "vehicle", "label": "Vehicle"},
        {"key": "experience_level", "label": "Experience"},
        {"key": "tshirt_size", "label": "Shirt size"},
        {"key": "id_verified", "label": "ID verified"},
        {"key": "profile_complete", "label": "Profile complete"},
        {"key": "worker_status", "label": "Status"},
        {"key": "joined_date", "label": "Joined"},
        {"key": "jobs_completed", "label": "Jobs completed"},
        {"key": "total_hours", "label": "Total hours"},
        {"key": "total_earned", "label": "Total earned"},
    ]
    if include_pii:
        cols += [
            {"key": "date_of_birth", "label": "DOB"},
            {"key": "address", "label": "Address"},
            {"key": "emergency_contact_name", "label": "Emergency contact"},
            {"key": "emergency_contact_phone", "label": "Emergency phone"},
            {"key": "bio", "label": "Bio"},
        ]
    return rows, cols


async def _build_gigs_report(
    start: Optional[str],
    end: Optional[str],
    category: Optional[str],
    status: Optional[str],
) -> tuple[List[dict], List[dict]]:
    """Gigs report: title, date, location, slots, status, workers assigned,
    total payout so far (sum of earnings from clocked-out workers)."""
    query: dict = {}
    if status:
        query["status"] = status
    if category:
        query["category"] = category
    if start or end:
        d: dict = {}
        if start:
            d["$gte"] = start[:10]
        if end:
            d["$lte"] = end[:10]
        query["scheduled_date"] = d

    gigs = await db.gigs.find(query, {"_id": 0}).sort("scheduled_date", -1).to_list(5000)
    if not gigs:
        return [], _gigs_cols()

    gig_ids = [g["gig_id"] for g in gigs]
    accs = await db.gig_acceptances.find(
        {"gig_id": {"$in": gig_ids}}, {"_id": 0}
    ).to_list(50000)
    acc_by_gig: dict = {}
    for a in accs:
        acc_by_gig.setdefault(a["gig_id"], []).append(a)

    rows: List[dict] = []
    for g in gigs:
        gaccs = acc_by_gig.get(g["gig_id"], [])
        assigned = [a for a in gaccs if a.get("status") != "requested"]
        completed = [a for a in assigned if a.get("clock_out_at")]
        payout = sum(float(a.get("earnings") or 0) for a in completed)
        rows.append({
            "gig_id": g["gig_id"],
            "title": g.get("title") or "",
            "category": g.get("category") or "",
            "subcategory": g.get("subcategory") or "",
            "scheduled_date": g.get("scheduled_date") or "",
            "start_time": g.get("start_time") or "",
            "duration_hours": g.get("duration_hours") or "",
            "location": g.get("location") or "",
            "slots": g.get("slots") or 0,
            "pay_rate": float(g.get("pay_rate") or 0),
            "pay_type": g.get("pay_type") or "",
            "status": g.get("status") or "",
            "workers_assigned": len(assigned),
            "workers_completed": len(completed),
            "total_payout": round(payout, 2),
        })
    return rows, _gigs_cols()


def _gigs_cols() -> List[dict]:
    return [
        {"key": "title", "label": "Title"},
        {"key": "category", "label": "Category"},
        {"key": "subcategory", "label": "Sub-type"},
        {"key": "scheduled_date", "label": "Date"},
        {"key": "start_time", "label": "Start"},
        {"key": "duration_hours", "label": "Duration"},
        {"key": "location", "label": "Location"},
        {"key": "slots", "label": "Slots"},
        {"key": "pay_rate", "label": "Pay rate"},
        {"key": "pay_type", "label": "Pay type"},
        {"key": "status", "label": "Status"},
        {"key": "workers_assigned", "label": "Workers assigned"},
        {"key": "workers_completed", "label": "Workers completed"},
        {"key": "total_payout", "label": "Total payout"},
    ]


async def _build_activity_report(
    start: Optional[str],
    end: Optional[str],
    worker_id: Optional[str],
) -> tuple[List[dict], List[dict]]:
    """Per-worker activity for a date range: gigs requested / approved /
    completed / no-shows, total hours, total earned. Range is matched against
    the acceptance's accepted_at (or created_at) timestamp."""
    wquery: dict = {"role": "worker"}
    if worker_id:
        wquery["user_id"] = worker_id
    workers = await db.users.find(
        wquery, {"_id": 0, "password_hash": 0}
    ).to_list(2000)
    user_ids = [w["user_id"] for w in workers]
    if not user_ids:
        return [], _activity_cols()

    accs = await db.gig_acceptances.find(
        {"worker_id": {"$in": user_ids}}, {"_id": 0}
    ).to_list(50000)
    # Filter accs in-memory by date range using the most relevant timestamp
    def _ts(a: dict) -> str:
        return (
            a.get("requested_at")
            or a.get("accepted_at")
            or a.get("created_at")
            or a.get("clock_in_at")
            or ""
        )
    if start or end:
        s = start[:19] if start else ""
        e = end[:19] if end else ""
        accs = [a for a in accs if (not s or _ts(a) >= s) and (not e or _ts(a) <= e)]
    acc_by_worker: dict = {}
    for a in accs:
        acc_by_worker.setdefault(a["worker_id"], []).append(a)

    rows: List[dict] = []
    for w in workers:
        a_list = acc_by_worker.get(w["user_id"], [])
        requested = len(a_list)
        approved = sum(1 for a in a_list if a.get("status") != "requested")
        completed = sum(1 for a in a_list if a.get("clock_out_at"))
        # No-show = approved but never clocked in
        no_show = sum(
            1 for a in a_list
            if a.get("status") not in ("requested",) and not a.get("clock_in_at")
        )
        total_hours = sum(float(a.get("hours_worked") or 0) for a in a_list)
        total_earned = sum(
            float(a.get("earnings") or 0)
            for a in a_list
            if a.get("timesheet_approved")
        )
        # Rating aggregates — combine admin + client stars across these accs
        stars = []
        for a in a_list:
            if isinstance(a.get("admin_rating"), (int, float)):
                stars.append(a["admin_rating"])
            if isinstance(a.get("client_rating"), (int, float)):
                stars.append(a["client_rating"])
        avg_rating = round(sum(stars) / len(stars), 2) if stars else None
        if requested == 0 and not worker_id:
            # Skip totally-inactive workers unless explicitly asked
            continue
        rows.append({
            "user_id": w["user_id"],
            "name": w.get("name") or "",
            "email": w.get("email") or "",
            "phone": w.get("phone") or "",
            "gigs_requested": requested,
            "gigs_approved": approved,
            "gigs_completed": completed,
            "no_shows": no_show,
            "total_hours": round(total_hours, 2),
            "total_earned": round(total_earned, 2),
            "avg_rating": avg_rating,
            "ratings_count": len(stars),
            "id_verified": "yes" if w.get("id_verified") else "no",
        })
    rows.sort(key=lambda r: r["gigs_completed"], reverse=True)
    return rows, _activity_cols()


def _activity_cols() -> List[dict]:
    return [
        {"key": "name", "label": "Worker"},
        {"key": "email", "label": "Email"},
        {"key": "phone", "label": "Phone"},
        {"key": "gigs_requested", "label": "Requested"},
        {"key": "gigs_approved", "label": "Approved"},
        {"key": "gigs_completed", "label": "Completed"},
        {"key": "no_shows", "label": "No-shows"},
        {"key": "total_hours", "label": "Total hours"},
        {"key": "total_earned", "label": "Total earned"},
        {"key": "avg_rating", "label": "Avg rating"},
        {"key": "ratings_count", "label": "# ratings"},
        {"key": "id_verified", "label": "ID verified"},
    ]


async def _build_earnings_report(
    start: Optional[str],
    end: Optional[str],
    only_approved: bool,
) -> tuple[List[dict], List[dict]]:
    """Payroll summary: one row per worker for the date range with total
    earnings, hours, gigs. only_approved=True restricts to approved
    timesheets (recommended for payroll)."""
    ts_rows = await _build_timesheet_rows(start, end, None, None, only_approved)
    by_w: dict = {}
    for r in ts_rows:
        wid = r["worker_id"]
        agg = by_w.setdefault(wid, {
            "user_id": wid,
            "name": r.get("worker_name") or "",
            "email": r.get("worker_email") or "",
            "gigs": 0,
            "total_hours": 0.0,
            "total_earned": 0.0,
            "approved_earned": 0.0,
            "pending_earned": 0.0,
        })
        agg["gigs"] += 1
        agg["total_hours"] += float(r.get("hours_worked") or 0)
        earn = float(r.get("earnings") or 0)
        agg["total_earned"] += earn
        if r.get("timesheet_approved"):
            agg["approved_earned"] += earn
        else:
            agg["pending_earned"] += earn
    rows = list(by_w.values())
    for r in rows:
        r["total_hours"] = round(r["total_hours"], 2)
        r["total_earned"] = round(r["total_earned"], 2)
        r["approved_earned"] = round(r["approved_earned"], 2)
        r["pending_earned"] = round(r["pending_earned"], 2)
    rows.sort(key=lambda r: r["approved_earned"], reverse=True)
    cols = [
        {"key": "name", "label": "Worker"},
        {"key": "email", "label": "Email"},
        {"key": "gigs", "label": "Gigs"},
        {"key": "total_hours", "label": "Total hours"},
        {"key": "approved_earned", "label": "Approved $"},
        {"key": "pending_earned", "label": "Pending $"},
        {"key": "total_earned", "label": "Total $"},
    ]
    return rows, cols


async def _build_timesheet_rows(
    start: Optional[str],
    end: Optional[str],
    worker_id: Optional[str],
    gig_id: Optional[str],
    only_approved: bool,
) -> List[dict]:
    """Return enriched timesheet rows, sorted by clock_in (newest first).

    A row is included only if the worker clocked OUT (completed). Filters by
    optional ISO date strings; only_approved=True restricts to approved
    timesheets (used for worker-facing endpoints)."""
    query: dict = {"clock_out_at": {"$ne": None}}
    if worker_id:
        query["worker_id"] = worker_id
    if gig_id:
        query["gig_id"] = gig_id
    if only_approved:
        query["timesheet_approved"] = True

    # Date filter on clock_in_at when provided
    if start or end:
        date_filter: dict = {}
        if start:
            date_filter["$gte"] = start
        if end:
            date_filter["$lte"] = end
        query["clock_in_at"] = date_filter

    rows = await db.gig_acceptances.find(query, {"_id": 0}).sort("clock_in_at", -1).to_list(5000)
    if not rows:
        return []
    gig_ids = list({r["gig_id"] for r in rows})
    worker_ids = list({r["worker_id"] for r in rows})
    gigs = await db.gigs.find({"gig_id": {"$in": gig_ids}}, {"_id": 0}).to_list(5000)
    gmap = {g["gig_id"]: g for g in gigs}
    workers = await db.users.find(
        {"user_id": {"$in": worker_ids}}, {"_id": 0, "password_hash": 0}
    ).to_list(5000)
    wmap = {w["user_id"]: w for w in workers}
    out: List[dict] = []
    for r in rows:
        g = gmap.get(r["gig_id"]) or {}
        w = wmap.get(r["worker_id"]) or {}
        br = _resolve_break_minutes(r, g)
        paid_hours = _compute_paid_hours(r.get("hours_worked"), br)
        # If earnings not snapshotted (legacy), compute on the fly using current rates
        earnings = r.get("earnings")
        rate = r.get("pay_rate_applied")
        ptype = r.get("pay_type_applied")
        if earnings is None:
            pay = _resolve_pay(r, w, g)
            rate, ptype = pay["pay_rate"], pay["pay_type"]
            earnings = _compute_earnings(rate, ptype, r.get("hours_worked"), br)
        out.append(
            {
                "acceptance_id": r["acceptance_id"],
                "gig_id": r["gig_id"],
                "gig_title": g.get("title"),
                "gig_category": g.get("category"),
                "gig_scheduled_date": g.get("scheduled_date"),
                "worker_id": r["worker_id"],
                "worker_name": w.get("name"),
                "worker_email": w.get("email"),
                "clock_in_at": r.get("clock_in_at"),
                "clock_out_at": r.get("clock_out_at"),
                "hours_worked": r.get("hours_worked"),
                "break_minutes": br,
                "paid_hours": paid_hours,
                "pay_rate_applied": rate,
                "pay_type_applied": ptype,
                "earnings": earnings,
                "timesheet_approved": bool(r.get("timesheet_approved")),
                "timesheet_approved_at": r.get("timesheet_approved_at"),
                "timesheet_approved_by": r.get("timesheet_approved_by"),
            }
        )
    return out


@router.get("/admin/reports/timesheets")
async def admin_reports_timesheets(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    worker_id: Optional[str] = Query(None),
    gig_id: Optional[str] = Query(None),
    only_approved: bool = Query(False),
    admin: dict = Depends(require_admin),
):
    """Return timesheet rows + totals."""
    rows = await _build_timesheet_rows(start, end, worker_id, gig_id, only_approved)
    total_hours = round(sum((r.get("hours_worked") or 0) for r in rows), 2)
    total_paid_hours = round(sum((r.get("paid_hours") or 0) for r in rows), 2)
    total_break_minutes = sum((r.get("break_minutes") or 0) for r in rows)
    total_earnings = round(sum((r.get("earnings") or 0) for r in rows), 2)
    approved_earnings = round(
        sum((r.get("earnings") or 0) for r in rows if r.get("timesheet_approved")), 2
    )
    return {
        "rows": rows,
        "totals": {
            "rows": len(rows),
            "hours": total_hours,
            "paid_hours": total_paid_hours,
            "break_minutes": total_break_minutes,
            "earnings": total_earnings,
            "approved_earnings": approved_earnings,
        },
        "filter": {"start": start, "end": end, "worker_id": worker_id, "gig_id": gig_id, "only_approved": only_approved},
    }


def _fmt_dt_for_csv(iso: Optional[str]) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso


def _csv_escape(v) -> str:
    if v is None:
        return ""
    s = str(v)
    if any(c in s for c in [",", '"', "\n", "\r"]):
        return '"' + s.replace('"', '""') + '"'
    return s


@router.get("/admin/reports/timesheets.csv")
async def admin_reports_timesheets_csv(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    worker_id: Optional[str] = Query(None),
    gig_id: Optional[str] = Query(None),
    only_approved: bool = Query(False),
    admin: dict = Depends(require_admin),
):
    """Download timesheet report as CSV."""
    rows = await _build_timesheet_rows(start, end, worker_id, gig_id, only_approved)
    header = [
        "Worker", "Worker email", "Gig", "Date", "Clock-in", "Clock-out",
        "Hours clocked", "Break (min)", "Paid hours", "Pay rate", "Pay type", "Earnings", "Timesheet approved",
    ]
    lines = [",".join(header)]
    for r in rows:
        rate = r.get("pay_rate_applied")
        rate_s = f"{rate:.2f}" if rate is not None else ""
        earnings = r.get("earnings")
        earnings_s = f"{earnings:.2f}" if earnings is not None else ""
        hours = r.get("hours_worked")
        hours_s = f"{hours:.2f}" if hours is not None else ""
        br = r.get("break_minutes")
        br_s = f"{br:d}" if br is not None else "0"
        paid = r.get("paid_hours")
        paid_s = f"{paid:.2f}" if paid is not None else ""
        lines.append(",".join(_csv_escape(c) for c in [
            r.get("worker_name") or "",
            r.get("worker_email") or "",
            r.get("gig_title") or "",
            r.get("gig_scheduled_date") or "",
            _fmt_dt_for_csv(r.get("clock_in_at")),
            _fmt_dt_for_csv(r.get("clock_out_at")),
            hours_s,
            br_s,
            paid_s,
            rate_s,
            r.get("pay_type_applied") or "",
            earnings_s,
            "yes" if r.get("timesheet_approved") else "no",
        ]))
    body = "\n".join(lines) + "\n"
    filename = f"hcob-timesheets-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    return FastAPIResponse(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ----------------------------------------------------------------------------
# Generic report dispatcher — workers / gigs / activity / earnings
# ----------------------------------------------------------------------------
async def _build_blasts_report(
    *,
    start: Optional[str],
    end: Optional[str],
    channel: Optional[str] = None,
    kind: Optional[str] = None,
) -> tuple[List[dict], List[dict]]:
    q: dict = {}
    if start or end:
        rng: dict = {}
        if start:
            rng["$gte"] = start
        if end:
            rng["$lte"] = end
        q["sent_at"] = rng
    if channel:
        q["channels"] = channel
    if kind:
        q["kind"] = kind
    rows = []
    async for d in db.blast_logs.find(q).sort("sent_at", -1).limit(2000):
        rows.append({
            "blast_id": d.get("blast_id"),
            "sent_at": d.get("sent_at"),
            "kind": d.get("kind"),
            "target_title": d.get("gig_title") or d.get("project_title") or "—",
            "target_id": d.get("gig_id") or d.get("project_id") or "",
            "channels": ", ".join(d.get("channels") or []) or "—",
            "channels_raw": d.get("channels") or [],
            "in_app": d.get("in_app", 0),
            "email": d.get("email", 0),
            "sms": d.get("sms", 0),
            "push": d.get("push", 0),
            "email_failed": d.get("email_failed", 0),
            "sms_failed": d.get("sms_failed", 0),
            "workers_targeted": d.get("workers_targeted", 0),
            "sent_by_name": d.get("sent_by_name") or "—",
        })
    cols = [
        {"key": "sent_at", "label": "Sent", "fmt": "dt"},
        {"key": "kind", "label": "Type"},
        {"key": "target_title", "label": "Gig / Project"},
        {"key": "channels", "label": "Channels"},
        {"key": "workers_targeted", "label": "Targeted"},
        {"key": "in_app", "label": "In-app"},
        {"key": "email", "label": "Email"},
        {"key": "sms", "label": "SMS"},
        {"key": "push", "label": "Push"},
        {"key": "email_failed", "label": "Email fail"},
        {"key": "sms_failed", "label": "SMS fail"},
        {"key": "sent_by_name", "label": "Sent by"},
    ]
    return rows, cols


async def _dispatch_report(report_type: str, params: dict) -> tuple[List[dict], List[dict], dict]:
    """Returns (rows, columns, totals) for the requested report type. Each
    report's totals dict has a `rows` count plus any meaningful sums."""
    if report_type == "workers":
        rows, cols = await _build_workers_report(
            skills=params.get("skills"),
            zip_code=params.get("zip_code"),
            zip_prefix=params.get("zip_prefix"),
            status=params.get("status"),
            profile_status=params.get("profile_status"),
            include_pii=bool(params.get("include_pii")),
        )
        totals = {
            "rows": len(rows),
            "jobs_completed": sum(r.get("jobs_completed", 0) for r in rows),
            "total_hours": round(sum(r.get("total_hours", 0) for r in rows), 2),
            "total_earned": round(sum(r.get("total_earned", 0) for r in rows), 2),
        }
        return rows, cols, totals
    if report_type == "gigs":
        rows, cols = await _build_gigs_report(
            start=params.get("start"),
            end=params.get("end"),
            category=params.get("category"),
            status=params.get("status"),
        )
        totals = {
            "rows": len(rows),
            "workers_assigned": sum(r.get("workers_assigned", 0) for r in rows),
            "workers_completed": sum(r.get("workers_completed", 0) for r in rows),
            "total_payout": round(sum(r.get("total_payout", 0) for r in rows), 2),
        }
        return rows, cols, totals
    if report_type == "activity":
        rows, cols = await _build_activity_report(
            start=params.get("start"),
            end=params.get("end"),
            worker_id=params.get("worker_id"),
        )
        totals = {
            "rows": len(rows),
            "completed": sum(r.get("gigs_completed", 0) for r in rows),
            "no_shows": sum(r.get("no_shows", 0) for r in rows),
            "total_hours": round(sum(r.get("total_hours", 0) for r in rows), 2),
            "total_earned": round(sum(r.get("total_earned", 0) for r in rows), 2),
        }
        return rows, cols, totals
    if report_type == "earnings":
        rows, cols = await _build_earnings_report(
            start=params.get("start"),
            end=params.get("end"),
            only_approved=bool(params.get("only_approved")),
        )
        totals = {
            "rows": len(rows),
            "approved_earned": round(sum(r.get("approved_earned", 0) for r in rows), 2),
            "pending_earned": round(sum(r.get("pending_earned", 0) for r in rows), 2),
            "total_earned": round(sum(r.get("total_earned", 0) for r in rows), 2),
            "total_hours": round(sum(r.get("total_hours", 0) for r in rows), 2),
        }
        return rows, cols, totals
    if report_type == "blasts":
        rows, cols = await _build_blasts_report(
            start=params.get("start"),
            end=params.get("end"),
            channel=params.get("channel"),
            kind=params.get("kind"),
        )
        totals = {
            "rows": len(rows),
            "workers_targeted": sum(r.get("workers_targeted", 0) for r in rows),
            "in_app": sum(r.get("in_app", 0) for r in rows),
            "email": sum(r.get("email", 0) for r in rows),
            "sms": sum(r.get("sms", 0) for r in rows),
            "push": sum(r.get("push", 0) for r in rows),
            "email_failed": sum(r.get("email_failed", 0) for r in rows),
            "sms_failed": sum(r.get("sms_failed", 0) for r in rows),
            "gig_blasts": sum(1 for r in rows if r.get("kind") == "gig"),
            "project_blasts": sum(1 for r in rows if r.get("kind") == "project"),
        }
        return rows, cols, totals
    raise HTTPException(400, f"Unknown report_type: {report_type}")


REPORT_TYPES = {"workers", "gigs", "activity", "earnings", "blasts"}
REPORT_TITLES = {
    "workers": "HCOB Workers",
    "gigs": "HCOB Gigs",
    "activity": "HCOB Worker Activity",
    "earnings": "HCOB Earnings",
    "blasts": "HCOB Gig Blasts",
}


def _params_from_query(
    start: Optional[str],
    end: Optional[str],
    worker_id: Optional[str],
    gig_id: Optional[str],
    skills: Optional[str],
    zip_code: Optional[str],
    zip_prefix: Optional[str],
    status: Optional[str],
    profile_status: Optional[str],
    category: Optional[str],
    only_approved: bool,
    include_pii: bool,
    channel: Optional[str] = None,
    kind: Optional[str] = None,
) -> dict:
    return {
        "start": start, "end": end,
        "worker_id": worker_id, "gig_id": gig_id,
        "skills": skills, "zip_code": zip_code, "zip_prefix": zip_prefix,
        "status": status, "profile_status": profile_status,
        "category": category, "only_approved": only_approved,
        "include_pii": include_pii,
        "channel": channel, "kind": kind,
    }


@router.get("/admin/reports/{report_type}.csv")
async def admin_reports_generic_csv(
    report_type: str,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    worker_id: Optional[str] = Query(None),
    gig_id: Optional[str] = Query(None),
    skills: Optional[str] = Query(None),
    zip_code: Optional[str] = Query(None),
    zip_prefix: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    profile_status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    only_approved: bool = Query(False),
    include_pii: bool = Query(False),
    channel: Optional[str] = Query(None),
    kind: Optional[str] = Query(None),
    admin: dict = Depends(require_admin),
):
    """Download any of the new report types as CSV."""
    if report_type == "timesheets":
        raise HTTPException(
            400,
            "Use /admin/reports/timesheets.csv directly for timesheets",
        )
    if report_type not in REPORT_TYPES:
        raise HTTPException(404, f"Unknown report_type: {report_type}")
    params = _params_from_query(
        start, end, worker_id, gig_id, skills, zip_code, zip_prefix, status,
        profile_status, category, only_approved, include_pii, channel, kind,
    )
    rows, cols, _totals = await _dispatch_report(report_type, params)
    header = ",".join(_csv_escape(c["label"]) for c in cols)
    lines = [header]
    for r in rows:
        lines.append(",".join(_csv_escape(r.get(c["key"], "")) for c in cols))
    body = "\n".join(lines) + "\n"
    filename = f"hcob-{report_type}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    return FastAPIResponse(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/admin/reports/{report_type}")
async def admin_reports_generic(
    report_type: str,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    worker_id: Optional[str] = Query(None),
    gig_id: Optional[str] = Query(None),
    skills: Optional[str] = Query(None),
    zip_code: Optional[str] = Query(None),
    zip_prefix: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    profile_status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    only_approved: bool = Query(False),
    include_pii: bool = Query(False),
    channel: Optional[str] = Query(None),
    kind: Optional[str] = Query(None),
    admin: dict = Depends(require_admin),
):
    """Generic JSON report. report_type ∈ {workers, gigs, activity, earnings, blasts}."""
    if report_type == "timesheets":
        raise HTTPException(
            400,
            "Use /admin/reports/timesheets directly for timesheets — this generic endpoint serves the newer report types",
        )
    if report_type not in REPORT_TYPES:
        raise HTTPException(404, f"Unknown report_type: {report_type}")
    params = _params_from_query(
        start, end, worker_id, gig_id, skills, zip_code, zip_prefix, status,
        profile_status, category, only_approved, include_pii, channel, kind,
    )
    rows, cols, totals = await _dispatch_report(report_type, params)
    return {"rows": rows, "columns": cols, "totals": totals, "filter": params}


@router.post("/admin/reports/export-google-sheets")
async def admin_reports_export_google_sheets(
    payload: dict,
    admin: dict = Depends(require_admin),
):
    """Export ANY report type to a new Google Sheet. Pass `report_type` in the
    body — defaults to `timesheets` for back-compat. Returns the sheet URL."""
    s = await _get_settings_doc()
    raw = s.get("google_service_account_json")
    if not raw:
        raise HTTPException(400, "Google service account JSON is not configured in admin settings")

    import json as _json
    try:
        info = _json.loads(raw)
    except Exception:
        raise HTTPException(400, "Saved Google service account JSON is invalid")

    report_type = (payload.get("report_type") or "timesheets").strip()
    start = payload.get("start")
    end = payload.get("end")

    # Build rows + columns based on the requested report
    if report_type == "timesheets":
        rows = await _build_timesheet_rows(
            start, end, payload.get("worker_id"), payload.get("gig_id"),
            bool(payload.get("only_approved")),
        )
        cols = [
            {"key": "worker_name", "label": "Worker"},
            {"key": "worker_email", "label": "Worker email"},
            {"key": "gig_title", "label": "Gig"},
            {"key": "gig_scheduled_date", "label": "Date"},
            {"key": "clock_in_at", "label": "Clock-in", "fmt": "dt"},
            {"key": "clock_out_at", "label": "Clock-out", "fmt": "dt"},
            {"key": "hours_worked", "label": "Hours", "fmt": "f2"},
            {"key": "pay_rate_applied", "label": "Pay rate", "fmt": "f2"},
            {"key": "pay_type_applied", "label": "Pay type"},
            {"key": "earnings", "label": "Earnings", "fmt": "f2"},
            {"key": "timesheet_approved", "label": "Timesheet approved", "fmt": "yesno"},
        ]
        sheet_tab = "Timesheets"
        totals_row = ["TOTALS"] + [""] * 5 + [
            round(sum(float(r.get("hours_worked") or 0) for r in rows), 2),
            "", "",
            round(sum(float(r.get("earnings") or 0) for r in rows), 2),
            "",
        ]
    else:
        if report_type not in REPORT_TYPES:
            raise HTTPException(400, f"Unknown report_type: {report_type}")
        params = {
            "start": start, "end": end,
            "worker_id": payload.get("worker_id"),
            "gig_id": payload.get("gig_id"),
            "skills": payload.get("skills"),
            "zip_code": payload.get("zip_code"),
            "zip_prefix": payload.get("zip_prefix"),
            "status": payload.get("status"),
            "profile_status": payload.get("profile_status"),
            "category": payload.get("category"),
            "only_approved": bool(payload.get("only_approved")),
            "include_pii": bool(payload.get("include_pii")),
        }
        rows, cols, totals = await _dispatch_report(report_type, params)
        sheet_tab = report_type.capitalize()
        # Build a totals row that fills only the numeric columns
        totals_row = []
        numeric_keys_to_total = {
            k for k in ("jobs_completed", "total_hours", "total_earned",
                        "workers_assigned", "workers_completed", "total_payout",
                        "gigs_requested", "gigs_approved", "gigs_completed", "no_shows",
                        "approved_earned", "pending_earned", "gigs", "slots")
        }
        for i, c in enumerate(cols):
            if i == 0:
                totals_row.append("TOTALS")
            elif c["key"] in numeric_keys_to_total:
                totals_row.append(
                    round(sum(float(r.get(c["key"]) or 0) for r in rows), 2)
                )
            else:
                totals_row.append("")

    title_parts = [REPORT_TITLES.get(report_type, "HCOB Report")]
    if start:
        title_parts.append(start[:10])
    if end:
        title_parts.append("→ " + end[:10])
    title_parts.append(datetime.now(timezone.utc).strftime("%H:%M UTC"))
    sheet_title = " ".join(title_parts)

    def _cell(r: dict, col: dict):
        v = r.get(col["key"])
        fmt = col.get("fmt")
        if v is None:
            return ""
        if fmt == "dt":
            return _fmt_dt_for_csv(v)
        if fmt == "f2":
            try:
                return float(v)
            except Exception:
                return v
        if fmt == "yesno":
            return "yes" if v else "no"
        return v

    def _build():
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
        drive = build("drive", "v3", credentials=creds, cache_discovery=False)

        spreadsheet = sheets.spreadsheets().create(body={
            "properties": {"title": sheet_title},
            "sheets": [{"properties": {"title": sheet_tab}}],
        }).execute()
        sheet_id = spreadsheet["spreadsheetId"]

        header = [c["label"] for c in cols]
        values = [header]
        for r in rows:
            values.append([_cell(r, c) for c in cols])
        values.append([])
        values.append(totals_row)

        sheets.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{sheet_tab}!A1",
            valueInputOption="RAW",
            body={"values": values},
        ).execute()

        share_email = s.get("google_sheets_share_email")
        if share_email:
            try:
                drive.permissions().create(
                    fileId=sheet_id,
                    body={"type": "user", "role": "writer", "emailAddress": share_email},
                    sendNotificationEmail=False,
                ).execute()
            except Exception as e:
                logger.warning(f"Could not share sheet with {share_email}: {e}")

        return {
            "spreadsheet_id": sheet_id,
            "url": f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit",
            "rows": len(rows),
            "report_type": report_type,
        }

    try:
        result = await asyncio.to_thread(_build)
    except Exception as e:
        logger.error(f"Google Sheets export failed: {e}")
        raise HTTPException(400, f"Google Sheets export failed: {e}")
    logger.info(f"Admin {admin['email']} exported {report_type} to {result['url']}")
    return result


@router.get("/me/shifts")
async def my_shifts(user: dict = Depends(get_current_user)):
    """Worker shift history — every completed shift (clock-out set) with
    full detail for the worker-facing history view. Unlike /me/earnings
    which is approved-only, this surfaces pending + approved + paid so
    the worker sees their entire timeline.

    Each row carries the gig/project context, clock times, hours + break,
    pay rate + earnings, approval status, admin notes, and the first
    names of every other approved contractor on the same gig.

    Returned sorted by clock-in time, newest first."""
    if user.get("role") != "worker":
        raise HTTPException(403, "Workers only")

    accs = await db.gig_acceptances.find(
        {"worker_id": user["user_id"], "clock_out_at": {"$ne": None}},
        {"_id": 0},
    ).sort("clock_in_at", -1).to_list(2000)
    if not accs:
        return {"shifts": []}

    # ---- Bulk-fetch gigs + projects + co-worker users ----------------------
    gig_ids = list({a["gig_id"] for a in accs if a.get("gig_id")})
    gigs = await db.gigs.find(
        {"gig_id": {"$in": gig_ids}}, {"_id": 0},
    ).to_list(length=2000)
    gmap = {g["gig_id"]: g for g in gigs}

    project_ids = list({g.get("project_id") for g in gigs if g.get("project_id")})
    projects = await db.projects.find(
        {"project_id": {"$in": project_ids}},
        {"_id": 0, "project_id": 1, "title": 1},
    ).to_list(length=500) if project_ids else []
    pmap = {p["project_id"]: p for p in projects}

    # Co-workers: every approved/clocked-in/completed contractor on each gig,
    # minus the requesting worker themselves.
    co_rows = await db.gig_acceptances.find(
        {
            "gig_id": {"$in": gig_ids},
            "worker_id": {"$ne": user["user_id"]},
            "status": {"$in": ["accepted", "on_the_clock", "completed", "backup"]},
        },
        {"_id": 0, "gig_id": 1, "worker_id": 1},
    ).to_list(length=4000)
    co_user_ids = list({c["worker_id"] for c in co_rows if c.get("worker_id")})
    co_users = await db.users.find(
        {"user_id": {"$in": co_user_ids}},
        {"_id": 0, "user_id": 1, "name": 1},
    ).to_list(length=2000) if co_user_ids else []
    co_user_by_id = {u["user_id"]: u for u in co_users}
    co_workers_by_gig: dict = {}
    for c in co_rows:
        gid = c.get("gig_id")
        wid = c.get("worker_id")
        u = co_user_by_id.get(wid)
        if not gid or not u:
            continue
        first = (u.get("name") or "").split(" ", 1)[0] or "—"
        co_workers_by_gig.setdefault(gid, []).append({
            "user_id": wid,
            "first_name": first,
        })

    def _status(a: dict) -> str:
        # Worker-friendly status label that respects payout lifecycle.
        if a.get("payout_paid_at") or a.get("paid_at"):
            return "paid"
        if a.get("timesheet_approved"):
            return "approved"
        if a.get("no_show_at"):
            return "no_show"
        return "pending"

    shifts: list[dict] = []
    for a in accs:
        g = gmap.get(a["gig_id"]) or {}
        br = _resolve_break_minutes(a, g)
        paid_hours = _compute_paid_hours(a.get("hours_worked"), br) or 0.0
        project_id = g.get("project_id")
        shifts.append({
            "acceptance_id": a.get("acceptance_id"),
            "gig_id": a.get("gig_id"),
            "gig_title": g.get("title"),
            "gig_category": g.get("category"),
            "gig_subcategory": g.get("subcategory"),
            "gig_scheduled_date": g.get("scheduled_date"),
            "project_id": project_id,
            "project_title": pmap.get(project_id, {}).get("title") if project_id else None,
            "clock_in_at": a.get("clock_in_at"),
            "clock_out_at": a.get("clock_out_at"),
            "hours_worked": round(float(a.get("hours_worked") or 0), 2),
            "break_minutes": int(br),
            "paid_hours": round(float(paid_hours), 2),
            "pay_rate_applied": a.get("pay_rate_applied"),
            "pay_type_applied": a.get("pay_type_applied"),
            "earnings": round(float(a.get("earnings") or 0), 2),
            "approval_status": _status(a),
            "timesheet_approved_at": a.get("timesheet_approved_at"),
            "admin_note": a.get("admin_note"),
            "no_show_reason": a.get("no_show_reason"),
            "co_workers": co_workers_by_gig.get(a["gig_id"], []),
        })

    return {"shifts": shifts}


@router.get("/me/earnings")
async def my_earnings(user: dict = Depends(get_current_user)):
    """Worker's own approved earnings — totals + per-gig list. Only APPROVED
    timesheets are released; pending timesheets are summarized separately."""
    if user.get("role") != "worker":
        raise HTTPException(403, "Workers only")
    rows = await db.gig_acceptances.find(
        {"worker_id": user["user_id"], "clock_out_at": {"$ne": None}}, {"_id": 0}
    ).sort("clock_out_at", -1).to_list(1000)
    if not rows:
        return {
            "approved": {"rows": [], "total_hours": 0, "total_earnings": 0},
            "pending": {"count": 0, "hours": 0},
        }
    gig_ids = list({r["gig_id"] for r in rows})
    gigs = await db.gigs.find({"gig_id": {"$in": gig_ids}}, {"_id": 0}).to_list(1000)
    gmap = {g["gig_id"]: g for g in gigs}

    approved_rows = []
    approved_hours = 0.0
    approved_paid_hours = 0.0
    approved_earnings = 0.0
    approved_break_minutes = 0
    pending_count = 0
    pending_hours = 0.0
    for r in rows:
        g = gmap.get(r["gig_id"]) or {}
        hours = r.get("hours_worked") or 0
        earnings = r.get("earnings")
        br = _resolve_break_minutes(r, g)
        paid_hours = _compute_paid_hours(r.get("hours_worked"), br) or 0.0
        if r.get("timesheet_approved"):
            approved_hours += float(hours)
            approved_paid_hours += float(paid_hours)
            approved_earnings += float(earnings or 0)
            approved_break_minutes += int(br)
            approved_rows.append({
                "acceptance_id": r["acceptance_id"],
                "gig_id": r["gig_id"],
                "gig_title": g.get("title"),
                "gig_category": g.get("category"),
                "gig_scheduled_date": g.get("scheduled_date"),
                "clock_in_at": r.get("clock_in_at"),
                "clock_out_at": r.get("clock_out_at"),
                "hours_worked": r.get("hours_worked"),
                "break_minutes": br,
                "paid_hours": paid_hours,
                "pay_rate_applied": r.get("pay_rate_applied"),
                "pay_type_applied": r.get("pay_type_applied"),
                "earnings": earnings,
                "timesheet_approved_at": r.get("timesheet_approved_at"),
            })
        else:
            pending_count += 1
            pending_hours += float(hours)
    return {
        "approved": {
            "rows": approved_rows,
            "total_hours": round(approved_hours, 2),
            "total_paid_hours": round(approved_paid_hours, 2),
            "total_break_minutes": approved_break_minutes,
            "total_earnings": round(approved_earnings, 2),
        },
        "pending": {
            "count": pending_count,
            "hours": round(pending_hours, 2),
        },
    }



