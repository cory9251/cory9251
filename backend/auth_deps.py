"""Auth dependencies + password/session helpers shared across all routes.

Anything that needs the current user, an admin check, or a password hash goes
through here. Route modules import `get_current_user` / `require_admin` as
FastAPI dependencies.
"""
from datetime import datetime, timezone
from typing import List, Optional
import secrets

import bcrypt
from fastapi import Depends, HTTPException, Request

from config import db
from constants import REQUIRED_PROFILE_FIELDS


# ---- Password helpers ------------------------------------------------------
def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except Exception:
        return False


def new_session_token() -> str:
    return secrets.token_urlsafe(48)


SESSION_DAYS = 7


def cookie_kwargs() -> dict:
    """httpOnly session cookie. SameSite=Lax — frontend and API share the same
    origin (preview + production), so Lax works everywhere and blocks CSRF
    from third-party sites."""
    return dict(
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=SESSION_DAYS * 86400,
    )


# ---- Profile completion helpers --------------------------------------------
def _profile_missing_fields(user: dict) -> List[str]:
    """Return required-profile fields that are blank/empty for a worker.
    An empty list means the profile is complete."""
    if user.get("role") != "worker":
        return []
    missing: List[str] = []
    for f in REQUIRED_PROFILE_FIELDS:
        v = user.get(f)
        if v is None:
            missing.append(f)
        elif isinstance(v, str) and not v.strip():
            missing.append(f)
        elif isinstance(v, list) and len(v) == 0:
            missing.append(f)
    return missing


def _is_profile_complete(user: dict) -> bool:
    return len(_profile_missing_fields(user)) == 0


def _worker_approval_blockers(user: dict) -> List[str]:
    """Return human-readable reasons the worker can't be marked 'approved' yet.
    Empty list = ready to approve. Mirrors the gates enforced on /gigs/accept
    so admin approval and worker booking can't drift apart."""
    if user.get("role") != "worker":
        return []
    blockers: List[str] = []
    if not user.get("id_image_path"):
        blockers.append("ID not uploaded")
    elif not user.get("id_verified"):
        blockers.append("ID awaiting verification")
    missing = _profile_missing_fields(user)
    if missing:
        blockers.append(f"Profile incomplete ({len(missing)} field{'s' if len(missing) != 1 else ''} missing)")
    return blockers


def _worker_is_fully_active(user: dict) -> bool:
    """True only when the worker is approved AND id-verified AND profile-complete —
    the same conditions enforced on /gigs/accept. Used by API responses so the
    frontend can render a truthful badge."""
    if user.get("role") != "worker":
        return False
    if (user.get("worker_status") or "approved") != "approved":
        return False
    return not _worker_approval_blockers(user)


# ---- User lookup + dependencies --------------------------------------------
async def _worker_rating_stats(user_id: str) -> dict:
    """Return rating aggregates for a worker — combined avg + per-source
    breakdowns (admin vs client). Considers only non-null star values."""
    cur = db.gig_acceptances.find(
        {"worker_id": user_id},
        {"_id": 0, "admin_rating": 1, "client_rating": 1},
    )
    admin_stars: list = []
    client_stars: list = []
    async for a in cur:
        if isinstance(a.get("admin_rating"), (int, float)):
            admin_stars.append(a["admin_rating"])
        if isinstance(a.get("client_rating"), (int, float)):
            client_stars.append(a["client_rating"])
    all_stars = admin_stars + client_stars
    return {
        "rating_avg": round(sum(all_stars) / len(all_stars), 2) if all_stars else None,
        "rating_count": len(all_stars),
        "admin_rating_avg": round(sum(admin_stars) / len(admin_stars), 2) if admin_stars else None,
        "admin_rating_count": len(admin_stars),
        "client_rating_avg": round(sum(client_stars) / len(client_stars), 2) if client_stars else None,
        "client_rating_count": len(client_stars),
    }


async def _get_user_by_id(user_id: str) -> Optional[dict]:
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        return None
    # Enrich with computed profile-completion fields so the client knows what
    # to prompt for. Admins are never blocked.
    if user.get("role") == "worker":
        missing = _profile_missing_fields(user)
        user["profile_complete"] = len(missing) == 0
        user["profile_missing_fields"] = missing
        # Attach rating aggregates — pulled across all of this worker's
        # acceptances. Admin-only data, but always returned (the worker UI
        # is responsible for not displaying it).
        stats = await _worker_rating_stats(user_id)
        user.update(stats)
    else:
        user["profile_complete"] = True
        user["profile_missing_fields"] = []
    # Default flags for owner / PM so the frontend always has them.
    user.setdefault("is_owner", False)
    user.setdefault("is_program_manager", False)
    user.setdefault("must_change_password", False)
    # "Available now" toggle — auto-expires at `available_until`. Clears the
    # field if expired so the client always sees the current truth.
    if user.get("available_now"):
        until = user.get("available_until")
        try:
            until_dt = datetime.fromisoformat(str(until).replace("Z", "+00:00")) if until else None
        except Exception:
            until_dt = None
        if not until_dt or until_dt < datetime.now(timezone.utc):
            user["available_now"] = False
            user["available_until"] = None
            # Persist the cleared state (fire-and-forget; ignore failure)
            try:
                await db.users.update_one(
                    {"user_id": user_id},
                    {"$set": {"available_now": False, "available_until": None}},
                )
            except Exception:
                pass
    else:
        user.setdefault("available_now", False)
        user.setdefault("available_until", None)
    if user.get("role") == "va":
        user.setdefault("va_status", "pending")
    return user


async def get_current_user(request: Request) -> dict:
    # Cookie first, header fallback
    token = request.cookies.get("session_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(401, "Not authenticated")

    session = await db.sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(401, "Invalid session")

    exp = session["expires_at"]
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise HTTPException(401, "Session expired")

    user = await _get_user_by_id(session["user_id"])
    if not user:
        raise HTTPException(401, "User not found")
    return user


async def require_admin(
    request: Request, user: dict = Depends(get_current_user)
) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    # Read-only admins can GET anything in the admin surface but cannot mutate.
    if (
        user.get("is_read_only")
        and request.method in ("POST", "PUT", "PATCH", "DELETE")
    ):
        raise HTTPException(
            403, "Read-only admin — ask a full-access admin to make this change"
        )
    return user
