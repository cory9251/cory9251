"""Virtual Professional recruiting applications.

Public form on /vas writes an applicant record, notifies ops (bell + email),
and sends the applicant a confirmation email. Admin endpoints power the
review queue under Admin → VA Program → Applications.
"""
import re
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from config import db, logger
from auth_deps import require_admin
from notifications import notify_admins, email_admins, _send_user_email, _public_base

router = APIRouter()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

STREAM_LABELS = {
    "commission_agent": "Commission Agent",
    "gig_work": "Virtual Gig Work",
    "both": "Both",
    "not_sure": "Not sure yet",
}
SKILL_LABELS = {
    "graphic_design": "Graphic Design",
    "web_development": "Web Development",
    "seo": "SEO",
    "social_media": "Social Media",
    "data_entry": "Data Entry",
    "admin_support": "Admin Support",
    "digital_products": "Digital Products",
    "marketing": "Marketing",
    "none_yet": "None yet",
}
STATUSES = ["new", "contacted", "onboarding", "accepted", "rejected"]


class VPApplicationIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    phone: str = Field(min_length=5, max_length=40)
    country: str = Field(min_length=2, max_length=80)
    timezone: Optional[str] = Field(default=None, max_length=80)
    streams: List[Literal["commission_agent", "gig_work", "both", "not_sure"]] = Field(min_length=1)
    skills: List[
        Literal[
            "graphic_design", "web_development", "seo", "social_media",
            "data_entry", "admin_support", "digital_products", "marketing", "none_yet",
        ]
    ] = Field(default_factory=list)
    portfolio_url: Optional[str] = Field(default=None, max_length=500)
    hours_per_day: Literal["4-6", "6-8", "8+"]
    sales_experience: Literal["none", "some", "experienced"]
    why_join: str = Field(min_length=1, max_length=500)
    heard_from: Optional[Literal["facebook", "linkedin", "referral", "job_board", "other"]] = None
    consent: bool
    src: Optional[str] = Field(default=None, max_length=60)
    website: Optional[str] = None  # honeypot


class VPApplicationPatch(BaseModel):
    status: Optional[Literal["new", "contacted", "onboarding", "accepted", "rejected"]] = None
    admin_note: Optional[str] = Field(default=None, max_length=2000)


def _ops_email_html(doc: dict) -> str:
    streams = ", ".join(STREAM_LABELS.get(s, s) for s in doc["streams"])
    skills = ", ".join(SKILL_LABELS.get(s, s) for s in doc["skills"]) or "—"
    rows = [
        ("Name", doc["full_name"]),
        ("Email", doc["email"]),
        ("Phone / WhatsApp", doc["phone"]),
        ("Country / TZ", f"{doc['country']}" + (f" · {doc['timezone']}" if doc.get("timezone") else "")),
        ("Streams", streams),
        ("Skills", skills),
        ("Portfolio", doc.get("portfolio_url") or "—"),
        ("Hours / day", doc["hours_per_day"]),
        ("Sales experience", doc["sales_experience"].capitalize()),
        ("Heard about us", (doc.get("heard_from") or "—").replace("_", " ").capitalize()),
        ("Source", doc.get("src") or "—"),
    ]
    table = "".join(
        f"<tr><td style='padding:6px 10px;border:1px solid #E5E7EB;font-weight:600;white-space:nowrap'>{k}</td>"
        f"<td style='padding:6px 10px;border:1px solid #E5E7EB'>{v}</td></tr>"
        for k, v in rows
    )
    why = (doc.get("why_join") or "").replace("<", "&lt;")
    return (
        f"<table cellspacing='0' style='border-collapse:collapse;width:100%'>{table}</table>"
        f"<p style='margin:16px 0 4px;font-weight:700;color:#030712'>Why they want to join:</p>"
        f"<p style='margin:0;background:#F9FAFB;border:1px solid #E5E7EB;padding:12px'>{why}</p>"
    )


@router.post("/public/vp-applications")
async def submit_vp_application(payload: VPApplicationIn, request: Request):
    """Public Virtual Professional application. No auth required."""
    if (payload.website or "").strip():
        return {"ok": True, "application_id": "spam_ignored"}

    full_name = payload.full_name.strip()
    if len(full_name.split()) < 2:
        raise HTTPException(400, "Please enter your full name (first and last).")
    email = payload.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Please enter a valid email address.")
    if not payload.consent:
        raise HTTPException(400, "You must acknowledge this is a commission and project-based opportunity.")

    ip = (request.client.host if request.client else "") or "unknown"
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    recent = await db.vp_applications.count_documents({"ip": ip, "created_at": {"$gte": one_hour_ago}})
    if recent >= 5:
        raise HTTPException(429, "Too many submissions. Please try again later.")

    application_id = f"vpa_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    doc = {
        "application_id": application_id,
        "full_name": full_name,
        "email": email,
        "phone": payload.phone.strip(),
        "country": payload.country.strip(),
        "timezone": (payload.timezone or "").strip() or None,
        "streams": sorted(set(payload.streams)),
        "skills": sorted(set(payload.skills)),
        "portfolio_url": (payload.portfolio_url or "").strip() or None,
        "hours_per_day": payload.hours_per_day,
        "sales_experience": payload.sales_experience,
        "why_join": payload.why_join.strip(),
        "heard_from": payload.heard_from,
        "src": (payload.src or "").strip() or None,
        "status": "new",
        "admin_note": None,
        "ip": ip,
        "user_agent": (request.headers.get("user-agent") or "")[:200],
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.vp_applications.insert_one(doc)

    streams_label = ", ".join(STREAM_LABELS.get(s, s) for s in doc["streams"])
    await notify_admins(
        f"New VP application: {full_name}",
        f"{streams_label} · {doc['country']} · {doc['hours_per_day']} hrs/day",
        url="/ops/va-program/applications",
    )
    asyncio.create_task(_send_vp_emails(doc))
    return {"ok": True, "application_id": application_id}


async def _send_vp_emails(doc: dict) -> None:
    try:
        await email_admins(
            subject=f"New Virtual Professional application — {doc['full_name']}",
            title="New Virtual Professional application",
            body_html=_ops_email_html(doc),
            cta_label="Review application",
            cta_url=f"{_public_base()}/ops/va-program/applications",
        )
    except Exception as e:
        logger.error(f"VP application ops email failed ({doc['application_id']}): {e}")
    try:
        first_name = doc["full_name"].split(" ")[0]
        body_html = (
            f"<p style='margin:0 0 14px'>Hi {first_name},</p>"
            "<p style='margin:0 0 14px'><strong>Application received!</strong> Our operations team reviews "
            "every application personally. If you're a fit, expect to hear from us within a few business days. "
            "Keep an eye on your email and WhatsApp.</p>"
            "<p style='margin:0 0 14px'>What happens next:</p>"
            "<ol style='margin:0 0 14px;padding-left:20px'>"
            "<li>Our team reviews your application and skills.</li>"
            "<li>Qualified candidates get an onboarding conversation scheduled.</li>"
            "<li>You get your welcome package, platform access, and training.</li>"
            "</ol>"
            "<p style='margin:0'>— The HCOB Network Team</p>"
        )
        await _send_user_email(
            {"email": doc["email"], "user_id": None, "name": doc["full_name"]},
            kind="vp_application_confirmation",
            subject="Application received — HCOB Network Virtual Professionals",
            body_html=body_html,
        )
    except Exception as e:
        logger.error(f"VP application confirmation email failed ({doc['application_id']}): {e}")


@router.get("/admin/vp-applications")
async def list_vp_applications(status: Optional[str] = None, admin: dict = Depends(require_admin)):
    q = {}
    if status and status in STATUSES:
        q["status"] = status
    items = await db.vp_applications.find(q, {"_id": 0, "ip": 0, "user_agent": 0}).sort(
        "created_at", -1
    ).to_list(500)
    counts_raw = await db.vp_applications.aggregate(
        [{"$group": {"_id": "$status", "n": {"$sum": 1}}}]
    ).to_list(20)
    counts = {c["_id"]: c["n"] for c in counts_raw}
    return {"items": items, "counts": counts, "total": sum(counts.values())}


@router.patch("/admin/vp-applications/{application_id}")
async def update_vp_application(
    application_id: str, payload: VPApplicationPatch, admin: dict = Depends(require_admin)
):
    updates = {}
    if payload.status is not None:
        updates["status"] = payload.status
    if payload.admin_note is not None:
        updates["admin_note"] = payload.admin_note.strip() or None
    if not updates:
        raise HTTPException(400, "Nothing to update.")
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.vp_applications.update_one({"application_id": application_id}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(404, "Application not found.")
    doc = await db.vp_applications.find_one(
        {"application_id": application_id}, {"_id": 0, "ip": 0, "user_agent": 0}
    )
    return doc
