"""Web Push helpers — VAPID-based send + per-user fanout.

Each user can have multiple subscriptions (one per device). Sending is
best-effort and expired subscriptions (HTTP 404/410) are auto-pruned.

The `_send_push_sync` helper is synchronous (the pywebpush SDK is blocking) —
async callers MUST wrap it with `asyncio.to_thread`. `_send_push_to_user` is
the high-level async helper that does the fan-out + pruning.
"""
import asyncio
import json
from datetime import datetime, timezone

from pywebpush import webpush, WebPushException

from config import (
    db,
    logger,
    VAPID_PRIVATE_KEY,
    VAPID_PUBLIC_KEY,
    VAPID_SUBJECT,
)


class PushSubscriptionGone(Exception):
    """Raised when the push gateway returns 404/410 — caller should prune."""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint


def _send_push_sync(subscription: dict, payload: dict) -> bool:
    """Synchronous push send — call via asyncio.to_thread from async code."""
    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        return False
    try:
        webpush(
            subscription_info={
                "endpoint": subscription["endpoint"],
                "keys": subscription.get("keys", {}),
            },
            data=json.dumps(payload),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_SUBJECT},
            ttl=60 * 60 * 24,  # keep undelivered messages for up to a day
        )
        return True
    except WebPushException as e:
        # 404/410 mean the subscription is dead — let the caller prune.
        status = getattr(e.response, "status_code", None) if e.response else None
        if status in (404, 410):
            raise PushSubscriptionGone(subscription["endpoint"])
        logger.error(f"Push send failed for {subscription['endpoint'][:60]}: {e}")
        return False
    except Exception as e:
        logger.error(f"Push send unexpected error: {e}")
        return False


async def _send_push_to_user(
    user_id: str, payload: dict, prune_failed: bool = True
) -> int:
    """Fan out a push payload to every subscription registered for a user.
    Returns how many sends succeeded. Auto-prunes dead subscriptions."""
    if not VAPID_PRIVATE_KEY:
        return 0
    subs = await db.push_subscriptions.find(
        {"user_id": user_id, "active": True}, {"_id": 0}
    ).to_list(20)
    sent = 0
    for sub in subs:
        try:
            ok = await asyncio.to_thread(_send_push_sync, sub, payload)
            if ok:
                sent += 1
                await db.push_subscriptions.update_one(
                    {"endpoint": sub["endpoint"]},
                    {"$set": {"last_sent_at": datetime.now(timezone.utc).isoformat()}},
                )
        except PushSubscriptionGone as gone:
            if prune_failed:
                logger.info(f"Pruning dead push subscription {gone.endpoint[:60]}")
                await db.push_subscriptions.update_one(
                    {"endpoint": gone.endpoint},
                    {"$set": {
                        "active": False,
                        "pruned_at": datetime.now(timezone.utc).isoformat(),
                    }},
                )
    return sent
