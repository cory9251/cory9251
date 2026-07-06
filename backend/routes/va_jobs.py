"""VA digital jobs — admin posts jobs to a board (or assigns a VA directly),
approved VAs claim → work → submit; admin approves and the payout drops into
the existing commissions pipeline (PM → Owner → Paid) so earnings stay unified.
"""
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from config import db
from va_commission import require_va_active, require_program_manager_or_owner
from notifications import notify_admins, email_admins, _public_base

router = APIRouter()

OPEN_STATUSES = ("open", "assigned", "in_progress", "submitted")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ser(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k != "_id"}


def _payout(job: dict) -> float:
    if job["pay_type"] == "hourly":
        return round(float(job["pay_amount"]) * float(job.get("hours_logged") or 0), 2)
    return round(float(job["pay_amount"]), 2)


async def _notify_user(user_id: str, title: str, body: str, url: Optional[str] = None):
    await db.notifications.insert_one({
        "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "title": title,
        "body": body,
        "url": url,
        "read": False,
        "created_at": _now_iso(),
    })


async def _get_job(job_id: str) -> dict:
    job = await db.va_jobs.find_one({"job_id": job_id})
    if not job:
        raise HTTPException(404, "Job not found")
    return job


class JobIn(BaseModel):
    title: str = Field(..., min_length=2, max_length=120)
    description: str = Field("", max_length=3000)
    pay_type: Literal["fixed", "hourly"]
    pay_amount: float = Field(..., gt=0, le=100000)
    due_date: Optional[str] = None
    assigned_va_id: Optional[str] = None


class AssignIn(BaseModel):
    va_user_id: Optional[str] = None  # None = back to open board


class SubmitIn(BaseModel):
    note: str = Field(..., min_length=1, max_length=3000)
    hours_logged: Optional[float] = Field(None, gt=0, le=1000)


class ReviewIn(BaseModel):
    note: Optional[str] = Field(None, max_length=1000)


async def _resolve_approved_va(va_user_id: str) -> dict:
    va = await db.users.find_one({"user_id": va_user_id, "role": "va"}, {"_id": 0})
    if not va:
        raise HTTPException(404, "VA not found")
    if (va.get("va_status") or "pending") != "approved":
        raise HTTPException(400, "VA is not approved yet")
    return va


# ---- VA side ---------------------------------------------------------------
@router.get("/va/jobs/board")
async def va_job_board(user: dict = Depends(require_va_active)):
    items = (
        await db.va_jobs.find({"status": "open"}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(100)
    )
    return {"items": items}


@router.get("/va/jobs/mine")
async def va_my_jobs(user: dict = Depends(require_va_active)):
    items = (
        await db.va_jobs.find({"assigned_va_id": user["user_id"]}, {"_id": 0})
        .sort("updated_at", -1)
        .to_list(200)
    )
    return {"items": items}


@router.post("/va/jobs/{job_id}/claim")
async def va_claim_job(job_id: str, user: dict = Depends(require_va_active)):
    now = _now_iso()
    result = await db.va_jobs.update_one(
        {"job_id": job_id, "status": "open"},
        {"$set": {
            "status": "assigned",
            "assigned_va_id": user["user_id"],
            "assigned_va_name": user.get("name") or user.get("email"),
            "claimed_at": now,
            "updated_at": now,
        }},
    )
    if result.modified_count == 0:
        raise HTTPException(409, "Job is no longer available")
    job = await _get_job(job_id)
    await notify_admins(
        f"Job claimed: {job['title']}",
        f"{user.get('name') or 'A VA'} claimed this digital job",
        url="/ops/va-program/jobs",
    )
    return _ser(job)


@router.post("/va/jobs/{job_id}/start")
async def va_start_job(job_id: str, user: dict = Depends(require_va_active)):
    job = await _get_job(job_id)
    if job.get("assigned_va_id") != user["user_id"]:
        raise HTTPException(403, "Not your job")
    if job["status"] != "assigned":
        raise HTTPException(400, f"Cannot start — job is {job['status']}")
    await db.va_jobs.update_one(
        {"job_id": job_id},
        {"$set": {"status": "in_progress", "started_at": _now_iso(), "updated_at": _now_iso()}},
    )
    return _ser(await _get_job(job_id))


@router.post("/va/jobs/{job_id}/submit")
async def va_submit_job(job_id: str, payload: SubmitIn, user: dict = Depends(require_va_active)):
    job = await _get_job(job_id)
    if job.get("assigned_va_id") != user["user_id"]:
        raise HTTPException(403, "Not your job")
    if job["status"] not in ("assigned", "in_progress"):
        raise HTTPException(400, f"Cannot submit — job is {job['status']}")
    if job["pay_type"] == "hourly" and not payload.hours_logged:
        raise HTTPException(400, "Log your hours to submit this hourly job")
    now = _now_iso()
    update = {
        "status": "submitted",
        "deliverable_note": payload.note.strip(),
        "submitted_at": now,
        "updated_at": now,
    }
    if job["pay_type"] == "hourly":
        update["hours_logged"] = round(float(payload.hours_logged), 2)
    await db.va_jobs.update_one({"job_id": job_id}, {"$set": update})
    fresh = await _get_job(job_id)
    va_name = user.get("name") or "A VA"
    await notify_admins(
        f"Job submitted for review: {job['title']}",
        f"{va_name} delivered — payout would be ${_payout(fresh):,.2f}",
        url="/ops/va-program/jobs",
    )
    await email_admins(
        f"[HCOB Jobs] Submitted for review: {job['title']}",
        "Digital job submitted",
        f"<p><strong>{va_name}</strong> submitted work for review.</p>"
        f"<p><strong>Job:</strong> {job['title']}<br/>"
        f"<strong>Pay:</strong> {'$%.2f fixed' % job['pay_amount'] if job['pay_type'] == 'fixed' else '$%.2f/hr × %.1f hrs' % (job['pay_amount'], fresh.get('hours_logged') or 0)}<br/>"
        f"<strong>Payout on approval:</strong> ${_payout(fresh):,.2f}</p>"
        f"<p><strong>Delivery note:</strong><br/>{payload.note.strip()}</p>",
        cta_label="Review job",
        cta_url=f"{_public_base()}/ops/va-program/jobs",
    )
    return _ser(fresh)


# ---- Admin side ------------------------------------------------------------
@router.post("/admin/va-jobs")
async def admin_create_job(payload: JobIn, admin: dict = Depends(require_program_manager_or_owner)):
    now = _now_iso()
    doc = {
        "job_id": f"vjob_{uuid.uuid4().hex[:12]}",
        "title": payload.title.strip(),
        "description": payload.description.strip(),
        "pay_type": payload.pay_type,
        "pay_amount": round(float(payload.pay_amount), 2),
        "due_date": payload.due_date or None,
        "status": "open",
        "assigned_va_id": None,
        "assigned_va_name": None,
        "hours_logged": None,
        "deliverable_note": None,
        "review_note": None,
        "payout_amount": None,
        "commission_id": None,
        "created_by": admin["user_id"],
        "created_at": now,
        "updated_at": now,
        "claimed_at": None,
        "started_at": None,
        "submitted_at": None,
        "approved_at": None,
    }
    if payload.assigned_va_id:
        va = await _resolve_approved_va(payload.assigned_va_id)
        doc["status"] = "assigned"
        doc["assigned_va_id"] = va["user_id"]
        doc["assigned_va_name"] = va.get("name") or va.get("email")
        doc["claimed_at"] = now
    await db.va_jobs.insert_one(doc)
    if doc["assigned_va_id"]:
        await _notify_user(
            doc["assigned_va_id"],
            f"New job assigned: {doc['title']}",
            f"{'$%.2f fixed' % doc['pay_amount'] if doc['pay_type'] == 'fixed' else '$%.2f/hr' % doc['pay_amount']} — open your Jobs tab to get started",
            url="/va/jobs",
        )
    return _ser(doc)


@router.get("/admin/va-jobs")
async def admin_list_jobs(
    status: Optional[str] = None,
    admin: dict = Depends(require_program_manager_or_owner),
):
    q = {"status": status} if status else {}
    items = (
        await db.va_jobs.find(q, {"_id": 0}).sort("updated_at", -1).to_list(300)
    )
    counts = {}
    async for row in db.va_jobs.aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}]):
        counts[row["_id"]] = row["n"]
    return {"items": items, "counts": counts}


@router.put("/admin/va-jobs/{job_id}")
async def admin_update_job(
    job_id: str, payload: JobIn, admin: dict = Depends(require_program_manager_or_owner)
):
    job = await _get_job(job_id)
    if job["status"] in ("approved", "cancelled"):
        raise HTTPException(400, f"Cannot edit a {job['status']} job")
    await db.va_jobs.update_one(
        {"job_id": job_id},
        {"$set": {
            "title": payload.title.strip(),
            "description": payload.description.strip(),
            "pay_type": payload.pay_type,
            "pay_amount": round(float(payload.pay_amount), 2),
            "due_date": payload.due_date or None,
            "updated_at": _now_iso(),
        }},
    )
    return _ser(await _get_job(job_id))


@router.post("/admin/va-jobs/{job_id}/assign")
async def admin_assign_job(
    job_id: str, payload: AssignIn, admin: dict = Depends(require_program_manager_or_owner)
):
    job = await _get_job(job_id)
    if job["status"] not in ("open", "assigned", "in_progress"):
        raise HTTPException(400, f"Cannot reassign — job is {job['status']}")
    now = _now_iso()
    if payload.va_user_id:
        va = await _resolve_approved_va(payload.va_user_id)
        await db.va_jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "assigned",
                "assigned_va_id": va["user_id"],
                "assigned_va_name": va.get("name") or va.get("email"),
                "claimed_at": now,
                "started_at": None,
                "updated_at": now,
            }},
        )
        await _notify_user(
            va["user_id"],
            f"New job assigned: {job['title']}",
            "Open your Jobs tab to get started",
            url="/va/jobs",
        )
    else:
        await db.va_jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "open",
                "assigned_va_id": None,
                "assigned_va_name": None,
                "claimed_at": None,
                "started_at": None,
                "updated_at": now,
            }},
        )
    return _ser(await _get_job(job_id))


@router.post("/admin/va-jobs/{job_id}/approve")
async def admin_approve_job(
    job_id: str, payload: ReviewIn, admin: dict = Depends(require_program_manager_or_owner)
):
    job = await _get_job(job_id)
    if job["status"] != "submitted":
        raise HTTPException(400, f"Cannot approve — job is {job['status']}")
    now = _now_iso()
    payout = _payout(job)
    commission_id = f"comm_{uuid.uuid4().hex[:12]}"
    # Payout rides the existing commissions pipeline (pending → PM → Owner → Paid)
    await db.commissions.insert_one({
        "commission_id": commission_id,
        "lead_id": None,
        "job_id": job_id,
        "va_user_id": job["assigned_va_id"],
        "va_name": job.get("assigned_va_name"),
        "prospect_name": job["title"],
        "service_type": "digital_job",
        "client_phone_norm": None,
        "client_email_norm": None,
        "amount": payout,
        "kind": "digital_job",
        "visit_number": None,
        "calc_notes": (
            f"Digital job payout — ${job['pay_amount']:.2f}/hr × {job.get('hours_logged') or 0:.1f} hrs"
            if job["pay_type"] == "hourly"
            else f"Digital job payout — fixed ${job['pay_amount']:.2f}"
        ),
        "status": "pending_approval",
        "pm_action_at": None,
        "pm_action_note": None,
        "owner_action_at": None,
        "paid_at": None,
        "payout_reference": None,
        "payout_method": None,
        "job_value": payout,
        "created_at": now,
        "updated_at": now,
    })
    await db.va_jobs.update_one(
        {"job_id": job_id},
        {"$set": {
            "status": "approved",
            "approved_at": now,
            "review_note": (payload.note or "").strip() or None,
            "payout_amount": payout,
            "commission_id": commission_id,
            "updated_at": now,
        }},
    )
    await _notify_user(
        job["assigned_va_id"],
        f"Job approved: {job['title']}",
        f"${payout:,.2f} payout is now in the commission queue — track it in Earnings",
        url="/va/earnings",
    )
    return _ser(await _get_job(job_id))


@router.post("/admin/va-jobs/{job_id}/reject")
async def admin_reject_job(
    job_id: str, payload: ReviewIn, admin: dict = Depends(require_program_manager_or_owner)
):
    job = await _get_job(job_id)
    if job["status"] != "submitted":
        raise HTTPException(400, f"Cannot send back — job is {job['status']}")
    if not (payload.note or "").strip():
        raise HTTPException(400, "Tell the VA what needs fixing")
    await db.va_jobs.update_one(
        {"job_id": job_id},
        {"$set": {
            "status": "in_progress",
            "review_note": payload.note.strip(),
            "updated_at": _now_iso(),
        }},
    )
    await _notify_user(
        job["assigned_va_id"],
        f"Changes requested: {job['title']}",
        payload.note.strip()[:200],
        url="/va/jobs",
    )
    return _ser(await _get_job(job_id))


@router.post("/admin/va-jobs/{job_id}/cancel")
async def admin_cancel_job(job_id: str, admin: dict = Depends(require_program_manager_or_owner)):
    job = await _get_job(job_id)
    if job["status"] == "approved":
        raise HTTPException(400, "Cannot cancel an approved job")
    await db.va_jobs.update_one(
        {"job_id": job_id},
        {"$set": {"status": "cancelled", "updated_at": _now_iso()}},
    )
    if job.get("assigned_va_id"):
        await _notify_user(
            job["assigned_va_id"],
            f"Job cancelled: {job['title']}",
            "This job was cancelled by the program manager.",
            url="/va/jobs",
        )
    return _ser(await _get_job(job_id))
