"""Web Push (PWA notifications) HTTP routes.

Subscription, status, and test endpoints. The actual send logic lives in
`push_service.py` so other modules (gigs, blasts, messenger digest) can
import the fan-out helper without dragging the router with them.

Wiring in server.py:
    from routes.push import router as push_router
    api.include_router(push_router)
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException

from config import VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, db
from auth_deps import get_current_user
from models import PushSubscriptionIn, PushTestIn
from push_service import _send_push_to_user

router = APIRouter()


@router.get("/push/public-key")
async def push_public_key():
    """Frontend reads this to call PushManager.subscribe()."""
    if not VAPID_PUBLIC_KEY:
        raise HTTPException(503, "Push notifications are not configured on this server")
    return {"public_key": VAPID_PUBLIC_KEY}


@router.post("/push/subscribe")
async def push_subscribe(
    payload: PushSubscriptionIn, user: dict = Depends(get_current_user)
):
    """Register or refresh this device's push subscription for the current user.
    Idempotent: same endpoint upserts."""
    now_iso = datetime.now(timezone.utc).isoformat()
    doc = {
        "user_id": user["user_id"],
        "endpoint": payload.endpoint,
        "keys": {"p256dh": payload.keys.p256dh, "auth": payload.keys.auth},
        "user_agent": (payload.user_agent or "")[:240],
        "platform": payload.platform,
        "active": True,
        "subscribed_at": now_iso,
        "pruned_at": None,
        "last_sent_at": None,
    }
    await db.push_subscriptions.update_one(
        {"endpoint": payload.endpoint},
        {"$set": doc},
        upsert=True,
    )
    return {"ok": True}


@router.delete("/push/subscribe")
async def push_unsubscribe(
    endpoint: str = Body(..., embed=True),
    user: dict = Depends(get_current_user),
):
    """Remove a device subscription. Workers can unsubscribe per-device."""
    await db.push_subscriptions.update_one(
        {"endpoint": endpoint, "user_id": user["user_id"]},
        {"$set": {"active": False, "unsubscribed_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True}


@router.get("/push/status")
async def push_status(user: dict = Depends(get_current_user)):
    """Return whether the current user has any active push subscriptions and a
    summary of devices — used by the Profile UI to show 'Enabled on N devices'.
    """
    rows = await db.push_subscriptions.find(
        {"user_id": user["user_id"], "active": True},
        {"_id": 0, "endpoint": 1, "platform": 1, "user_agent": 1, "subscribed_at": 1},
    ).to_list(20)
    return {
        "enabled": len(rows) > 0,
        "device_count": len(rows),
        "devices": rows,
        "server_configured": bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY),
    }


@router.post("/push/test")
async def push_test(
    payload: PushTestIn, user: dict = Depends(get_current_user)
):
    """Fire a test push to every device the current user has registered.
    Useful from the Profile UI to confirm setup."""
    sent = await _send_push_to_user(
        user["user_id"],
        {
            "title": payload.title or "HCOB Network test",
            "body": payload.body or "Push is working.",
            "tag": "hcob-test",
            "url": "/crew",
        },
    )
    return {"ok": True, "sent": sent}
