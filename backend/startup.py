"""Startup orchestration for the HCOB Network backend.

server.py's `on_startup` event used to be 300+ lines of mixed concerns —
indices, legacy backfills, idempotent seeds, and background-task kickoff
all jammed together. This module breaks those into 4 focused coroutines
that server.py calls in order:

    1. `ensure_indices(db)`       — Mongo indices (idempotent)
    2. `run_migrations(db)`       — legacy backfills + data healing
    3. `seed_accounts_and_templates(db)` — admin / Mechie / pitch templates
    4. `start_background_tasks()` — long-running asyncio tasks

Each function is idempotent and safe to re-run on every boot. Errors are
caught and logged but never crash the app — a stale index or missing seed
script shouldn't take down production.
"""
import os
import uuid
import asyncio
from datetime import datetime, timezone

from config import db, logger
from auth_deps import hash_password, verify_password


# ============================================================================
# 1. INDICES
# ============================================================================
async def ensure_indices() -> None:
    """Create all Mongo indices the app relies on. Idempotent — Mongo's
    `create_index` is a no-op when an identical index already exists."""
    # Core collections
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.sessions.create_index("session_token", unique=True)
    await db.gigs.create_index("gig_id", unique=True)
    await db.gig_acceptances.create_index([("gig_id", 1), ("worker_id", 1)], unique=True)
    await db.notifications.create_index("user_id")

    # Worker agreement audit log — one doc per gig accept submission.
    await db.worker_agreements.create_index("agreement_id", unique=True)
    await db.worker_agreements.create_index("worker_id")
    await db.worker_agreements.create_index("gig_id")
    await db.worker_agreements.create_index([("accepted_at", -1)])

    # Messenger
    await db.threads.create_index("thread_id", unique=True)
    await db.threads.create_index("participant_ids")
    await db.threads.create_index("last_message_at")
    await db.messages.create_index([("thread_id", 1), ("created_at", -1)])
    await db.thread_reads.create_index(
        [("thread_id", 1), ("user_id", 1)], unique=True
    )

    # Projects
    await db.projects.create_index("project_id", unique=True)
    await db.projects.create_index([("archived", 1), ("created_at", -1)])
    await db.gigs.create_index("project_id")

    # Blast logs (Reports → Blasts)
    await db.blast_logs.create_index([("sent_at", -1)])
    await db.blast_logs.create_index("gig_id")
    await db.blast_logs.create_index("project_id")

    # Email blast (per-template cooldown lookup)
    await db.email_blast_log.create_index([("template_key", 1), ("user_id", 1), ("sent_at", -1)])
    await db.email_blast_log.create_index([("sent_at", -1)])

    # VA Objection Coach (rate-limit lookup: calls by VA in last hour)
    await db.va_objection_calls.create_index([("va_user_id", 1), ("called_at", -1)])

    # Password reset tokens — public forgot/reset flow
    await db.password_reset_tokens.create_index("token", unique=True)
    await db.password_reset_tokens.create_index("user_id")
    await db.password_reset_tokens.create_index("expires_at")

    # VA Commission Program
    await db.va_leads.create_index("lead_id", unique=True)
    await db.va_leads.create_index("va_user_id")
    await db.va_leads.create_index("prospect_phone_norm")
    await db.va_leads.create_index("prospect_email_norm")
    await db.va_leads.create_index([("created_at", -1)])
    await db.commissions.create_index("commission_id", unique=True)
    await db.commissions.create_index("lead_id")
    await db.commissions.create_index("va_user_id")
    await db.commissions.create_index("status")
    await db.commercial_accounts.create_index("account_id", unique=True)
    await db.commercial_accounts.create_index("va_user_id")
    await db.va_violations.create_index("va_user_id")
    await db.va_violations.create_index([("created_at", -1)])


# ============================================================================
# 2. MIGRATIONS / BACKFILLS
# ============================================================================
async def _backfill_gigs() -> None:
    """Add default values to any field added after a gig was created."""
    # is_rush — needed by public landing sort
    await db.gigs.update_many(
        {"is_rush": {"$exists": False}},
        {"$set": {"is_rush": False, "rush_at": None}},
    )
    # tags array — pre-tag-feature gigs. Carry forward rush state.
    await db.gigs.update_many(
        {"tags": {"$exists": False}, "is_rush": True},
        {"$set": {"tags": ["rush"]}},
    )
    await db.gigs.update_many(
        {"tags": {"$exists": False}},
        {"$set": {"tags": []}},
    )
    # break_minutes
    await db.gigs.update_many(
        {"break_minutes": {"$exists": False}},
        {"$set": {"break_minutes": 0}},
    )
    # payment_timeline
    await db.gigs.update_many(
        {"payment_timeline": {"$exists": False}},
        {"$set": {"payment_timeline": "2_3_days", "payment_timeline_note": None}},
    )
    # project_id
    await db.gigs.update_many(
        {"project_id": {"$exists": False}},
        {"$set": {"project_id": None}},
    )


async def _backfill_scheduled_local() -> None:
    """Wall-clock string is the single source of truth for display. Without
    it the calendar/feed fall back to parsing UTC + converting to viewer-TZ,
    which makes the displayed hour drift. For legacy docs we derive
    scheduled_local from scheduled_at assuming the platform's default TZ
    (America/New_York — HCOB Baltimore HQ)."""
    try:
        from zoneinfo import ZoneInfo
        site_tz = ZoneInfo(os.environ.get("HCOB_SITE_TZ", "America/New_York"))
    except Exception:  # noqa: BLE001
        site_tz = None
    legacy = await db.gigs.find(
        {"scheduled_local": {"$in": [None, ""]}, "scheduled_at": {"$ne": None}},
        {"gig_id": 1, "scheduled_at": 1},
    ).to_list(length=None)
    for lg in legacy:
        sa = lg.get("scheduled_at")
        if not sa:
            continue
        try:
            dt = datetime.fromisoformat(str(sa).replace("Z", "+00:00"))
            dt_local = dt.astimezone(site_tz) if (site_tz and dt.tzinfo is not None) else dt
            sl = dt_local.strftime("%Y-%m-%dT%H:%M")
            await db.gigs.update_one(
                {"gig_id": lg["gig_id"]}, {"$set": {"scheduled_local": sl}}
            )
        except Exception:  # noqa: BLE001
            continue


async def _migrate_truthful_approvals() -> None:
    """Iter47 added a write-time gate that rejects approvals when a worker
    has unresolved profile/ID blockers. This migration cleans up historical
    data in newly-deployed environments — downgrading any pre-existing
    `approved` worker who still has blockers back to `pending`."""
    try:
        from auth_deps import _worker_approval_blockers
        downgraded = 0
        boot_iso = datetime.now(timezone.utc).isoformat()
        cursor = db.users.find(
            {"role": "worker", "worker_status": "approved"},
            {
                "user_id": 1, "_id": 1, "id_image_path": 1, "id_verified": 1,
                "name": 1, "phone": 1, "address": 1, "skills": 1, "bio": 1,
                "date_of_birth": 1, "availability": 1,
                "emergency_contact_name": 1, "emergency_contact_phone": 1,
                "zip_code": 1, "role": 1, "worker_status": 1, "email": 1,
            },
        )
        async for w in cursor:
            blockers = _worker_approval_blockers(w)
            if not blockers:
                continue
            await db.users.update_one(
                {"_id": w["_id"]},
                {"$set": {
                    "worker_status": "pending",
                    "worker_status_at": boot_iso,
                    "worker_status_by": "system:startup:iter47-truthful-approval",
                    "auto_downgraded_at": boot_iso,
                    "auto_downgrade_blockers": blockers,
                }},
            )
            downgraded += 1
        if downgraded:
            logger.info(
                f"truthful-approval auto-migration: downgraded {downgraded} "
                f"workers from 'approved' → 'pending' (had unresolved blockers)"
            )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"truthful-approval auto-migration failed (non-fatal): {e}")


async def _reconcile_slot_counts() -> None:
    """Heal any `slots_filled` / `backups_filled` / `status` drift caused by
    the pre-Iter52 race condition where two concurrent admin approvals could
    both squeeze past the capacity check and overbook a gig. Idempotent —
    clean gigs are skipped."""
    try:
        reconciled = 0
        async for g in db.gigs.find(
            {},
            {"gig_id": 1, "slots": 1, "slots_filled": 1, "backups_filled": 1, "status": 1},
        ):
            primary_count = await db.gig_acceptances.count_documents({
                "gig_id": g["gig_id"],
                "status": {"$in": ["accepted", "on_the_clock", "completed"]},
            })
            backup_count = await db.gig_acceptances.count_documents({
                "gig_id": g["gig_id"], "status": "backup",
            })
            current_primary = int(g.get("slots_filled") or 0)
            current_backup = int(g.get("backups_filled") or 0)
            updates = {}
            if primary_count != current_primary:
                updates["slots_filled"] = primary_count
            if backup_count != current_backup:
                updates["backups_filled"] = backup_count
            total_slots = int(g.get("slots", 1))
            should_be_filled = primary_count >= total_slots
            if should_be_filled and g.get("status") == "open":
                updates["status"] = "filled"
            elif not should_be_filled and g.get("status") == "filled":
                updates["status"] = "open"
            if updates:
                await db.gigs.update_one({"gig_id": g["gig_id"]}, {"$set": updates})
                reconciled += 1
        if reconciled:
            logger.info(f"slot-count reconciliation: healed {reconciled} gigs with drifted counters")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"slot-count reconciliation failed (non-fatal): {e}")


async def run_migrations() -> None:
    """Run every legacy backfill + data healing pass. Each one is its own
    try/except so a failure in one doesn't block the others."""
    await _backfill_gigs()
    await _backfill_scheduled_local()
    await _migrate_truthful_approvals()
    await _reconcile_slot_counts()


# ============================================================================
# 3. SEEDS
# ============================================================================
async def _seed_pitch_templates() -> None:
    """Run the pitch-templates seeder when fewer than 50 active templates
    exist. The seeder itself skips templates whose title already exists
    (case-insensitive), so re-runs are cheap and safe."""
    try:
        active_count = await db.pitch_templates.count_documents(
            {"active": True, "deleted_at": {"$in": [None, ""]}}
        )
        if active_count < 50:
            from scripts.seed_pitch_templates import seed as seed_pitch_templates
            created, skipped = await seed_pitch_templates()
            logger.info(
                f"pitch_templates auto-seed: {created} new, {skipped} skipped"
                f" (had {active_count} active before)"
            )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"pitch_templates auto-seed failed (non-fatal): {e}")


async def _seed_admin() -> None:
    """Seed the legacy GigBlast admin. If they exist and the env-var
    password is different, re-hash so a manual env change rotates the
    creds without redeploying a migration script."""
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@gigblast.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "GigBlast2026!")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "name": "Operations Admin",
            "role": "admin",
            "phone": "", "address": "", "bio": "", "skills": [],
            "avatar_path": None,
            "id_image_path": None,
            "id_verified": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "auth_provider": "local",
        })
        logger.info(f"Seeded admin user {admin_email}")
    elif not verify_password(admin_password, existing.get("password_hash", "")):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password)}},
        )


async def _owner_reset_failsafe() -> None:
    """Production unlock failsafe — if `OWNER_RESET_EMAIL` AND
    `OWNER_RESET_PASSWORD` are BOTH set in the environment, forcibly reset
    that user's password on boot. Designed for emergency lockout recovery.
    Remove the env vars after using or every boot will re-reset."""
    reset_email = (os.environ.get("OWNER_RESET_EMAIL") or "").strip().lower()
    reset_pwd = (os.environ.get("OWNER_RESET_PASSWORD") or "").strip()
    if not (reset_email and reset_pwd):
        return
    target = await db.users.find_one({"email": reset_email})
    if not target:
        logger.error(f"[OWNER_RESET] Email {reset_email} not found in users.")
        return
    await db.users.update_one(
        {"email": reset_email},
        {"$set": {"password_hash": hash_password(reset_pwd)}},
    )
    await db.sessions.delete_many({"user_id": target.get("user_id")})
    logger.warning(
        f"[OWNER_RESET] Forcibly reset password for {reset_email} on startup. "
        f"REMOVE OWNER_RESET_EMAIL and OWNER_RESET_PASSWORD env vars now."
    )


async def _seed_hcob_owner_and_pm() -> None:
    """Mark `admin@hcobcleaners.com` as Owner (VA Commission final payout
    sign-off) and seed Mechie as Program Manager. Idempotent."""
    await db.users.update_one(
        {"email": "admin@hcobcleaners.com"},
        {"$set": {"is_owner": True}},
    )
    mechie_email = "mechiebadlong77@gmail.com"
    mechie_password = "Mechie2026!"
    mechie = await db.users.find_one({"email": mechie_email})
    if not mechie:
        await db.users.insert_one({
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "email": mechie_email,
            "password_hash": hash_password(mechie_password),
            "name": "Mechie (Program Manager)",
            "role": "admin",
            "is_program_manager": True,
            "is_owner": False,
            "must_change_password": True,
            "phone": "", "address": "", "bio": "", "skills": [],
            "avatar_path": None,
            "id_image_path": None,
            "id_verified": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "auth_provider": "local",
        })
        logger.info(f"Seeded Program Manager {mechie_email}")
    else:
        # Idempotent flag set
        await db.users.update_one(
            {"email": mechie_email},
            {"$set": {"is_program_manager": True}},
        )


async def seed_accounts_and_templates() -> None:
    """Run every idempotent seed. Each one wraps its own errors so a single
    bad seed doesn't break the rest."""
    await _seed_pitch_templates()
    await _seed_admin()
    await _owner_reset_failsafe()
    await _seed_hcob_owner_and_pm()


# ============================================================================
# 4. BACKGROUND TASKS
# ============================================================================
def start_background_tasks() -> None:
    """Kick off long-running asyncio tasks. Lazy-imports avoid circular
    imports during module load."""
    from routes.messages import _message_digest_runner
    from reminders import reminders_runner
    asyncio.create_task(_message_digest_runner())
    asyncio.create_task(reminders_runner())
