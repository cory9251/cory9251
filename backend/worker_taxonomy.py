"""Worker questionnaire v2 (FRD Addendum A) — classes, trades, cert tags.

The legacy `users.skills` array stays the single field all dispatch, filter
and blast code reads. This module derives it from the structured v2 fields:
general_skills + ACTIVE specialist trades + ACTIVE cert tags. A trade/cert is
active when verified, or unverified but inside its migration grace window.
Work attributes are never included (never displayed as skills).
"""
import asyncio
from datetime import datetime, timezone, timedelta

from config import db, logger
from constants import (
    GENERAL_SKILLS,
    SPECIALIST_TRADES,
    WORK_ATTRIBUTES,
    CERT_TAGS,
)

MIGRATION_GRACE_DAYS = 30

# Legacy free-text chips seen in old rosters → canonical v2 values (FRD §3).
LEGACY_SKILL_SYNONYMS = {
    "cleaning": "routine_cleaning",
    "move_outs": "moveouts",
    "post_construction_cleaning": "post_construction",
}


def _parse_iso(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def trade_is_active(claim: dict, now: datetime = None) -> bool:
    """Active for dispatch: verified, or unverified but within grace (FRD §7)."""
    if claim.get("status") == "verified":
        return True
    now = now or datetime.now(timezone.utc)
    g = _parse_iso(claim.get("grace_until"))
    return bool(g and g > now)


def cert_is_active(ct: dict, now: datetime = None) -> bool:
    if ct.get("verified"):
        return True
    now = now or datetime.now(timezone.utc)
    g = _parse_iso(ct.get("grace_until"))
    return bool(g and g > now)


def compute_legacy_skills(user: dict) -> list:
    now = datetime.now(timezone.utc)
    skills = [s for s in (user.get("general_skills") or []) if s in GENERAL_SKILLS]
    for c in user.get("specialist_trades") or []:
        if c.get("trade") in SPECIALIST_TRADES and trade_is_active(c, now):
            skills.append(c["trade"])
    for ct in user.get("cert_tags") or []:
        if ct.get("tag") in CERT_TAGS and cert_is_active(ct, now):
            skills.append(ct["tag"])
    # Unrecognized legacy values are preserved verbatim so migration never
    # silently changes a worker's dispatch eligibility.
    skills.extend(user.get("legacy_unmapped_skills") or [])
    return sorted(set(skills))


async def sync_user_skills(user_id: str) -> None:
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        return
    await db.users.update_one(
        {"user_id": user_id}, {"$set": {"skills": compute_legacy_skills(user)}}
    )


# ============================================================================
# One-time migration of the legacy flat skill chips (FRD §3 / §7)
# ============================================================================
_MIGRATED_TRADES = ("painting", "landscaping", "carpet_cleaning")


async def migrate_workers_to_v2() -> int:
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    grace = (now + timedelta(days=MIGRATION_GRACE_DAYS)).isoformat()
    count = 0
    cursor = db.users.find(
        {"role": "worker", "questionnaire_version": {"$ne": 2}}, {"_id": 0}
    )
    async for w in cursor:
        legacy_raw = w.get("skills") or []
        legacy = [LEGACY_SKILL_SYNONYMS.get(s, s) for s in legacy_raw]
        general = [s for s in legacy if s in GENERAL_SKILLS]
        trades = []
        for t in _MIGRATED_TRADES:
            if t in legacy:
                trades.append({
                    "trade": t,
                    "status": "pending",
                    "experience": w.get("experience_level"),
                    "checklist": {},
                    "detail_fields": {},
                    "photos": [],
                    "license_number": None,
                    "admin_note": None,
                    "claimed_at": now_iso,
                    "submitted_at": now_iso,
                    "verified_at": None,
                    "verified_by": None,
                    "grace_until": grace,
                    "migrated": True,
                })
        certs = []
        if "forklift" in legacy:
            certs.append({"tag": "forklift", "verified": False, "grace_until": grace, "source": "migration"})
        if "cdl" in legacy or w.get("has_cdl"):
            certs.append({"tag": "cdl", "verified": False, "grace_until": grace, "source": "migration"})
        attrs = [s for s in legacy if s in WORK_ATTRIBUTES]
        classes = []
        if general:
            classes.append("general_labor")
        if trades:
            classes.append("specialist")
        known = set(GENERAL_SKILLS) | set(_MIGRATED_TRADES) | {"forklift", "cdl"} | set(WORK_ATTRIBUTES)
        unmapped = [s for s in legacy if s not in known]
        updates = {
            "questionnaire_version": 2,
            "general_skills": general,
            "specialist_trades": trades,
            "cert_tags": certs,
            "work_attributes": attrs,
            "work_classes": classes,
            "general_experience": w.get("experience_level"),
            "legacy_unmapped_skills": unmapped,
            "skills_legacy_backup": legacy_raw,
        }
        updates["skills"] = compute_legacy_skills({**w, **updates})
        await db.users.update_one({"user_id": w["user_id"]}, {"$set": updates})
        count += 1
    if count:
        logger.info(f"Questionnaire v2 migration: migrated {count} workers")
    return count


# ============================================================================
# Grace-expiry resync — removes expired unverified trades/certs from `skills`
# ============================================================================
async def resync_grace_expired_loop():
    while True:
        try:
            now = datetime.now(timezone.utc)
            cursor = db.users.find(
                {"role": "worker", "questionnaire_version": 2,
                 "$or": [
                     {"specialist_trades.grace_until": {"$ne": None}},
                     {"cert_tags.grace_until": {"$ne": None}},
                 ]},
                {"_id": 0, "user_id": 1, "general_skills": 1, "specialist_trades": 1,
                 "cert_tags": 1, "skills": 1},
            )
            async for w in cursor:
                fresh = compute_legacy_skills(w)
                if fresh != sorted(set(w.get("skills") or [])):
                    await db.users.update_one(
                        {"user_id": w["user_id"]}, {"$set": {"skills": fresh}}
                    )
        except Exception as e:
            logger.warning(f"grace resync loop error: {e}")
        await asyncio.sleep(6 * 3600)
