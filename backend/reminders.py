"""Email reminder cadences for HCOB Network workers.

Runs as a single background coroutine kicked off in `on_startup`. The loop
ticks every 10 minutes and performs two passes:

1. **Shift reminders** — for every accepted gig with a scheduled_at within
   the next 25-23 hours, email the worker once. We dedupe via a tiny
   `reminder_log` collection so a worker never gets two reminders for the
   same shift even if the loop runs twice in the window.

2. **Payment-info reminders** — for any worker whose `payout_method` is
   missing 3 days after registration (or 7 days). Each tier sends at most
   once. After the 7-day reminder we stop nagging.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from config import db, logger
from notifications import _send_user_email, _send_gig_event_email, _public_base


# 10 minutes between passes — fine resolution for shift reminders without
# hammering the DB.
REMINDER_LOOP_INTERVAL_SEC = 10 * 60

# Reminder windows
SHIFT_REMINDER_WINDOW_AHEAD = timedelta(hours=25)
SHIFT_REMINDER_WINDOW_FLOOR = timedelta(hours=23)

PAYMENT_REMINDER_TIERS = [
    ("payment_3d", timedelta(days=3)),
    ("payment_7d", timedelta(days=7)),
]


async def _has_logged(reminder_key: str) -> bool:
    doc = await db.reminder_log.find_one({"_id": reminder_key})
    return doc is not None


async def _mark_logged(reminder_key: str, payload: dict | None = None) -> None:
    await db.reminder_log.update_one(
        {"_id": reminder_key},
        {"$set": {**(payload or {}), "sent_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )


# ----------------------------- SHIFT REMINDERS ------------------------------
async def _send_shift_reminders_pass() -> None:
    """Find every accepted-status acceptance whose gig starts in ~24 hours,
    send a one-time reminder email, and log it so we don't double-send."""
    now = datetime.now(timezone.utc)
    target_min = now + SHIFT_REMINDER_WINDOW_FLOOR
    target_max = now + SHIFT_REMINDER_WINDOW_AHEAD
    # We compare against the gig's scheduled_at ISO string lexicographically.
    target_min_iso = target_min.isoformat()
    target_max_iso = target_max.isoformat()

    cursor = db.gigs.find(
        {
            "scheduled_at": {"$gte": target_min_iso, "$lte": target_max_iso},
            "status": {"$nin": ["cancelled", "draft"]},
        },
        {"gig_id": 1, "title": 1, "location": 1, "scheduled_at": 1, "scheduled_local": 1,
         "scheduled_date": 1, "pay_rate": 1, "pay_type": 1},
    )
    gigs = await cursor.to_list(length=500)
    if not gigs:
        return

    sent = 0
    for gig in gigs:
        gig_id = gig["gig_id"]
        # Active acceptances for this gig
        accs = await db.gig_acceptances.find(
            {
                "gig_id": gig_id,
                "status": {"$in": ["accepted", "on_the_clock"]},
            },
            {"worker_id": 1, "acceptance_id": 1, "status": 1},
        ).to_list(length=200)
        for a in accs:
            key = f"shift_24h::{a['acceptance_id']}"
            if await _has_logged(key):
                continue
            when = gig.get("scheduled_local") or gig.get("scheduled_at") or gig.get("scheduled_date") or ""
            pay = gig.get("pay_rate") or 0
            pay_type = gig.get("pay_type") or "hourly"
            pay_str = f"${float(pay):.2f}{'/hr' if pay_type == 'hourly' else ' flat'}"
            body = f"""
              <p style="margin:0 0 14px;font-size:15px;color:#030712">
                Heads up — your shift is in about 24 hours.
              </p>
              <div style="border:1px solid #E5E7EB;background:#F9FAFB;padding:14px;margin:0 0 16px">
                <div style="font-weight:700;font-size:15px;color:#030712">{gig.get('title') or 'Your shift'}</div>
                <div style="margin-top:6px;font-size:13px;color:#4B5563"><strong>When:</strong> {when}</div>
                <div style="margin-top:2px;font-size:13px;color:#4B5563"><strong>Where:</strong> {gig.get('location') or 'See gig'}</div>
                <div style="margin-top:2px;font-size:13px;color:#4B5563"><strong>Pay:</strong> {pay_str}</div>
              </div>
              <p style="margin:0 0 8px;font-size:13px;color:#030712">
                Don't forget to <strong>clock in</strong> when you arrive — no clock-in means no pay.
              </p>
            """
            try:
                await _send_gig_event_email(
                    a["worker_id"],
                    kind="shift_reminder_24h",
                    subject=f"Tomorrow: {gig.get('title') or 'Your HCOB shift'}",
                    body_html=body,
                    gig_id=gig_id,
                )
                await _mark_logged(key, {"gig_id": gig_id, "worker_id": a["worker_id"]})
                sent += 1
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[reminders] shift reminder failed for {a['acceptance_id']}: {e}")
    if sent:
        logger.info(f"[reminders] shift_reminder_24h sent {sent} emails")


# --------------------------- PAYMENT-INFO REMINDERS -------------------------
async def _send_payment_reminders_pass() -> None:
    """For workers missing payout_method, ping them at +3d and +7d post-signup.
    Each tier sends at most once per worker."""
    now = datetime.now(timezone.utc)
    sent = 0
    for tier_key, tier_delta in PAYMENT_REMINDER_TIERS:
        cutoff_iso = (now - tier_delta).isoformat()
        # Workers who:
        #  - registered at least `tier_delta` ago
        #  - still have no payout_method
        #  - are role=worker (skip admin/VA/customer)
        #  - aren't rejected
        cursor = db.users.find(
            {
                "role": "worker",
                "$or": [
                    {"payout_method": {"$exists": False}},
                    {"payout_method": None},
                    {"payout_method": ""},
                ],
                "created_at": {"$lte": cutoff_iso},
                "worker_status": {"$nin": ["rejected", "suspended"]},
            },
            {"user_id": 1, "email": 1, "name": 1, "created_at": 1, "payout_method": 1},
        )
        workers = await cursor.to_list(length=500)
        for u in workers:
            key = f"{tier_key}::{u['user_id']}"
            if await _has_logged(key):
                continue
            first = (u.get("name") or "").split(" ")[0] or "there"
            body = f"""
              <p style="margin:0 0 14px;font-size:15px;color:#030712">
                Hey {first} — quick housekeeping.
              </p>
              <p style="margin:0 0 16px;font-size:14px;line-height:1.6;color:#030712">
                You haven't told us how you'd like to be paid. We pay every shift via
                <strong>Zelle, Apple Cash, or Chime</strong>. Without a payout method on file
                we have no way to send you money once you start picking up shifts.
              </p>
              <p style="margin:0 0 4px;font-size:14px;color:#030712">
                It only takes 30 seconds — pick one and drop in your phone number or username.
              </p>
            """
            try:
                await _send_user_email(
                    u,
                    kind=tier_key,
                    subject="Add your payment info — Zelle, Apple Cash, or Chime",
                    body_html=body,
                    cta_label="Add payment method",
                    cta_url=f"{_public_base()}/crew/profile",
                )
                await _mark_logged(key, {"worker_id": u["user_id"], "tier": tier_key})
                sent += 1
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[reminders] {tier_key} email failed for {u.get('email')}: {e}")
    if sent:
        logger.info(f"[reminders] payment reminders sent {sent} emails")


# ----------------------------- RUNNER ---------------------------------------
async def reminders_runner() -> None:
    """Long-running coroutine — kicked off once in on_startup."""
    # Stagger the first pass so the worker_pool isn't slammed at boot
    await asyncio.sleep(60)
    while True:
        try:
            await _send_shift_reminders_pass()
        except Exception as e:  # noqa: BLE001
            logger.exception(f"[reminders] shift pass failed: {e}")
        try:
            await _send_payment_reminders_pass()
        except Exception as e:  # noqa: BLE001
            logger.exception(f"[reminders] payment pass failed: {e}")
        await asyncio.sleep(REMINDER_LOOP_INTERVAL_SEC)
