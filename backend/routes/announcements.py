"""Centralized announcements — admin posts once, workers/VAs see a login popup
+ a revisitable board, and delivery fans out via in-app / email / SMS / push
using the existing blast infrastructure (kill switch, dedupe, rate limits)."""
import asyncio
import html as html_mod
import uuid
from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from config import db, logger
from auth_deps import get_current_user, require_admin
from notifications import _email_layout, _log_blast, _public_base, fanout_blast_channels

router = APIRouter()

AUDIENCE_LABELS = {"worker": "Workers", "va": "VAs"}


class AnnouncementIn(BaseModel):
    title: str = Field(min_length=2, max_length=140)
    body: str = Field(min_length=2, max_length=4000)
    audience: List[Literal["worker", "va"]] = Field(min_length=1)
    popup: bool = False
    channels: List[Literal["in_app", "email", "sms", "push"]] = Field(default=["in_app"], min_length=1)


class AnnouncementPatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=140)
    body: Optional[str] = Field(default=None, min_length=2, max_length=4000)
    audience: Optional[List[Literal["worker", "va"]]] = Field(default=None, min_length=1)
    popup: Optional[bool] = None
    active: Optional[bool] = None


def _body_html(body: str) -> str:
    return html_mod.escape(body).replace("\n", "<br>")


@router.post("/admin/announcements")
async def create_announcement(payload: AnnouncementIn, admin: dict = Depends(require_admin)):
    now = datetime.now(timezone.utc).isoformat()
    audience = sorted(set(payload.audience))
    channels = sorted(set(payload.channels))

    recipients = await db.users.find(
        {"role": {"$in": audience}},
        {"_id": 0, "user_id": 1, "name": 1, "email": 1, "phone": 1},
    ).to_list(5000)

    announcement_id = f"ann_{uuid.uuid4().hex[:12]}"

    in_app_count = 0
    if "in_app" in channels and recipients:
        notif_docs = [
            {
                "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
                "user_id": r["user_id"],
                "kind": "announcement",
                "announcement_id": announcement_id,
                "title": f"Announcement: {payload.title}",
                "body": payload.body[:140],
                "read": False,
                "created_at": now,
            }
            for r in recipients
        ]
        await db.notifications.insert_many(notif_docs)
        in_app_count = len(notif_docs)

    blast_id = None
    external = [c for c in channels if c in ("email", "sms", "push")]
    if external and recipients:
        base = _public_base()
        subject = f"HCOB Announcement: {payload.title}"
        html = _email_layout(
            payload.title,
            _body_html(payload.body),
            cta_label="Open HCOB Network",
            cta_url=base,
        )
        sms_body = f"HCOB announcement — {payload.title}: {payload.body[:130]}" + (
            "…" if len(payload.body) > 130 else ""
        ) + f" More: {base}"
        push_payload = {
            "title": f"📢 {payload.title}",
            "body": payload.body[:120],
            "tag": f"announcement-{announcement_id}",
            "url": "/",
            "kind": "announcement",
        }
        blast_id = await _log_blast(
            kind="announcement",
            gig_id=None,
            gig_title=None,
            project_id=None,
            project_title=payload.title,
            channels=external,
            counts={"in_app": in_app_count},
            workers_targeted=len(recipients),
            sent_by_id=admin["user_id"],
            sent_by_name=admin.get("name"),
            extra={"announcement_id": announcement_id, "audience": audience},
        )
        asyncio.create_task(fanout_blast_channels(
            workers=recipients,
            channels=external,
            subject=subject,
            html=html,
            sms_body=sms_body,
            push_payload=push_payload,
            blast_log_id=blast_id,
        ))

    doc = {
        "announcement_id": announcement_id,
        "title": payload.title.strip(),
        "body": payload.body.strip(),
        "audience": audience,
        "popup": payload.popup,
        "channels": channels,
        "active": True,
        "dismissed_by": [],
        "recipients": len(recipients),
        "in_app": in_app_count,
        "blast_id": blast_id,
        "created_by": admin["user_id"],
        "created_by_name": admin.get("name"),
        "created_at": now,
        "updated_at": now,
    }
    await db.announcements.insert_one(doc)
    logger.info(
        f"Announcement {announcement_id} posted by {admin['user_id']}: "
        f"audience={audience} channels={channels} recipients={len(recipients)}"
    )
    return {k: v for k, v in doc.items() if k not in ("_id", "dismissed_by")}


@router.get("/admin/announcements")
async def admin_list_announcements(admin: dict = Depends(require_admin)):
    docs = await db.announcements.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    blast_ids = [d["blast_id"] for d in docs if d.get("blast_id")]
    logs = {}
    if blast_ids:
        async for b in db.blast_logs.find(
            {"blast_id": {"$in": blast_ids}},
            {"_id": 0, "blast_id": 1, "email": 1, "sms": 1, "push": 1, "email_failed": 1, "sms_failed": 1},
        ):
            logs[b["blast_id"]] = b
    items = []
    for d in docs:
        d["read_count"] = len(d.pop("dismissed_by", []) or [])
        blast = logs.get(d.get("blast_id")) or {}
        d["delivery"] = {
            "in_app": d.get("in_app", 0),
            "email": blast.get("email", 0),
            "sms": blast.get("sms", 0),
            "push": blast.get("push", 0),
            "email_failed": blast.get("email_failed", 0),
            "sms_failed": blast.get("sms_failed", 0),
        }
        items.append(d)
    return {"items": items}


@router.put("/admin/announcements/{announcement_id}")
async def update_announcement(
    announcement_id: str,
    payload: AnnouncementPatch,
    admin: dict = Depends(require_admin),
):
    ann = await db.announcements.find_one({"announcement_id": announcement_id})
    if not ann:
        raise HTTPException(404, "Announcement not found")
    updates: dict = {}
    if payload.title is not None:
        updates["title"] = payload.title.strip()
    if payload.body is not None:
        updates["body"] = payload.body.strip()
    if payload.audience is not None:
        updates["audience"] = sorted(set(payload.audience))
    if payload.popup is not None:
        updates["popup"] = payload.popup
    if payload.active is not None:
        updates["active"] = payload.active
    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.announcements.update_one({"announcement_id": announcement_id}, {"$set": updates})
    fresh = await db.announcements.find_one({"announcement_id": announcement_id}, {"_id": 0})
    fresh["read_count"] = len(fresh.pop("dismissed_by", []) or [])
    return fresh


@router.delete("/admin/announcements/{announcement_id}")
async def delete_announcement(announcement_id: str, admin: dict = Depends(require_admin)):
    res = await db.announcements.delete_one({"announcement_id": announcement_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Announcement not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# User-facing (workers + VAs)
# ---------------------------------------------------------------------------
@router.get("/announcements")
async def my_announcements(user: dict = Depends(get_current_user)):
    role = user.get("role")
    if role not in ("worker", "va"):
        return {"items": []}
    docs = await db.announcements.find(
        {"active": True, "audience": role}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    items = []
    for d in docs:
        dismissed = user["user_id"] in (d.get("dismissed_by") or [])
        d.pop("dismissed_by", None)
        d.pop("blast_id", None)
        d["dismissed"] = dismissed
        items.append(d)
    return {"items": items}


@router.post("/announcements/{announcement_id}/dismiss")
async def dismiss_announcement(announcement_id: str, user: dict = Depends(get_current_user)):
    res = await db.announcements.update_one(
        {"announcement_id": announcement_id},
        {"$addToSet": {"dismissed_by": user["user_id"]}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Announcement not found")
    return {"ok": True}
