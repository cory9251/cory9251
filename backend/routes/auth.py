"""Auth routes — register / login / logout / me / google OAuth /
change-password / forgot-password / reset-password.

Wiring in server.py:
    from routes.auth import router as auth_router
    api.include_router(auth_router)
"""
import os
import uuid
import secrets
import asyncio
from datetime import datetime, timezone, timedelta

import requests
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from config import db, logger
from auth_deps import (
    hash_password,
    verify_password,
    new_session_token,
    SESSION_DAYS,
    cookie_kwargs,
    _get_user_by_id,
    get_current_user,
)
from notifications import _resolve_email_creds, _send_email_sync
from models import (
    RegisterIn,
    LoginIn,
    GoogleSessionIn,
    ChangePasswordIn,
    ForgotPasswordIn,
    ResetPasswordIn,
)

router = APIRouter()


async def _issue_session(user_id: str, response: Response) -> str:
    token = new_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    await db.sessions.insert_one(
        {
            "session_token": token,
            "user_id": user_id,
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    response.set_cookie(key="session_token", value=token, **cookie_kwargs())
    return token


@router.post("/auth/register")
async def register(payload: RegisterIn, response: Response):
    email = payload.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(400, "Email already registered")

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    # VA signup path — separate doc shape, pending approval by Program Manager.
    if payload.role == "va":
        doc = {
            "user_id": user_id,
            "email": email,
            "password_hash": hash_password(payload.password),
            "name": payload.name,
            "role": "va",
            "va_status": "pending",  # pending | approved | suspended | removed
            "va_phone": (payload.va_phone or "").strip(),
            "va_address": (payload.va_address or "").strip(),
            "must_change_password": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "auth_provider": "local",
        }
        await db.users.insert_one(doc)
        await _issue_session(user_id, response)
        return await _get_user_by_id(user_id)

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    doc = {
        "user_id": user_id,
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": payload.name,
        # Public registration is always worker — admins are seeded server-side only.
        "role": "worker",
        # Iter47: New workers start as `pending`. Admin approval is gated on
        # ID-verified + profile-complete (see _worker_approval_blockers), so
        # auto-approving here would be a lie that breaks the badge UI and
        # the booking gate alike.
        "worker_status": "pending",
        "phone": "",
        "address": "",
        "bio": "",
        "skills": [],
        "zip_code": "",
        "city": "",
        "state": "",
        "date_of_birth": "",
        "has_car": False,
        "has_truck": False,
        "has_cdl": False,
        "experience_level": "",
        "availability": [],
        "emergency_contact_name": "",
        "emergency_contact_phone": "",
        "tshirt_size": "",
        "avatar_path": None,
        "id_image_path": None,
        "id_verified": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "auth_provider": "local",
    }
    await db.users.insert_one(doc)
    await _issue_session(user_id, response)
    user = await _get_user_by_id(user_id)
    # Founder welcome email — fire-and-forget so the signup response stays
    # snappy even if Resend is slow. Errors are logged inside the helper.
    try:
        from notifications import send_worker_welcome_email
        import asyncio as _asyncio
        _asyncio.create_task(send_worker_welcome_email(user))
    except Exception:
        logger.exception("welcome email enqueue failed (non-fatal)")
    return user


@router.post("/auth/login")
async def login(payload: LoginIn, response: Response):
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user:
        raise HTTPException(401, "Invalid email or password")
    # Account exists but was created via Google — they never set a password.
    # Tell the frontend explicitly so it can show a "Continue with Google"
    # affordance instead of generic "wrong password".
    if not user.get("password_hash"):
        provider = user.get("auth_provider") or "google"
        raise HTTPException(
            status_code=409,
            detail={
                "code": "no_password_set",
                "provider": provider,
                "message": (
                    "This account was created with Google sign-in. "
                    "Use 'Continue with Google' to sign in, or reset your password from the link below."
                ),
            },
        )
    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    await _issue_session(user["user_id"], response)
    return await _get_user_by_id(user["user_id"])


@router.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await db.sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


@router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@router.post("/auth/google/session")
async def google_session(payload: GoogleSessionIn, response: Response):
    """Exchange Emergent OAuth session_id for our session_token."""
    try:
        resp = requests.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": payload.session_id},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"Google session exchange failed: {e}")
        raise HTTPException(401, "Invalid OAuth session")

    email = (data.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(400, "No email returned from Google")

    user = await db.users.find_one({"email": email})
    is_new = False
    if not user:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one(
            {
                "user_id": user_id,
                "email": email,
                "name": data.get("name") or email.split("@")[0],
                "role": "worker",
                # Iter47: see register() above — new workers must complete
                # profile + ID verification before admin can approve them.
                "worker_status": "pending",
                "phone": "",
                "address": "",
                "bio": "",
                "skills": [],
                "avatar_path": None,
                "avatar_url_external": data.get("picture"),
                "id_image_path": None,
                "id_verified": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "auth_provider": "google",
                "google_id": data.get("id"),
            }
        )
        is_new = True
    else:
        user_id = user["user_id"]

    await _issue_session(user_id, response)
    fresh = await _get_user_by_id(user_id)
    if is_new and fresh:
        try:
            from notifications import send_worker_welcome_email
            import asyncio as _asyncio
            _asyncio.create_task(send_worker_welcome_email(fresh))
        except Exception:
            logger.exception("welcome email enqueue failed (non-fatal)")
    return fresh


@router.post("/auth/forgot-password")
async def forgot_password(payload: ForgotPasswordIn):
    """Public — issue a reset token and email it. Always returns OK to prevent
    user enumeration."""
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    # Always behave the same regardless of whether user exists.
    if user and user.get("password_hash"):
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        # 60-minute window. Single use.
        await db.password_reset_tokens.insert_one({
            "token": token,
            "user_id": user["user_id"],
            "email": email,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=60)).isoformat(),
            "used": False,
        })
        # Build the reset link
        base = (os.environ.get("PUBLIC_BASE_URL") or "").rstrip("/")
        if not base:
            base = "https://hcobnetwork.com"  # production fallback
        link = f"{base}/reset-password?token={token}"
        # Send email (best-effort)
        try:
            creds = await _resolve_email_creds()
            if creds.get("api_key") and creds.get("sender"):
                html = f"""
                <div style="font-family:system-ui,sans-serif;max-width:560px;margin:0 auto;padding:24px">
                  <div style="background:#030712;color:#fff;padding:18px 22px;font-weight:900;letter-spacing:-0.02em;font-size:22px">HCOB Network</div>
                  <div style="padding:24px 22px;border:1px solid #E5E7EB;border-top:0">
                    <h2 style="margin:0 0 12px 0;font-size:20px">Password reset requested</h2>
                    <p style="color:#4B5563;line-height:1.5">Someone (hopefully you) asked to reset the password for <strong>{email}</strong>.</p>
                    <p style="margin:24px 0">
                      <a href="{link}" style="background:#0044FF;color:#fff;text-decoration:none;padding:14px 22px;font-weight:700">Reset my password</a>
                    </p>
                    <p style="color:#4B5563;font-size:12px">Or paste this link into your browser:</p>
                    <p style="color:#0044FF;font-size:12px;word-break:break-all">{link}</p>
                    <p style="color:#9CA3AF;font-size:12px;margin-top:32px;border-top:1px solid #E5E7EB;padding-top:16px">
                      This link expires in 60 minutes and can only be used once. If you didn't request this, ignore this email.
                    </p>
                  </div>
                </div>
                """
                await asyncio.to_thread(
                    _send_email_sync,
                    creds["api_key"], creds["sender"], email,
                    "Reset your HCOB Network password",
                    html,
                )
                logger.info(f"Sent password reset email to {email}")
            else:
                # Log the link prominently so a server admin can recover the user manually
                logger.warning(
                    f"[PASSWORD RESET] No Resend creds configured — manual reset link for "
                    f"{email}: {link}"
                )
        except Exception as e:
            logger.exception(f"Failed to send password reset email to {email}: {e}")
    return {"ok": True, "message": "If that email is registered, a reset link has been sent."}


@router.post("/auth/reset-password")
async def reset_password_with_token(payload: ResetPasswordIn):
    """Public — consume a single-use reset token."""
    record = await db.password_reset_tokens.find_one({"token": payload.token})
    if not record:
        raise HTTPException(400, "Invalid or expired reset link")
    if record.get("used"):
        raise HTTPException(400, "This reset link has already been used")
    try:
        exp = datetime.fromisoformat(record["expires_at"])
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            raise HTTPException(400, "This reset link has expired")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "Invalid reset link")

    user = await db.users.find_one({"user_id": record["user_id"]})
    if not user:
        raise HTTPException(400, "Account no longer exists")

    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {
            "password_hash": hash_password(payload.new_password),
            "must_change_password": False,
        }},
    )
    # Burn the token + kill all other sessions
    await db.password_reset_tokens.update_one(
        {"token": payload.token},
        {"$set": {"used": True, "used_at": datetime.now(timezone.utc).isoformat()}},
    )
    await db.sessions.delete_many({"user_id": user["user_id"]})
    logger.info(f"Password reset via token for {user.get('email')}")
    return {"ok": True, "email": user.get("email")}


@router.post("/auth/change-password")
async def change_password(
    payload: ChangePasswordIn, user: dict = Depends(get_current_user)
):
    db_user = await db.users.find_one({"user_id": user["user_id"]})
    if not db_user or not db_user.get("password_hash"):
        raise HTTPException(400, "Password change unavailable for this account")
    if not verify_password(payload.current_password, db_user["password_hash"]):
        raise HTTPException(401, "Current password is incorrect")
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"password_hash": hash_password(payload.new_password)}},
    )
    return {"ok": True}
