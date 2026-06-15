"""Gigs routes — CRUD + accept/withdraw/approve/reject/assign/remove +
blast/rush/tags/publish + clock in/out + cancel-shift + backup logic.

Wiring in server.py:
    from routes.gigs import (
        router as gigs_router,
        _gig_doc,
        _strip_sensitive_for_worker,
        _effective_status,
        _resolve_pay,
        _resolve_break_minutes,
        _compute_paid_hours,
        _compute_earnings,
        _format_gig_email,
        _format_gig_sms,
        _notify_matching_workers_of_new_gig,
        _publish_due_gigs_loop,
    )
    api.include_router(gigs_router)
"""
import re
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from config import db, logger, VAPID_PRIVATE_KEY
from auth_deps import (
    get_current_user,
    require_admin,
    _profile_missing_fields,
    _get_user_by_id,
)
from notifications import (
    _resolve_public_base,
    _resolve_email_creds,
    _resolve_sms_creds,
    _send_email_sync,
    _send_sms_sync,
    _send_gig_event_email,
    _log_blast,
)
from push_service import _send_push_to_user
from constants import GIG_TAG_VALUES, GIG_CATEGORY_TO_SKILLS
from models import (
    GigIn,
    GigPatch,
    BlastIn,
    RushToggleIn,
    GigTagsIn,
    AssignWorkerIn,
    CancelShiftIn,
)

router = APIRouter()


# ============================================================================
# Helpers — re-exported for use by other modules (admin/timesheet/reports)
# ============================================================================
def _gig_doc(payload: GigIn, created_by: str) -> dict:
    return {
        "gig_id": f"gig_{uuid.uuid4().hex[:12]}",
        "title": payload.title,
        "description": payload.description,
        "category": payload.category,
        "subcategory": payload.subcategory,
        "location": payload.location,
        "address_line": payload.address_line,
        "scheduled_date": payload.scheduled_date,
        "scheduled_at": payload.scheduled_at,
        "scheduled_local": payload.scheduled_local,
        "pay_rate": payload.pay_rate,
        "pay_type": payload.pay_type,
        "slots": payload.slots,
        "slots_filled": 0,
        "backup_slots": int(payload.backup_slots or 0),
        "backups_filled": 0,
        "duration_hours": payload.duration_hours,
        "break_minutes": int(payload.break_minutes or 0),
        "payment_timeline": payload.payment_timeline or "2_3_days",
        "payment_timeline_note": payload.payment_timeline_note,
        "contact_phone": payload.contact_phone,
        "project_id": payload.project_id,
        "status": payload.status or "open",
        "publish_at": payload.publish_at,
        "is_rush": False,
        "rush_at": None,
        "tags": [],
        "created_by": created_by,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "blast_count": 0,
        "last_blast_at": None,
        "blast_channels": [],
    }


def _strip_sensitive_for_worker(gig: dict, my_acceptance: Optional[dict]) -> dict:
    """Hide address_line from workers whose request is still 'requested'.

    The full address is only revealed when the admin has approved the request
    (status in 'accepted' / 'on_the_clock' / 'completed'), or to admins.
    """
    revealed_statuses = {"accepted", "on_the_clock", "completed"}
    if my_acceptance and my_acceptance.get("status") in revealed_statuses:
        return gig
    g = dict(gig)
    g.pop("address_line", None)
    return g


def _effective_status(user: dict) -> str:
    """Existing users without the field default to 'approved' for back-compat."""
    if user.get("role") == "admin":
        return "approved"
    return user.get("worker_status") or "approved"


def _resolve_pay(
    acceptance: Optional[dict], worker: Optional[dict], gig: Optional[dict]
) -> dict:
    """Resolve the effective pay rate + type for a worker on a gig.

    Precedence: per-gig override > worker default > gig posted rate.
    Rate and type are resolved independently (e.g. worker default rate can apply
    while gig's pay_type drives whether it's hourly vs flat).
    """
    rate = None
    rate_source = None
    if acceptance and acceptance.get("pay_rate_override") is not None:
        rate = float(acceptance["pay_rate_override"])
        rate_source = "gig_override"
    elif worker and worker.get("default_pay_rate") is not None:
        rate = float(worker["default_pay_rate"])
        rate_source = "worker_default"
    elif gig and gig.get("pay_rate") is not None:
        rate = float(gig["pay_rate"])
        rate_source = "gig_posted"

    ptype = None
    ptype_source = None
    if acceptance and acceptance.get("pay_type_override"):
        ptype = acceptance["pay_type_override"]
        ptype_source = "gig_override"
    elif worker and worker.get("default_pay_type"):
        ptype = worker["default_pay_type"]
        ptype_source = "worker_default"
    elif gig and gig.get("pay_type"):
        ptype = gig["pay_type"]
        ptype_source = "gig_posted"

    return {
        "pay_rate": rate,
        "pay_type": ptype,
        "pay_rate_source": rate_source,
        "pay_type_source": ptype_source,
    }


def _resolve_break_minutes(acceptance: Optional[dict], gig: Optional[dict]) -> int:
    """Per-worker break override on the acceptance wins; otherwise fall back to
    the gig's default break_minutes; otherwise 0. Never negative."""
    if acceptance is not None and acceptance.get("break_minutes") is not None:
        return max(0, int(acceptance["break_minutes"]))
    if gig is not None and gig.get("break_minutes") is not None:
        return max(0, int(gig["break_minutes"]))
    return 0


def _compute_paid_hours(hours_worked: Optional[float], break_minutes: int) -> Optional[float]:
    """Subtract unpaid break minutes from clocked hours. Never negative."""
    if hours_worked is None:
        return None
    paid = round(float(hours_worked) - (float(break_minutes) / 60.0), 2)
    return max(0.0, paid)


def _compute_earnings(pay_rate: Optional[float], pay_type: Optional[str], hours: Optional[float], break_minutes: int = 0) -> Optional[float]:
    """Compute earnings, deducting unpaid break minutes from hourly pay only.
    Flat-rate gigs always pay the posted amount regardless of break."""
    if pay_rate is None or pay_type is None:
        return None
    if pay_type == "hourly":
        paid_hours = _compute_paid_hours(hours, break_minutes) or 0.0
        return round(float(pay_rate) * float(paid_hours), 2)
    # flat / fixed rate — full posted amount regardless of hours / break
    return round(float(pay_rate), 2)


def _format_gig_email(gig: dict, base_url: str = "") -> str:
    pay = (
        f"${gig['pay_rate']:.2f}/hr"
        if gig["pay_type"] == "hourly"
        else f"${gig['pay_rate']:.2f} flat"
    )
    base = (base_url or _resolve_public_base()).rstrip("/")
    cta_url = f"{base}/gigs/{gig['gig_id']}"
    cta_block = f"""
            <table cellpadding="0" cellspacing="0" style="margin:24px 0 8px;">
              <tr><td bgcolor="#0044FF" style="border-radius:0;">
                <a href="{cta_url}" target="_blank" style="display:inline-block;padding:14px 28px;background:#0044FF;color:#FFFFFF;font-size:15px;font-weight:bold;letter-spacing:.04em;text-decoration:none;text-transform:uppercase;">
                  View & accept this gig →
                </a>
              </td></tr>
            </table>
            <p style="margin:4px 0 0;font-size:12px;color:#6B7280;">
              Or open this link in your phone:<br/>
              <a href="{cta_url}" style="color:#0044FF;word-break:break-all;">{cta_url}</a>
            </p>"""
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="font-family:Arial,Helvetica,sans-serif;background:#F9FAFB;padding:24px;">
      <tr><td>
        <table width="600" cellpadding="0" cellspacing="0" align="center" style="background:#FFFFFF;border:1px solid #E5E7EB;">
          <tr><td style="padding:24px;border-bottom:4px solid #0044FF;">
            <div style="font-size:11px;letter-spacing:.2em;color:#4B5563;text-transform:uppercase;">New Gig Opportunity</div>
            <h1 style="margin:8px 0 0;font-size:28px;color:#030712;">{gig['title']}</h1>
          </td></tr>
          <tr><td style="padding:24px;color:#030712;font-size:15px;line-height:1.6;">
            <p>{gig['description']}</p>
            <table cellpadding="6" style="margin-top:16px;font-size:14px;">
              <tr><td style="color:#4B5563;">Category</td><td><strong>{gig['category'].title()}</strong></td></tr>
              <tr><td style="color:#4B5563;">Location</td><td><strong>{gig['location']}</strong></td></tr>
              <tr><td style="color:#4B5563;">When</td><td><strong>{gig['scheduled_date']}</strong></td></tr>
              <tr><td style="color:#4B5563;">Pay</td><td><strong>{pay}</strong></td></tr>
              <tr><td style="color:#4B5563;">Slots</td><td><strong>{gig['slots']}</strong></td></tr>
            </table>
            {cta_block}
            <p style="margin-top:24px;color:#4B5563;font-size:13px;">Be quick — gigs fill on a first-claimed basis.</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
    """


def _format_gig_sms(gig: dict, base_url: str = "") -> str:
    pay = (
        f"${gig['pay_rate']:.0f}/hr"
        if gig["pay_type"] == "hourly"
        else f"${gig['pay_rate']:.0f}"
    )
    base = (base_url or _resolve_public_base()).rstrip("/")
    link = f"{base}/gigs/{gig['gig_id']}"
    return (
        f"[HCOB Network] {gig['title']} — {gig['location']} — "
        f"{gig['scheduled_date']} — {pay}. Tap to claim: {link}"
    )


async def _promote_first_backup(gig_id: str, *, reason: str = "auto") -> Optional[dict]:
    """Promote the lowest-numbered backup to primary on a gig. Returns the
    promoted acceptance doc, or None if no backup exists."""
    backup = await db.gig_acceptances.find_one(
        {"gig_id": gig_id, "is_backup": True, "status": "backup"},
        sort=[("backup_order", 1)],
    )
    if not backup:
        return None
    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        return None
    filled = int(gig.get("slots_filled") or 0)
    if filled >= int(gig.get("slots", 1)):
        return None  # no primary spot to promote into
    now = datetime.now(timezone.utc).isoformat()
    await db.gig_acceptances.update_one(
        {"acceptance_id": backup["acceptance_id"]},
        {"$set": {
            "status": "accepted",
            "is_backup": False,
            "backup_order": None,
            "promoted_at": now,
            "promoted_reason": reason,
        }},
    )
    new_filled = filled + 1
    gig_update = {
        "slots_filled": new_filled,
        "backups_filled": max(0, int(gig.get("backups_filled") or 0) - 1),
    }
    if new_filled >= int(gig.get("slots", 1)):
        gig_update["status"] = "filled"
    await db.gigs.update_one({"gig_id": gig_id}, {"$set": gig_update})

    # Notify the promoted worker
    await db.notifications.insert_one({
        "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
        "user_id": backup["worker_id"],
        "gig_id": gig_id,
        "title": f"You're up! Promoted to primary: {gig.get('title')}",
        "body": "A backup spot opened — you're now a primary worker on this gig.",
        "read": False,
        "created_at": now,
    })
    body_html = (
        f"<p><strong>You've been promoted to primary</strong> on <strong>{gig.get('title')}</strong>!</p>"
        f"<p>A primary worker dropped out, so your backup slot just became real.</p>"
        f"<p><strong>When:</strong> {gig.get('scheduled_date') or 'See gig'}<br/>"
        f"<strong>Where:</strong> {gig.get('location') or 'TBD'}<br/>"
        f"<strong>Pay:</strong> ${gig.get('pay_rate'):.2f}{'/hr' if gig.get('pay_type') == 'hourly' else ' flat'}</p>"
        f"<p>Open the app to see the full address and clock in when you arrive.</p>"
    )
    await _send_gig_event_email(
        backup["worker_id"], kind="gig_backup_promoted",
        subject=f"Promoted to primary — {gig.get('title')}",
        body_html=body_html, gig_id=gig_id,
    )
    # Best-effort push notification
    try:
        await _send_push_to_user(
            backup["worker_id"],
            {
                "title": f"You're up on {gig.get('title')}",
                "body": "A backup slot opened — you're now primary. Open the app.",
                "tag": f"gig-promoted-{gig_id}",
                "url": f"/gigs/{gig_id}",
                "kind": "gig_promoted",
            },
        )
    except Exception:
        pass
    logger.info(f"Promoted backup {backup['acceptance_id']} → primary on gig {gig_id} ({reason})")
    return {k: v for k, v in backup.items() if k != "_id"}


async def _notify_matching_workers_of_new_gig(gig: dict) -> int:
    """Push an in-app notification to every approved worker whose skills
    overlap with the gig's category AND whose ZIP starts with the gig's ZIP
    prefix (or has no ZIP — they get notified too rather than miss out)."""
    target_skills = GIG_CATEGORY_TO_SKILLS.get(gig.get("category"), [])
    if not target_skills:
        return 0

    # Extract ZIP from gig.location for proximity match (same regex used by
    # the create-gig dialog auto-suggest panel).
    m = re.search(r"\b(\d{5})\b", (gig.get("location") or ""))
    gig_zip = m.group(1) if m else ""
    zip_prefix = gig_zip[:3] if gig_zip else ""

    workers = await db.users.find(
        {"role": "worker"}, {"_id": 0, "user_id": 1, "skills": 1, "zip_code": 1, "worker_status": 1}
    ).to_list(5000)
    notified_ids: List[str] = []
    for w in workers:
        if _effective_status(w) in ("rejected", "suspended"):
            continue
        if not any(s in (w.get("skills") or []) for s in target_skills):
            continue
        wzip = (w.get("zip_code") or "").strip()
        if zip_prefix and wzip and not wzip.startswith(zip_prefix):
            continue
        notified_ids.append(w["user_id"])

    if not notified_ids:
        return 0
    now_iso = datetime.now(timezone.utc).isoformat()
    docs = [
        {
            "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
            "user_id": uid,
            "gig_id": gig["gig_id"],
            "title": f"New gig: {gig.get('title')}",
            "body": (gig.get("description") or "")[:140],
            "read": False,
            "created_at": now_iso,
        }
        for uid in notified_ids
    ]
    await db.notifications.insert_many(docs)
    logger.info(f"Notified {len(notified_ids)} matching workers about gig {gig['gig_id']}")
    return len(notified_ids)


async def _publish_due_gigs_loop():
    """Background task — every 60s, flip any `coming_soon` gig whose
    publish_at has passed into `open` and notify matching workers."""
    while True:
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            due = await db.gigs.find(
                {
                    "status": "coming_soon",
                    "publish_at": {"$ne": None, "$lte": now_iso},
                },
                {"_id": 0},
            ).to_list(100)
            for g in due:
                await db.gigs.update_one(
                    {"gig_id": g["gig_id"]},
                    {"$set": {"status": "open", "published_at": now_iso}},
                )
                try:
                    await _notify_matching_workers_of_new_gig(g)
                except Exception as e:
                    logger.error(f"Auto-publish notify failed for {g['gig_id']}: {e}")
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"_publish_due_gigs_loop error: {e}")
            await asyncio.sleep(60)


# ============================================================================
# Routes
# ============================================================================
@router.post("/gigs")
async def create_gig(payload: GigIn, admin: dict = Depends(require_admin)):
    base = _gig_doc(payload, admin["user_id"])

    rec = payload.recurrence or "none"
    count = max(1, min(52, payload.repeat_count or 1)) if rec != "none" else 1

    if rec == "none" or count == 1:
        await db.gigs.insert_one(base)
        base.pop("_id", None)
        return {**base, "created_count": 1}

    # Need a base ISO datetime to space occurrences. Bail back to single-gig if missing.
    if not payload.scheduled_at:
        await db.gigs.insert_one(base)
        base.pop("_id", None)
        return {**base, "created_count": 1}

    try:
        base_dt = datetime.fromisoformat(payload.scheduled_at.replace("Z", "+00:00"))
    except Exception:
        await db.gigs.insert_one(base)
        base.pop("_id", None)
        return {**base, "created_count": 1}

    # Parse the wall-clock too (if the client sent it). This lets us format the
    # human-readable `scheduled_date` for every occurrence using the admin's
    # local wall-clock time instead of UTC (which would shift the displayed
    # hour for every admin not in UTC).
    base_local: Optional[datetime] = None
    if payload.scheduled_local:
        try:
            base_local = datetime.fromisoformat(payload.scheduled_local)
        except Exception:
            base_local = None

    def _add_months(dt: datetime, months: int) -> datetime:
        m0 = dt.month - 1 + months
        new_year = dt.year + m0 // 12
        new_month = m0 % 12 + 1
        max_day = [31, 29 if new_year % 4 == 0 and (new_year % 100 != 0 or new_year % 400 == 0) else 28,
                   31, 30, 31, 30, 31, 31, 30, 31, 30, 31][new_month - 1]
        return dt.replace(year=new_year, month=new_month, day=min(dt.day, max_day))

    series_id = f"ser_{uuid.uuid4().hex[:12]}"
    docs: List[dict] = []
    for i in range(count):
        if rec == "daily":
            occ_dt = base_dt + timedelta(days=i)
            occ_local = base_local + timedelta(days=i) if base_local else None
        elif rec == "weekly":
            occ_dt = base_dt + timedelta(weeks=i)
            occ_local = base_local + timedelta(weeks=i) if base_local else None
        elif rec == "biweekly":
            occ_dt = base_dt + timedelta(weeks=i * 2)
            occ_local = base_local + timedelta(weeks=i * 2) if base_local else None
        elif rec == "monthly":
            occ_dt = _add_months(base_dt, i)
            occ_local = _add_months(base_local, i) if base_local else None
        else:
            occ_dt = base_dt
            occ_local = base_local

        # Pick the source datetime for the human display string. Wall-clock
        # wins — that's what the admin saw in the dialog and is the same
        # number any worker will see in the feed, regardless of their TZ.
        display_src = occ_local or occ_dt

        doc = dict(base)
        doc["gig_id"] = f"gig_{uuid.uuid4().hex[:12]}"
        doc["scheduled_at"] = occ_dt.isoformat()
        doc["scheduled_local"] = occ_local.strftime("%Y-%m-%dT%H:%M") if occ_local else base.get("scheduled_local")
        doc["scheduled_date"] = display_src.strftime("%a %b %d · %-I:%M %p")
        doc["series_id"] = series_id
        doc["series_index"] = i
        doc["series_total"] = count
        doc["series_recurrence"] = rec
        docs.append(doc)

    await db.gigs.insert_many(docs)
    first = docs[0]
    first.pop("_id", None)
    return {**first, "created_count": count, "series_id": series_id}


@router.get("/gigs")
async def list_gigs(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    query: dict = {}
    # "all" means: no status filter at all (used by admin calendar / worker accepted list)
    if status and status != "all":
        query["status"] = status
    if category:
        query["category"] = category
    # Workers see open + coming_soon gigs by default (coming_soon is browseable
    # but not yet claimable; the request endpoint enforces the gate).
    if user.get("role") != "admin" and status is None:
        query["status"] = {"$in": ["open", "coming_soon"]}

    # Sort: RUSH first (newest rush_at first), then created_at desc.
    # MongoDB's sort treats missing fields as null which sorts BEFORE values
    # asc / AFTER values desc, so this puts rush_at-present gigs at the top.
    gigs = (
        await db.gigs.find(query, {"_id": 0})
        .sort([("is_rush", -1), ("rush_at", -1), ("created_at", -1)])
        .to_list(500)
    )

    # For workers, attach acceptance state + hide sensitive address until accepted
    if user.get("role") == "worker":
        accepted = await db.gig_acceptances.find(
            {"worker_id": user["user_id"]}, {"_id": 0}
        ).to_list(1000)
        accepted_map = {a["gig_id"]: a for a in accepted}

        # Pre-fetch project titles for any project-linked gigs in this feed so
        # the worker UI can show a 'PROJECT' badge on the card. We intentionally
        # only expose `project_id` + `title` here (no client_name) — full
        # project context is only revealed after acceptance.
        wpids = list({g.get("project_id") for g in gigs if g.get("project_id")})
        wpmap = {}
        if wpids:
            wprojs = await db.projects.find(
                {"project_id": {"$in": wpids}, "archived": {"$ne": True}},
                {"_id": 0, "project_id": 1, "title": 1},
            ).to_list(500)
            wpmap = {p["project_id"]: p for p in wprojs}

        out = []
        for g in gigs:
            a = accepted_map.get(g["gig_id"])
            g = _strip_sensitive_for_worker(g, a)
            g["my_acceptance"] = a
            pid = g.get("project_id")
            if pid and pid in wpmap:
                g["project"] = {
                    "project_id": pid,
                    "title": wpmap[pid].get("title"),
                }
            out.append(g)
        return out

    # For admins, enrich gigs that belong to a project with the project's title
    # so list views (Calendar, AdminGigs, Dashboard) can show a project pill
    # without N+1 fetches.
    pids = list({g.get("project_id") for g in gigs if g.get("project_id")})
    if pids:
        projs = await db.projects.find(
            {"project_id": {"$in": pids}},
            {"_id": 0, "project_id": 1, "title": 1, "client_name": 1},
        ).to_list(500)
        pmap = {p["project_id"]: p for p in projs}
        for g in gigs:
            pid = g.get("project_id")
            if pid and pid in pmap:
                g["project"] = {
                    "project_id": pid,
                    "title": pmap[pid].get("title"),
                    "client_name": pmap[pid].get("client_name"),
                }
    return gigs


@router.get("/gigs/{gig_id}")
async def get_gig(gig_id: str, user: dict = Depends(get_current_user)):
    gig = await db.gigs.find_one({"gig_id": gig_id}, {"_id": 0})
    if not gig:
        raise HTTPException(404, "Gig not found")
    if user.get("role") == "admin":
        # Attach BOTH pending requests and approved acceptances
        all_rows = await db.gig_acceptances.find(
            {"gig_id": gig_id}, {"_id": 0}
        ).to_list(500)
        if all_rows:
            worker_ids = list({a["worker_id"] for a in all_rows})
            workers = await db.users.find(
                {"user_id": {"$in": worker_ids}}, {"_id": 0, "password_hash": 0}
            ).to_list(500)
            wmap = {w["user_id"]: w for w in workers}
            for a in all_rows:
                w = wmap.get(a["worker_id"]) or {}
                a["worker_name"] = w.get("name")
                a["worker_email"] = w.get("email")
                a["worker_phone"] = w.get("phone")
                a["worker_id_verified"] = w.get("id_verified", False)
                a["worker_status"] = w.get("worker_status", "approved")
                a["worker_default_pay_rate"] = w.get("default_pay_rate")
                a["worker_default_pay_type"] = w.get("default_pay_type")
                # Resolved effective pay for this worker on this gig
                pay = _resolve_pay(a, w, gig)
                a["pay_rate_effective"] = pay["pay_rate"]
                a["pay_type_effective"] = pay["pay_type"]
                a["pay_rate_source"] = a.get("pay_rate_source") or pay["pay_rate_source"]
                a["pay_type_source"] = a.get("pay_type_source") or pay["pay_type_source"]
                # If not yet clocked out, project what they'd earn
                if a.get("earnings") is None and a.get("hours_worked") is not None:
                    br = _resolve_break_minutes(a, gig)
                    a["break_minutes_effective"] = br
                    a["paid_hours"] = _compute_paid_hours(a.get("hours_worked"), br)
                    a["projected_earnings"] = _compute_earnings(
                        pay["pay_rate"], pay["pay_type"], a.get("hours_worked"), br
                    )
                else:
                    # Surface the effective break + paid_hours for the admin UI
                    br = _resolve_break_minutes(a, gig)
                    a["break_minutes_effective"] = br
                    a["paid_hours"] = _compute_paid_hours(a.get("hours_worked"), br)
        gig["pending_requests"] = [a for a in all_rows if a.get("status") == "requested"]
        gig["backups"] = sorted(
            [a for a in all_rows if a.get("status") == "backup"],
            key=lambda a: a.get("backup_order") or 999,
        )
        gig["acceptances"] = [a for a in all_rows if a.get("status") not in ("requested", "backup")]

        # Project context for admins — surface the project title so the gig
        # detail page can show a "Part of project: …" banner with a deep link.
        if gig.get("project_id"):
            proj = await db.projects.find_one(
                {"project_id": gig["project_id"]},
                {"_id": 0, "project_id": 1, "title": 1, "client_name": 1, "archived": 1},
            )
            if proj:
                # Sibling gigs (any other gig linked to the same project)
                sib = await db.gigs.find(
                    {"project_id": gig["project_id"], "gig_id": {"$ne": gig_id}},
                    {"_id": 0, "gig_id": 1, "title": 1, "category": 1, "subcategory": 1, "scheduled_date": 1, "scheduled_at": 1, "slots": 1, "slots_filled": 1, "status": 1},
                ).sort("scheduled_at", 1).to_list(50)
                gig["project"] = {
                    "project_id": proj["project_id"],
                    "title": proj.get("title"),
                    "client_name": proj.get("client_name"),
                    "archived": bool(proj.get("archived")),
                    "sibling_gigs": sib,
                }
    else:
        my = await db.gig_acceptances.find_one(
            {"gig_id": gig_id, "worker_id": user["user_id"]}, {"_id": 0}
        )
        gig = _strip_sensitive_for_worker(gig, my)
        gig["my_acceptance"] = my

        # Minimal project hint shown to ALL workers (even before requesting) so
        # they know this gig is part of a coordinated project. Full sibling/
        # crew details are only revealed once approved (below).
        if gig.get("project_id"):
            proj_lite = await db.projects.find_one(
                {"project_id": gig["project_id"], "archived": {"$ne": True}},
                {"_id": 0, "project_id": 1, "title": 1},
            )
            if proj_lite:
                gig["project_lite"] = {
                    "project_id": proj_lite["project_id"],
                    "title": proj_lite.get("title"),
                }
        # If this worker is APPROVED (not just "requested"), let them see their
        # crew — other approved workers, first name + role only.
        if my and my.get("status") and my["status"] != "requested":
            crew_accs = await db.gig_acceptances.find(
                {
                    "gig_id": gig_id,
                    "status": {"$ne": "requested"},
                    "worker_id": {"$ne": user["user_id"]},
                },
                {"_id": 0, "worker_id": 1, "gig_role": 1},
            ).to_list(200)
            crew_ids = [a["worker_id"] for a in crew_accs]
            if crew_ids:
                crew_users = await db.users.find(
                    {"user_id": {"$in": crew_ids}},
                    {"_id": 0, "user_id": 1, "name": 1},
                ).to_list(200)
                wmap = {w["user_id"]: w for w in crew_users}
                gig["crew"] = [
                    {
                        "first_name": ((wmap.get(a["worker_id"]) or {}).get("name") or "Worker").split(" ")[0],
                        "gig_role": a.get("gig_role") or "worker",
                    }
                    for a in crew_accs
                ]
            else:
                gig["crew"] = []

        # Project context — show sibling gigs + their crews so coordinated
        # workers can see who else is on the same job site. Only exposed to
        # workers with an approved (non-requested) acceptance on THIS gig.
        if my and my.get("status") and my["status"] != "requested" and gig.get("project_id"):
            proj = await db.projects.find_one(
                {"project_id": gig["project_id"]},
                {"_id": 0, "project_id": 1, "title": 1, "client_name": 1},
            )
            if proj:
                sib_gigs = await db.gigs.find(
                    {"project_id": gig["project_id"], "gig_id": {"$ne": gig_id}},
                    {"_id": 0, "gig_id": 1, "title": 1, "category": 1, "subcategory": 1, "scheduled_date": 1, "scheduled_at": 1},
                ).sort("scheduled_at", 1).to_list(50)
                sib_ids = [g["gig_id"] for g in sib_gigs]
                sib_accs = await db.gig_acceptances.find(
                    {
                        "gig_id": {"$in": sib_ids},
                        "status": {"$in": ["accepted", "on_the_clock", "clocked_in", "completed"]},
                    },
                    {"_id": 0, "gig_id": 1, "worker_id": 1, "gig_role": 1},
                ).to_list(500)
                sib_worker_ids = [a["worker_id"] for a in sib_accs]
                sib_users = await db.users.find(
                    {"user_id": {"$in": sib_worker_ids}},
                    {"_id": 0, "user_id": 1, "name": 1},
                ).to_list(500) if sib_worker_ids else []
                wmap = {w["user_id"]: w for w in sib_users}
                gtitle = {g["gig_id"]: g.get("title") for g in sib_gigs}
                project_crew = [
                    {
                        "first_name": ((wmap.get(a["worker_id"]) or {}).get("name") or "Worker").split(" ")[0],
                        "gig_role": a.get("gig_role") or "worker",
                        "gig_id": a["gig_id"],
                        "gig_title": gtitle.get(a["gig_id"]),
                    }
                    for a in sib_accs
                ]
                gig["project"] = {
                    "project_id": proj["project_id"],
                    "title": proj.get("title"),
                    "client_name": proj.get("client_name"),
                    "sibling_gigs": sib_gigs,
                    "crew": project_crew,
                }
    return gig


@router.delete("/gigs/{gig_id}")
async def delete_gig(gig_id: str, admin: dict = Depends(require_admin)):
    result = await db.gigs.delete_one({"gig_id": gig_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Gig not found")
    await db.gig_acceptances.delete_many({"gig_id": gig_id})
    return {"ok": True}


@router.put("/gigs/{gig_id}")
async def update_gig(
    gig_id: str, payload: GigPatch, admin: dict = Depends(require_admin)
):
    """Partial update of a gig. Validates slots vs slots_filled and recomputes status."""
    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")

    updates = payload.model_dump(exclude_unset=True)
    # Handle `clear_project` sentinel separately — it isn't a real DB field.
    clear_project = updates.pop("clear_project", False)
    if clear_project:
        updates["project_id"] = None
    if "slots" in updates:
        new_slots = int(updates["slots"])
        filled = int(gig.get("slots_filled") or 0)
        if new_slots < filled:
            raise HTTPException(
                400,
                f"Cannot reduce slots below current acceptances ({filled} workers already accepted)",
            )
        # Re-evaluate status when slot count changes
        if filled >= new_slots:
            updates["status"] = "filled"
        elif gig.get("status") == "filled" and filled < new_slots:
            updates["status"] = "open"

    if "backup_slots" in updates:
        new_backup = int(updates["backup_slots"] or 0)
        backups_filled = int(gig.get("backups_filled") or 0)
        if new_backup < backups_filled:
            raise HTTPException(
                400,
                f"Cannot reduce backup slots below current backups ({backups_filled} backups already approved)",
            )

    if not updates:
        return {k: v for k, v in gig.items() if k != "_id"}

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    updates["updated_by"] = admin["email"]
    await db.gigs.update_one({"gig_id": gig_id}, {"$set": updates})
    fresh = await db.gigs.find_one({"gig_id": gig_id}, {"_id": 0})

    # ---- Email notifications to currently-accepted workers if material change ----
    changed_fields: List[str] = []
    if "scheduled_date" in updates and updates["scheduled_date"] != gig.get("scheduled_date"):
        changed_fields.append(f"new date/time: <strong>{updates['scheduled_date']}</strong>")
    if "scheduled_at" in updates and updates["scheduled_at"] != gig.get("scheduled_at"):
        changed_fields.append("schedule timestamp updated")
    if "pay_rate" in updates and float(updates["pay_rate"]) != float(gig.get("pay_rate") or 0):
        changed_fields.append(f"new pay rate: <strong>${float(updates['pay_rate']):.2f}{'/hr' if (updates.get('pay_type') or gig.get('pay_type')) == 'hourly' else ' flat'}</strong>")
    if "pay_type" in updates and updates["pay_type"] != gig.get("pay_type"):
        changed_fields.append(f"pay type changed to <strong>{updates['pay_type']}</strong>")
    if "location" in updates and updates["location"] != gig.get("location"):
        changed_fields.append("location updated")
    if "status" in updates and updates["status"] == "cancelled" and gig.get("status") != "cancelled":
        # Special path — fire a dedicated "gig cancelled" email instead
        cancelled_acceptances = await db.gig_acceptances.find(
            {"gig_id": gig_id, "status": {"$in": ["accepted", "backup", "on_the_clock"]}}
        ).to_list(500)
        for a in cancelled_acceptances:
            body_html = (
                f"<p><strong>Heads up — this gig was cancelled by HCOB.</strong></p>"
                f"<p><strong>{gig.get('title')}</strong> on {gig.get('scheduled_date') or ''} is no longer happening.</p>"
                f"<p>Check the app for other open gigs in your feed.</p>"
            )
            await _send_gig_event_email(
                a["worker_id"], kind="gig_cancelled_by_admin",
                subject=f"Gig cancelled: {gig.get('title')}",
                body_html=body_html, gig_id=gig_id,
            )
        changed_fields = []  # don't double-fire the generic "updated" email
    if changed_fields:
        affected = await db.gig_acceptances.find(
            {"gig_id": gig_id, "status": {"$in": ["accepted", "backup", "on_the_clock"]}}
        ).to_list(500)
        change_html = "<ul>" + "".join(f"<li>{c}</li>" for c in changed_fields) + "</ul>"
        for a in affected:
            body_html = (
                f"<p>HCOB updated the details for <strong>{fresh.get('title')}</strong>:</p>"
                f"{change_html}"
                f"<p>Open the app to see the latest info.</p>"
            )
            await _send_gig_event_email(
                a["worker_id"], kind="gig_updated",
                subject=f"Gig updated: {fresh.get('title')}",
                body_html=body_html, gig_id=gig_id,
            )

    return fresh


@router.post("/gigs/{gig_id}/duplicate")
async def duplicate_gig(gig_id: str, admin: dict = Depends(require_admin)):
    """Clone an existing gig into a fresh, empty 'open' gig."""
    src = await db.gigs.find_one({"gig_id": gig_id})
    if not src:
        raise HTTPException(404, "Gig not found")
    title = src.get("title") or "Gig"
    suffix = " (copy)" if not title.endswith(" (copy)") else ""
    doc = {
        "gig_id": f"gig_{uuid.uuid4().hex[:12]}",
        "title": f"{title}{suffix}",
        "description": src.get("description") or "",
        "category": src.get("category"),
        "subcategory": src.get("subcategory"),
        "location": src.get("location"),
        "address_line": src.get("address_line"),
        "scheduled_date": src.get("scheduled_date"),
        "scheduled_at": src.get("scheduled_at"),
        "pay_rate": src.get("pay_rate"),
        "pay_type": src.get("pay_type"),
        "slots": src.get("slots") or 1,
        "slots_filled": 0,
        "backup_slots": int(src.get("backup_slots") or 0),
        "backups_filled": 0,
        "duration_hours": src.get("duration_hours"),
        "break_minutes": int(src.get("break_minutes") or 0),
        "payment_timeline": src.get("payment_timeline") or "2_3_days",
        "payment_timeline_note": src.get("payment_timeline_note"),
        "contact_phone": src.get("contact_phone"),
        "project_id": src.get("project_id"),
        "status": "open",
        "publish_at": None,
        "is_rush": False,
        "rush_at": None,
        "tags": [],
        "created_by": admin["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "blast_count": 0,
        "last_blast_at": None,
        "blast_channels": [],
        "duplicated_from": gig_id,
    }
    await db.gigs.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.post("/gigs/{gig_id}/accept")
async def accept_gig(gig_id: str, user: dict = Depends(get_current_user)):
    """Worker REQUESTS a gig. Admin must approve before slot is reserved."""
    if user.get("role") != "worker":
        raise HTTPException(403, "Only workers can request gigs")

    # Ban gate — admins can reject or suspend a bad actor to stop them entirely.
    status_ = _effective_status(user)
    if status_ == "rejected":
        raise HTTPException(
            403, "Your account is not authorized to request gigs. Contact HCOB if you believe this is a mistake."
        )
    if status_ == "suspended":
        raise HTTPException(
            403, "Your account has been suspended. Contact HCOB to reinstate."
        )

    # ID gate — workers must have an ID on file and HCOB-verified before requesting.
    if not user.get("id_image_path"):
        raise HTTPException(
            403, "Upload a photo of your ID on your profile before requesting gigs"
        )
    if not user.get("id_verified"):
        raise HTTPException(
            403, "Your ID is awaiting verification by HCOB before you can request gigs"
        )

    # Profile gate — make sure the worker has filled out the required profile
    # fields so admins have enough context to approve them.
    missing = _profile_missing_fields(user)
    if missing:
        raise HTTPException(
            403,
            "Complete your profile before requesting gigs. Missing: "
            + ", ".join(missing),
        )

    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")
    if gig.get("status") == "coming_soon":
        publish_at = gig.get("publish_at")
        when = f" — opens {publish_at[:16].replace('T', ' ')}" if publish_at else ""
        raise HTTPException(
            400, f"This gig isn't claimable yet{when}. Check back soon."
        )
    if gig.get("status") != "open":
        raise HTTPException(400, "Gig is not open")

    existing = await db.gig_acceptances.find_one(
        {"gig_id": gig_id, "worker_id": user["user_id"]}
    )
    if existing:
        raise HTTPException(400, "You've already requested or been approved for this gig")

    acceptance = {
        "acceptance_id": f"acc_{uuid.uuid4().hex[:12]}",
        "gig_id": gig_id,
        "worker_id": user["user_id"],
        # NEW model: worker requests, admin approves. Slot is NOT reserved on request.
        "status": "requested",
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "accepted_at": None,
    }
    await db.gig_acceptances.insert_one(acceptance)
    acceptance.pop("_id", None)
    return acceptance


@router.post("/gigs/{gig_id}/requests/{acceptance_id}/approve")
async def approve_request(
    gig_id: str,
    acceptance_id: str,
    admin: dict = Depends(require_admin),
):
    """Admin approves a worker's gig request — reserves the slot."""
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Request not found")
    if acceptance.get("status") != "requested":
        raise HTTPException(400, "Request is not pending approval")

    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")
    filled = int(gig.get("slots_filled") or 0)
    if filled >= int(gig.get("slots", 1)):
        raise HTTPException(400, "All slots are already filled — use /approve-backup instead")

    now = datetime.now(timezone.utc).isoformat()
    await db.gig_acceptances.update_one(
        {"acceptance_id": acceptance_id},
        {
            "$set": {
                "status": "accepted",
                "accepted_at": now,
                "approved_by": admin["email"],
                "is_backup": False,
                "backup_order": None,
            }
        },
    )
    new_filled = filled + 1
    gig_update = {"slots_filled": new_filled}
    if new_filled >= int(gig.get("slots", 1)):
        gig_update["status"] = "filled"
    await db.gigs.update_one({"gig_id": gig_id}, {"$set": gig_update})

    # In-app notification
    await db.notifications.insert_one(
        {
            "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
            "user_id": acceptance["worker_id"],
            "gig_id": gig_id,
            "title": f"Approved for: {gig.get('title')}",
            "body": "Your gig request was approved. You can now see the full address and clock in.",
            "read": False,
            "created_at": now,
        }
    )
    # Email notification
    body_html = (
        f"<p>Great news — you're approved for <strong>{gig.get('title')}</strong>.</p>"
        f"<p><strong>When:</strong> {gig.get('scheduled_date') or 'See gig'}<br/>"
        f"<strong>Where:</strong> {gig.get('location') or 'TBD'}<br/>"
        f"<strong>Pay:</strong> ${gig.get('pay_rate'):.2f}{'/hr' if gig.get('pay_type') == 'hourly' else ' flat'}</p>"
        f"<p>Open the app to see the full address and clock in when you arrive.</p>"
    )
    await _send_gig_event_email(
        acceptance["worker_id"], kind="gig_approved",
        subject=f"You're approved — {gig.get('title')}",
        body_html=body_html, gig_id=gig_id,
    )
    logger.info(f"Admin {admin['email']} approved request {acceptance_id} on gig {gig_id}")
    return {"ok": True, "slots_filled": new_filled, "gig_status": gig_update.get("status", gig["status"])}


@router.post("/gigs/{gig_id}/requests/{acceptance_id}/approve-backup")
async def approve_request_as_backup(
    gig_id: str,
    acceptance_id: str,
    admin: dict = Depends(require_admin),
):
    """Admin approves a worker as a BACKUP — counts against backup_slots, not slots."""
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Request not found")
    if acceptance.get("status") != "requested":
        raise HTTPException(400, "Request is not pending approval")

    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")
    backup_slots = int(gig.get("backup_slots") or 0)
    backups_filled = int(gig.get("backups_filled") or 0)
    if backup_slots <= 0:
        raise HTTPException(400, "This gig has no backup slots configured")
    if backups_filled >= backup_slots:
        raise HTTPException(400, "All backup slots are already filled")

    now = datetime.now(timezone.utc).isoformat()
    backup_order = backups_filled + 1
    await db.gig_acceptances.update_one(
        {"acceptance_id": acceptance_id},
        {"$set": {
            "status": "backup",
            "accepted_at": now,
            "approved_by": admin["email"],
            "is_backup": True,
            "backup_order": backup_order,
        }},
    )
    await db.gigs.update_one(
        {"gig_id": gig_id},
        {"$set": {"backups_filled": backups_filled + 1}},
    )
    await db.notifications.insert_one({
        "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
        "user_id": acceptance["worker_id"],
        "gig_id": gig_id,
        "title": f"You're a backup for: {gig.get('title')}",
        "body": f"You're backup #{backup_order}. We'll promote you if a primary worker drops out.",
        "read": False,
        "created_at": now,
    })
    body_html = (
        f"<p>You've been approved as a <strong>backup worker</strong> (#{backup_order}) for "
        f"<strong>{gig.get('title')}</strong>.</p>"
        f"<p><strong>When:</strong> {gig.get('scheduled_date') or 'See gig'}<br/>"
        f"<strong>Where:</strong> {gig.get('location') or 'TBD'}</p>"
        f"<p>If a primary worker cancels, you'll automatically be promoted and notified immediately. "
        f"Keep the date open!</p>"
    )
    await _send_gig_event_email(
        acceptance["worker_id"], kind="gig_backup_approved",
        subject=f"You're a backup — {gig.get('title')}",
        body_html=body_html, gig_id=gig_id,
    )
    logger.info(f"Admin {admin['email']} approved request {acceptance_id} as BACKUP #{backup_order} on gig {gig_id}")
    return {"ok": True, "backup_order": backup_order, "backups_filled": backups_filled + 1}


@router.post("/gigs/{gig_id}/acceptances/{acceptance_id}/promote")
async def admin_promote_backup(
    gig_id: str,
    acceptance_id: str,
    admin: dict = Depends(require_admin),
):
    """Manual promote — admin button on the gig detail page."""
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Acceptance not found")
    if not acceptance.get("is_backup"):
        raise HTTPException(400, "This worker is not a backup")

    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")
    filled = int(gig.get("slots_filled") or 0)
    if filled >= int(gig.get("slots", 1)):
        raise HTTPException(400, "No open primary slot to promote into")

    now = datetime.now(timezone.utc).isoformat()
    await db.gig_acceptances.update_one(
        {"acceptance_id": acceptance_id},
        {"$set": {
            "status": "accepted",
            "is_backup": False,
            "backup_order": None,
            "promoted_at": now,
            "promoted_reason": "admin_manual",
            "promoted_by": admin["email"],
        }},
    )
    new_filled = filled + 1
    gig_update = {
        "slots_filled": new_filled,
        "backups_filled": max(0, int(gig.get("backups_filled") or 0) - 1),
    }
    if new_filled >= int(gig.get("slots", 1)):
        gig_update["status"] = "filled"
    await db.gigs.update_one({"gig_id": gig_id}, {"$set": gig_update})

    await db.notifications.insert_one({
        "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
        "user_id": acceptance["worker_id"],
        "gig_id": gig_id,
        "title": f"You're up! Promoted to primary: {gig.get('title')}",
        "body": "Admin just promoted you to a primary slot on this gig.",
        "read": False,
        "created_at": now,
    })
    body_html = (
        f"<p><strong>You've been promoted to primary</strong> on <strong>{gig.get('title')}</strong>!</p>"
        f"<p>Admin manually promoted you from backup. Open the app to see the address and clock in.</p>"
    )
    await _send_gig_event_email(
        acceptance["worker_id"], kind="gig_backup_promoted",
        subject=f"Promoted to primary — {gig.get('title')}",
        body_html=body_html, gig_id=gig_id,
    )
    try:
        await _send_push_to_user(
            acceptance["worker_id"],
            {
                "title": f"You're up on {gig.get('title')}",
                "body": "Admin promoted you to primary.",
                "tag": f"gig-promoted-{gig_id}",
                "url": f"/gigs/{gig_id}",
            },
        )
    except Exception:
        pass
    return {"ok": True, "slots_filled": new_filled}


@router.post("/gigs/{gig_id}/requests/{acceptance_id}/reject")
async def reject_request(
    gig_id: str,
    acceptance_id: str,
    admin: dict = Depends(require_admin),
):
    """Admin rejects a worker's gig request — removes it; slot was never reserved."""
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Request not found")
    if acceptance.get("status") != "requested":
        raise HTTPException(400, "Request is no longer pending")
    gig = await db.gigs.find_one({"gig_id": gig_id})
    await db.gig_acceptances.delete_one({"acceptance_id": acceptance_id})
    # Notify the worker
    await db.notifications.insert_one({
        "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
        "user_id": acceptance["worker_id"],
        "gig_id": gig_id,
        "title": f"Request declined: {gig.get('title') if gig else 'gig'}",
        "body": "Your request wasn't approved this time. Plenty of other gigs are open.",
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    body_html = (
        f"<p>Your request for <strong>{gig.get('title') if gig else 'this gig'}</strong> "
        f"wasn't approved this time.</p>"
        f"<p>No worries — plenty of other gigs are open in your feed. Keep an eye on the app for new postings.</p>"
    )
    await _send_gig_event_email(
        acceptance["worker_id"], kind="gig_rejected",
        subject="Request not approved this time",
        body_html=body_html, gig_id=gig_id,
    )
    logger.info(f"Admin {admin['email']} rejected request {acceptance_id} on gig {gig_id}")
    return {"ok": True}


@router.post("/gigs/{gig_id}/assign")
async def assign_worker(
    gig_id: str,
    payload: AssignWorkerIn,
    admin: dict = Depends(require_admin),
):
    """Admin directly places a worker on a gig (skips the request step)."""
    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")
    filled = int(gig.get("slots_filled") or 0)
    if filled >= int(gig.get("slots", 1)):
        raise HTTPException(400, "All slots are already filled")

    worker = await db.users.find_one({"user_id": payload.worker_id})
    if not worker or worker.get("role") != "worker":
        raise HTTPException(404, "Worker not found")
    w_status = _effective_status(worker)
    if w_status in ("rejected", "suspended"):
        raise HTTPException(400, f"Worker is {w_status} and cannot be assigned")

    existing = await db.gig_acceptances.find_one(
        {"gig_id": gig_id, "worker_id": payload.worker_id}
    )
    if existing:
        if existing.get("status") == "requested":
            # Convert their pending request into an admin-assigned acceptance
            now = datetime.now(timezone.utc).isoformat()
            await db.gig_acceptances.update_one(
                {"acceptance_id": existing["acceptance_id"]},
                {"$set": {"status": "accepted", "accepted_at": now, "approved_by": admin["email"]}},
            )
            acceptance_id = existing["acceptance_id"]
        else:
            raise HTTPException(400, "Worker is already on this gig")
    else:
        acceptance_id = f"acc_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        await db.gig_acceptances.insert_one(
            {
                "acceptance_id": acceptance_id,
                "gig_id": gig_id,
                "worker_id": payload.worker_id,
                "status": "accepted",
                "requested_at": now,
                "accepted_at": now,
                "approved_by": admin["email"],
                "assigned_by_admin": True,
            }
        )

    new_filled = filled + 1
    gig_update = {"slots_filled": new_filled}
    if new_filled >= int(gig.get("slots", 1)):
        gig_update["status"] = "filled"
    await db.gigs.update_one({"gig_id": gig_id}, {"$set": gig_update})

    await db.notifications.insert_one(
        {
            "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
            "user_id": payload.worker_id,
            "gig_id": gig_id,
            "title": f"You were added to: {gig.get('title')}",
            "body": "HCOB added you to this gig. Open the app to see the full address and clock in when you arrive.",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    logger.info(f"Admin {admin['email']} assigned worker {payload.worker_id} to gig {gig_id}")
    return {"ok": True, "acceptance_id": acceptance_id, "slots_filled": new_filled}


@router.delete("/gigs/{gig_id}/acceptances/{acceptance_id}")
async def remove_worker_from_gig(
    gig_id: str,
    acceptance_id: str,
    admin: dict = Depends(require_admin),
):
    """Admin removes a worker from a gig. Releases the slot if it was reserved.
    If the removed worker was primary, automatically promotes the first backup."""
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Acceptance not found")

    was_primary = acceptance.get("status") in (
        "accepted",
        "on_the_clock",
        "completed",
    )
    was_backup = acceptance.get("is_backup") and acceptance.get("status") == "backup"
    await db.gig_acceptances.delete_one({"acceptance_id": acceptance_id})

    gig = await db.gigs.find_one({"gig_id": gig_id})
    if gig:
        gig_update = {}
        if was_primary:
            new_filled = max(0, int(gig.get("slots_filled") or 0) - 1)
            gig_update["slots_filled"] = new_filled
            if gig.get("status") == "filled" and new_filled < int(gig.get("slots", 1)):
                gig_update["status"] = "open"
        if was_backup:
            gig_update["backups_filled"] = max(0, int(gig.get("backups_filled") or 0) - 1)
        if gig_update:
            await db.gigs.update_one({"gig_id": gig_id}, {"$set": gig_update})

    await db.notifications.insert_one(
        {
            "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
            "user_id": acceptance["worker_id"],
            "gig_id": gig_id,
            "title": f"Removed from: {gig.get('title') if gig else 'gig'}",
            "body": "HCOB removed you from this gig. Reach out if you have questions.",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    body_html = (
        f"<p>You've been removed from <strong>{gig.get('title') if gig else 'this gig'}</strong>.</p>"
        f"<p>If this was a mistake or you have questions, reach out to HCOB Ops.</p>"
    )
    await _send_gig_event_email(
        acceptance["worker_id"], kind="gig_removed",
        subject=f"Removed from: {gig.get('title') if gig else 'gig'}",
        body_html=body_html, gig_id=gig_id,
    )

    # Auto-promote a backup if a primary slot just opened up
    if was_primary and gig:
        await _promote_first_backup(gig_id, reason="admin_removed")

    logger.info(f"Admin {admin['email']} removed worker {acceptance['worker_id']} from gig {gig_id}")
    return {"ok": True}


@router.post("/gigs/{gig_id}/cancel-shift")
async def cancel_shift(
    gig_id: str,
    payload: CancelShiftIn,
    user: dict = Depends(get_current_user),
):
    """Worker cancels a shift they were approved for. Auto-promotes the first
    backup if available. Flags late cancellations (< 24h before scheduled_at)."""
    if user.get("role") != "worker":
        raise HTTPException(403, "Only workers can cancel their shift")

    acceptance = await db.gig_acceptances.find_one(
        {"gig_id": gig_id, "worker_id": user["user_id"]}
    )
    if not acceptance:
        raise HTTPException(404, "You're not on this gig")

    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")

    was_primary = acceptance.get("status") in ("accepted", "on_the_clock")
    was_backup = acceptance.get("is_backup") and acceptance.get("status") == "backup"
    was_requested = acceptance.get("status") == "requested"

    if not (was_primary or was_backup or was_requested):
        raise HTTPException(400, f"Cannot cancel — current status is {acceptance.get('status')}")

    # Detect late cancellation (< 24 hours before scheduled_at)
    is_late = False
    if was_primary:
        sched = gig.get("scheduled_at")
        if sched:
            try:
                sdt = datetime.fromisoformat(sched.replace("Z", "+00:00") if isinstance(sched, str) else sched)
                if sdt.tzinfo is None:
                    sdt = sdt.replace(tzinfo=timezone.utc)
                if sdt - datetime.now(timezone.utc) < timedelta(hours=24):
                    is_late = True
            except Exception:
                pass

    now = datetime.now(timezone.utc).isoformat()
    # Delete the acceptance so the slot frees up
    await db.gig_acceptances.delete_one({"acceptance_id": acceptance["acceptance_id"]})
    # Update the gig's filled counts
    gig_update = {}
    if was_primary:
        new_filled = max(0, int(gig.get("slots_filled") or 0) - 1)
        gig_update["slots_filled"] = new_filled
        if gig.get("status") == "filled" and new_filled < int(gig.get("slots", 1)):
            gig_update["status"] = "open"
    if was_backup:
        gig_update["backups_filled"] = max(0, int(gig.get("backups_filled") or 0) - 1)
    if gig_update:
        await db.gigs.update_one({"gig_id": gig_id}, {"$set": gig_update})

    # Audit log
    await db.gig_cancellations.insert_one({
        "cancellation_id": f"can_{uuid.uuid4().hex[:12]}",
        "gig_id": gig_id,
        "worker_id": user["user_id"],
        "worker_name": user.get("name"),
        "reason": payload.reason,
        "note": (payload.note or "").strip() or None,
        "was_primary": was_primary,
        "was_backup": was_backup,
        "was_requested": was_requested,
        "is_late": is_late,
        "cancelled_at": now,
        "gig_title": gig.get("title"),
        "scheduled_at": gig.get("scheduled_at"),
    })

    # Notify the worker (confirmation) — small, in-app only
    await db.notifications.insert_one({
        "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
        "user_id": user["user_id"],
        "gig_id": gig_id,
        "title": f"Cancelled: {gig.get('title')}",
        "body": "Your shift has been cancelled. Reason: " + payload.reason,
        "read": False,
        "created_at": now,
    })
    # Notify admins (in-app) so they see the cancellation in the requests/admin surface
    admins = await db.users.find({"role": "admin"}, {"_id": 0, "user_id": 1}).to_list(50)
    for a in admins:
        await db.notifications.insert_one({
            "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
            "user_id": a["user_id"],
            "gig_id": gig_id,
            "title": ("⚠ LATE cancel: " if is_late else "Cancelled: ") + (gig.get("title") or "gig"),
            "body": f"{user.get('name') or 'A worker'} cancelled their shift. Reason: {payload.reason}.",
            "read": False,
            "created_at": now,
        })

    # Auto-promote a backup if a primary slot just opened
    promoted = None
    if was_primary:
        promoted = await _promote_first_backup(gig_id, reason="worker_cancelled")

    return {
        "ok": True,
        "is_late": is_late,
        "backup_promoted": bool(promoted),
        "promoted_worker_id": (promoted or {}).get("worker_id"),
    }


# Legacy alias — keep the old endpoint name working so older clients/CSVs that
# called /withdraw don't 404. Internally just forwards to cancel-shift with a
# default reason.
@router.post("/gigs/{gig_id}/withdraw")
async def withdraw_gig(gig_id: str, user: dict = Depends(get_current_user)):
    return await cancel_shift(
        gig_id=gig_id,
        payload=CancelShiftIn(reason="other", note="legacy withdraw"),
        user=user,
    )


@router.post("/gigs/{gig_id}/blast")
async def blast_gig(
    gig_id: str,
    payload: BlastIn,
    request: Request,
    admin: dict = Depends(require_admin),
):
    gig = await db.gigs.find_one({"gig_id": gig_id}, {"_id": 0})
    if not gig:
        raise HTTPException(404, "Gig not found")

    workers = await db.users.find(
        {"role": "worker"}, {"_id": 0, "password_hash": 0}
    ).to_list(1000)

    email_creds = await _resolve_email_creds() if "email" in payload.channels else None
    sms_creds = await _resolve_sms_creds() if "sms" in payload.channels else None

    counts = {"in_app": 0, "email": 0, "sms": 0, "push": 0, "email_failed": 0, "sms_failed": 0}
    subject = f"New Gig: {gig['title']}"
    base_url = _resolve_public_base(request)
    html = _format_gig_email(gig, base_url)
    sms_body = _format_gig_sms(gig, base_url)
    push_payload = {
        "title": gig["title"],
        "body": (
            f"${gig['pay_rate']:.0f}"
            + ("/hr" if gig.get("pay_type") == "hourly" else "")
            + f" · {gig.get('location') or 'Baltimore, MD'} · {gig.get('scheduled_date') or 'Flexible'}"
        ),
        "tag": f"gig-{gig_id}",
        "url": f"/gigs/{gig_id}",
        "kind": "gig",
        "rush": True,
    }

    notif_docs = []
    for w in workers:
        if "in_app" in payload.channels:
            notif_docs.append(
                {
                    "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
                    "user_id": w["user_id"],
                    "gig_id": gig_id,
                    "title": subject,
                    "body": gig["description"][:140],
                    "read": False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            counts["in_app"] += 1
        if "email" in payload.channels and w.get("email") and email_creds:
            try:
                await asyncio.to_thread(
                    _send_email_sync,
                    email_creds["api_key"],
                    email_creds["sender"],
                    w["email"],
                    subject,
                    html,
                )
                counts["email"] += 1
            except Exception as e:
                logger.error(f"Email send failed for {w['email']}: {e}")
                counts["email_failed"] += 1
        if "sms" in payload.channels and w.get("phone") and sms_creds:
            try:
                await asyncio.to_thread(
                    _send_sms_sync,
                    sms_creds["sid"],
                    sms_creds["token"],
                    sms_creds["from_"],
                    w["phone"],
                    sms_body,
                )
                counts["sms"] += 1
            except Exception as e:
                logger.error(f"SMS send failed for {w.get('phone')}: {e}")
                counts["sms_failed"] += 1
        # Push notifications fan out alongside other channels. We always try
        # push when configured — workers control their own opt-in via the
        # browser permission prompt + subscription record.
        if "push" in payload.channels and VAPID_PRIVATE_KEY:
            sent = await _send_push_to_user(w["user_id"], push_payload)
            counts["push"] += sent

    if notif_docs:
        await db.notifications.insert_many(notif_docs)

    # Ensure 'rush' is included in tags after blast (idempotent merge)
    existing_tags = [t for t in (gig.get("tags") or []) if t in GIG_TAG_VALUES]
    if "rush" not in existing_tags:
        existing_tags.insert(0, "rush")

    await db.gigs.update_one(
        {"gig_id": gig_id},
        {
            "$set": {
                "last_blast_at": datetime.now(timezone.utc).isoformat(),
                "blast_channels": payload.channels,
                # Blasting a gig auto-pins it to the top of the worker feed by
                # adding the 'rush' tag and flipping `is_rush=true`. Admin can
                # untag via the rush/tags endpoints without re-blasting.
                "is_rush": True,
                "rush_at": datetime.now(timezone.utc).isoformat(),
                "tags": existing_tags,
            },
            "$inc": {"blast_count": 1},
        },
    )

    # Persistent blast log — surfaces in Admin → Reports → Blasts.
    await _log_blast(
        kind="gig",
        gig_id=gig_id,
        gig_title=gig.get("title"),
        project_id=gig.get("project_id"),
        project_title=None,
        channels=payload.channels,
        counts=counts,
        workers_targeted=len(workers),
        sent_by_id=admin["user_id"],
        sent_by_name=admin.get("name") or admin.get("email"),
    )

    return {"ok": True, "counts": counts, "workers_targeted": len(workers), "is_rush": True, "tags": existing_tags}


@router.put("/gigs/{gig_id}/rush")
async def toggle_rush(
    gig_id: str, payload: RushToggleIn, admin: dict = Depends(require_admin)
):
    """Flip the RUSH flag on a gig without sending a blast. RUSH-flagged gigs
    float to the top of every worker feed with a red border + flame badge.
    Also syncs the 'rush' entry in the gig's tags array."""
    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")
    existing_tags = [t for t in (gig.get("tags") or []) if t in GIG_TAG_VALUES]
    if payload.is_rush:
        if "rush" not in existing_tags:
            existing_tags.insert(0, "rush")
    else:
        existing_tags = [t for t in existing_tags if t != "rush"]
    new_is_pinned = len(existing_tags) > 0
    set_ops: dict = {
        "is_rush": new_is_pinned,
        "tags": existing_tags,
        "rush_at": datetime.now(timezone.utc).isoformat() if new_is_pinned else None,
    }
    await db.gigs.update_one({"gig_id": gig_id}, {"$set": set_ops})
    return {"ok": True, "is_rush": new_is_pinned, "tags": existing_tags}


@router.put("/gigs/{gig_id}/tags")
async def set_gig_tags(
    gig_id: str, payload: GigTagsIn, admin: dict = Depends(require_admin)
):
    """Replace the gig's `tags` array. Any tag pins the gig to the top of the
    feed (sets `is_rush=True` so the existing sort path keeps working).
    Pass `tags=[]` to clear all tags and un-pin the gig."""
    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")
    # Deduplicate while preserving order
    seen = set()
    clean_tags = []
    for t in payload.tags:
        if t in GIG_TAG_VALUES and t not in seen:
            clean_tags.append(t)
            seen.add(t)
    is_pinned = len(clean_tags) > 0
    set_ops = {
        "tags": clean_tags,
        "is_rush": is_pinned,
        "rush_at": datetime.now(timezone.utc).isoformat() if is_pinned else None,
    }
    await db.gigs.update_one({"gig_id": gig_id}, {"$set": set_ops})
    return {"ok": True, "tags": clean_tags, "is_rush": is_pinned}


@router.post("/gigs/{gig_id}/publish")
async def publish_gig(gig_id: str, admin: dict = Depends(require_admin)):
    """Flip a `coming_soon` gig to `open` immediately AND notify matching
    workers (skills overlap + same/nearby ZIP)."""
    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")
    if gig.get("status") == "open":
        return {"ok": True, "already_open": True, "notified": 0}
    if gig.get("status") not in ("coming_soon", None):
        raise HTTPException(400, f"Can't publish a {gig.get('status')} gig")

    await db.gigs.update_one(
        {"gig_id": gig_id},
        {
            "$set": {
                "status": "open",
                "published_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    notified = await _notify_matching_workers_of_new_gig(gig)
    return {"ok": True, "notified": notified, "status": "open"}


# ---- Clock in / out --------------------------------------------------------
@router.post("/gigs/{gig_id}/clock-in")
async def clock_in(gig_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "worker":
        raise HTTPException(403, "Only workers can clock in")
    acceptance = await db.gig_acceptances.find_one(
        {"gig_id": gig_id, "worker_id": user["user_id"]}
    )
    if not acceptance:
        raise HTTPException(400, "You must request and be approved for this gig before clocking in")
    if acceptance.get("status") == "requested":
        raise HTTPException(400, "Your request is still pending HCOB approval")
    if acceptance.get("clock_in_at") and not acceptance.get("clock_out_at"):
        raise HTTPException(400, "You're already clocked in")
    if acceptance.get("clock_out_at"):
        raise HTTPException(400, "Already completed — cannot clock in again")

    now = datetime.now(timezone.utc).isoformat()
    await db.gig_acceptances.update_one(
        {"acceptance_id": acceptance["acceptance_id"]},
        {"$set": {"clock_in_at": now, "status": "on_the_clock"}},
    )
    return {"ok": True, "clock_in_at": now}


@router.post("/gigs/{gig_id}/clock-out")
async def clock_out(gig_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "worker":
        raise HTTPException(403, "Only workers can clock out")
    acceptance = await db.gig_acceptances.find_one(
        {"gig_id": gig_id, "worker_id": user["user_id"]}
    )
    if not acceptance:
        raise HTTPException(400, "No acceptance for this gig")
    if not acceptance.get("clock_in_at"):
        raise HTTPException(400, "You haven't clocked in yet")
    if acceptance.get("clock_out_at"):
        raise HTTPException(400, "You've already clocked out")

    now = datetime.now(timezone.utc)
    clock_in_dt = datetime.fromisoformat(acceptance["clock_in_at"])
    if clock_in_dt.tzinfo is None:
        clock_in_dt = clock_in_dt.replace(tzinfo=timezone.utc)
    hours = round((now - clock_in_dt).total_seconds() / 3600.0, 2)

    gig = await db.gigs.find_one({"gig_id": gig_id})
    worker = await db.users.find_one({"user_id": user["user_id"]})
    pay = _resolve_pay(acceptance, worker, gig)
    break_minutes = _resolve_break_minutes(acceptance, gig)
    paid_hours = _compute_paid_hours(hours, break_minutes)
    earnings = _compute_earnings(pay["pay_rate"], pay["pay_type"], hours, break_minutes)

    await db.gig_acceptances.update_one(
        {"acceptance_id": acceptance["acceptance_id"]},
        {
            "$set": {
                "clock_out_at": now.isoformat(),
                "hours_worked": hours,
                "break_minutes_applied": break_minutes,
                "paid_hours": paid_hours,
                "pay_rate_applied": pay["pay_rate"],
                "pay_type_applied": pay["pay_type"],
                "pay_rate_source": pay["pay_rate_source"],
                "pay_type_source": pay["pay_type_source"],
                "earnings": earnings,
                "timesheet_approved": False,
                "status": "completed",
            }
        },
    )
    return {
        "ok": True,
        "clock_out_at": now.isoformat(),
        "hours_worked": hours,
        "break_minutes": break_minutes,
        "paid_hours": paid_hours,
        "earnings": earnings,
        "pay_rate_applied": pay["pay_rate"],
        "pay_type_applied": pay["pay_type"],
    }
