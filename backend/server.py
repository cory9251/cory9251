"""HCOB Network — Gig Opportunity Management Platform."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import json
import logging
import secrets
import asyncio
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal, Dict

import bcrypt
import jwt
import requests
import resend
from fastapi import (
    FastAPI,
    APIRouter,
    HTTPException,
    Depends,
    Request,
    Response,
    UploadFile,
    File,
    Form,
    Query,
    Header,
    Body,
)
from fastapi.responses import Response as FastAPIResponse, HTMLResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from twilio.rest import Client as TwilioClient
from pywebpush import webpush, WebPushException

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
APP_NAME = os.environ.get("APP_NAME", "gigblast")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.environ.get("TWILIO_FROM_NUMBER", "")
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:admin@hcobcleaners.com")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("gigblast")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

# ----------------------------------------------------------------------------
# Object Storage helper
# ----------------------------------------------------------------------------
_storage_key: Optional[str] = None


def init_storage() -> Optional[str]:
    global _storage_key
    if _storage_key:
        return _storage_key
    if not EMERGENT_LLM_KEY:
        logger.warning("EMERGENT_LLM_KEY missing — storage disabled")
        return None
    try:
        resp = requests.post(
            f"{STORAGE_URL}/init",
            json={"emergent_key": EMERGENT_LLM_KEY},
            timeout=30,
        )
        resp.raise_for_status()
        _storage_key = resp.json()["storage_key"]
        logger.info("Object storage initialized")
        return _storage_key
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
        return None


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    if not key:
        raise HTTPException(500, "Storage not initialized")
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def get_object(path: str):
    key = init_storage()
    if not key:
        raise HTTPException(500, "Storage not initialized")
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


# ----------------------------------------------------------------------------
# Password / Token helpers
# ----------------------------------------------------------------------------
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
    """httpOnly cookie config that works for Emergent preview (cross-site)."""
    return dict(
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=SESSION_DAYS * 86400,
    )


# ----------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------
GigCategory = Literal["cleaning", "labor", "driver"]
PayType = Literal["hourly", "flat"]
GigRecurrence = Literal["none", "daily", "weekly", "biweekly", "monthly"]

# Canonical worker skill tags. Workers select these on their profile; admins
# filter on them. Sub-category strings on gigs use the same values.
WORKER_SKILLS = [
    # Cleaning
    "deep_cleaning",
    "routine_cleaning",
    "moveouts",
    "detailing",
    "window_cleaning",
    "carpet_cleaning",
    "post_construction",
    # Labor
    "hourly_labor",
    "heavy_lifting",
    "forklift",
    "moving",
    "warehouse",
    "landscaping",
    "painting",
    # Driver / transport
    "driving",
    "delivery",
    "cdl",
    # Soft skills HCOB cares about
    "fast_learner",
    "bilingual",
    "team_lead",
]
SKILL_LABELS = {
    "deep_cleaning": "Deep cleaning",
    "routine_cleaning": "Routine cleaning",
    "moveouts": "Move-outs",
    "detailing": "Detailing",
    "window_cleaning": "Window cleaning",
    "carpet_cleaning": "Carpet cleaning",
    "post_construction": "Post-construction",
    "hourly_labor": "Hourly labor",
    "heavy_lifting": "Heavy lifting",
    "forklift": "Forklift",
    "moving": "Moving",
    "warehouse": "Warehouse",
    "landscaping": "Landscaping",
    "painting": "Painting",
    "driving": "Driving",
    "delivery": "Delivery",
    "cdl": "CDL",
    "fast_learner": "Fast learner",
    "bilingual": "Bilingual",
    "team_lead": "Team lead",
}
# Map a gig's category → which skill tags qualify a worker for it
GIG_CATEGORY_TO_SKILLS = {
    "cleaning": ["deep_cleaning", "routine_cleaning", "moveouts", "detailing", "window_cleaning", "carpet_cleaning", "post_construction"],
    "labor": ["hourly_labor", "heavy_lifting", "forklift", "moving", "warehouse", "landscaping", "painting"],
    "driver": ["driving", "delivery", "cdl"],
}

AVAILABILITY_OPTIONS = ["weekdays", "weekends", "mornings", "evenings", "overnight", "full_time"]
EXPERIENCE_OPTIONS = ["none", "0_1_yr", "1_3_yr", "3_plus_yr"]
TSHIRT_SIZES = ["XS", "S", "M", "L", "XL", "XXL", "XXXL"]


# Fields required for a worker profile to be considered "complete" — gates the
# ability to request gigs together with id_verified.
REQUIRED_PROFILE_FIELDS = [
    "phone",
    "zip_code",
    "date_of_birth",
    "skills",        # at least 1
    "availability",  # at least 1
    "emergency_contact_name",
    "emergency_contact_phone",
]


def _profile_missing_fields(user: dict) -> List[str]:
    """Return the list of required-profile fields that are blank/empty for a
    worker. An empty list means the profile is complete."""
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


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str
    role: Optional[Literal["worker", "admin"]] = "worker"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class GoogleSessionIn(BaseModel):
    session_id: str


class ProfileUpdateIn(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    bio: Optional[str] = None
    skills: Optional[List[str]] = None
    # Extended profile fields ----------------------------------------------
    zip_code: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    date_of_birth: Optional[str] = None  # ISO date YYYY-MM-DD
    has_car: Optional[bool] = None
    has_truck: Optional[bool] = None
    has_cdl: Optional[bool] = None
    experience_level: Optional[str] = None
    availability: Optional[List[str]] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    tshirt_size: Optional[str] = None


class GigIn(BaseModel):
    title: str
    description: str
    category: GigCategory
    subcategory: Optional[str] = None
    location: str  # PUBLIC preview — e.g. "Oak Ave · 94110" — visible to all workers
    address_line: Optional[str] = None  # SENSITIVE — revealed only after accept
    scheduled_date: str  # display string (kept for backwards compat / human display)
    scheduled_at: Optional[str] = None  # ISO 8601 datetime — drives the calendar
    pay_rate: float
    pay_type: PayType
    slots: int = 1
    duration_hours: Optional[float] = None
    # Unpaid break minutes deducted from each worker's clocked time. Default
    # is 0 — admin sets it per-gig in the Create/Edit dialog. Per-worker
    # override lives on the acceptance.
    break_minutes: Optional[int] = 0
    # When workers can expect payment. UI shows this as a colored pill on
    # cards and detail pages so workers know if it's same-day cash vs payroll.
    payment_timeline: Optional[Literal["same_day", "2_3_days", "weekly", "custom"]] = "2_3_days"
    payment_timeline_note: Optional[str] = None
    contact_phone: Optional[str] = None
    # Optional link to a parent project. When set, this gig is shown alongside
    # its sibling gigs in the worker UI so the crews can coordinate.
    project_id: Optional[str] = None
    # Recurrence — optional. If recurrence != 'none', the create endpoint generates
    # `repeat_count` gig instances spaced by the chosen period.
    recurrence: Optional[GigRecurrence] = "none"
    repeat_count: Optional[int] = 1  # ignored when recurrence == 'none'
    # New: optional "Coming soon" → "Open" toggle. publish_at is a hint; the
    # background loop auto-flips, but the admin can publish manually anytime.
    status: Optional[Literal["open", "coming_soon"]] = "open"
    publish_at: Optional[str] = None  # ISO 8601 — when to auto-flip to open


class GigPatch(BaseModel):
    """All fields optional — partial update from the Edit dialog."""
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[GigCategory] = None
    subcategory: Optional[str] = None
    location: Optional[str] = None
    address_line: Optional[str] = None
    scheduled_date: Optional[str] = None
    scheduled_at: Optional[str] = None
    pay_rate: Optional[float] = None
    pay_type: Optional[PayType] = None
    slots: Optional[int] = None
    duration_hours: Optional[float] = None
    break_minutes: Optional[int] = None
    payment_timeline: Optional[Literal["same_day", "2_3_days", "weekly", "custom"]] = None
    payment_timeline_note: Optional[str] = None
    contact_phone: Optional[str] = None
    project_id: Optional[str] = None
    clear_project: Optional[bool] = False
    status: Optional[str] = None  # admin can flip status from the Edit dialog
    publish_at: Optional[str] = None


class BlastIn(BaseModel):
    channels: List[Literal["in_app", "email", "sms", "push"]]


class RushToggleIn(BaseModel):
    """Manual RUSH on/off without blasting. Blast endpoint flips this on as a
    side effect; admin can also toggle it independently here."""
    is_rush: bool


# Allowed pin-tag values. Any active tag pins the gig to the top of the
# worker feed and the public landing snippet. Multiple can be active at once.
GIG_TAG_VALUES = ("rush", "priority_need", "same_day", "top_pay")
GigTag = Literal["rush", "priority_need", "same_day", "top_pay"]


class GigTagsIn(BaseModel):
    """Replace the gig's `tags` array entirely. Any tag pins the gig to the
    top of the feed. Pass an empty list to clear all tags."""
    tags: List[GigTag]


class SettingsIn(BaseModel):
    resend_api_key: Optional[str] = None
    sender_email: Optional[str] = None
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_from_number: Optional[str] = None
    google_service_account_json: Optional[str] = None
    google_sheets_share_email: Optional[str] = None


class WorkerPayIn(BaseModel):
    """Set a worker's default pay rate/type. Either field can be cleared with `null`
    by sending an explicit JSON `null`."""
    default_pay_rate: Optional[float] = None
    default_pay_type: Optional[PayType] = None
    clear_rate: Optional[bool] = False
    clear_type: Optional[bool] = False


class AcceptancePayIn(BaseModel):
    """Override pay rate/type for a worker on a specific gig."""
    pay_rate_override: Optional[float] = None
    pay_type_override: Optional[PayType] = None
    clear_rate: Optional[bool] = False
    clear_type: Optional[bool] = False


class TimesheetApproveIn(BaseModel):
    """Optional admin corrections when approving a timesheet."""
    hours_worked: Optional[float] = None
    earnings: Optional[float] = None
    note: Optional[str] = None
    # Per-worker break override (minutes). When set, overrides the gig's default
    # break_minutes for this acceptance. Pass null to leave unchanged.
    break_minutes: Optional[int] = None


class TimesheetEditIn(BaseModel):
    """Admin edits raw clock-in/out times. Either field accepts an ISO datetime
    string. Passing `clear_clock_out=true` reverts the acceptance back to
    on-the-clock state. Editing always recomputes hours+earnings and resets
    timesheet_approved=false."""
    clock_in_at: Optional[str] = None
    clock_out_at: Optional[str] = None
    clear_clock_out: Optional[bool] = False
    # Per-worker break override (minutes). Same semantics as the approve payload.
    break_minutes: Optional[int] = None


# ----- Projects ---------------------------------------------------------------
# A project groups 2+ gigs that share a job site or coordinated outcome (e.g.,
# trash-removal driver + handyman with tools). Workers on linked gigs see each
# other in the project crew so they can coordinate; admins get a combined
# roster + a shared notes thread for ops.

class ProjectDefaults(BaseModel):
    """Pre-fill values when adding a new gig under a project. Each is optional
    so an admin can sync any subset (or none). On gig-create the dialog reads
    these and pre-fills the form; the admin can then opt in/out per gig."""
    location: Optional[str] = None
    address_line: Optional[str] = None
    scheduled_date: Optional[str] = None
    scheduled_at: Optional[str] = None
    payment_timeline: Optional[Literal["same_day", "2_3_days", "weekly", "custom"]] = None
    payment_timeline_note: Optional[str] = None
    contact_phone: Optional[str] = None


class ProjectIn(BaseModel):
    title: str
    description: Optional[str] = ""
    client_name: Optional[str] = None
    defaults: Optional[ProjectDefaults] = None


class ProjectPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    client_name: Optional[str] = None
    defaults: Optional[ProjectDefaults] = None
    archived: Optional[bool] = None


class ProjectNoteIn(BaseModel):
    text: str


class LinkGigToProjectIn(BaseModel):
    project_id: str
    # When true, apply the project's defaults to the gig now. Defaults to
    # false so admin can opt in explicitly.
    sync_defaults: Optional[bool] = False


class AdminRatingIn(BaseModel):
    """Admin sets a 1-5 star rating for a worker on a specific gig. Optional
    private note. Passing `clear=true` removes the rating."""
    stars: Optional[int] = None
    note: Optional[str] = None
    clear: Optional[bool] = False


class ClientRatingLinkIn(BaseModel):
    """Generate (or regenerate) a public client-feedback link for an
    acceptance. Optional `client_email` is stored for reference."""
    client_email: Optional[str] = None
    regenerate: Optional[bool] = False


class ClientRatingSubmitIn(BaseModel):
    """Body of the public client rating submission."""
    stars: int
    note: Optional[str] = None
    client_name: Optional[str] = None


class SettingsTestIn(BaseModel):
    channel: Literal["email", "sms"]
    to: str


class QuoteRequestIn(BaseModel):
    """Public lead capture from /customers — a prospective client requesting a
    quote. SMS notifies HCOB ops. Honeypot field 'website' silently rejected."""
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=7, max_length=40)
    email: Optional[str] = None
    service: str = Field(min_length=2, max_length=120)
    timeline: str = Field(min_length=1, max_length=60)
    message: Optional[str] = Field(default=None, max_length=2000)
    address: Optional[str] = Field(default=None, max_length=240)
    # Honeypot — bots fill in hidden fields. Real users won't.
    website: Optional[str] = None


class QuoteRequestPatch(BaseModel):
    status: Optional[Literal["new", "contacted", "won", "lost", "dismissed"]] = None
    admin_note: Optional[str] = None


class PushKeysIn(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=10, max_length=1024)
    keys: PushKeysIn
    user_agent: Optional[str] = None
    platform: Optional[str] = None  # ios | android | other


class PushTestIn(BaseModel):
    title: Optional[str] = "HCOB Network test"
    body: Optional[str] = "Push is working — you'll get pinged on new gigs."


class AdminResetPasswordIn(BaseModel):
    new_password: Optional[str] = None  # If None/blank, server generates a temp password


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


WorkerStatus = Literal["pending", "approved", "rejected", "suspended"]


class WorkerStatusIn(BaseModel):
    note: Optional[str] = None  # Optional internal note for the action


# ----------------------------------------------------------------------------
# Auth dependency
# ----------------------------------------------------------------------------
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
    return user


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


# ----------------------------------------------------------------------------
# FastAPI app
# ----------------------------------------------------------------------------
app = FastAPI(title="HCOB Network API")
api = APIRouter(prefix="/api")


@api.get("/")
async def root():
    return {"service": "hcob-network", "ok": True}


# ---- Auth ------------------------------------------------------------------
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


@api.post("/auth/register")
async def register(payload: RegisterIn, response: Response):
    email = payload.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(400, "Email already registered")

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    doc = {
        "user_id": user_id,
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": payload.name,
        # Public registration is always worker — admins are seeded server-side only.
        "role": "worker",
        # Workers are auto-approved at registration. Admin still has Suspend/Reject
        # to ban bad actors, but the per-gig request flow is where actual approval
        # happens.
        "worker_status": "approved",
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
    return user


@api.post("/auth/login")
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


@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await db.sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@api.post("/auth/google/session")
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
    if not user:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one(
            {
                "user_id": user_id,
                "email": email,
                "name": data.get("name") or email.split("@")[0],
                "role": "worker",
                "worker_status": "approved",
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
    else:
        user_id = user["user_id"]

    await _issue_session(user_id, response)
    return await _get_user_by_id(user_id)


# ---- Profile / uploads -----------------------------------------------------
@api.get("/profile/options")
async def profile_options(user: dict = Depends(get_current_user)):
    """Static lookup data the profile form needs to render its dropdowns &
    checkboxes. Lives on the backend so the frontend stays in sync with what
    skills the platform supports."""
    return {
        "skills": [{"value": s, "label": SKILL_LABELS[s]} for s in WORKER_SKILLS],
        "availability": AVAILABILITY_OPTIONS,
        "experience_levels": EXPERIENCE_OPTIONS,
        "tshirt_sizes": TSHIRT_SIZES,
        "required_fields": REQUIRED_PROFILE_FIELDS,
    }


@api.put("/profile")
async def update_profile(payload: ProfileUpdateIn, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}

    # Validate enum-ish fields. For multi-select chip fields we silently drop
    # values we don't recognize rather than 400 — keeps saves working even when
    # legacy free-text data is still on the record.
    if "skills" in updates:
        updates["skills"] = [s for s in updates["skills"] if s in WORKER_SKILLS]
    if "availability" in updates:
        updates["availability"] = [a for a in updates["availability"] if a in AVAILABILITY_OPTIONS]
    if "experience_level" in updates and updates["experience_level"] and updates["experience_level"] not in EXPERIENCE_OPTIONS:
        raise HTTPException(400, f"experience_level must be one of {EXPERIENCE_OPTIONS}")
    if "tshirt_size" in updates and updates["tshirt_size"] and updates["tshirt_size"] not in TSHIRT_SIZES:
        raise HTTPException(400, f"tshirt_size must be one of {TSHIRT_SIZES}")
    if "zip_code" in updates and updates["zip_code"]:
        z = updates["zip_code"].strip()
        if not (z.isdigit() and len(z) == 5):
            raise HTTPException(400, "zip_code must be a 5-digit US ZIP code")
        updates["zip_code"] = z

    if updates:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": updates})
    return await _get_user_by_id(user["user_id"])


def _ext_from(filename: str, content_type: str) -> str:
    if "." in (filename or ""):
        return filename.rsplit(".", 1)[-1].lower()
    return {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/gif": "gif",
    }.get(content_type, "bin")


async def _upload_user_image(user_id: str, kind: str, file: UploadFile) -> str:
    ext = _ext_from(file.filename or "", file.content_type or "")
    path = f"{APP_NAME}/users/{user_id}/{kind}/{uuid.uuid4().hex}.{ext}"
    data = await file.read()
    result = await asyncio.to_thread(
        put_object, path, data, file.content_type or "application/octet-stream"
    )
    await db.files.insert_one(
        {
            "file_id": str(uuid.uuid4()),
            "storage_path": result["path"],
            "original_filename": file.filename,
            "content_type": file.content_type,
            "size": result.get("size"),
            "owner_id": user_id,
            "kind": kind,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return result["path"]


@api.post("/profile/avatar")
async def upload_avatar(
    file: UploadFile = File(...), user: dict = Depends(get_current_user)
):
    path = await _upload_user_image(user["user_id"], "avatar", file)
    await db.users.update_one(
        {"user_id": user["user_id"]}, {"$set": {"avatar_path": path}}
    )
    return {"avatar_path": path}


@api.post("/profile/id")
async def upload_id(
    file: UploadFile = File(...), user: dict = Depends(get_current_user)
):
    path = await _upload_user_image(user["user_id"], "id", file)
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"id_image_path": path, "id_verified": False}},
    )
    return {"id_image_path": path}


@api.get("/files/{path:path}")
async def download_file(
    path: str,
    request: Request,
    auth: Optional[str] = Query(None),
):
    # Auth via cookie OR ?auth= query token (for <img src>)
    token = request.cookies.get("session_token") or auth
    if not token:
        raise HTTPException(401, "Not authenticated")
    session = await db.sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(401, "Invalid session")

    record = await db.files.find_one({"storage_path": path}, {"_id": 0})
    if not record:
        raise HTTPException(404, "File not found")

    requester = await _get_user_by_id(session["user_id"])
    if not requester:
        raise HTTPException(401, "User not found")
    # Owners can always view their own files. Admins can view any file.
    if record["owner_id"] != requester["user_id"] and requester.get("role") != "admin":
        raise HTTPException(403, "Forbidden")

    data, content_type = await asyncio.to_thread(get_object, path)
    return FastAPIResponse(
        content=data, media_type=record.get("content_type") or content_type
    )


# ---- Gigs ------------------------------------------------------------------
def _gig_doc(payload: GigIn, created_by: str) -> dict:
    return {
        "gig_id": f"gig_{uuid.uuid4().hex[:12]}",
        "title": payload.title,
        "description": payload.description,
        "category": payload.category,
        "subcategory": payload.subcategory,
        "location": payload.location,
        "address_line": payload.address_line,
        "scheduled_date": payload.scheduled_date,
        "scheduled_at": payload.scheduled_at,
        "pay_rate": payload.pay_rate,
        "pay_type": payload.pay_type,
        "slots": payload.slots,
        "slots_filled": 0,
        "duration_hours": payload.duration_hours,
        "break_minutes": int(payload.break_minutes or 0),
        "payment_timeline": payload.payment_timeline or "2_3_days",
        "payment_timeline_note": payload.payment_timeline_note,
        "contact_phone": payload.contact_phone,
        "project_id": payload.project_id,
        "status": payload.status or "open",
        "publish_at": payload.publish_at,
        "is_rush": False,
        "rush_at": None,
        "tags": [],
        "created_by": created_by,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "blast_count": 0,
        "last_blast_at": None,
        "blast_channels": [],
    }


def _strip_sensitive_for_worker(gig: dict, my_acceptance: Optional[dict]) -> dict:
    """Hide address_line from workers whose request is still 'requested'.

    The full address is only revealed when the admin has approved the request
    (status in 'accepted' / 'on_the_clock' / 'completed'), or to admins.
    """
    revealed_statuses = {"accepted", "on_the_clock", "completed"}
    if my_acceptance and my_acceptance.get("status") in revealed_statuses:
        return gig
    g = dict(gig)
    g.pop("address_line", None)
    return g


@api.post("/gigs")
async def create_gig(payload: GigIn, admin: dict = Depends(require_admin)):
    base = _gig_doc(payload, admin["user_id"])

    rec = payload.recurrence or "none"
    count = max(1, min(52, payload.repeat_count or 1)) if rec != "none" else 1

    if rec == "none" or count == 1:
        await db.gigs.insert_one(base)
        base.pop("_id", None)
        return {**base, "created_count": 1}

    # Need a base ISO datetime to space occurrences. Bail back to single-gig if missing.
    if not payload.scheduled_at:
        await db.gigs.insert_one(base)
        base.pop("_id", None)
        return {**base, "created_count": 1}

    try:
        base_dt = datetime.fromisoformat(payload.scheduled_at.replace("Z", "+00:00"))
    except Exception:
        await db.gigs.insert_one(base)
        base.pop("_id", None)
        return {**base, "created_count": 1}

    series_id = f"ser_{uuid.uuid4().hex[:12]}"
    docs: List[dict] = []
    for i in range(count):
        if rec == "daily":
            occ_dt = base_dt + timedelta(days=i)
        elif rec == "weekly":
            occ_dt = base_dt + timedelta(weeks=i)
        elif rec == "biweekly":
            occ_dt = base_dt + timedelta(weeks=i * 2)
        elif rec == "monthly":
            # Add i months — naive but predictable; falls back to last-day-of-month
            month = base_dt.month - 1 + i
            year = base_dt.year + month // 12
            month = month % 12 + 1
            day = min(
                base_dt.day,
                [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1],
            )
            occ_dt = base_dt.replace(year=year, month=month, day=day)
        else:
            occ_dt = base_dt

        doc = dict(base)
        doc["gig_id"] = f"gig_{uuid.uuid4().hex[:12]}"
        doc["scheduled_at"] = occ_dt.isoformat()
        doc["scheduled_date"] = occ_dt.strftime("%a %b %d · %-I:%M %p")
        doc["series_id"] = series_id
        doc["series_index"] = i
        doc["series_total"] = count
        doc["series_recurrence"] = rec
        docs.append(doc)

    await db.gigs.insert_many(docs)
    first = docs[0]
    first.pop("_id", None)
    return {**first, "created_count": count, "series_id": series_id}


@api.get("/gigs")
async def list_gigs(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    query: dict = {}
    # "all" means: no status filter at all (used by admin calendar / worker accepted list)
    if status and status != "all":
        query["status"] = status
    if category:
        query["category"] = category
    # Workers see open + coming_soon gigs by default (coming_soon is browseable
    # but not yet claimable; the request endpoint enforces the gate).
    if user.get("role") != "admin" and status is None:
        query["status"] = {"$in": ["open", "coming_soon"]}

    # Sort: RUSH first (newest rush_at first), then created_at desc.
    # MongoDB's sort treats missing fields as null which sorts BEFORE values
    # asc / AFTER values desc, so this puts rush_at-present gigs at the top.
    gigs = (
        await db.gigs.find(query, {"_id": 0})
        .sort([("is_rush", -1), ("rush_at", -1), ("created_at", -1)])
        .to_list(500)
    )

    # For workers, attach acceptance state + hide sensitive address until accepted
    if user.get("role") == "worker":
        accepted = await db.gig_acceptances.find(
            {"worker_id": user["user_id"]}, {"_id": 0}
        ).to_list(1000)
        accepted_map = {a["gig_id"]: a for a in accepted}

        # Pre-fetch project titles for any project-linked gigs in this feed so
        # the worker UI can show a 'PROJECT' badge on the card. We intentionally
        # only expose `project_id` + `title` here (no client_name) — full
        # project context is only revealed after acceptance.
        wpids = list({g.get("project_id") for g in gigs if g.get("project_id")})
        wpmap = {}
        if wpids:
            wprojs = await db.projects.find(
                {"project_id": {"$in": wpids}, "archived": {"$ne": True}},
                {"_id": 0, "project_id": 1, "title": 1},
            ).to_list(500)
            wpmap = {p["project_id"]: p for p in wprojs}

        out = []
        for g in gigs:
            a = accepted_map.get(g["gig_id"])
            g = _strip_sensitive_for_worker(g, a)
            g["my_acceptance"] = a
            pid = g.get("project_id")
            if pid and pid in wpmap:
                g["project"] = {
                    "project_id": pid,
                    "title": wpmap[pid].get("title"),
                }
            out.append(g)
        return out

    # For admins, enrich gigs that belong to a project with the project's title
    # so list views (Calendar, AdminGigs, Dashboard) can show a project pill
    # without N+1 fetches.
    pids = list({g.get("project_id") for g in gigs if g.get("project_id")})
    if pids:
        projs = await db.projects.find(
            {"project_id": {"$in": pids}},
            {"_id": 0, "project_id": 1, "title": 1, "client_name": 1},
        ).to_list(500)
        pmap = {p["project_id"]: p for p in projs}
        for g in gigs:
            pid = g.get("project_id")
            if pid and pid in pmap:
                g["project"] = {
                    "project_id": pid,
                    "title": pmap[pid].get("title"),
                    "client_name": pmap[pid].get("client_name"),
                }
    return gigs


@api.get("/gigs/{gig_id}")
async def get_gig(gig_id: str, user: dict = Depends(get_current_user)):
    gig = await db.gigs.find_one({"gig_id": gig_id}, {"_id": 0})
    if not gig:
        raise HTTPException(404, "Gig not found")
    if user.get("role") == "admin":
        # Attach BOTH pending requests and approved acceptances
        all_rows = await db.gig_acceptances.find(
            {"gig_id": gig_id}, {"_id": 0}
        ).to_list(500)
        if all_rows:
            worker_ids = list({a["worker_id"] for a in all_rows})
            workers = await db.users.find(
                {"user_id": {"$in": worker_ids}}, {"_id": 0, "password_hash": 0}
            ).to_list(500)
            wmap = {w["user_id"]: w for w in workers}
            for a in all_rows:
                w = wmap.get(a["worker_id"]) or {}
                a["worker_name"] = w.get("name")
                a["worker_email"] = w.get("email")
                a["worker_phone"] = w.get("phone")
                a["worker_id_verified"] = w.get("id_verified", False)
                a["worker_status"] = w.get("worker_status", "approved")
                a["worker_default_pay_rate"] = w.get("default_pay_rate")
                a["worker_default_pay_type"] = w.get("default_pay_type")
                # Resolved effective pay for this worker on this gig
                pay = _resolve_pay(a, w, gig)
                a["pay_rate_effective"] = pay["pay_rate"]
                a["pay_type_effective"] = pay["pay_type"]
                a["pay_rate_source"] = a.get("pay_rate_source") or pay["pay_rate_source"]
                a["pay_type_source"] = a.get("pay_type_source") or pay["pay_type_source"]
                # If not yet clocked out, project what they'd earn
                if a.get("earnings") is None and a.get("hours_worked") is not None:
                    br = _resolve_break_minutes(a, gig)
                    a["break_minutes_effective"] = br
                    a["paid_hours"] = _compute_paid_hours(a.get("hours_worked"), br)
                    a["projected_earnings"] = _compute_earnings(
                        pay["pay_rate"], pay["pay_type"], a.get("hours_worked"), br
                    )
                else:
                    # Surface the effective break + paid_hours for the admin UI
                    br = _resolve_break_minutes(a, gig)
                    a["break_minutes_effective"] = br
                    a["paid_hours"] = _compute_paid_hours(a.get("hours_worked"), br)
        gig["pending_requests"] = [a for a in all_rows if a.get("status") == "requested"]
        gig["acceptances"] = [a for a in all_rows if a.get("status") != "requested"]

        # Project context for admins — surface the project title so the gig
        # detail page can show a "Part of project: …" banner with a deep link.
        if gig.get("project_id"):
            proj = await db.projects.find_one(
                {"project_id": gig["project_id"]},
                {"_id": 0, "project_id": 1, "title": 1, "client_name": 1, "archived": 1},
            )
            if proj:
                # Sibling gigs (any other gig linked to the same project)
                sib = await db.gigs.find(
                    {"project_id": gig["project_id"], "gig_id": {"$ne": gig_id}},
                    {"_id": 0, "gig_id": 1, "title": 1, "category": 1, "subcategory": 1, "scheduled_date": 1, "scheduled_at": 1, "slots": 1, "slots_filled": 1, "status": 1},
                ).sort("scheduled_at", 1).to_list(50)
                gig["project"] = {
                    "project_id": proj["project_id"],
                    "title": proj.get("title"),
                    "client_name": proj.get("client_name"),
                    "archived": bool(proj.get("archived")),
                    "sibling_gigs": sib,
                }
    else:
        my = await db.gig_acceptances.find_one(
            {"gig_id": gig_id, "worker_id": user["user_id"]}, {"_id": 0}
        )
        gig = _strip_sensitive_for_worker(gig, my)
        gig["my_acceptance"] = my

        # Minimal project hint shown to ALL workers (even before requesting) so
        # they know this gig is part of a coordinated project. Full sibling/
        # crew details are only revealed once approved (below).
        if gig.get("project_id"):
            proj_lite = await db.projects.find_one(
                {"project_id": gig["project_id"], "archived": {"$ne": True}},
                {"_id": 0, "project_id": 1, "title": 1},
            )
            if proj_lite:
                gig["project_lite"] = {
                    "project_id": proj_lite["project_id"],
                    "title": proj_lite.get("title"),
                }
        # If this worker is APPROVED (not just "requested"), let them see their
        # crew — other approved workers, first name + role only.
        if my and my.get("status") and my["status"] != "requested":
            crew_accs = await db.gig_acceptances.find(
                {
                    "gig_id": gig_id,
                    "status": {"$ne": "requested"},
                    "worker_id": {"$ne": user["user_id"]},
                },
                {"_id": 0, "worker_id": 1, "gig_role": 1},
            ).to_list(200)
            crew_ids = [a["worker_id"] for a in crew_accs]
            if crew_ids:
                crew_users = await db.users.find(
                    {"user_id": {"$in": crew_ids}},
                    {"_id": 0, "user_id": 1, "name": 1},
                ).to_list(200)
                wmap = {w["user_id"]: w for w in crew_users}
                gig["crew"] = [
                    {
                        "first_name": ((wmap.get(a["worker_id"]) or {}).get("name") or "Worker").split(" ")[0],
                        "gig_role": a.get("gig_role") or "worker",
                    }
                    for a in crew_accs
                ]
            else:
                gig["crew"] = []

        # Project context — show sibling gigs + their crews so coordinated
        # workers can see who else is on the same job site. Only exposed to
        # workers with an approved (non-requested) acceptance on THIS gig.
        if my and my.get("status") and my["status"] != "requested" and gig.get("project_id"):
            proj = await db.projects.find_one(
                {"project_id": gig["project_id"]},
                {"_id": 0, "project_id": 1, "title": 1, "client_name": 1},
            )
            if proj:
                sib_gigs = await db.gigs.find(
                    {"project_id": gig["project_id"], "gig_id": {"$ne": gig_id}},
                    {"_id": 0, "gig_id": 1, "title": 1, "category": 1, "subcategory": 1, "scheduled_date": 1, "scheduled_at": 1},
                ).sort("scheduled_at", 1).to_list(50)
                sib_ids = [g["gig_id"] for g in sib_gigs]
                sib_accs = await db.gig_acceptances.find(
                    {
                        "gig_id": {"$in": sib_ids},
                        "status": {"$in": ["accepted", "on_the_clock", "clocked_in", "completed"]},
                    },
                    {"_id": 0, "gig_id": 1, "worker_id": 1, "gig_role": 1},
                ).to_list(500)
                sib_worker_ids = [a["worker_id"] for a in sib_accs]
                sib_users = await db.users.find(
                    {"user_id": {"$in": sib_worker_ids}},
                    {"_id": 0, "user_id": 1, "name": 1},
                ).to_list(500) if sib_worker_ids else []
                wmap = {w["user_id"]: w for w in sib_users}
                gtitle = {g["gig_id"]: g.get("title") for g in sib_gigs}
                project_crew = [
                    {
                        "first_name": ((wmap.get(a["worker_id"]) or {}).get("name") or "Worker").split(" ")[0],
                        "gig_role": a.get("gig_role") or "worker",
                        "gig_id": a["gig_id"],
                        "gig_title": gtitle.get(a["gig_id"]),
                    }
                    for a in sib_accs
                ]
                gig["project"] = {
                    "project_id": proj["project_id"],
                    "title": proj.get("title"),
                    "client_name": proj.get("client_name"),
                    "sibling_gigs": sib_gigs,
                    "crew": project_crew,
                }
    return gig


@api.delete("/gigs/{gig_id}")
async def delete_gig(gig_id: str, admin: dict = Depends(require_admin)):
    result = await db.gigs.delete_one({"gig_id": gig_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Gig not found")
    await db.gig_acceptances.delete_many({"gig_id": gig_id})
    return {"ok": True}


@api.put("/gigs/{gig_id}")
async def update_gig(
    gig_id: str, payload: GigPatch, admin: dict = Depends(require_admin)
):
    """Partial update of a gig. Validates slots vs slots_filled and recomputes status."""
    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")

    updates = payload.model_dump(exclude_unset=True)
    # Handle `clear_project` sentinel separately — it isn't a real DB field.
    clear_project = updates.pop("clear_project", False)
    if clear_project:
        updates["project_id"] = None
    if "slots" in updates:
        new_slots = int(updates["slots"])
        filled = int(gig.get("slots_filled") or 0)
        if new_slots < filled:
            raise HTTPException(
                400,
                f"Cannot reduce slots below current acceptances ({filled} workers already accepted)",
            )
        # Re-evaluate status when slot count changes
        if filled >= new_slots:
            updates["status"] = "filled"
        elif gig.get("status") == "filled" and filled < new_slots:
            updates["status"] = "open"

    if not updates:
        return {**gig, "_id": None} if False else {k: v for k, v in gig.items() if k != "_id"}

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    updates["updated_by"] = admin["email"]
    await db.gigs.update_one({"gig_id": gig_id}, {"$set": updates})
    fresh = await db.gigs.find_one({"gig_id": gig_id}, {"_id": 0})
    return fresh


@api.post("/gigs/{gig_id}/duplicate")
async def duplicate_gig(gig_id: str, admin: dict = Depends(require_admin)):
    """Clone an existing gig into a fresh, empty 'open' gig."""
    src = await db.gigs.find_one({"gig_id": gig_id})
    if not src:
        raise HTTPException(404, "Gig not found")
    title = src.get("title") or "Gig"
    suffix = " (copy)" if not title.endswith(" (copy)") else ""
    doc = {
        "gig_id": f"gig_{uuid.uuid4().hex[:12]}",
        "title": f"{title}{suffix}",
        "description": src.get("description") or "",
        "category": src.get("category"),
        "subcategory": src.get("subcategory"),
        "location": src.get("location"),
        "address_line": src.get("address_line"),
        "scheduled_date": src.get("scheduled_date"),
        "scheduled_at": src.get("scheduled_at"),
        "pay_rate": src.get("pay_rate"),
        "pay_type": src.get("pay_type"),
        "slots": src.get("slots") or 1,
        "slots_filled": 0,
        "duration_hours": src.get("duration_hours"),
        "break_minutes": int(src.get("break_minutes") or 0),
        "payment_timeline": src.get("payment_timeline") or "2_3_days",
        "payment_timeline_note": src.get("payment_timeline_note"),
        "contact_phone": src.get("contact_phone"),
        "project_id": src.get("project_id"),
        "status": "open",
        "publish_at": None,
        "is_rush": False,
        "rush_at": None,
        "tags": [],
        "created_by": admin["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "blast_count": 0,
        "last_blast_at": None,
        "blast_channels": [],
        "duplicated_from": gig_id,
    }
    await db.gigs.insert_one(doc)
    doc.pop("_id", None)
    return doc


def _effective_status(user: dict) -> str:
    """Existing users without the field default to 'approved' for back-compat."""
    if user.get("role") == "admin":
        return "approved"
    return user.get("worker_status") or "approved"


def _resolve_pay(
    acceptance: Optional[dict], worker: Optional[dict], gig: Optional[dict]
) -> dict:
    """Resolve the effective pay rate + type for a worker on a gig.

    Precedence: per-gig override > worker default > gig posted rate.
    Rate and type are resolved independently (e.g. worker default rate can apply
    while gig's pay_type drives whether it's hourly vs flat).
    """
    rate = None
    rate_source = None
    if acceptance and acceptance.get("pay_rate_override") is not None:
        rate = float(acceptance["pay_rate_override"])
        rate_source = "gig_override"
    elif worker and worker.get("default_pay_rate") is not None:
        rate = float(worker["default_pay_rate"])
        rate_source = "worker_default"
    elif gig and gig.get("pay_rate") is not None:
        rate = float(gig["pay_rate"])
        rate_source = "gig_posted"

    ptype = None
    ptype_source = None
    if acceptance and acceptance.get("pay_type_override"):
        ptype = acceptance["pay_type_override"]
        ptype_source = "gig_override"
    elif worker and worker.get("default_pay_type"):
        ptype = worker["default_pay_type"]
        ptype_source = "worker_default"
    elif gig and gig.get("pay_type"):
        ptype = gig["pay_type"]
        ptype_source = "gig_posted"

    return {
        "pay_rate": rate,
        "pay_type": ptype,
        "pay_rate_source": rate_source,
        "pay_type_source": ptype_source,
    }


def _resolve_break_minutes(acceptance: Optional[dict], gig: Optional[dict]) -> int:
    """Per-worker break override on the acceptance wins; otherwise fall back to
    the gig's default break_minutes; otherwise 0. Never negative."""
    if acceptance is not None and acceptance.get("break_minutes") is not None:
        return max(0, int(acceptance["break_minutes"]))
    if gig is not None and gig.get("break_minutes") is not None:
        return max(0, int(gig["break_minutes"]))
    return 0


def _compute_paid_hours(hours_worked: Optional[float], break_minutes: int) -> Optional[float]:
    """Subtract unpaid break minutes from clocked hours. Never negative."""
    if hours_worked is None:
        return None
    paid = round(float(hours_worked) - (float(break_minutes) / 60.0), 2)
    return max(0.0, paid)


def _compute_earnings(pay_rate: Optional[float], pay_type: Optional[str], hours: Optional[float], break_minutes: int = 0) -> Optional[float]:
    """Compute earnings, deducting unpaid break minutes from hourly pay only.
    Flat-rate gigs always pay the posted amount regardless of break."""
    if pay_rate is None or pay_type is None:
        return None
    if pay_type == "hourly":
        paid_hours = _compute_paid_hours(hours, break_minutes) or 0.0
        return round(float(pay_rate) * float(paid_hours), 2)
    # flat / fixed rate — full posted amount regardless of hours / break
    return round(float(pay_rate), 2)


@api.post("/gigs/{gig_id}/accept")
async def accept_gig(gig_id: str, user: dict = Depends(get_current_user)):
    """Worker REQUESTS a gig. Admin must approve before slot is reserved."""
    if user.get("role") != "worker":
        raise HTTPException(403, "Only workers can request gigs")

    # Ban gate — admins can reject or suspend a bad actor to stop them entirely.
    status_ = _effective_status(user)
    if status_ == "rejected":
        raise HTTPException(
            403, "Your account is not authorized to request gigs. Contact HCOB if you believe this is a mistake."
        )
    if status_ == "suspended":
        raise HTTPException(
            403, "Your account has been suspended. Contact HCOB to reinstate."
        )

    # ID gate — workers must have an ID on file and HCOB-verified before requesting.
    if not user.get("id_image_path"):
        raise HTTPException(
            403, "Upload a photo of your ID on your profile before requesting gigs"
        )
    if not user.get("id_verified"):
        raise HTTPException(
            403, "Your ID is awaiting verification by HCOB before you can request gigs"
        )

    # Profile gate — make sure the worker has filled out the required profile
    # fields so admins have enough context to approve them.
    missing = _profile_missing_fields(user)
    if missing:
        raise HTTPException(
            403,
            "Complete your profile before requesting gigs. Missing: "
            + ", ".join(missing),
        )

    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")
    if gig.get("status") == "coming_soon":
        publish_at = gig.get("publish_at")
        when = f" — opens {publish_at[:16].replace('T', ' ')}" if publish_at else ""
        raise HTTPException(
            400, f"This gig isn't claimable yet{when}. Check back soon."
        )
    if gig.get("status") != "open":
        raise HTTPException(400, "Gig is not open")

    existing = await db.gig_acceptances.find_one(
        {"gig_id": gig_id, "worker_id": user["user_id"]}
    )
    if existing:
        raise HTTPException(400, "You've already requested or been approved for this gig")

    acceptance = {
        "acceptance_id": f"acc_{uuid.uuid4().hex[:12]}",
        "gig_id": gig_id,
        "worker_id": user["user_id"],
        # NEW model: worker requests, admin approves. Slot is NOT reserved on request.
        "status": "requested",
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "accepted_at": None,
    }
    await db.gig_acceptances.insert_one(acceptance)
    acceptance.pop("_id", None)
    return acceptance


@api.post("/gigs/{gig_id}/requests/{acceptance_id}/approve")
async def approve_request(
    gig_id: str,
    acceptance_id: str,
    admin: dict = Depends(require_admin),
):
    """Admin approves a worker's gig request — reserves the slot."""
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Request not found")
    if acceptance.get("status") != "requested":
        raise HTTPException(400, "Request is not pending approval")

    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")
    filled = int(gig.get("slots_filled") or 0)
    if filled >= int(gig.get("slots", 1)):
        raise HTTPException(400, "All slots are already filled")

    now = datetime.now(timezone.utc).isoformat()
    await db.gig_acceptances.update_one(
        {"acceptance_id": acceptance_id},
        {
            "$set": {
                "status": "accepted",
                "accepted_at": now,
                "approved_by": admin["email"],
            }
        },
    )
    new_filled = filled + 1
    gig_update = {"slots_filled": new_filled}
    if new_filled >= int(gig.get("slots", 1)):
        gig_update["status"] = "filled"
    await db.gigs.update_one({"gig_id": gig_id}, {"$set": gig_update})

    # Notify the worker that their request was approved
    await db.notifications.insert_one(
        {
            "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
            "user_id": acceptance["worker_id"],
            "gig_id": gig_id,
            "title": f"Approved for: {gig.get('title')}",
            "body": "Your gig request was approved. You can now see the full address and clock in.",
            "read": False,
            "created_at": now,
        }
    )
    logger.info(f"Admin {admin['email']} approved request {acceptance_id} on gig {gig_id}")
    return {"ok": True, "slots_filled": new_filled, "gig_status": gig_update.get("status", gig["status"])}


@api.post("/gigs/{gig_id}/requests/{acceptance_id}/reject")
async def reject_request(
    gig_id: str,
    acceptance_id: str,
    admin: dict = Depends(require_admin),
):
    """Admin rejects a worker's gig request — removes it; slot was never reserved."""
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Request not found")
    if acceptance.get("status") != "requested":
        raise HTTPException(400, "Only pending requests can be rejected")

    gig = await db.gigs.find_one({"gig_id": gig_id}, {"_id": 0, "title": 1})
    await db.gig_acceptances.delete_one({"acceptance_id": acceptance_id})
    await db.notifications.insert_one(
        {
            "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
            "user_id": acceptance["worker_id"],
            "gig_id": gig_id,
            "title": f"Not selected: {gig.get('title') if gig else 'gig'}",
            "body": "Your gig request was not approved this time.",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    logger.info(f"Admin {admin['email']} rejected request {acceptance_id} on gig {gig_id}")
    return {"ok": True}


class AssignWorkerIn(BaseModel):
    worker_id: str


@api.post("/gigs/{gig_id}/assign")
async def assign_worker(
    gig_id: str,
    payload: AssignWorkerIn,
    admin: dict = Depends(require_admin),
):
    """Admin directly places a worker on a gig (skips the request step)."""
    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")
    filled = int(gig.get("slots_filled") or 0)
    if filled >= int(gig.get("slots", 1)):
        raise HTTPException(400, "All slots are already filled")

    worker = await db.users.find_one({"user_id": payload.worker_id})
    if not worker or worker.get("role") != "worker":
        raise HTTPException(404, "Worker not found")
    w_status = _effective_status(worker)
    if w_status in ("rejected", "suspended"):
        raise HTTPException(400, f"Worker is {w_status} and cannot be assigned")

    existing = await db.gig_acceptances.find_one(
        {"gig_id": gig_id, "worker_id": payload.worker_id}
    )
    if existing:
        if existing.get("status") == "requested":
            # Convert their pending request into an admin-assigned acceptance
            now = datetime.now(timezone.utc).isoformat()
            await db.gig_acceptances.update_one(
                {"acceptance_id": existing["acceptance_id"]},
                {"$set": {"status": "accepted", "accepted_at": now, "approved_by": admin["email"]}},
            )
            acceptance_id = existing["acceptance_id"]
        else:
            raise HTTPException(400, "Worker is already on this gig")
    else:
        acceptance_id = f"acc_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        await db.gig_acceptances.insert_one(
            {
                "acceptance_id": acceptance_id,
                "gig_id": gig_id,
                "worker_id": payload.worker_id,
                "status": "accepted",
                "requested_at": now,
                "accepted_at": now,
                "approved_by": admin["email"],
                "assigned_by_admin": True,
            }
        )

    new_filled = filled + 1
    gig_update = {"slots_filled": new_filled}
    if new_filled >= int(gig.get("slots", 1)):
        gig_update["status"] = "filled"
    await db.gigs.update_one({"gig_id": gig_id}, {"$set": gig_update})

    await db.notifications.insert_one(
        {
            "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
            "user_id": payload.worker_id,
            "gig_id": gig_id,
            "title": f"You were added to: {gig.get('title')}",
            "body": "HCOB added you to this gig. Open the app to see the full address and clock in when you arrive.",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    logger.info(f"Admin {admin['email']} assigned worker {payload.worker_id} to gig {gig_id}")
    return {"ok": True, "acceptance_id": acceptance_id, "slots_filled": new_filled}


@api.delete("/gigs/{gig_id}/acceptances/{acceptance_id}")
async def remove_worker_from_gig(
    gig_id: str,
    acceptance_id: str,
    admin: dict = Depends(require_admin),
):
    """Admin removes a worker from a gig. Releases the slot if it was reserved."""
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Acceptance not found")

    was_reserved = acceptance.get("status") in (
        "accepted",
        "on_the_clock",
        "completed",
    )
    await db.gig_acceptances.delete_one({"acceptance_id": acceptance_id})

    gig = await db.gigs.find_one({"gig_id": gig_id})
    if gig and was_reserved:
        new_filled = max(0, int(gig.get("slots_filled") or 0) - 1)
        gig_update = {"slots_filled": new_filled}
        if gig.get("status") == "filled" and new_filled < int(gig.get("slots", 1)):
            gig_update["status"] = "open"
        await db.gigs.update_one({"gig_id": gig_id}, {"$set": gig_update})

    await db.notifications.insert_one(
        {
            "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
            "user_id": acceptance["worker_id"],
            "gig_id": gig_id,
            "title": f"Removed from: {gig.get('title') if gig else 'gig'}",
            "body": "HCOB removed you from this gig. Reach out if you have questions.",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    logger.info(f"Admin {admin['email']} removed worker {acceptance['worker_id']} from gig {gig_id}")
    return {"ok": True}


@api.post("/gigs/{gig_id}/withdraw")
async def withdraw_gig(gig_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "worker":
        raise HTTPException(403, "Only workers can withdraw")
    existing = await db.gig_acceptances.find_one(
        {"gig_id": gig_id, "worker_id": user["user_id"]}
    )
    if not existing:
        raise HTTPException(404, "Not requested")
    was_approved = existing.get("status") in ("accepted", "on_the_clock", "completed")
    await db.gig_acceptances.delete_one(
        {"gig_id": gig_id, "worker_id": user["user_id"]}
    )
    if was_approved:
        gig = await db.gigs.find_one({"gig_id": gig_id})
        if gig:
            new_filled = max(0, (gig.get("slots_filled") or 0) - 1)
            await db.gigs.update_one(
                {"gig_id": gig_id},
                {"$set": {"slots_filled": new_filled, "status": "open"}},
            )
    return {"ok": True}


# ---- Web Push (PWA notifications) -----------------------------------------
# Workers register a browser PushSubscription once after granting permission.
# The subscription is identified by its unique `endpoint` URL — workers can
# have multiple subscriptions (one per device). Sending is best-effort and
# expired subscriptions (HTTP 410) are auto-pruned.
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


class PushSubscriptionGone(Exception):
    def __init__(self, endpoint: str):
        self.endpoint = endpoint


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
                    {"$set": {"active": False, "pruned_at": datetime.now(timezone.utc).isoformat()}},
                )
    return sent


@api.get("/push/public-key")
async def push_public_key():
    """Frontend reads this to call PushManager.subscribe()."""
    if not VAPID_PUBLIC_KEY:
        raise HTTPException(503, "Push notifications are not configured on this server")
    return {"public_key": VAPID_PUBLIC_KEY}


@api.post("/push/subscribe")
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


@api.delete("/push/subscribe")
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


@api.get("/push/status")
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


@api.post("/push/test")
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



def _resolve_public_base(request: Request | None = None) -> str:
    """Return the canonical public origin so blast emails/SMS can include deep
    links. Order of precedence: proxy-forwarded headers → PUBLIC_BASE_URL env
    → safe production fallback."""
    if request is not None:
        fwd_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        fwd_proto = request.headers.get("x-forwarded-proto") or "https"
        if fwd_host and "localhost" not in fwd_host and "0.0.0.0" not in fwd_host:
            return f"{fwd_proto}://{fwd_host}".rstrip("/")
    env_base = (os.environ.get("PUBLIC_BASE_URL") or "").strip()
    if env_base:
        return env_base.rstrip("/")
    return "https://hcobnetwork.com"


def _format_gig_email(gig: dict, base_url: str = "") -> str:
    pay = (
        f"${gig['pay_rate']:.2f}/hr"
        if gig["pay_type"] == "hourly"
        else f"${gig['pay_rate']:.2f} flat"
    )
    base = (base_url or _resolve_public_base()).rstrip("/")
    cta_url = f"{base}/gigs/{gig['gig_id']}"
    cta_block = f"""
            <table cellpadding="0" cellspacing="0" style="margin:24px 0 8px;">
              <tr><td bgcolor="#0044FF" style="border-radius:0;">
                <a href="{cta_url}" target="_blank" style="display:inline-block;padding:14px 28px;background:#0044FF;color:#FFFFFF;font-size:15px;font-weight:bold;letter-spacing:.04em;text-decoration:none;text-transform:uppercase;">
                  View & accept this gig →
                </a>
              </td></tr>
            </table>
            <p style="margin:4px 0 0;font-size:12px;color:#6B7280;">
              Or open this link in your phone:<br/>
              <a href="{cta_url}" style="color:#0044FF;word-break:break-all;">{cta_url}</a>
            </p>"""
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="font-family:Arial,Helvetica,sans-serif;background:#F9FAFB;padding:24px;">
      <tr><td>
        <table width="600" cellpadding="0" cellspacing="0" align="center" style="background:#FFFFFF;border:1px solid #E5E7EB;">
          <tr><td style="padding:24px;border-bottom:4px solid #0044FF;">
            <div style="font-size:11px;letter-spacing:.2em;color:#4B5563;text-transform:uppercase;">New Gig Opportunity</div>
            <h1 style="margin:8px 0 0;font-size:28px;color:#030712;">{gig['title']}</h1>
          </td></tr>
          <tr><td style="padding:24px;color:#030712;font-size:15px;line-height:1.6;">
            <p>{gig['description']}</p>
            <table cellpadding="6" style="margin-top:16px;font-size:14px;">
              <tr><td style="color:#4B5563;">Category</td><td><strong>{gig['category'].title()}</strong></td></tr>
              <tr><td style="color:#4B5563;">Location</td><td><strong>{gig['location']}</strong></td></tr>
              <tr><td style="color:#4B5563;">When</td><td><strong>{gig['scheduled_date']}</strong></td></tr>
              <tr><td style="color:#4B5563;">Pay</td><td><strong>{pay}</strong></td></tr>
              <tr><td style="color:#4B5563;">Slots</td><td><strong>{gig['slots']}</strong></td></tr>
            </table>
            {cta_block}
            <p style="margin-top:24px;color:#4B5563;font-size:13px;">Be quick — gigs fill on a first-claimed basis.</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
    """


def _format_gig_sms(gig: dict, base_url: str = "") -> str:
    pay = (
        f"${gig['pay_rate']:.0f}/hr"
        if gig["pay_type"] == "hourly"
        else f"${gig['pay_rate']:.0f}"
    )
    base = (base_url or _resolve_public_base()).rstrip("/")
    link = f"{base}/gigs/{gig['gig_id']}"
    return (
        f"[HCOB Network] {gig['title']} — {gig['location']} — "
        f"{gig['scheduled_date']} — {pay}. Tap to claim: {link}"
    )


async def _get_settings_doc() -> dict:
    """Return the singleton app_settings document (creating an empty one if missing)."""
    doc = await db.app_settings.find_one({"_id": "global"})
    return doc or {}


async def _resolve_email_creds() -> dict:
    s = await _get_settings_doc()
    return {
        "api_key": (s.get("resend_api_key") or RESEND_API_KEY or "").strip(),
        "sender": (s.get("sender_email") or SENDER_EMAIL or "").strip(),
    }


async def _resolve_sms_creds() -> dict:
    s = await _get_settings_doc()
    return {
        "sid": (s.get("twilio_account_sid") or TWILIO_SID or "").strip(),
        "token": (s.get("twilio_auth_token") or TWILIO_TOKEN or "").strip(),
        "from_": (s.get("twilio_from_number") or TWILIO_FROM or "").strip(),
    }


def _send_email_sync(api_key: str, sender: str, to: str, subject: str, html: str) -> dict:
    if not api_key:
        return {"skipped": "no_resend_key"}
    resend.api_key = api_key
    return resend.Emails.send(
        {"from": sender, "to": [to], "subject": subject, "html": html}
    )


def _send_sms_sync(sid: str, token: str, from_: str, to: str, body: str) -> dict:
    if not (sid and token and from_):
        return {"skipped": "no_twilio_creds"}
    c = TwilioClient(sid, token)
    m = c.messages.create(body=body, from_=from_, to=to)
    return {"sid": m.sid}


@api.post("/gigs/{gig_id}/blast")
async def blast_gig(
    gig_id: str,
    payload: BlastIn,
    request: Request,
    admin: dict = Depends(require_admin),
):
    gig = await db.gigs.find_one({"gig_id": gig_id}, {"_id": 0})
    if not gig:
        raise HTTPException(404, "Gig not found")

    workers = await db.users.find(
        {"role": "worker"}, {"_id": 0, "password_hash": 0}
    ).to_list(1000)

    email_creds = await _resolve_email_creds() if "email" in payload.channels else None
    sms_creds = await _resolve_sms_creds() if "sms" in payload.channels else None

    counts = {"in_app": 0, "email": 0, "sms": 0, "push": 0, "email_failed": 0, "sms_failed": 0}
    subject = f"New Gig: {gig['title']}"
    base_url = _resolve_public_base(request)
    html = _format_gig_email(gig, base_url)
    sms_body = _format_gig_sms(gig, base_url)
    push_payload = {
        "title": gig["title"],
        "body": (
            f"${gig['pay_rate']:.0f}"
            + ("/hr" if gig.get("pay_type") == "hourly" else "")
            + f" · {gig.get('location') or 'Baltimore, MD'} · {gig.get('scheduled_date') or 'Flexible'}"
        ),
        "tag": f"gig-{gig_id}",
        "url": f"/gigs/{gig_id}",
        "kind": "gig",
        "rush": True,
    }

    notif_docs = []
    for w in workers:
        if "in_app" in payload.channels:
            notif_docs.append(
                {
                    "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
                    "user_id": w["user_id"],
                    "gig_id": gig_id,
                    "title": subject,
                    "body": gig["description"][:140],
                    "read": False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            counts["in_app"] += 1
        if "email" in payload.channels and w.get("email") and email_creds:
            try:
                await asyncio.to_thread(
                    _send_email_sync,
                    email_creds["api_key"],
                    email_creds["sender"],
                    w["email"],
                    subject,
                    html,
                )
                counts["email"] += 1
            except Exception as e:
                logger.error(f"Email send failed for {w['email']}: {e}")
                counts["email_failed"] += 1
        if "sms" in payload.channels and w.get("phone") and sms_creds:
            try:
                await asyncio.to_thread(
                    _send_sms_sync,
                    sms_creds["sid"],
                    sms_creds["token"],
                    sms_creds["from_"],
                    w["phone"],
                    sms_body,
                )
                counts["sms"] += 1
            except Exception as e:
                logger.error(f"SMS send failed for {w.get('phone')}: {e}")
                counts["sms_failed"] += 1
        # Push notifications fan out alongside other channels. We always try
        # push when configured — workers control their own opt-in via the
        # browser permission prompt + subscription record.
        if "push" in payload.channels and VAPID_PRIVATE_KEY:
            sent = await _send_push_to_user(w["user_id"], push_payload)
            counts["push"] += sent

    if notif_docs:
        await db.notifications.insert_many(notif_docs)

    # Ensure 'rush' is included in tags after blast (idempotent merge)
    existing_tags = [t for t in (gig.get("tags") or []) if t in GIG_TAG_VALUES]
    if "rush" not in existing_tags:
        existing_tags.insert(0, "rush")

    await db.gigs.update_one(
        {"gig_id": gig_id},
        {
            "$set": {
                "last_blast_at": datetime.now(timezone.utc).isoformat(),
                "blast_channels": payload.channels,
                # Blasting a gig auto-pins it to the top of the worker feed by
                # adding the 'rush' tag and flipping `is_rush=true`. Admin can
                # untag via the rush/tags endpoints without re-blasting.
                "is_rush": True,
                "rush_at": datetime.now(timezone.utc).isoformat(),
                "tags": existing_tags,
            },
            "$inc": {"blast_count": 1},
        },
    )

    return {"ok": True, "counts": counts, "workers_targeted": len(workers), "is_rush": True, "tags": existing_tags}


@api.put("/gigs/{gig_id}/rush")
async def toggle_rush(
    gig_id: str, payload: RushToggleIn, admin: dict = Depends(require_admin)
):
    """Flip the RUSH flag on a gig without sending a blast. RUSH-flagged gigs
    float to the top of every worker feed with a red border + flame badge.
    Also syncs the 'rush' entry in the gig's tags array."""
    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")
    existing_tags = [t for t in (gig.get("tags") or []) if t in GIG_TAG_VALUES]
    if payload.is_rush:
        if "rush" not in existing_tags:
            existing_tags.insert(0, "rush")
    else:
        existing_tags = [t for t in existing_tags if t != "rush"]
    new_is_pinned = len(existing_tags) > 0
    set_ops: dict = {
        "is_rush": new_is_pinned,
        "tags": existing_tags,
        "rush_at": datetime.now(timezone.utc).isoformat() if new_is_pinned else None,
    }
    await db.gigs.update_one({"gig_id": gig_id}, {"$set": set_ops})
    return {"ok": True, "is_rush": new_is_pinned, "tags": existing_tags}


@api.put("/gigs/{gig_id}/tags")
async def set_gig_tags(
    gig_id: str, payload: GigTagsIn, admin: dict = Depends(require_admin)
):
    """Replace the gig's `tags` array. Any tag pins the gig to the top of the
    feed (sets `is_rush=True` so the existing sort path keeps working).
    Pass `tags=[]` to clear all tags and un-pin the gig."""
    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")
    # Deduplicate while preserving order
    seen = set()
    clean_tags = []
    for t in payload.tags:
        if t in GIG_TAG_VALUES and t not in seen:
            clean_tags.append(t)
            seen.add(t)
    is_pinned = len(clean_tags) > 0
    set_ops = {
        "tags": clean_tags,
        "is_rush": is_pinned,
        "rush_at": datetime.now(timezone.utc).isoformat() if is_pinned else None,
    }
    await db.gigs.update_one({"gig_id": gig_id}, {"$set": set_ops})
    return {"ok": True, "tags": clean_tags, "is_rush": is_pinned}


@api.post("/gigs/{gig_id}/publish")
async def publish_gig(gig_id: str, admin: dict = Depends(require_admin)):
    """Flip a `coming_soon` gig to `open` immediately AND notify matching
    workers (skills overlap + same/nearby ZIP)."""
    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")
    if gig.get("status") == "open":
        return {"ok": True, "already_open": True, "notified": 0}
    if gig.get("status") not in ("coming_soon", None):
        raise HTTPException(400, f"Can't publish a {gig.get('status')} gig")

    await db.gigs.update_one(
        {"gig_id": gig_id},
        {
            "$set": {
                "status": "open",
                "published_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    notified = await _notify_matching_workers_of_new_gig(gig)
    return {"ok": True, "notified": notified, "status": "open"}


async def _notify_matching_workers_of_new_gig(gig: dict) -> int:
    """Push an in-app notification to every approved worker whose skills
    overlap with the gig's category AND whose ZIP starts with the gig's ZIP
    prefix (or has no ZIP — they get notified too rather than miss out)."""
    target_skills = GIG_CATEGORY_TO_SKILLS.get(gig.get("category"), [])
    if not target_skills:
        return 0

    # Extract ZIP from gig.location for proximity match (same regex used by
    # the create-gig dialog auto-suggest panel).
    m = re.search(r"\b(\d{5})\b", (gig.get("location") or ""))
    gig_zip = m.group(1) if m else ""
    zip_prefix = gig_zip[:3] if gig_zip else ""

    workers = await db.users.find(
        {"role": "worker"}, {"_id": 0, "user_id": 1, "skills": 1, "zip_code": 1, "worker_status": 1}
    ).to_list(5000)
    notified_ids: List[str] = []
    for w in workers:
        if _effective_status(w) in ("rejected", "suspended"):
            continue
        if not any(s in (w.get("skills") or []) for s in target_skills):
            continue
        wzip = (w.get("zip_code") or "").strip()
        if zip_prefix and wzip and not wzip.startswith(zip_prefix):
            continue
        notified_ids.append(w["user_id"])

    if not notified_ids:
        return 0
    now_iso = datetime.now(timezone.utc).isoformat()
    docs = [
        {
            "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
            "user_id": uid,
            "gig_id": gig["gig_id"],
            "title": f"New gig: {gig.get('title')}",
            "body": (gig.get("description") or "")[:140],
            "read": False,
            "created_at": now_iso,
        }
        for uid in notified_ids
    ]
    await db.notifications.insert_many(docs)
    logger.info(f"Notified {len(notified_ids)} matching workers about gig {gig['gig_id']}")
    return len(notified_ids)


async def _publish_due_gigs_loop():
    """Background task — every 60s, flip any `coming_soon` gig whose
    publish_at has passed into `open` and notify matching workers."""
    while True:
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            due = await db.gigs.find(
                {
                    "status": "coming_soon",
                    "publish_at": {"$ne": None, "$lte": now_iso},
                },
                {"_id": 0},
            ).to_list(100)
            for g in due:
                await db.gigs.update_one(
                    {"gig_id": g["gig_id"]},
                    {"$set": {"status": "open", "published_at": now_iso}},
                )
                try:
                    await _notify_matching_workers_of_new_gig(g)
                except Exception as e:
                    logger.error(f"Auto-publish notify failed for {g['gig_id']}: {e}")
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"_publish_due_gigs_loop error: {e}")
            await asyncio.sleep(60)


# ---- Notifications ---------------------------------------------------------
@api.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    items = (
        await db.notifications.find({"user_id": user["user_id"]}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(100)
    )
    return items


@api.post("/notifications/{notification_id}/read")
async def mark_read(notification_id: str, user: dict = Depends(get_current_user)):
    await db.notifications.update_one(
        {"notification_id": notification_id, "user_id": user["user_id"]},
        {"$set": {"read": True}},
    )
    return {"ok": True}


# ---- Admin endpoints -------------------------------------------------------
@api.get("/admin/workers")
async def list_workers(
    status: Optional[str] = Query(None),
    skills: Optional[str] = Query(None, description="Comma-separated skill values"),
    availability: Optional[str] = Query(None, description="Comma-separated availability values"),
    zip_code: Optional[str] = Query(None, description="Exact 5-digit ZIP"),
    zip_prefix: Optional[str] = Query(None, description="First N digits of ZIP for 'nearby' filter"),
    vehicle: Optional[str] = Query(None, description="one of: any, car, truck, cdl"),
    profile_complete: Optional[bool] = Query(None),
    min_rating: Optional[float] = Query(None, ge=0, le=5, description="Hide workers below this avg rating"),
    search: Optional[str] = Query(None, description="Free-text search across name/email/phone"),
    admin: dict = Depends(require_admin),
):
    query: dict = {"role": "worker"}
    if status == "pending":
        query["worker_status"] = "pending"
    elif status == "approved":
        # Treat missing field as approved for back-compat
        query["$or"] = [
            {"worker_status": "approved"},
            {"worker_status": {"$exists": False}},
        ]
    elif status in ("rejected", "suspended"):
        query["worker_status"] = status

    if skills:
        skill_list = [s.strip() for s in skills.split(",") if s.strip()]
        if skill_list:
            query["skills"] = {"$in": skill_list}
    if availability:
        av_list = [a.strip() for a in availability.split(",") if a.strip()]
        if av_list:
            query["availability"] = {"$in": av_list}
    if zip_code:
        query["zip_code"] = zip_code.strip()
    elif zip_prefix:
        # ZIP starts-with for a "nearby" filter (no geocoding required)
        prefix = zip_prefix.strip()
        if prefix:
            query["zip_code"] = {"$regex": f"^{re.escape(prefix)}"}

    if vehicle == "car":
        query["has_car"] = True
    elif vehicle == "truck":
        query["has_truck"] = True
    elif vehicle == "cdl":
        query["has_cdl"] = True
    elif vehicle == "any":
        query["$or"] = (query.get("$or") or []) + [
            {"has_car": True}, {"has_truck": True}, {"has_cdl": True}
        ]

    if search:
        s = re.escape(search.strip())
        if s:
            query["$or"] = (query.get("$or") or []) + [
                {"name": {"$regex": s, "$options": "i"}},
                {"email": {"$regex": s, "$options": "i"}},
                {"phone": {"$regex": s, "$options": "i"}},
            ]

    workers = await db.users.find(
        query, {"_id": 0, "password_hash": 0}
    ).sort("created_at", -1).to_list(1000)

    # Enrich with computed profile_complete + missing + rating stats
    for w in workers:
        miss = _profile_missing_fields(w)
        w["profile_complete"] = len(miss) == 0
        w["profile_missing_fields"] = miss
        stats = await _worker_rating_stats(w["user_id"])
        w.update(stats)

    if profile_complete is True:
        workers = [w for w in workers if w["profile_complete"]]
    elif profile_complete is False:
        workers = [w for w in workers if not w["profile_complete"]]

    if min_rating is not None:
        # Only include workers WITH a rating and at or above threshold. If
        # they have no rating yet, exclude — matches admin intent of "show me
        # 4-star+ workers."
        workers = [w for w in workers if (w.get("rating_avg") or 0) >= min_rating]

    return workers


@api.get("/admin/workers/match")
async def match_workers_for_gig(
    category: Optional[GigCategory] = Query(None),
    zip_code: Optional[str] = Query(None, description="Gig ZIP — matched against worker zip_code"),
    zip_prefix_length: int = Query(3, ge=1, le=5),
    availability: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    admin: dict = Depends(require_admin),
):
    """Suggest workers for a gig admin is about to create.

    Scoring:
    - +3 skills overlap (any skill in GIG_CATEGORY_TO_SKILLS[category])
    - +3 exact zip match, +1 same zip prefix (default first 3 digits ~ SCF area)
    - +1 ID verified, +1 availability overlap, +1 has any vehicle
    - +1 per 3 completed gigs in this category (capped at +5) — proven track record
    - profile_complete is required (returns []  when no candidate matches)
    """
    cand = await db.users.find(
        {"role": "worker"}, {"_id": 0, "password_hash": 0}
    ).to_list(2000)

    target_skills: List[str] = (
        GIG_CATEGORY_TO_SKILLS.get(category, []) if category else []
    )
    avail_list = [a.strip() for a in (availability or "").split(",") if a.strip()]
    zip_pref = (zip_code or "")[:zip_prefix_length] if zip_code else ""

    # Pre-compute completed-by-category for every worker so we can bump
    # experienced candidates higher. Single Mongo query, in-memory bucket.
    completed_by_category = await _completed_gigs_by_worker_and_category()

    matches: List[dict] = []
    for w in cand:
        if _effective_status(w) in ("rejected", "suspended"):
            continue
        miss = _profile_missing_fields(w)
        if miss:
            continue
        score = 0
        reasons: List[str] = []

        worker_skills = w.get("skills") or []
        skill_overlap = [s for s in worker_skills if s in target_skills]
        if target_skills:
            if skill_overlap:
                score += 3
                reasons.append(
                    f"skills: {', '.join(SKILL_LABELS.get(s, s) for s in skill_overlap)}"
                )
            else:
                continue  # require skill match if category given

        wzip = (w.get("zip_code") or "").strip()
        if zip_code and wzip == zip_code:
            score += 3
            reasons.append(f"same ZIP {zip_code}")
        elif zip_pref and wzip.startswith(zip_pref):
            score += 1
            reasons.append(f"nearby ZIP ({wzip})")

        if avail_list:
            wav = w.get("availability") or []
            if any(a in wav for a in avail_list):
                score += 1
                reasons.append("availability matches")

        if w.get("id_verified"):
            score += 1
        if w.get("has_car") or w.get("has_truck") or w.get("has_cdl"):
            score += 1
            reasons.append("has vehicle")

        # Category track-record — +1 per 3 completed, capped at +5
        cat_done = (
            completed_by_category.get(w["user_id"], {}).get(category, 0)
            if category else 0
        )
        if cat_done > 0:
            score += min(5, cat_done // 3 + 1)
            reasons.append(
                f"{cat_done} {category} gig{'s' if cat_done != 1 else ''} done"
            )

        if score == 0:
            continue
        matches.append({
            "user_id": w["user_id"],
            "name": w.get("name"),
            "email": w.get("email"),
            "phone": w.get("phone"),
            "zip_code": wzip,
            "skills": worker_skills,
            "id_verified": bool(w.get("id_verified")),
            "category_completed_count": cat_done,
            "score": score,
            "reasons": reasons,
        })

    matches.sort(key=lambda m: m["score"], reverse=True)
    return matches[:limit]


async def _completed_gigs_by_worker_and_category() -> dict:
    """Build a {worker_id: {category: count}} dict of completed gigs (i.e.
    acceptances that have been clocked out). One aggregate scan — caller can
    cache the result for the duration of a request."""
    accs = await db.gig_acceptances.find(
        {"clock_out_at": {"$ne": None}}, {"_id": 0, "worker_id": 1, "gig_id": 1}
    ).to_list(50000)
    if not accs:
        return {}
    gig_ids = list({a["gig_id"] for a in accs})
    gigs = await db.gigs.find(
        {"gig_id": {"$in": gig_ids}}, {"_id": 0, "gig_id": 1, "category": 1}
    ).to_list(50000)
    cat_by_gig = {g["gig_id"]: g.get("category") for g in gigs}
    out: dict = {}
    for a in accs:
        cat = cat_by_gig.get(a["gig_id"])
        if not cat:
            continue
        out.setdefault(a["worker_id"], {})
        out[a["worker_id"]][cat] = out[a["worker_id"]].get(cat, 0) + 1
    return out


@api.get("/admin/workers/{user_id}")
async def get_worker(user_id: str, admin: dict = Depends(require_admin)):
    w = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    if not w:
        raise HTTPException(404, "Worker not found")
    accepted = await db.gig_acceptances.find(
        {"worker_id": user_id}, {"_id": 0}
    ).sort("accepted_at", -1).to_list(500)
    if accepted:
        gig_ids = list({a["gig_id"] for a in accepted})
        gigs = await db.gigs.find(
            {"gig_id": {"$in": gig_ids}},
            {"_id": 0},
        ).to_list(500)
        gmap = {g["gig_id"]: g for g in gigs}
        for a in accepted:
            g = gmap.get(a["gig_id"]) or {}
            a["gig_title"] = g.get("title")
            a["gig_category"] = g.get("category")
            a["gig_scheduled_date"] = g.get("scheduled_date")
            a["gig_pay_rate"] = g.get("pay_rate")
            a["gig_pay_type"] = g.get("pay_type")
            # If never clocked out, project resolved pay so admin can see what
            # the worker WOULD earn at current rate.
            if a.get("earnings") is None:
                pay = _resolve_pay(a, w, g)
                a["pay_rate_effective"] = pay["pay_rate"]
                a["pay_type_effective"] = pay["pay_type"]
                br = _resolve_break_minutes(a, g)
                a["break_minutes_effective"] = br
                a["paid_hours"] = _compute_paid_hours(a.get("hours_worked"), br)
                a["projected_earnings"] = _compute_earnings(
                    pay["pay_rate"], pay["pay_type"], a.get("hours_worked"), br
                )
            else:
                br = _resolve_break_minutes(a, g)
                a["break_minutes_effective"] = br
                a["paid_hours"] = _compute_paid_hours(a.get("hours_worked"), br)
    w["accepted_gigs"] = accepted
    # Attach rating aggregates so the WorkerDetail header can render stars.
    w.update(await _worker_rating_stats(user_id))
    return w


@api.get("/admin/requests")
async def list_pending_requests(
    search: Optional[str] = Query(None, description="Free-text — worker name/email/phone or gig title/location"),
    admin: dict = Depends(require_admin),
):
    """Return ALL pending gig requests across the platform, flat, sorted oldest
    first. Enriched with gig and worker fields so admin can decide inline.

    Optional `search` is case-insensitive and matches against the enriched
    worker + gig fields. Filtering is done in-memory after enrichment so admin
    can search across both sides in one go."""
    rows = await db.gig_acceptances.find(
        {"status": "requested"}, {"_id": 0}
    ).sort("requested_at", 1).to_list(1000)
    if not rows:
        return []
    gig_ids = list({r["gig_id"] for r in rows})
    worker_ids = list({r["worker_id"] for r in rows})
    gigs = await db.gigs.find(
        {"gig_id": {"$in": gig_ids}},
        {
            "_id": 0,
            "gig_id": 1,
            "title": 1,
            "category": 1,
            "subcategory": 1,
            "location": 1,
            "scheduled_date": 1,
            "scheduled_at": 1,
            "pay_rate": 1,
            "pay_type": 1,
            "slots": 1,
            "slots_filled": 1,
            "status": 1,
        },
    ).to_list(1000)
    gmap = {g["gig_id"]: g for g in gigs}
    workers = await db.users.find(
        {"user_id": {"$in": worker_ids}}, {"_id": 0, "password_hash": 0}
    ).to_list(1000)
    wmap = {w["user_id"]: w for w in workers}
    for r in rows:
        g = gmap.get(r["gig_id"]) or {}
        w = wmap.get(r["worker_id"]) or {}
        r["gig"] = g
        r["worker_name"] = w.get("name")
        r["worker_email"] = w.get("email")
        r["worker_phone"] = w.get("phone")
        r["worker_id_verified"] = w.get("id_verified", False)
        r["worker_status"] = w.get("worker_status", "approved")

    if search:
        q = search.strip().lower()
        if q:
            rows = [
                r for r in rows
                if q in (r.get("worker_name") or "").lower()
                or q in (r.get("worker_email") or "").lower()
                or q in (r.get("worker_phone") or "").lower()
                or q in ((r.get("gig") or {}).get("title") or "").lower()
                or q in ((r.get("gig") or {}).get("location") or "").lower()
            ]
    return rows


class AdminProfileUpdateIn(BaseModel):
    """All fields are optional — admin sends only what's changing. Mirrors
    ProfileUpdateIn + admin-only fields (worker_status, id_verified, email)."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    bio: Optional[str] = None
    skills: Optional[List[str]] = None
    zip_code: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    date_of_birth: Optional[str] = None
    has_car: Optional[bool] = None
    has_truck: Optional[bool] = None
    has_cdl: Optional[bool] = None
    experience_level: Optional[str] = None
    availability: Optional[List[str]] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    tshirt_size: Optional[str] = None
    # Admin-only overrides
    worker_status: Optional[str] = None
    id_verified: Optional[bool] = None
    # Admin sticky-note (internal — workers never see this)
    admin_note: Optional[str] = None


class AdminGigNoteIn(BaseModel):
    """Per-gig private admin note about a worker on a specific acceptance.
    Separate from the rating note — used for ops context like 'arrived late'
    or 'client requested this worker again'."""
    note: Optional[str] = None


class WorkerMessageIn(BaseModel):
    """One-way message from admin → worker. Surfaces in /me/notifications and
    on the worker's gig detail page when gig_id is set."""
    body: str
    title: Optional[str] = None
    gig_id: Optional[str] = None


# Per-gig role for a worker. `manager` gets a badge + sees the crew's contact
# info (next iteration); `worker` is the default.
GIG_ROLES = ["worker", "manager", "lead", "trainer"]
GIG_ROLE_LABELS = {
    "worker": "Worker",
    "manager": "Manager",
    "lead": "Lead",
    "trainer": "Trainer",
}


class AcceptanceRoleIn(BaseModel):
    role: str


class AdminCreateIn(BaseModel):
    """Create a new admin user from Settings → Admin users."""
    name: str
    email: str
    password: str
    is_read_only: Optional[bool] = False


class AdminRoleUpdateIn(BaseModel):
    """Toggle read-only or promote/demote between admin↔worker."""
    is_read_only: Optional[bool] = None
    promote_to_admin: Optional[bool] = None
    demote_to_worker: Optional[bool] = None


@api.post("/admin/workers/{user_id}/verify-id")
async def verify_worker_id(user_id: str, admin: dict = Depends(require_admin)):
    await db.users.update_one(
        {"user_id": user_id}, {"$set": {"id_verified": True}}
    )
    return {"ok": True}


@api.put("/admin/workers/{user_id}/profile")
async def admin_update_worker_profile(
    user_id: str,
    payload: AdminProfileUpdateIn,
    admin: dict = Depends(require_admin),
):
    """Admin override editor — set any field on a worker's profile. Validates
    enum-ish fields identically to the worker self-serve endpoint. Used when
    a worker can't update their own profile (system glitch, missing info,
    etc)."""
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(404, "Worker not found")
    if user.get("role") == "admin":
        raise HTTPException(400, "Use the admin self-service flow to edit an admin")

    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}

    # Validate enum-ish fields (same rules as PUT /profile — silently drop
    # unknown skill/availability values so legacy/free-text data doesn't break
    # admin saves).
    if "skills" in updates:
        updates["skills"] = [s for s in updates["skills"] if s in WORKER_SKILLS]
    if "availability" in updates:
        updates["availability"] = [a for a in updates["availability"] if a in AVAILABILITY_OPTIONS]
    if "experience_level" in updates and updates["experience_level"] and updates["experience_level"] not in EXPERIENCE_OPTIONS:
        raise HTTPException(400, f"experience_level must be one of {EXPERIENCE_OPTIONS}")
    if "tshirt_size" in updates and updates["tshirt_size"] and updates["tshirt_size"] not in TSHIRT_SIZES:
        raise HTTPException(400, f"tshirt_size must be one of {TSHIRT_SIZES}")
    if "zip_code" in updates and updates["zip_code"]:
        z = updates["zip_code"].strip()
        if not (z.isdigit() and len(z) == 5):
            raise HTTPException(400, "zip_code must be a 5-digit US ZIP code")
        updates["zip_code"] = z
    if "worker_status" in updates and updates["worker_status"] not in (
        "approved", "pending", "rejected", "suspended"
    ):
        raise HTTPException(400, "worker_status must be approved|pending|rejected|suspended")
    if "email" in updates and updates["email"]:
        new_email = updates["email"].strip().lower()
        if "@" not in new_email or "." not in new_email:
            raise HTTPException(400, "Invalid email")
        # Make sure no other user has that email
        existing = await db.users.find_one(
            {"email": new_email, "user_id": {"$ne": user_id}}
        )
        if existing:
            raise HTTPException(400, "That email is already in use by another account")
        updates["email"] = new_email

    if updates:
        # If status changed, also stamp the audit-ish fields & kill sessions for
        # rejected/suspended so the worker doesn't keep using the app.
        if "worker_status" in updates:
            updates["worker_status_at"] = datetime.now(timezone.utc).isoformat()
            updates["worker_status_by"] = admin["email"]
        await db.users.update_one({"user_id": user_id}, {"$set": updates})
        if updates.get("worker_status") in ("rejected", "suspended"):
            await db.sessions.delete_many({"user_id": user_id})

    logger.info(
        f"Admin {admin['email']} edited worker {user.get('email')} profile: "
        f"{list(updates.keys())}"
    )
    return await _get_user_by_id(user_id)


@api.post("/admin/workers/{user_id}/id-upload")
async def admin_upload_worker_id(
    user_id: str,
    file: UploadFile = File(...),
    admin: dict = Depends(require_admin),
):
    """Upload an ID image on behalf of a worker (e.g. they emailed a photo
    instead of uploading in the app). The ID lands UNverified — admin must
    still hit the Verify button afterwards if it's accepted."""
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(404, "Worker not found")
    if user.get("role") != "worker":
        raise HTTPException(400, "Only worker IDs can be uploaded this way")
    path = await _upload_user_image(user_id, "id", file)
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"id_image_path": path, "id_verified": False}},
    )
    logger.info(f"Admin {admin['email']} uploaded ID for worker {user.get('email')}")
    return {"id_image_path": path}


async def _set_worker_status(
    user_id: str, status: str, admin: dict, kill_sessions: bool = False
) -> dict:
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(404, "Worker not found")
    if user.get("role") == "admin":
        raise HTTPException(400, "Cannot change status of an admin user")
    await db.users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "worker_status": status,
                "worker_status_at": datetime.now(timezone.utc).isoformat(),
                "worker_status_by": admin["email"],
            }
        },
    )
    if kill_sessions:
        await db.sessions.delete_many({"user_id": user_id})
    logger.info(f"Admin {admin['email']} set worker {user.get('email')} status -> {status}")
    return {"ok": True, "worker_status": status}


@api.post("/admin/workers/{user_id}/approve")
async def approve_worker(
    user_id: str, _: WorkerStatusIn = WorkerStatusIn(), admin: dict = Depends(require_admin)
):
    return await _set_worker_status(user_id, "approved", admin)


@api.post("/admin/workers/{user_id}/reject")
async def reject_worker(
    user_id: str, _: WorkerStatusIn = WorkerStatusIn(), admin: dict = Depends(require_admin)
):
    # Rejection invalidates active sessions
    return await _set_worker_status(user_id, "rejected", admin, kill_sessions=True)


@api.post("/admin/workers/{user_id}/suspend")
async def suspend_worker(
    user_id: str, _: WorkerStatusIn = WorkerStatusIn(), admin: dict = Depends(require_admin)
):
    return await _set_worker_status(user_id, "suspended", admin, kill_sessions=True)


@api.post("/admin/workers/{user_id}/reinstate")
async def reinstate_worker(
    user_id: str, _: WorkerStatusIn = WorkerStatusIn(), admin: dict = Depends(require_admin)
):
    return await _set_worker_status(user_id, "approved", admin)


@api.post("/admin/workers/{user_id}/reset-password")
async def admin_reset_password(
    user_id: str,
    payload: AdminResetPasswordIn,
    admin: dict = Depends(require_admin),
):
    """Set a new password for a worker. Invalidates all of their sessions."""
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(404, "Worker not found")
    if user.get("role") == "admin":
        raise HTTPException(400, "Admins must use the self-service change-password flow")

    new_password = (payload.new_password or "").strip()
    if not new_password:
        # Generate an easy-to-share temp password
        new_password = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10]
    elif len(new_password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"password_hash": hash_password(new_password)}},
    )
    # Force re-login by killing all of their sessions
    await db.sessions.delete_many({"user_id": user_id})
    logger.info(f"Admin {admin['email']} reset password for {user.get('email')}")
    return {"ok": True, "new_password": new_password}


@api.delete("/admin/workers/{user_id}")
async def delete_worker(user_id: str, admin: dict = Depends(require_admin)):
    """Delete a worker and cascade clean their acceptances, sessions, files."""
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(404, "Worker not found")
    if user.get("role") == "admin":
        raise HTTPException(400, "Cannot delete an admin from this endpoint")

    # Free up gig slots for any open acceptances
    acceptances = await db.gig_acceptances.find({"worker_id": user_id}).to_list(1000)
    for a in acceptances:
        gig = await db.gigs.find_one({"gig_id": a["gig_id"]})
        if not gig:
            continue
        new_filled = max(0, (gig.get("slots_filled") or 0) - 1)
        new_status = (
            "open" if new_filled < gig.get("slots", 1) else gig.get("status", "open")
        )
        await db.gigs.update_one(
            {"gig_id": a["gig_id"]},
            {"$set": {"slots_filled": new_filled, "status": new_status}},
        )

    await db.gig_acceptances.delete_many({"worker_id": user_id})
    await db.sessions.delete_many({"user_id": user_id})
    await db.notifications.delete_many({"user_id": user_id})
    await db.files.delete_many({"owner_id": user_id})
    await db.users.delete_one({"user_id": user_id})
    logger.info(f"Admin {admin['email']} deleted worker {user.get('email')}")
    return {"ok": True}


# ---- Self-service password change ------------------------------------------
@api.post("/auth/change-password")
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


# ---- Clock in / out --------------------------------------------------------
@api.post("/gigs/{gig_id}/clock-in")
async def clock_in(gig_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "worker":
        raise HTTPException(403, "Only workers can clock in")
    acceptance = await db.gig_acceptances.find_one(
        {"gig_id": gig_id, "worker_id": user["user_id"]}
    )
    if not acceptance:
        raise HTTPException(400, "You must request and be approved for this gig before clocking in")
    if acceptance.get("status") == "requested":
        raise HTTPException(400, "Your request is still pending HCOB approval")
    if acceptance.get("clock_in_at") and not acceptance.get("clock_out_at"):
        raise HTTPException(400, "You're already clocked in")
    if acceptance.get("clock_out_at"):
        raise HTTPException(400, "Already completed — cannot clock in again")

    now = datetime.now(timezone.utc).isoformat()
    await db.gig_acceptances.update_one(
        {"acceptance_id": acceptance["acceptance_id"]},
        {"$set": {"clock_in_at": now, "status": "on_the_clock"}},
    )
    return {"ok": True, "clock_in_at": now}


@api.post("/gigs/{gig_id}/clock-out")
async def clock_out(gig_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "worker":
        raise HTTPException(403, "Only workers can clock out")
    acceptance = await db.gig_acceptances.find_one(
        {"gig_id": gig_id, "worker_id": user["user_id"]}
    )
    if not acceptance:
        raise HTTPException(400, "No acceptance for this gig")
    if not acceptance.get("clock_in_at"):
        raise HTTPException(400, "You haven't clocked in yet")
    if acceptance.get("clock_out_at"):
        raise HTTPException(400, "You've already clocked out")

    now = datetime.now(timezone.utc)
    clock_in_dt = datetime.fromisoformat(acceptance["clock_in_at"])
    if clock_in_dt.tzinfo is None:
        clock_in_dt = clock_in_dt.replace(tzinfo=timezone.utc)
    hours = round((now - clock_in_dt).total_seconds() / 3600.0, 2)

    gig = await db.gigs.find_one({"gig_id": gig_id})
    worker = await db.users.find_one({"user_id": user["user_id"]})
    pay = _resolve_pay(acceptance, worker, gig)
    break_minutes = _resolve_break_minutes(acceptance, gig)
    paid_hours = _compute_paid_hours(hours, break_minutes)
    earnings = _compute_earnings(pay["pay_rate"], pay["pay_type"], hours, break_minutes)

    await db.gig_acceptances.update_one(
        {"acceptance_id": acceptance["acceptance_id"]},
        {
            "$set": {
                "clock_out_at": now.isoformat(),
                "hours_worked": hours,
                "break_minutes_applied": break_minutes,
                "paid_hours": paid_hours,
                "pay_rate_applied": pay["pay_rate"],
                "pay_type_applied": pay["pay_type"],
                "pay_rate_source": pay["pay_rate_source"],
                "pay_type_source": pay["pay_type_source"],
                "earnings": earnings,
                "timesheet_approved": False,
                "status": "completed",
            }
        },
    )
    return {
        "ok": True,
        "clock_out_at": now.isoformat(),
        "hours_worked": hours,
        "break_minutes": break_minutes,
        "paid_hours": paid_hours,
        "earnings": earnings,
        "pay_rate_applied": pay["pay_rate"],
        "pay_type_applied": pay["pay_type"],
    }


@api.get("/admin/stats")
async def admin_stats(admin: dict = Depends(require_admin)):
    total_workers = await db.users.count_documents({"role": "worker"})
    open_gigs = await db.gigs.count_documents({"status": "open"})
    filled_gigs = await db.gigs.count_documents({"status": "filled"})
    total_gigs = await db.gigs.count_documents({})
    total_acceptances = await db.gig_acceptances.count_documents({})
    pending_id = await db.users.count_documents(
        {"role": "worker", "id_image_path": {"$ne": None}, "id_verified": False}
    )
    pending_approval = await db.users.count_documents(
        {"role": "worker", "worker_status": "pending"}
    )
    pending_requests = await db.gig_acceptances.count_documents(
        {"status": "requested"}
    )
    return {
        "total_workers": total_workers,
        "open_gigs": open_gigs,
        "filled_gigs": filled_gigs,
        "total_gigs": total_gigs,
        "total_acceptances": total_acceptances,
        "pending_id_verification": pending_id,
        "pending_approval": pending_approval,
        "pending_requests": pending_requests,
    }


# ----------------------------------------------------------------------------
# Pay, timesheet approval, reports, and Google Sheets export
# ----------------------------------------------------------------------------
@api.put("/admin/workers/{user_id}/pay")
async def set_worker_default_pay(
    user_id: str, payload: WorkerPayIn, admin: dict = Depends(require_admin)
):
    """Admin sets a worker's default pay rate / type (used as a fallback when a
    gig-specific override is not set)."""
    worker = await db.users.find_one({"user_id": user_id})
    if not worker or worker.get("role") != "worker":
        raise HTTPException(404, "Worker not found")

    set_ops: dict = {}
    unset_ops: dict = {}
    if payload.clear_rate:
        unset_ops["default_pay_rate"] = ""
    elif payload.default_pay_rate is not None:
        if payload.default_pay_rate < 0:
            raise HTTPException(400, "pay rate must be >= 0")
        set_ops["default_pay_rate"] = float(payload.default_pay_rate)
    if payload.clear_type:
        unset_ops["default_pay_type"] = ""
    elif payload.default_pay_type is not None:
        set_ops["default_pay_type"] = payload.default_pay_type

    if not set_ops and not unset_ops:
        return {"ok": True, "changed": 0}

    ops: dict = {}
    if set_ops:
        ops["$set"] = set_ops
    if unset_ops:
        ops["$unset"] = unset_ops
    await db.users.update_one({"user_id": user_id}, ops)
    logger.info(f"Admin {admin['email']} set pay for worker {user_id}: {set_ops or unset_ops}")
    return {"ok": True, "default_pay_rate": set_ops.get("default_pay_rate"), "default_pay_type": set_ops.get("default_pay_type")}


@api.put("/gigs/{gig_id}/acceptances/{acceptance_id}/pay")
async def set_acceptance_pay_override(
    gig_id: str,
    acceptance_id: str,
    payload: AcceptancePayIn,
    admin: dict = Depends(require_admin),
):
    """Admin overrides pay rate/type for a single worker on a single gig.

    Useful when one worker earns differently from the posted gig rate (e.g.
    performance, seniority). If the acceptance is already completed (clocked
    out), this also recomputes the snapshotted earnings."""
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Acceptance not found")

    set_ops: dict = {}
    unset_ops: dict = {}
    if payload.clear_rate:
        unset_ops["pay_rate_override"] = ""
    elif payload.pay_rate_override is not None:
        if payload.pay_rate_override < 0:
            raise HTTPException(400, "pay rate must be >= 0")
        set_ops["pay_rate_override"] = float(payload.pay_rate_override)
    if payload.clear_type:
        unset_ops["pay_type_override"] = ""
    elif payload.pay_type_override is not None:
        set_ops["pay_type_override"] = payload.pay_type_override

    if not set_ops and not unset_ops:
        return {"ok": True, "changed": 0}

    ops: dict = {}
    if set_ops:
        ops["$set"] = set_ops
    if unset_ops:
        ops["$unset"] = unset_ops
    await db.gig_acceptances.update_one({"acceptance_id": acceptance_id}, ops)

    # Recompute earnings if already clocked out
    refreshed = await db.gig_acceptances.find_one({"acceptance_id": acceptance_id})
    if refreshed and refreshed.get("clock_out_at"):
        gig = await db.gigs.find_one({"gig_id": gig_id})
        worker = await db.users.find_one({"user_id": refreshed["worker_id"]})
        pay = _resolve_pay(refreshed, worker, gig)
        br = _resolve_break_minutes(refreshed, gig)
        new_paid = _compute_paid_hours(refreshed.get("hours_worked"), br)
        new_earnings = _compute_earnings(pay["pay_rate"], pay["pay_type"], refreshed.get("hours_worked"), br)
        await db.gig_acceptances.update_one(
            {"acceptance_id": acceptance_id},
            {
                "$set": {
                    "pay_rate_applied": pay["pay_rate"],
                    "pay_type_applied": pay["pay_type"],
                    "pay_rate_source": pay["pay_rate_source"],
                    "pay_type_source": pay["pay_type_source"],
                    "break_minutes_applied": br,
                    "paid_hours": new_paid,
                    "earnings": new_earnings,
                    # Override invalidates a prior approval — admin should re-approve
                    "timesheet_approved": False,
                    "timesheet_approved_at": None,
                    "timesheet_approved_by": None,
                }
            },
        )
    logger.info(f"Admin {admin['email']} set per-gig pay override on acceptance {acceptance_id}")
    return {"ok": True}


@api.post("/gigs/{gig_id}/acceptances/{acceptance_id}/approve-timesheet")
async def approve_timesheet(
    gig_id: str,
    acceptance_id: str,
    payload: TimesheetApproveIn,
    admin: dict = Depends(require_admin),
):
    """Admin approves the worker's clocked timesheet — releases earnings to the
    worker's earnings view. Optionally allows correcting hours_worked / earnings
    (e.g. worker forgot to clock out)."""
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Acceptance not found")
    if not acceptance.get("clock_out_at"):
        raise HTTPException(400, "Worker hasn't clocked out yet — cannot approve timesheet")

    set_ops: dict = {
        "timesheet_approved": True,
        "timesheet_approved_at": datetime.now(timezone.utc).isoformat(),
        "timesheet_approved_by": admin["email"],
    }
    if payload.note:
        set_ops["timesheet_note"] = payload.note

    # Per-worker break override (minutes) — when present, replaces the gig default
    if payload.break_minutes is not None:
        if payload.break_minutes < 0:
            raise HTTPException(400, "break_minutes must be >= 0")
        set_ops["break_minutes"] = int(payload.break_minutes)

    # Optional admin corrections (e.g. trim hours, set earnings manually)
    if payload.hours_worked is not None:
        if payload.hours_worked < 0:
            raise HTTPException(400, "hours_worked must be >= 0")
        set_ops["hours_worked"] = round(float(payload.hours_worked), 2)
    if payload.earnings is not None:
        if payload.earnings < 0:
            raise HTTPException(400, "earnings must be >= 0")
        set_ops["earnings"] = round(float(payload.earnings), 2)
        set_ops["earnings_manual_override"] = True
    elif payload.hours_worked is not None or payload.break_minutes is not None:
        # Recompute earnings whenever hours OR break changed.
        rate = acceptance.get("pay_rate_applied")
        ptype = acceptance.get("pay_type_applied")
        gig = await db.gigs.find_one({"gig_id": gig_id})
        # Fallback to a fresh resolution if not snapshotted yet
        if rate is None or ptype is None:
            worker = await db.users.find_one({"user_id": acceptance["worker_id"]})
            pay = _resolve_pay(acceptance, worker, gig)
            rate, ptype = pay["pay_rate"], pay["pay_type"]
            set_ops["pay_rate_applied"] = rate
            set_ops["pay_type_applied"] = ptype
        effective_hours = set_ops.get("hours_worked", acceptance.get("hours_worked"))
        # Use the new break if provided, else fall back to existing resolution
        effective_break = (
            set_ops.get("break_minutes")
            if "break_minutes" in set_ops
            else _resolve_break_minutes(acceptance, gig)
        )
        set_ops["break_minutes_applied"] = effective_break
        set_ops["paid_hours"] = _compute_paid_hours(effective_hours, effective_break)
        set_ops["earnings"] = _compute_earnings(rate, ptype, effective_hours, effective_break)

    await db.gig_acceptances.update_one(
        {"acceptance_id": acceptance_id}, {"$set": set_ops}
    )

    # Notify worker that their timesheet was approved + earnings now visible
    gig = await db.gigs.find_one({"gig_id": gig_id}, {"_id": 0, "title": 1})
    refreshed = await db.gig_acceptances.find_one({"acceptance_id": acceptance_id}, {"_id": 0})
    earned = refreshed.get("earnings") if refreshed else None
    await db.notifications.insert_one(
        {
            "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
            "user_id": acceptance["worker_id"],
            "gig_id": gig_id,
            "title": f"Timesheet approved: {gig.get('title') if gig else 'gig'}",
            "body": f"You earned ${earned:.2f} for this gig." if earned is not None else "Your timesheet was approved.",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    logger.info(f"Admin {admin['email']} approved timesheet {acceptance_id}")
    return {"ok": True, "earnings": earned, "timesheet_approved": True}


@api.post("/gigs/{gig_id}/acceptances/{acceptance_id}/unapprove-timesheet")
async def unapprove_timesheet(
    gig_id: str,
    acceptance_id: str,
    admin: dict = Depends(require_admin),
):
    """Reverse a prior timesheet approval (e.g. if a dispute is raised)."""
    res = await db.gig_acceptances.update_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id},
        {
            "$set": {
                "timesheet_approved": False,
                "timesheet_approved_at": None,
                "timesheet_approved_by": None,
            }
        },
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Acceptance not found")
    return {"ok": True}


def _parse_admin_dt(value: str) -> datetime:
    """Parse a datetime string from the admin UI. Accepts ISO 8601 with or
    without timezone (treats naive as UTC) and the `YYYY-MM-DDTHH:MM` shape
    that `<input type=datetime-local>` emits."""
    raw = value.strip()
    if not raw:
        raise HTTPException(400, "Empty datetime value")
    # Handle trailing Z
    raw = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        raise HTTPException(400, f"Invalid datetime: {value}")
    if dt.tzinfo is None:
        # datetime-local from the admin's browser is in their local time, but
        # we don't know the offset. Treat as UTC — the admin form will preview
        # the value back to them so they can correct if needed.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@api.put("/gigs/{gig_id}/acceptances/{acceptance_id}/timesheet")
async def edit_acceptance_timesheet(
    gig_id: str,
    acceptance_id: str,
    payload: TimesheetEditIn,
    admin: dict = Depends(require_admin),
):
    """Admin sets / edits / clears clock-in & clock-out times for an acceptance.

    Recomputes `hours_worked` + `earnings` whenever both times are present.
    Any edit resets `timesheet_approved=false` so the admin must re-approve.
    Status is kept in sync: completed if clocked out, accepted if clocked back in only.
    """
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Acceptance not found")

    # Allow editing only for workers who were actually approved/clocked-in/completed
    if acceptance.get("status") == "requested":
        raise HTTPException(
            400, "Approve the worker for this gig before editing their timesheet"
        )

    new_in: Optional[datetime] = None
    new_out: Optional[datetime] = None
    if payload.clock_in_at is not None:
        new_in = _parse_admin_dt(payload.clock_in_at)
    elif acceptance.get("clock_in_at"):
        new_in = _parse_admin_dt(acceptance["clock_in_at"])

    if payload.clear_clock_out:
        new_out = None
    elif payload.clock_out_at is not None:
        new_out = _parse_admin_dt(payload.clock_out_at)
    elif acceptance.get("clock_out_at") and not payload.clear_clock_out:
        new_out = _parse_admin_dt(acceptance["clock_out_at"])

    # Validation
    if new_in is None and new_out is not None:
        raise HTTPException(400, "Cannot set a clock-out time without a clock-in time")
    if new_in and new_out and new_out <= new_in:
        raise HTTPException(400, "Clock-out must be after clock-in")

    set_ops: dict = {
        "timesheet_approved": False,
        "timesheet_approved_at": None,
        "timesheet_approved_by": None,
        "timesheet_edited_at": datetime.now(timezone.utc).isoformat(),
        "timesheet_edited_by": admin["email"],
    }
    unset_ops: dict = {}

    if new_in is None:
        unset_ops["clock_in_at"] = ""
        unset_ops["hours_worked"] = ""
        unset_ops["paid_hours"] = ""
        unset_ops["break_minutes_applied"] = ""
        unset_ops["earnings"] = ""
        set_ops["status"] = "accepted"
    else:
        set_ops["clock_in_at"] = new_in.isoformat()

    if new_out is None:
        unset_ops["clock_out_at"] = ""
        unset_ops["hours_worked"] = ""
        unset_ops["paid_hours"] = ""
        unset_ops["break_minutes_applied"] = ""
        unset_ops["earnings"] = ""
        if new_in is not None:
            set_ops["status"] = "clocked_in"
    else:
        set_ops["clock_out_at"] = new_out.isoformat()
        hours = round((new_out - new_in).total_seconds() / 3600.0, 2)
        set_ops["hours_worked"] = hours

        # Recompute earnings using the resolved pay (which respects per-gig
        # override → worker default → gig posted precedence)
        gig = await db.gigs.find_one({"gig_id": gig_id})
        worker = await db.users.find_one({"user_id": acceptance["worker_id"]})
        pay = _resolve_pay(acceptance, worker, gig)

        # Per-worker break override (minutes) — if provided, apply now so we
        # can include it in the recompute below
        if payload.break_minutes is not None:
            if payload.break_minutes < 0:
                raise HTTPException(400, "break_minutes must be >= 0")
            set_ops["break_minutes"] = int(payload.break_minutes)
            effective_break = int(payload.break_minutes)
        else:
            effective_break = _resolve_break_minutes(acceptance, gig)

        set_ops["pay_rate_applied"] = pay["pay_rate"]
        set_ops["pay_type_applied"] = pay["pay_type"]
        set_ops["pay_rate_source"] = pay["pay_rate_source"]
        set_ops["pay_type_source"] = pay["pay_type_source"]
        set_ops["break_minutes_applied"] = effective_break
        set_ops["paid_hours"] = _compute_paid_hours(hours, effective_break)
        set_ops["earnings"] = _compute_earnings(pay["pay_rate"], pay["pay_type"], hours, effective_break)
        set_ops["earnings_manual_override"] = False
        set_ops["status"] = "completed"

    ops: dict = {"$set": set_ops}
    if unset_ops:
        ops["$unset"] = unset_ops
    await db.gig_acceptances.update_one({"acceptance_id": acceptance_id}, ops)

    logger.info(
        f"Admin {admin['email']} edited timesheet {acceptance_id}: "
        f"in={set_ops.get('clock_in_at')} out={set_ops.get('clock_out_at')}"
    )
    refreshed = await db.gig_acceptances.find_one({"acceptance_id": acceptance_id}, {"_id": 0})
    return {
        "ok": True,
        "clock_in_at": refreshed.get("clock_in_at"),
        "clock_out_at": refreshed.get("clock_out_at"),
        "hours_worked": refreshed.get("hours_worked"),
        "earnings": refreshed.get("earnings"),
        "status": refreshed.get("status"),
    }




# ----------------------------------------------------------------------------
# Projects — bundle 2+ gigs that share a job site so crews can coordinate
# ----------------------------------------------------------------------------

def _serialize_project(p: dict) -> dict:
    """Strip Mongo's _id and return the safe view."""
    out = {k: v for k, v in p.items() if k != "_id"}
    out.setdefault("defaults", {})
    out.setdefault("notes", [])
    out.setdefault("archived", False)
    return out


def _apply_project_defaults_to_gig(gig_payload: dict, defaults: dict) -> dict:
    """Pre-fill the optional fields on a new gig from the project defaults.
    Returns a new dict (does not mutate the input). Only fills fields that
    are empty/None on the gig payload — never overwrites explicit values."""
    if not defaults:
        return gig_payload
    merged = dict(gig_payload)
    for key in ("location", "address_line", "scheduled_date", "scheduled_at",
                "payment_timeline", "payment_timeline_note", "contact_phone"):
        if defaults.get(key) and not merged.get(key):
            merged[key] = defaults[key]
    return merged


@api.post("/projects")
async def create_project(payload: ProjectIn, admin: dict = Depends(require_admin)):
    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    doc = {
        "project_id": project_id,
        "title": payload.title.strip(),
        "description": payload.description or "",
        "client_name": (payload.client_name or "").strip() or None,
        "defaults": payload.defaults.model_dump() if payload.defaults else {},
        "notes": [],
        "archived": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": admin["user_id"],
    }
    await db.projects.insert_one(doc)
    return _serialize_project(doc)


@api.get("/projects")
async def list_projects(
    archived: bool = Query(False),
    q: Optional[str] = Query(None),
    admin: dict = Depends(require_admin),
):
    """List projects with linked-gig + crew counts. `q` filters by title or client."""
    query: dict = {"archived": archived}
    if q and q.strip():
        rx = {"$regex": q.strip(), "$options": "i"}
        query["$or"] = [{"title": rx}, {"client_name": rx}]
    projects = await db.projects.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    if not projects:
        return []
    pids = [p["project_id"] for p in projects]
    gigs = await db.gigs.find({"project_id": {"$in": pids}}, {"_id": 0, "gig_id": 1, "project_id": 1, "status": 1, "slots": 1, "slots_filled": 1, "scheduled_at": 1}).to_list(2000)
    gig_ids_by_proj: Dict[str, List[str]] = {}
    slots_by_proj: Dict[str, Dict[str, int]] = {}
    dates_by_proj: Dict[str, List[str]] = {}
    for g in gigs:
        gig_ids_by_proj.setdefault(g["project_id"], []).append(g["gig_id"])
        s = slots_by_proj.setdefault(g["project_id"], {"slots": 0, "filled": 0})
        s["slots"] += int(g.get("slots") or 0)
        s["filled"] += int(g.get("slots_filled") or 0)
        if g.get("scheduled_at"):
            dates_by_proj.setdefault(g["project_id"], []).append(g["scheduled_at"])
    # Crew counts via acceptances
    accs = await db.gig_acceptances.find(
        {"gig_id": {"$in": [g["gig_id"] for g in gigs]}, "status": {"$in": ["accepted", "on_the_clock", "clocked_in", "completed"]}},
        {"_id": 0, "gig_id": 1, "worker_id": 1},
    ).to_list(5000)
    worker_set_by_proj: Dict[str, set] = {}
    gig_to_proj = {g["gig_id"]: g["project_id"] for g in gigs}
    for a in accs:
        pid = gig_to_proj.get(a["gig_id"])
        if pid:
            worker_set_by_proj.setdefault(pid, set()).add(a["worker_id"])
    out = []
    for p in projects:
        pid = p["project_id"]
        dates = sorted(dates_by_proj.get(pid, []))
        out.append({
            **_serialize_project(p),
            "gig_count": len(gig_ids_by_proj.get(pid, [])),
            "worker_count": len(worker_set_by_proj.get(pid, set())),
            "slots_total": slots_by_proj.get(pid, {}).get("slots", 0),
            "slots_filled": slots_by_proj.get(pid, {}).get("filled", 0),
            "first_scheduled_at": dates[0] if dates else None,
            "last_scheduled_at": dates[-1] if dates else None,
        })
    return out


@api.get("/projects/{project_id}")
async def get_project(project_id: str, admin: dict = Depends(require_admin)):
    """Full project: details + linked gigs + combined roster (admin view)."""
    proj = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not proj:
        raise HTTPException(404, "Project not found")
    gigs = await db.gigs.find({"project_id": project_id}, {"_id": 0}).sort("scheduled_at", 1).to_list(500)
    gig_ids = [g["gig_id"] for g in gigs]
    accs = await db.gig_acceptances.find({"gig_id": {"$in": gig_ids}}, {"_id": 0}).to_list(2000)
    worker_ids = list({a["worker_id"] for a in accs})
    workers = await db.users.find(
        {"user_id": {"$in": worker_ids}},
        {"_id": 0, "user_id": 1, "name": 1, "email": 1, "phone": 1, "first_name": 1, "last_name": 1},
    ).to_list(2000)
    wmap = {w["user_id"]: w for w in workers}
    gtitle = {g["gig_id"]: g.get("title") for g in gigs}
    gcat = {g["gig_id"]: g.get("category") for g in gigs}
    crew = []
    for a in accs:
        if a.get("status") not in ("accepted", "on_the_clock", "clocked_in", "completed", "requested"):
            continue
        w = wmap.get(a["worker_id"]) or {}
        crew.append({
            "acceptance_id": a["acceptance_id"],
            "gig_id": a["gig_id"],
            "gig_title": gtitle.get(a["gig_id"]),
            "gig_category": gcat.get(a["gig_id"]),
            "worker_id": a["worker_id"],
            "worker_name": w.get("name") or (
                f"{w.get('first_name','')} {w.get('last_name','')}".strip()
            ),
            "worker_email": w.get("email"),
            "worker_phone": w.get("phone"),
            "gig_role": a.get("gig_role") or "worker",
            "status": a.get("status"),
        })
    return {
        **_serialize_project(proj),
        "gigs": gigs,
        "crew": crew,
    }


@api.put("/projects/{project_id}")
async def update_project(project_id: str, payload: ProjectPatch, admin: dict = Depends(require_admin)):
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return await get_project(project_id, admin)
    if "defaults" in updates and updates["defaults"] is not None:
        # Already a dict via model_dump; keep as-is
        pass
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    updates["updated_by"] = admin["email"]
    r = await db.projects.update_one({"project_id": project_id}, {"$set": updates})
    if r.matched_count == 0:
        raise HTTPException(404, "Project not found")
    return await get_project(project_id, admin)


@api.delete("/projects/{project_id}")
async def archive_project(project_id: str, admin: dict = Depends(require_admin)):
    """Soft-archive a project and unlink all child gigs (gigs keep existing)."""
    proj = await db.projects.find_one({"project_id": project_id})
    if not proj:
        raise HTTPException(404, "Project not found")
    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {"archived": True, "archived_at": datetime.now(timezone.utc).isoformat()}},
    )
    await db.gigs.update_many({"project_id": project_id}, {"$set": {"project_id": None}})
    return {"ok": True, "unlinked_gigs": True}


@api.get("/projects/{project_id}/worker-view")
async def get_project_worker_view(
    project_id: str, user: dict = Depends(get_current_user)
):
    """Read-only project view for workers. Project structure (title, gigs,
    roles, slots) is visible to ANY logged-in worker so they can shop the
    feed. Crew identity (first names + roles per gig) is only revealed once
    the requesting worker is APPROVED on at least one project gig — matches
    the same gate as the per-gig 'You're working alongside' card."""
    if user.get("role") not in ("worker", "admin"):
        raise HTTPException(403, "Workers and admins only")

    proj = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not proj or proj.get("archived"):
        raise HTTPException(404, "Project not found")

    # Pull every gig linked to this project
    gigs = await db.gigs.find({"project_id": project_id}, {"_id": 0}).sort(
        "scheduled_at", 1
    ).to_list(200)
    if not gigs:
        return {
            "project_id": project_id,
            "title": proj.get("title"),
            "description": proj.get("description") or "",
            "scheduled_window": None,
            "linked_gigs": [],
            "crew_visible": False,
            "my_gigs": [],
        }

    # The worker's own acceptances across the project's gigs
    my_acceptances = []
    if user.get("role") == "worker":
        my_acceptances = await db.gig_acceptances.find(
            {
                "worker_id": user["user_id"],
                "gig_id": {"$in": [g["gig_id"] for g in gigs]},
            },
            {"_id": 0},
        ).to_list(200)
    my_acc_by_gig = {a["gig_id"]: a for a in my_acceptances}

    # Worker can see crew identity only if they're already approved on at
    # least one project gig (status that isn't 'requested').
    approved_statuses = {"accepted", "on_the_clock", "clocked_in", "completed"}
    crew_visible = (
        user.get("role") == "admin"
        or any(a.get("status") in approved_statuses for a in my_acceptances)
    )

    # Approved roster for every project gig (PII stripped — first name only)
    crew_by_gig: Dict[str, List[dict]] = {}
    if crew_visible:
        all_accs = await db.gig_acceptances.find(
            {
                "gig_id": {"$in": [g["gig_id"] for g in gigs]},
                "status": {"$in": list(approved_statuses)},
            },
            {"_id": 0, "gig_id": 1, "worker_id": 1, "gig_role": 1, "status": 1},
        ).to_list(2000)
        wids = list({a["worker_id"] for a in all_accs})
        wlookup = await db.users.find(
            {"user_id": {"$in": wids}},
            {"_id": 0, "user_id": 1, "name": 1, "first_name": 1, "last_name": 1},
        ).to_list(2000)
        wmap = {w["user_id"]: w for w in wlookup}
        for a in all_accs:
            w = wmap.get(a["worker_id"]) or {}
            first = (
                w.get("first_name")
                or (w.get("name") or "").split()[0]
                or "Crew"
            )
            crew_by_gig.setdefault(a["gig_id"], []).append(
                {
                    "first_name": first,
                    "gig_role": a.get("gig_role") or "worker",
                    "is_me": a["worker_id"] == user.get("user_id"),
                    "status": a.get("status"),
                }
            )

    # Build the gig list with worker-safe fields only
    safe_gigs = []
    my_gig_titles = []
    for g in gigs:
        mine = my_acc_by_gig.get(g["gig_id"])
        slots_open = max(0, (g.get("slots") or 0) - (g.get("slots_filled") or 0))
        is_approved_here = mine and mine.get("status") in approved_statuses
        safe_gigs.append(
            {
                "gig_id": g["gig_id"],
                "title": g.get("title"),
                "category": g.get("category"),
                "subcategory": g.get("subcategory"),
                "description_snippet": (g.get("description") or "")[:200],
                "scheduled_date": g.get("scheduled_date"),
                "scheduled_at": g.get("scheduled_at"),
                # Public location only (city/state) — never the address line
                "location": g.get("location"),
                "slots": g.get("slots") or 0,
                "slots_filled": g.get("slots_filled") or 0,
                "slots_open": slots_open,
                "pay_rate": g.get("pay_rate"),
                "pay_type": g.get("pay_type"),
                "status": g.get("status"),
                "tags": g.get("tags") or [],
                "is_rush": bool(g.get("is_rush")),
                "my_acceptance_status": mine.get("status") if mine else None,
                "my_gig_role": mine.get("gig_role") if mine else None,
                "approved_crew": crew_by_gig.get(g["gig_id"], [])
                if crew_visible
                else None,
                "approved_count": len(crew_by_gig.get(g["gig_id"], []))
                if crew_visible
                else g.get("slots_filled") or 0,
            }
        )
        if is_approved_here:
            my_gig_titles.append(g.get("title"))

    # Scheduled window (earliest → latest gig date)
    dates = [g.get("scheduled_at") for g in gigs if g.get("scheduled_at")]
    window = None
    if dates:
        window = {"start": min(dates), "end": max(dates)}

    return {
        "project_id": project_id,
        "title": proj.get("title"),
        "description": proj.get("description") or "",
        "scheduled_window": window,
        "linked_gigs": safe_gigs,
        "crew_visible": crew_visible,
        "my_gigs": my_gig_titles,
    }


@api.post("/projects/{project_id}/notes")
async def add_project_note(project_id: str, payload: ProjectNoteIn, admin: dict = Depends(require_admin)):
    if not payload.text or not payload.text.strip():
        raise HTTPException(400, "Note text is required")
    proj = await db.projects.find_one({"project_id": project_id})
    if not proj:
        raise HTTPException(404, "Project not found")
    note = {
        "note_id": f"note_{uuid.uuid4().hex[:12]}",
        "author_id": admin["user_id"],
        "author_name": admin.get("name") or admin.get("email"),
        "text": payload.text.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.projects.update_one(
        {"project_id": project_id},
        {"$push": {"notes": note}},
    )
    return note


@api.delete("/projects/{project_id}/notes/{note_id}")
async def delete_project_note(project_id: str, note_id: str, admin: dict = Depends(require_admin)):
    r = await db.projects.update_one(
        {"project_id": project_id},
        {"$pull": {"notes": {"note_id": note_id}}},
    )
    if r.modified_count == 0:
        raise HTTPException(404, "Note not found")
    return {"ok": True}


@api.post("/gigs/{gig_id}/link-to-project")
async def link_gig_to_project(gig_id: str, payload: LinkGigToProjectIn, admin: dict = Depends(require_admin)):
    """Attach an existing gig to a project. Optionally pull the project's
    defaults onto the gig in the same call."""
    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")
    proj = await db.projects.find_one({"project_id": payload.project_id})
    if not proj:
        raise HTTPException(404, "Project not found")
    updates: dict = {"project_id": payload.project_id}
    if payload.sync_defaults:
        # Always overwrite when admin opts in
        d = proj.get("defaults") or {}
        for key in ("location", "address_line", "scheduled_date", "scheduled_at",
                    "payment_timeline", "payment_timeline_note", "contact_phone"):
            if d.get(key) is not None:
                updates[key] = d[key]
    await db.gigs.update_one({"gig_id": gig_id}, {"$set": updates})
    return {"ok": True, "project_id": payload.project_id}


@api.delete("/gigs/{gig_id}/project")
async def unlink_gig_from_project(gig_id: str, admin: dict = Depends(require_admin)):
    r = await db.gigs.update_one({"gig_id": gig_id}, {"$set": {"project_id": None}})
    if r.matched_count == 0:
        raise HTTPException(404, "Gig not found")
    return {"ok": True}


def _format_project_email(project: dict, gigs: list, base_url: str = "") -> str:
    base = (base_url or _resolve_public_base()).rstrip("/")
    rows = []
    for g in gigs:
        pay = (
            f"${g['pay_rate']:.0f}/hr"
            if g.get("pay_type") == "hourly"
            else f"${g['pay_rate']:.0f}"
        )
        slots_open = max(0, (g.get("slots") or 0) - (g.get("slots_filled") or 0))
        gig_url = f"{base}/gigs/{g.get('gig_id')}"
        rows.append(
            f"<li style='margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid #F3F4F6;'>"
            f"<div style='font-weight:bold;color:#030712;font-size:15px'>{g.get('title', '')}</div>"
            f"<div style='color:#4B5563;font-size:13px;margin:2px 0 6px;'>"
            f"{g.get('category', '').title()}"
            f"{' · ' + g.get('subcategory') if g.get('subcategory') else ''} · "
            f"{g.get('scheduled_date') or 'TBD'} · {pay} · {slots_open} spot{'' if slots_open == 1 else 's'} open"
            f"</div>"
            f"<a href='{gig_url}' target='_blank' style='display:inline-block;padding:8px 14px;background:#030712;color:#FFFFFF;font-size:12px;font-weight:bold;letter-spacing:.04em;text-decoration:none;text-transform:uppercase;'>"
            f"View this gig →"
            f"</a>"
            f"</li>"
        )
    rows_html = "<ul style='padding-left:0;list-style:none;margin:14px 0'>" + "".join(rows) + "</ul>"
    feed_url = f"{base}/crew"
    return (
        f"<div style='font-family:Inter,Arial,sans-serif;max-width:600px;padding:20px;background:#F9FAFB'>"
        f"<div style='background:#FFFFFF;border:1px solid #E5E7EB;padding:24px;'>"
        f"<div style='font-size:11px;letter-spacing:2px;color:#0044FF;font-weight:bold'>NEW PROJECT · HCOB NETWORK</div>"
        f"<h2 style='margin:6px 0 0 0;font-weight:900;font-size:24px;color:#030712'>{project.get('title', '')}</h2>"
        f"<div style='color:#4B5563;font-size:13px;margin-top:4px'>"
        f"{len(gigs)} gig{'' if len(gigs) == 1 else 's'} available · {(project.get('defaults') or {}).get('location') or 'Baltimore, MD'}"
        f"</div>"
        f"<div style='font-size:11px;letter-spacing:2px;color:#4B5563;margin-top:18px;font-weight:bold'>ROLES AVAILABLE</div>"
        f"{rows_html}"
        f"<table cellpadding='0' cellspacing='0' style='margin-top:8px'>"
        f"<tr><td bgcolor='#0044FF'>"
        f"<a href='{feed_url}' target='_blank' style='display:inline-block;padding:14px 28px;background:#0044FF;color:#FFFFFF;font-size:15px;font-weight:bold;letter-spacing:.04em;text-decoration:none;text-transform:uppercase;'>"
        f"Open the full feed →"
        f"</a></td></tr></table>"
        f"<p style='font-size:12px;color:#6B7280;margin-top:14px;'>"
        f"Or open this link on your phone:<br/>"
        f"<a href='{feed_url}' style='color:#0044FF;word-break:break-all;'>{feed_url}</a>"
        f"</p>"
        f"</div>"
        f"</div>"
    )


def _format_project_sms(project: dict, gigs: list, base_url: str = "") -> str:
    # Build a compact summary. Twilio accepts 1600 char multipart SMS but we
    # keep this under ~320 to land as a single message most of the time.
    base = (base_url or _resolve_public_base()).rstrip("/")
    title = project.get("title") or "Project"
    n = len(gigs)
    roles = []
    for g in gigs[:4]:
        # Use subcategory if present, otherwise the short title
        roles.append((g.get("subcategory") or g.get("title") or "").strip()[:30])
    role_str = ", ".join([r for r in roles if r])
    if len(gigs) > 4:
        role_str += f", +{len(gigs) - 4} more"
    loc = (project.get("defaults") or {}).get("location") or "Baltimore, MD"
    pays = [g.get("pay_rate") or 0 for g in gigs if g.get("pay_rate")]
    pay_line = f" Pay from ${min(pays):.0f}/hr." if pays else ""
    # For single-gig projects, deep-link straight to that gig; otherwise drop
    # them into the feed where the project-pill helps them find the right one.
    link = (
        f"{base}/gigs/{gigs[0].get('gig_id')}"
        if len(gigs) == 1 and gigs[0].get("gig_id")
        else f"{base}/crew"
    )
    return (
        f"[HCOB Project] {title} — {loc}. {n} gig{'s' if n != 1 else ''}: {role_str}."
        f"{pay_line} Tap to claim: {link}"
    )


@api.post("/projects/{project_id}/blast")
async def blast_project(
    project_id: str,
    payload: BlastIn,
    request: Request,
    admin: dict = Depends(require_admin),
):
    """Send ONE consolidated notification about a multi-gig project to every
    worker. Each linked gig is also auto-flagged as RUSH (consistent with the
    individual gig-blast endpoint) so the project's gigs float to the top of
    the feed."""
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(404, "Project not found")
    if project.get("archived"):
        raise HTTPException(400, "Cannot blast an archived project")

    # Be permissive about what counts as blastable — we want any non-terminal
    # gig that still has at least one available slot to count. Legacy gigs
    # that predate the status field have `status` missing/None, so we exclude
    # by terminal statuses rather than including by an allow-list.
    TERMINAL_STATUSES = {"closed", "cancelled", "completed", "archived", "draft"}
    all_linked = await db.gigs.find(
        {"project_id": project_id}, {"_id": 0}
    ).to_list(500)
    blastable_gigs = []
    excluded = {"terminal_status": 0, "no_slots": 0}
    for g in all_linked:
        st = (g.get("status") or "").strip().lower()
        if st in TERMINAL_STATUSES:
            excluded["terminal_status"] += 1
            continue
        slots = g.get("slots") or 0
        filled = g.get("slots_filled") or 0
        if slots > 0 and (slots - filled) <= 0:
            excluded["no_slots"] += 1
            continue
        blastable_gigs.append(g)

    if not blastable_gigs:
        # Surface diagnostic info — helps the admin understand WHY no gigs
        # qualified instead of staring at a generic error.
        total = len(all_linked)
        bits = []
        if excluded["terminal_status"]:
            bits.append(
                f"{excluded['terminal_status']} gig(s) are closed/cancelled/completed"
            )
        if excluded["no_slots"]:
            bits.append(
                f"{excluded['no_slots']} gig(s) have no available slots"
            )
        why = " · ".join(bits) if bits else "the project has no linked gigs yet"
        raise HTTPException(
            400,
            f"Nothing to blast — {why}. (Linked gigs: {total}.) "
            f"Add a gig or reopen an existing one.",
        )

    workers = await db.users.find(
        {"role": "worker"}, {"_id": 0, "password_hash": 0}
    ).to_list(1000)

    email_creds = await _resolve_email_creds() if "email" in payload.channels else None
    sms_creds = await _resolve_sms_creds() if "sms" in payload.channels else None

    counts = {"in_app": 0, "email": 0, "sms": 0, "push": 0, "email_failed": 0, "sms_failed": 0}
    subject = f"New Project: {project.get('title')}"
    base_url = _resolve_public_base(request)
    html = _format_project_email(project, blastable_gigs, base_url)
    sms_body = _format_project_sms(project, blastable_gigs, base_url)
    # Project push deep-links to the dedicated worker project view so the
    # crew can scan every role + crew chip in one tap.
    project_url = f"/crew/projects/{project_id}"
    n = len(blastable_gigs)
    push_payload = {
        "title": f"New project: {project.get('title')}",
        "body": (
            f"{n} gig{'s' if n != 1 else ''} available · "
            f"{(project.get('defaults') or {}).get('location') or 'Baltimore, MD'}"
        ),
        "tag": f"project-{project_id}",
        "url": project_url,
        "kind": "project",
        "rush": True,
    }

    notif_docs = []
    for w in workers:
        if "in_app" in payload.channels:
            notif_docs.append(
                {
                    "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
                    "user_id": w["user_id"],
                    "project_id": project_id,
                    "gig_id": None,
                    "title": subject,
                    "body": f"{len(blastable_gigs)} gigs available — {project.get('title')}",
                    "read": False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            counts["in_app"] += 1
        if "email" in payload.channels and w.get("email") and email_creds:
            try:
                await asyncio.to_thread(
                    _send_email_sync,
                    email_creds["api_key"],
                    email_creds["sender"],
                    w["email"],
                    subject,
                    html,
                )
                counts["email"] += 1
            except Exception as e:
                logger.error(f"Project email send failed for {w['email']}: {e}")
                counts["email_failed"] += 1
        if "sms" in payload.channels and w.get("phone") and sms_creds:
            try:
                await asyncio.to_thread(
                    _send_sms_sync,
                    sms_creds["sid"],
                    sms_creds["token"],
                    sms_creds["from_"],
                    w["phone"],
                    sms_body,
                )
                counts["sms"] += 1
            except Exception as e:
                logger.error(f"Project SMS send failed for {w.get('phone')}: {e}")
                counts["sms_failed"] += 1
        if "push" in payload.channels and VAPID_PRIVATE_KEY:
            sent = await _send_push_to_user(w["user_id"], push_payload)
            counts["push"] += sent

    if notif_docs:
        await db.notifications.insert_many(notif_docs)

    # Auto-pin all blasted gigs to the top of the feed by flipping is_rush=True
    # and adding the "rush" tag (matches single-gig blast behavior).
    now_iso = datetime.now(timezone.utc).isoformat()
    for g in blastable_gigs:
        existing_tags = [t for t in (g.get("tags") or []) if t in GIG_TAG_VALUES]
        if "rush" not in existing_tags:
            existing_tags.insert(0, "rush")
        await db.gigs.update_one(
            {"gig_id": g["gig_id"]},
            {
                "$set": {
                    "last_blast_at": now_iso,
                    "blast_channels": payload.channels,
                    "is_rush": True,
                    "rush_at": now_iso,
                    "tags": existing_tags,
                },
                "$inc": {"blast_count": 1},
            },
        )

    # Track on the project doc itself.
    await db.projects.update_one(
        {"project_id": project_id},
        {
            "$set": {"last_blast_at": now_iso, "last_blast_channels": payload.channels},
            "$inc": {"blast_count": 1},
        },
    )

    return {
        "ok": True,
        "counts": counts,
        "workers_targeted": len(workers),
        "gigs_blasted": len(blastable_gigs),
    }


# ----------------------------------------------------------------------------
# Worker ratings — admin manual stars + public client feedback link
# ----------------------------------------------------------------------------
@api.put("/gigs/{gig_id}/acceptances/{acceptance_id}/rating")
async def admin_set_rating(
    gig_id: str,
    acceptance_id: str,
    payload: AdminRatingIn,
    admin: dict = Depends(require_admin),
):
    """Admin sets a 1-5 star rating + optional private note for a worker on a
    specific gig. Pass `clear=true` to remove the rating."""
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Acceptance not found")

    set_ops: dict = {}
    unset_ops: dict = {}
    if payload.clear:
        unset_ops["admin_rating"] = ""
        unset_ops["admin_rating_note"] = ""
        unset_ops["admin_rating_at"] = ""
        unset_ops["admin_rating_by"] = ""
    else:
        if payload.stars is None:
            raise HTTPException(400, "stars (1-5) required unless clear=true")
        if payload.stars < 1 or payload.stars > 5:
            raise HTTPException(400, "stars must be between 1 and 5")
        set_ops["admin_rating"] = int(payload.stars)
        set_ops["admin_rating_at"] = datetime.now(timezone.utc).isoformat()
        set_ops["admin_rating_by"] = admin["email"]
        if payload.note is not None:
            set_ops["admin_rating_note"] = payload.note

    ops: dict = {}
    if set_ops:
        ops["$set"] = set_ops
    if unset_ops:
        ops["$unset"] = unset_ops
    await db.gig_acceptances.update_one({"acceptance_id": acceptance_id}, ops)
    logger.info(
        f"Admin {admin['email']} set rating {payload.stars} on {acceptance_id}"
    )
    return {"ok": True, "admin_rating": set_ops.get("admin_rating")}



@api.put("/gigs/{gig_id}/acceptances/{acceptance_id}/admin-note")
async def admin_set_gig_note(
    gig_id: str,
    acceptance_id: str,
    payload: AdminGigNoteIn,
    admin: dict = Depends(require_admin),
):
    """Per-gig private admin note about this worker on this gig. Separate
    from the rating note. Pass an empty string or null to clear."""
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Acceptance not found")
    text = (payload.note or "").strip()
    if not text:
        await db.gig_acceptances.update_one(
            {"acceptance_id": acceptance_id},
            {
                "$unset": {
                    "admin_gig_note": "",
                    "admin_gig_note_at": "",
                    "admin_gig_note_by": "",
                }
            },
        )
    else:
        await db.gig_acceptances.update_one(
            {"acceptance_id": acceptance_id},
            {
                "$set": {
                    "admin_gig_note": text,
                    "admin_gig_note_at": datetime.now(timezone.utc).isoformat(),
                    "admin_gig_note_by": admin["email"],
                }
            },
        )
    return {"ok": True}


@api.post("/admin/workers/{user_id}/message")
async def admin_send_worker_message(
    user_id: str,
    payload: WorkerMessageIn,
    admin: dict = Depends(require_admin),
):
    """Drop a notification into the worker's inbox. Surfaces in /notifications
    and (if gig_id provided) is visible on that gig's detail page."""
    worker = await db.users.find_one({"user_id": user_id})
    if not worker or worker.get("role") != "worker":
        raise HTTPException(404, "Worker not found")
    body = (payload.body or "").strip()
    if not body:
        raise HTTPException(400, "Message body required")
    title = (payload.title or "Message from HCOB").strip()
    if payload.gig_id:
        gig = await db.gigs.find_one({"gig_id": payload.gig_id}, {"_id": 0, "title": 1})
        if gig and not payload.title:
            title = f"Note for: {gig.get('title')}"

    notif_id = f"ntf_{uuid.uuid4().hex[:12]}"
    await db.notifications.insert_one(
        {
            "notification_id": notif_id,
            "user_id": user_id,
            "gig_id": payload.gig_id,
            "title": title,
            "body": body,
            "from_admin": admin["email"],
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    logger.info(
        f"Admin {admin['email']} sent message to worker {worker.get('email')}: {title}"
    )
    return {"ok": True, "notification_id": notif_id}




@api.put("/gigs/{gig_id}/acceptances/{acceptance_id}/role")
async def admin_set_gig_role(
    gig_id: str,
    acceptance_id: str,
    payload: AcceptanceRoleIn,
    admin: dict = Depends(require_admin),
):
    """Set a worker's per-gig role (worker / manager / lead / trainer).
    Workers see their role + their crew's roles after they're approved."""
    if payload.role not in GIG_ROLES:
        raise HTTPException(400, f"role must be one of {GIG_ROLES}")
    res = await db.gig_acceptances.update_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id},
        {"$set": {"gig_role": payload.role}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Acceptance not found")
    return {"ok": True, "gig_role": payload.role}


@api.get("/public/gigs/{gig_id}")
async def public_gig_lookup(gig_id: str):
    """Public no-auth view of a gig — used by direct share links. Strips the
    private address line; the rest is the same info workers see when browsing.
    Returns 404 for cancelled gigs."""
    gig = await db.gigs.find_one({"gig_id": gig_id}, {"_id": 0})
    if not gig:
        raise HTTPException(404, "Gig not found")
    if gig.get("status") == "cancelled":
        raise HTTPException(404, "Gig is no longer available")
    # Strip sensitive fields
    safe = {
        "gig_id": gig["gig_id"],
        "title": gig.get("title"),
        "description": gig.get("description"),
        "category": gig.get("category"),
        "subcategory": gig.get("subcategory"),
        "location": gig.get("location"),
        "scheduled_date": gig.get("scheduled_date"),
        "scheduled_at": gig.get("scheduled_at"),
        "start_time": gig.get("start_time"),
        "duration_hours": gig.get("duration_hours"),
        "pay_rate": gig.get("pay_rate"),
        "pay_type": gig.get("pay_type"),
        "payment_timeline": gig.get("payment_timeline") or "2_3_days",
        "payment_timeline_note": gig.get("payment_timeline_note"),
        "slots": gig.get("slots"),
        "slots_filled": gig.get("slots_filled"),
        "status": gig.get("status"),
    }
    return safe


# --- HTML escape helper for the OG share endpoint ---
def _html_escape(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


@api.get("/share/gigs/{gig_id}", response_class=HTMLResponse)
async def share_gig_og(gig_id: str, request: Request):
    """Server-rendered HTML page with Open Graph + Twitter Card meta tags so
    that social previews (iMessage, Slack, WhatsApp, Facebook, Twitter, LinkedIn)
    unfurl with the gig's title, category, pay, and a branded image.

    Real browsers see a meta-refresh to `/gigs/{gig_id}` so they land on the
    React app immediately. Bots that just scrape the head will read the tags."""
    gig = await db.gigs.find_one({"gig_id": gig_id}, {"_id": 0})
    # Use proxy-forwarded headers if present so the canonical host matches the
    # public URL (not the internal cluster hostname FastAPI sees). Falls back
    # to env vars, then request.base_url.
    fwd_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    fwd_proto = request.headers.get("x-forwarded-proto") or "https"
    if fwd_host:
        base = f"{fwd_proto}://{fwd_host}"
    else:
        base = (
            os.environ.get("PUBLIC_BASE_URL")
            or str(request.base_url).rstrip("/")
        )
    base = base.rstrip("/")
    canonical = f"{base}/api/share/gigs/{gig_id}"
    react_url = f"{base}/gigs/{gig_id}"
    og_image = f"{base}/og-default.png"

    if not gig or gig.get("status") == "cancelled":
        title = "Gig no longer available — HCOB Network"
        desc = "This gig has been filled or removed. See open gigs at HCOB Network."
        html = f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{_html_escape(title)}</title>
<meta name="description" content="{_html_escape(desc)}" />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="HCOB Network" />
<meta property="og:title" content="{_html_escape(title)}" />
<meta property="og:description" content="{_html_escape(desc)}" />
<meta property="og:image" content="{og_image}" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta property="og:url" content="{canonical}" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{_html_escape(title)}" />
<meta name="twitter:description" content="{_html_escape(desc)}" />
<meta name="twitter:image" content="{og_image}" />
<meta http-equiv="refresh" content="0;url={react_url}" />
<link rel="canonical" href="{canonical}" />
</head><body><p>Redirecting… <a href="{react_url}">View on HCOB Network</a>.</p></body></html>"""
        return HTMLResponse(content=html, status_code=200)

    title_raw = gig.get("title") or "HCOB Network Gig"
    category = (gig.get("category") or "").title()
    sub = (gig.get("subcategory") or "").replace("_", " ")
    pay = gig.get("pay_rate")
    pay_type = gig.get("pay_type") or "hourly"
    location = gig.get("location") or "Baltimore, MD"
    scheduled = gig.get("scheduled_date") or "TBD"
    pay_str = f"${pay:.0f}{'/hr' if pay_type == 'hourly' else ' flat'}" if pay else ""

    title_full = f"{title_raw} — {pay_str} · {location} · HCOB Network"
    parts = [category]
    if sub and sub != "general":
        parts.append(sub)
    if pay_str:
        parts.append(pay_str)
    parts.append(location)
    parts.append(f"Scheduled {scheduled}")
    desc = " · ".join(parts) + ". Apply on HCOB Network."

    # Use the dynamic OG image if available; otherwise fall back to default
    dynamic_og_image = f"{base}/api/share/gigs/{gig_id}/og-image"

    html = f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{_html_escape(title_full)}</title>
<meta name="description" content="{_html_escape(desc)}" />
<meta name="theme-color" content="#0044FF" />

<meta property="og:type" content="website" />
<meta property="og:site_name" content="HCOB Network" />
<meta property="og:title" content="{_html_escape(title_raw)} — {_html_escape(pay_str)}" />
<meta property="og:description" content="{_html_escape(desc)}" />
<meta property="og:image" content="{dynamic_og_image}" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta property="og:image:alt" content="{_html_escape(title_raw)} on HCOB Network" />
<meta property="og:url" content="{canonical}" />
<meta property="og:locale" content="en_US" />

<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{_html_escape(title_raw)} — {_html_escape(pay_str)}" />
<meta name="twitter:description" content="{_html_escape(desc)}" />
<meta name="twitter:image" content="{dynamic_og_image}" />

<link rel="canonical" href="{canonical}" />
<link rel="icon" href="/favicon.ico" />
<meta http-equiv="refresh" content="0;url={react_url}" />
<style>body{{margin:0;padding:64px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#030712;color:#fff;text-align:center;}}a{{color:#0044FF;}}</style>
</head>
<body>
<h1>Redirecting to HCOB Network…</h1>
<p>If you are not redirected automatically, <a href="{react_url}">click here to view this gig</a>.</p>
<script>window.location.replace("{react_url}");</script>
</body></html>"""
    return HTMLResponse(content=html, status_code=200)


@api.get("/share/gigs/{gig_id}/og-image", response_class=Response)
async def share_gig_og_image(gig_id: str):
    """Dynamically rendered 1200x630 PNG for the gig's social preview. Falls
    back to the default site OG image if the gig is missing/cancelled or PIL
    fails for any reason."""
    gig = await db.gigs.find_one({"gig_id": gig_id}, {"_id": 0})
    fallback_path = "/app/frontend/public/og-default.png"
    if not gig or gig.get("status") == "cancelled":
        try:
            with open(fallback_path, "rb") as f:
                return Response(content=f.read(), media_type="image/png")
        except FileNotFoundError:
            raise HTTPException(404, "Image unavailable")

    try:
        from PIL import Image, ImageDraw, ImageFont
        import os

        def find_font(size, bold=False):
            cands = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
            for c in cands:
                if os.path.exists(c):
                    return ImageFont.truetype(c, size)
            return ImageFont.load_default()

        W, H = 1200, 630
        INK = (3, 7, 18)
        BLUE = (0, 68, 255)
        WHITE = (255, 255, 255)
        RED = (239, 68, 68)
        YELLOW = (234, 179, 8)
        ORANGE = (249, 115, 22)

        TAG_STYLE = {
            "rush": ("RUSH", RED, WHITE),
            "priority_need": ("PRIORITY", ORANGE, WHITE),
            "same_day": ("SAME DAY", YELLOW, INK),
            "top_pay": ("TOP PAY", BLUE, WHITE),
        }

        img = Image.new("RGB", (W, H), INK)
        d = ImageDraw.Draw(img)
        # Subtle grid
        for x in range(0, W, 60):
            d.line([(x, 0), (x, H)], fill=(20, 25, 40), width=1)
        for y in range(0, H, 60):
            d.line([(0, y), (W, y)], fill=(20, 25, 40), width=1)
        d.rectangle([(0, 0), (W, 8)], fill=BLUE)

        # Logo
        d.rounded_rectangle([(80, 80), (160, 160)], radius=12, fill=BLUE)
        bolt = [(130, 98), (108, 130), (122, 130), (116, 152), (140, 118), (126, 118), (132, 98)]
        d.polygon(bolt, fill=WHITE)

        # Branding text
        d.text((180, 92), "HCOB NETWORK", font=find_font(38, bold=True), fill=WHITE)
        d.text((180, 134), "DISPATCH · BALTIMORE, MD", font=find_font(18), fill=BLUE)

        # Category label
        cat = (gig.get("category") or "").upper()
        sub = (gig.get("subcategory") or "").replace("_", " ").upper()
        cat_label = f"{cat} · {sub}" if sub and sub != "GENERAL" else cat
        d.text((80, 220), cat_label, font=find_font(22, bold=True), fill=(180, 195, 215))

        # Gig title (wrapped to 2 lines)
        title = gig.get("title") or "HCOB Gig"
        font_title = find_font(76, bold=True)
        # Naive wrap by char width
        words = title.split()
        lines = []
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if d.textlength(test, font=font_title) > 1040 and cur:
                lines.append(cur)
                cur = w
            else:
                cur = test
        if cur:
            lines.append(cur)
        lines = lines[:2]
        if len(lines) == 2 and d.textlength(title, font=font_title) > 2080:
            lines[1] = lines[1][:40] + "…"
        ty = 270
        for ln in lines:
            d.text((80, ty), ln, font=font_title, fill=WHITE)
            ty += 86

        # Meta line: location · scheduled · pay
        loc = gig.get("location") or "Baltimore, MD"
        sched = gig.get("scheduled_date") or "TBD"
        pay = gig.get("pay_rate")
        pay_type = gig.get("pay_type") or "hourly"
        pay_str = f"${int(pay)}{'/hr' if pay_type == 'hourly' else ' flat'}" if pay else ""
        meta_parts = [loc, sched]
        if pay_str:
            meta_parts.append(pay_str)
        d.text((80, 470), " · ".join(meta_parts), font=find_font(28), fill=(180, 195, 215))

        # Pay block (right side, big)
        if pay_str:
            font_pay = find_font(82, bold=True)
            pw = d.textlength(pay_str, font=font_pay)
            d.text((W - 80 - pw, 250), pay_str, font=font_pay, fill=BLUE)
            d.text((W - 80 - pw + (pw - d.textlength("PAY", font=find_font(20, bold=True))) / 2, 226), "PAY", font=find_font(20, bold=True), fill=(180, 195, 215))

        # Tag pills bottom-right
        active_tags = [t for t in (gig.get("tags") or []) if t in TAG_STYLE]
        if active_tags:
            px = W - 60
            py = H - 80
            font_pill = find_font(22, bold=True)
            for t in reversed(active_tags):
                label, bg, fg = TAG_STYLE[t]
                tw = d.textlength(label, font=font_pill)
                pw_ = int(tw + 36)
                d.rounded_rectangle([(px - pw_, py), (px, py + 48)], radius=24, fill=bg)
                d.text((px - pw_ + 18, py + 12), label, font=font_pill, fill=fg)
                px -= pw_ + 12

        from io import BytesIO
        buf = BytesIO()
        img.save(buf, "PNG", optimize=True)
        return Response(content=buf.getvalue(), media_type="image/png", headers={"Cache-Control": "public, max-age=300"})
    except Exception as e:
        logger.exception("OG image generation failed for gig %s: %s", gig_id, e)
        try:
            with open(fallback_path, "rb") as f:
                return Response(content=f.read(), media_type="image/png")
        except FileNotFoundError:
            raise HTTPException(500, "Image generation failed")


@api.get("/public/gigs")
async def public_gig_feed(limit: int = Query(3, ge=1, le=24)):
    """Public no-auth feed of currently-open + upcoming gigs for the marketing
    landing page. RUSH first, then highest-paying, then newest. Address and
    contact phone are never exposed; only marketing-safe fields."""
    gigs = (
        await db.gigs.find(
            {"status": {"$in": ["open", "coming_soon"]}},
            {"_id": 0},
        )
        .sort([("is_rush", -1), ("pay_rate", -1), ("created_at", -1)])
        .to_list(limit)
    )
    return [
        {
            "gig_id": g["gig_id"],
            "title": g.get("title"),
            "category": g.get("category"),
            "subcategory": g.get("subcategory"),
            "location": g.get("location"),
            "scheduled_date": g.get("scheduled_date"),
            "scheduled_at": g.get("scheduled_at"),
            "pay_rate": g.get("pay_rate"),
            "pay_type": g.get("pay_type"),
            "payment_timeline": g.get("payment_timeline") or "2_3_days",
            "slots": g.get("slots"),
            "slots_filled": g.get("slots_filled"),
            "status": g.get("status"),
            "is_rush": bool(g.get("is_rush")),
            "tags": [t for t in (g.get("tags") or []) if t in GIG_TAG_VALUES],
        }
        for g in gigs
    ]


# ----------------------------------------------------------------------------
# Public quote-request lead capture from /customers — emails the owner with
# the lead and stores it so admins can follow up.
# ----------------------------------------------------------------------------
# Owner contact defaults. Both overridable via app_settings (Settings page).
HCOB_OWNER_PHONE = os.environ.get("HCOB_OWNER_PHONE", "+14108709347")
HCOB_OWNER_EMAIL = os.environ.get("HCOB_OWNER_EMAIL", "corymclarke7126@gmail.com")


def _format_quote_email(q: dict) -> tuple[str, str]:
    """Build a (subject, html_body) pair for the owner's lead notification."""
    rows = [
        ("Name", q.get("name")),
        ("Phone", q.get("phone")),
        ("Email", q.get("email")),
        ("Service", q.get("service")),
        ("Timeline", q.get("timeline")),
        ("Address", q.get("address")),
    ]
    table_rows = "".join(
        f"<tr><td style='padding:6px 12px;color:#4B5563;font-size:13px;width:100px'>{k}</td>"
        f"<td style='padding:6px 12px;color:#030712;font-weight:600;font-size:14px'>{v}</td></tr>"
        for k, v in rows
        if v
    )
    message_block = ""
    if q.get("message"):
        message_block = (
            f"<div style='margin-top:16px;padding:14px;background:#F9FAFB;border-left:3px solid #0044FF;color:#030712;font-size:14px;line-height:1.5'>"
            f"{q['message']}</div>"
        )
    phone_link = f"tel:{q.get('phone', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')}"
    subject = f"[HCOB Lead] {q.get('name')} — {q.get('service')} ({q.get('timeline')})"
    html = (
        f"<div style='font-family:Inter,Arial,sans-serif;max-width:600px;padding:20px;background:#F9FAFB'>"
        f"<div style='background:#FFFFFF;border:1px solid #E5E7EB;padding:24px'>"
        f"<div style='font-size:11px;letter-spacing:2px;color:#0044FF;font-weight:bold'>NEW QUOTE REQUEST · HCOB NETWORK</div>"
        f"<h2 style='margin:6px 0 16px 0;font-size:22px;color:#030712'>{q.get('name')}</h2>"
        f"<table cellspacing='0' style='border-collapse:collapse;border:1px solid #E5E7EB;width:100%'>"
        f"{table_rows}"
        f"</table>"
        f"{message_block}"
        f"<table cellpadding='0' cellspacing='0' style='margin-top:22px'><tr>"
        f"<td bgcolor='#0044FF' style='padding:0 8px 0 0'>"
        f"<a href='{phone_link}' style='display:inline-block;padding:12px 22px;background:#0044FF;color:#FFFFFF;font-size:14px;font-weight:bold;text-decoration:none'>"
        f"📞 Call {q.get('name', '').split()[0] if q.get('name') else 'them'}"
        f"</a></td>"
        f"<td bgcolor='#030712'>"
        f"<a href='https://hcobnetwork.com/ops/quotes' style='display:inline-block;padding:12px 22px;background:#030712;color:#FFFFFF;font-size:14px;font-weight:bold;text-decoration:none'>"
        f"Open lead inbox →"
        f"</a></td>"
        f"</tr></table>"
        f"<p style='font-size:11px;color:#9CA3AF;margin-top:18px'>"
        f"Lead ID: {q.get('quote_id')} · Received {q.get('created_at')}"
        f"</p>"
        f"</div></div>"
    )
    return subject, html


@api.post("/public/quote-requests")
async def create_quote_request(payload: QuoteRequestIn, request: Request):
    """Lead capture from the customer marketing page. No auth required."""
    # Honeypot — bots fill hidden fields, real users don't. Silently accept.
    if (payload.website or "").strip():
        return {"ok": True, "quote_id": "spam_ignored"}

    name = payload.name.strip()
    phone = payload.phone.strip()
    if not name or not phone:
        raise HTTPException(400, "Name and phone are required.")

    # Light rate-limit: max 5 leads per IP per hour.
    ip = (request.client.host if request.client else "") or "unknown"
    one_hour_ago = (
        datetime.now(timezone.utc) - timedelta(hours=1)
    ).isoformat()
    recent = await db.quote_requests.count_documents(
        {"ip": ip, "created_at": {"$gte": one_hour_ago}}
    )
    if recent >= 5:
        raise HTTPException(
            429,
            "Too many requests. Please call (410) 870-9347 directly — we'll help right away.",
        )

    quote_id = f"qr_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    doc = {
        "quote_id": quote_id,
        "name": name,
        "phone": phone,
        "email": (payload.email or "").strip() or None,
        "service": payload.service.strip(),
        "timeline": payload.timeline.strip(),
        "message": (payload.message or "").strip() or None,
        "address": (payload.address or "").strip() or None,
        "status": "new",
        "admin_note": None,
        "ip": ip,
        "user_agent": (request.headers.get("user-agent") or "")[:200],
        "created_at": now_iso,
        # Notification delivery status (email-first now, sms field kept for
        # backward-compat with existing admin UI).
        "notify_sent": False,
        "notify_error": None,
        "sms_sent": False,
        "sms_error": None,
    }
    await db.quote_requests.insert_one(doc)

    # Email the owner — primary delivery channel for new leads.
    settings_doc = await _get_settings_doc()
    email_creds = await _resolve_email_creds()
    owner_email = (
        (settings_doc.get("quote_notify_email") or HCOB_OWNER_EMAIL)
    ).strip()
    notify_sent = False
    notify_err = None
    if email_creds and email_creds.get("api_key") and owner_email:
        try:
            subject, html = _format_quote_email(doc)
            await asyncio.to_thread(
                _send_email_sync,
                email_creds["api_key"],
                email_creds["sender"],
                owner_email,
                subject,
                html,
            )
            notify_sent = True
        except Exception as e:
            notify_err = str(e)[:200]
            logger.error(f"Quote-request email failed for {quote_id}: {e}")
    else:
        notify_err = "no_email_creds"

    await db.quote_requests.update_one(
        {"quote_id": quote_id},
        {"$set": {"notify_sent": notify_sent, "notify_error": notify_err}},
    )

    return {
        "ok": True,
        "quote_id": quote_id,
        "message": "Thanks! We'll text or call you back shortly. For urgent needs call (410) 870-9347.",
    }


@api.get("/admin/quote-requests")
async def list_quote_requests(
    status: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    admin: dict = Depends(require_admin),
):
    q = {}
    if status:
        q["status"] = status
    rows = (
        await db.quote_requests.find(q, {"_id": 0, "ip": 0, "user_agent": 0})
        .sort("created_at", -1)
        .to_list(limit)
    )
    counts = {
        "new": await db.quote_requests.count_documents({"status": "new"}),
        "contacted": await db.quote_requests.count_documents({"status": "contacted"}),
        "won": await db.quote_requests.count_documents({"status": "won"}),
        "lost": await db.quote_requests.count_documents({"status": "lost"}),
        "dismissed": await db.quote_requests.count_documents({"status": "dismissed"}),
    }
    return {"items": rows, "counts": counts}


@api.patch("/admin/quote-requests/{quote_id}")
async def update_quote_request(
    quote_id: str, payload: QuoteRequestPatch, admin: dict = Depends(require_admin)
):
    existing = await db.quote_requests.find_one({"quote_id": quote_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Quote request not found")
    updates = {}
    if payload.status is not None:
        updates["status"] = payload.status
    if payload.admin_note is not None:
        updates["admin_note"] = payload.admin_note
    if not updates:
        return existing
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.quote_requests.update_one({"quote_id": quote_id}, {"$set": updates})
    return await db.quote_requests.find_one(
        {"quote_id": quote_id}, {"_id": 0, "ip": 0, "user_agent": 0}
    )


# ----------------------------------------------------------------------------
# Admin user management (super admins only — read-only admins blocked by
# require_admin's method check)
# ----------------------------------------------------------------------------
@api.get("/admin/admins")
async def list_admin_users(admin: dict = Depends(require_admin)):
    """List all admin users so the Settings page can show who has access."""
    rows = await db.users.find(
        {"role": "admin"}, {"_id": 0, "password_hash": 0}
    ).sort("created_at", 1).to_list(200)
    # Public-shape each row
    return [
        {
            "user_id": r["user_id"],
            "name": r.get("name"),
            "email": r.get("email"),
            "is_read_only": bool(r.get("is_read_only")),
            "created_at": r.get("created_at"),
            "is_self": r["user_id"] == admin["user_id"],
        }
        for r in rows
    ]


@api.post("/admin/admins")
async def create_admin_user(
    payload: AdminCreateIn,
    admin: dict = Depends(require_admin),
):
    """Create a new admin user. Read-only admins are blocked by the method
    check in require_admin."""
    name = (payload.name or "").strip()
    email = (payload.email or "").strip().lower()
    if not name:
        raise HTTPException(400, "Name required")
    if "@" not in email or "." not in email:
        raise HTTPException(400, "Valid email required")
    if len(payload.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(400, "An account with that email already exists")
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    doc = {
        "user_id": user_id,
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": name,
        "role": "admin",
        "is_read_only": bool(payload.is_read_only),
        "phone": "",
        "address": "",
        "bio": "",
        "skills": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "auth_provider": "local",
        "id_verified": True,  # admins don't need ID verification
    }
    await db.users.insert_one(doc)
    logger.info(
        f"Admin {admin['email']} created new admin {email} (read_only={doc['is_read_only']})"
    )
    return {
        "user_id": user_id,
        "name": name,
        "email": email,
        "is_read_only": doc["is_read_only"],
        "created_at": doc["created_at"],
    }


@api.put("/admin/admins/{user_id}")
async def update_admin_user(
    user_id: str,
    payload: AdminRoleUpdateIn,
    admin: dict = Depends(require_admin),
):
    """Toggle read-only flag on an admin OR promote a worker → admin / demote
    an admin → worker."""
    target = await db.users.find_one({"user_id": user_id})
    if not target:
        raise HTTPException(404, "User not found")

    updates: dict = {}
    if payload.promote_to_admin:
        if target.get("role") == "admin":
            raise HTTPException(400, "Already an admin")
        updates["role"] = "admin"
        updates["is_read_only"] = bool(payload.is_read_only)
    elif payload.demote_to_worker:
        if target.get("user_id") == admin["user_id"]:
            raise HTTPException(400, "You can't demote yourself")
        if target.get("role") != "admin":
            raise HTTPException(400, "Not an admin")
        updates["role"] = "worker"
        updates["is_read_only"] = False
        updates["worker_status"] = "approved"
    elif payload.is_read_only is not None:
        if target.get("role") != "admin":
            raise HTTPException(400, "Read-only flag only applies to admins")
        if target.get("user_id") == admin["user_id"] and payload.is_read_only:
            raise HTTPException(400, "You can't make yourself read-only")
        updates["is_read_only"] = bool(payload.is_read_only)
    else:
        raise HTTPException(400, "Nothing to update")

    await db.users.update_one({"user_id": user_id}, {"$set": updates})
    if updates.get("role") == "worker":
        # When demoting, drop their sessions so they re-login as worker
        await db.sessions.delete_many({"user_id": user_id})
    logger.info(f"Admin {admin['email']} updated admin {target.get('email')}: {updates}")
    return await _get_user_by_id(user_id)


@api.delete("/admin/admins/{user_id}")
async def delete_admin_user(user_id: str, admin: dict = Depends(require_admin)):
    """Demote+delete an admin account. Cannot delete yourself or the last
    full-access admin."""
    if user_id == admin["user_id"]:
        raise HTTPException(400, "You can't delete yourself")
    target = await db.users.find_one({"user_id": user_id})
    if not target or target.get("role") != "admin":
        raise HTTPException(404, "Admin not found")
    # Guardrail: never let admin count drop to 0 full-access admins
    full_count = await db.users.count_documents(
        {"role": "admin", "is_read_only": {"$ne": True}, "user_id": {"$ne": user_id}}
    )
    if full_count == 0:
        raise HTTPException(
            400, "Can't delete the last full-access admin — promote someone first"
        )
    await db.users.delete_one({"user_id": user_id})
    await db.sessions.delete_many({"user_id": user_id})
    logger.info(f"Admin {admin['email']} deleted admin {target.get('email')}")
    return {"ok": True}






@api.post("/gigs/{gig_id}/acceptances/{acceptance_id}/rating-link")
async def admin_generate_client_rating_link(
    gig_id: str,
    acceptance_id: str,
    payload: ClientRatingLinkIn,
    admin: dict = Depends(require_admin),
):
    """Generate (or regenerate) a public client-feedback token for an
    acceptance. Returns the absolute URL the admin can share with the client.

    Tokens never expire — they're invalidated once a client submits OR when
    regenerate=true is sent."""
    acceptance = await db.gig_acceptances.find_one(
        {"acceptance_id": acceptance_id, "gig_id": gig_id}
    )
    if not acceptance:
        raise HTTPException(404, "Acceptance not found")

    token = acceptance.get("client_rating_token")
    if not token or payload.regenerate:
        token = secrets.token_urlsafe(20)

    set_ops: dict = {
        "client_rating_token": token,
        "client_rating_token_at": datetime.now(timezone.utc).isoformat(),
    }
    if payload.client_email is not None:
        set_ops["client_email"] = payload.client_email.strip().lower() or None
    # Regenerate also clears any previous submission so the new token is valid
    if payload.regenerate:
        set_ops["client_rating"] = None
        set_ops["client_rating_note"] = None
        set_ops["client_rating_at"] = None
        set_ops["client_rating_submitted_name"] = None
    await db.gig_acceptances.update_one({"acceptance_id": acceptance_id}, {"$set": set_ops})

    base = os.environ.get("FRONTEND_BASE_URL", "").rstrip("/")
    url = f"{base}/rate/{token}" if base else f"/rate/{token}"
    return {
        "token": token,
        "url": url,
        "client_email": set_ops.get("client_email"),
    }


@api.get("/public/rating/{token}")
async def public_rating_lookup(token: str):
    """Public, no-auth lookup. Returns minimum info needed for the client to
    leave a rating: worker name, gig title, gig date, gig location."""
    acceptance = await db.gig_acceptances.find_one(
        {"client_rating_token": token}, {"_id": 0}
    )
    if not acceptance:
        raise HTTPException(404, "Rating link not found or already used")
    gig = await db.gigs.find_one(
        {"gig_id": acceptance["gig_id"]},
        {"_id": 0, "title": 1, "category": 1, "scheduled_date": 1, "location": 1},
    )
    worker = await db.users.find_one(
        {"user_id": acceptance["worker_id"]},
        {"_id": 0, "name": 1},
    )
    return {
        "token": token,
        "worker_name": (worker or {}).get("name") or "Worker",
        "gig_title": (gig or {}).get("title") or "",
        "gig_category": (gig or {}).get("category") or "",
        "gig_scheduled_date": (gig or {}).get("scheduled_date") or "",
        "gig_location": (gig or {}).get("location") or "",
    }


@api.post("/public/rating/{token}")
async def public_rating_submit(token: str, payload: ClientRatingSubmitIn):
    """Public submission of a client rating. After submission, the token is
    burned so the URL can't be reused. Admin can regenerate."""
    if payload.stars < 1 or payload.stars > 5:
        raise HTTPException(400, "stars must be between 1 and 5")
    acceptance = await db.gig_acceptances.find_one({"client_rating_token": token})
    if not acceptance:
        raise HTTPException(404, "Rating link not found or already used")
    if acceptance.get("client_rating") is not None:
        raise HTTPException(
            400,
            "This rating has already been submitted. Ask HCOB for a new link if you want to change it.",
        )
    await db.gig_acceptances.update_one(
        {"acceptance_id": acceptance["acceptance_id"]},
        {
            "$set": {
                "client_rating": int(payload.stars),
                "client_rating_note": (payload.note or "").strip() or None,
                "client_rating_at": datetime.now(timezone.utc).isoformat(),
                "client_rating_submitted_name": (payload.client_name or "").strip() or None,
                "client_rating_token": None,  # burn so it can't be replayed
            }
        },
    )
    logger.info(
        f"Client rating submitted: {payload.stars} on {acceptance['acceptance_id']}"
    )
    return {"ok": True, "stars": payload.stars}





async def _build_workers_report(
    skills: Optional[str],
    zip_code: Optional[str],
    zip_prefix: Optional[str],
    status: Optional[str],
    profile_status: Optional[str],
    include_pii: bool,
) -> tuple[List[dict], List[dict]]:
    """Roster report: every worker + work stats. Optional PII columns when
    include_pii=True (DOB, full address, emergency contact). Filters mirror
    /admin/workers."""
    query: dict = {"role": "worker"}
    if status in ("approved", "pending", "rejected", "suspended"):
        if status == "approved":
            query["$or"] = [
                {"worker_status": "approved"},
                {"worker_status": {"$exists": False}},
            ]
        else:
            query["worker_status"] = status
    if skills:
        skill_list = [s.strip() for s in skills.split(",") if s.strip()]
        if skill_list:
            query["skills"] = {"$in": skill_list}
    if zip_code:
        query["zip_code"] = zip_code.strip()
    elif zip_prefix:
        query["zip_code"] = {"$regex": f"^{re.escape(zip_prefix.strip())}"}

    workers = await db.users.find(
        query, {"_id": 0, "password_hash": 0}
    ).sort("created_at", -1).to_list(2000)

    # Pre-load all acceptances grouped by worker (only need finished ones for stats)
    user_ids = [w["user_id"] for w in workers]
    accs = []
    if user_ids:
        accs = await db.gig_acceptances.find(
            {"worker_id": {"$in": user_ids}}, {"_id": 0}
        ).to_list(20000)
    acc_by_worker: dict = {}
    for a in accs:
        acc_by_worker.setdefault(a["worker_id"], []).append(a)

    rows: List[dict] = []
    for w in workers:
        missing = _profile_missing_fields(w)
        complete = len(missing) == 0
        if profile_status == "complete" and not complete:
            continue
        if profile_status == "incomplete" and complete:
            continue
        accs_w = acc_by_worker.get(w["user_id"], [])
        completed = [a for a in accs_w if a.get("clock_out_at")]
        approved_earnings = sum(
            float(a.get("earnings") or 0)
            for a in completed
            if a.get("timesheet_approved")
        )
        total_hours = sum(float(a.get("hours_worked") or 0) for a in completed)

        row: dict = {
            "user_id": w["user_id"],
            "name": w.get("name") or "",
            "email": w.get("email") or "",
            "phone": w.get("phone") or "",
            "zip_code": w.get("zip_code") or "",
            "city": w.get("city") or "",
            "state": w.get("state") or "",
            "skills": ", ".join(w.get("skills") or []),
            "availability": ", ".join(w.get("availability") or []),
            "vehicle": ", ".join(
                v for v, present in [
                    ("car", w.get("has_car")),
                    ("truck", w.get("has_truck")),
                    ("cdl", w.get("has_cdl")),
                ] if present
            ),
            "experience_level": w.get("experience_level") or "",
            "tshirt_size": w.get("tshirt_size") or "",
            "id_verified": "yes" if w.get("id_verified") else "no",
            "profile_complete": "yes" if complete else "no",
            "worker_status": w.get("worker_status") or "approved",
            "joined_date": (w.get("created_at") or "")[:10],
            "jobs_completed": len(completed),
            "total_hours": round(total_hours, 2),
            "total_earned": round(approved_earnings, 2),
        }
        if include_pii:
            row["date_of_birth"] = w.get("date_of_birth") or ""
            row["address"] = w.get("address") or ""
            row["emergency_contact_name"] = w.get("emergency_contact_name") or ""
            row["emergency_contact_phone"] = w.get("emergency_contact_phone") or ""
            row["bio"] = w.get("bio") or ""
        rows.append(row)

    cols = [
        {"key": "name", "label": "Name"},
        {"key": "email", "label": "Email"},
        {"key": "phone", "label": "Phone"},
        {"key": "zip_code", "label": "ZIP"},
        {"key": "city", "label": "City"},
        {"key": "state", "label": "State"},
        {"key": "skills", "label": "Skills"},
        {"key": "availability", "label": "Availability"},
        {"key": "vehicle", "label": "Vehicle"},
        {"key": "experience_level", "label": "Experience"},
        {"key": "tshirt_size", "label": "Shirt size"},
        {"key": "id_verified", "label": "ID verified"},
        {"key": "profile_complete", "label": "Profile complete"},
        {"key": "worker_status", "label": "Status"},
        {"key": "joined_date", "label": "Joined"},
        {"key": "jobs_completed", "label": "Jobs completed"},
        {"key": "total_hours", "label": "Total hours"},
        {"key": "total_earned", "label": "Total earned"},
    ]
    if include_pii:
        cols += [
            {"key": "date_of_birth", "label": "DOB"},
            {"key": "address", "label": "Address"},
            {"key": "emergency_contact_name", "label": "Emergency contact"},
            {"key": "emergency_contact_phone", "label": "Emergency phone"},
            {"key": "bio", "label": "Bio"},
        ]
    return rows, cols


async def _build_gigs_report(
    start: Optional[str],
    end: Optional[str],
    category: Optional[str],
    status: Optional[str],
) -> tuple[List[dict], List[dict]]:
    """Gigs report: title, date, location, slots, status, workers assigned,
    total payout so far (sum of earnings from clocked-out workers)."""
    query: dict = {}
    if status:
        query["status"] = status
    if category:
        query["category"] = category
    if start or end:
        d: dict = {}
        if start:
            d["$gte"] = start[:10]
        if end:
            d["$lte"] = end[:10]
        query["scheduled_date"] = d

    gigs = await db.gigs.find(query, {"_id": 0}).sort("scheduled_date", -1).to_list(5000)
    if not gigs:
        return [], _gigs_cols()

    gig_ids = [g["gig_id"] for g in gigs]
    accs = await db.gig_acceptances.find(
        {"gig_id": {"$in": gig_ids}}, {"_id": 0}
    ).to_list(50000)
    acc_by_gig: dict = {}
    for a in accs:
        acc_by_gig.setdefault(a["gig_id"], []).append(a)

    rows: List[dict] = []
    for g in gigs:
        gaccs = acc_by_gig.get(g["gig_id"], [])
        assigned = [a for a in gaccs if a.get("status") != "requested"]
        completed = [a for a in assigned if a.get("clock_out_at")]
        payout = sum(float(a.get("earnings") or 0) for a in completed)
        rows.append({
            "gig_id": g["gig_id"],
            "title": g.get("title") or "",
            "category": g.get("category") or "",
            "subcategory": g.get("subcategory") or "",
            "scheduled_date": g.get("scheduled_date") or "",
            "start_time": g.get("start_time") or "",
            "duration_hours": g.get("duration_hours") or "",
            "location": g.get("location") or "",
            "slots": g.get("slots") or 0,
            "pay_rate": float(g.get("pay_rate") or 0),
            "pay_type": g.get("pay_type") or "",
            "status": g.get("status") or "",
            "workers_assigned": len(assigned),
            "workers_completed": len(completed),
            "total_payout": round(payout, 2),
        })
    return rows, _gigs_cols()


def _gigs_cols() -> List[dict]:
    return [
        {"key": "title", "label": "Title"},
        {"key": "category", "label": "Category"},
        {"key": "subcategory", "label": "Sub-type"},
        {"key": "scheduled_date", "label": "Date"},
        {"key": "start_time", "label": "Start"},
        {"key": "duration_hours", "label": "Duration"},
        {"key": "location", "label": "Location"},
        {"key": "slots", "label": "Slots"},
        {"key": "pay_rate", "label": "Pay rate"},
        {"key": "pay_type", "label": "Pay type"},
        {"key": "status", "label": "Status"},
        {"key": "workers_assigned", "label": "Workers assigned"},
        {"key": "workers_completed", "label": "Workers completed"},
        {"key": "total_payout", "label": "Total payout"},
    ]


async def _build_activity_report(
    start: Optional[str],
    end: Optional[str],
    worker_id: Optional[str],
) -> tuple[List[dict], List[dict]]:
    """Per-worker activity for a date range: gigs requested / approved /
    completed / no-shows, total hours, total earned. Range is matched against
    the acceptance's accepted_at (or created_at) timestamp."""
    wquery: dict = {"role": "worker"}
    if worker_id:
        wquery["user_id"] = worker_id
    workers = await db.users.find(
        wquery, {"_id": 0, "password_hash": 0}
    ).to_list(2000)
    user_ids = [w["user_id"] for w in workers]
    if not user_ids:
        return [], _activity_cols()

    accs = await db.gig_acceptances.find(
        {"worker_id": {"$in": user_ids}}, {"_id": 0}
    ).to_list(50000)
    # Filter accs in-memory by date range using the most relevant timestamp
    def _ts(a: dict) -> str:
        return (
            a.get("requested_at")
            or a.get("accepted_at")
            or a.get("created_at")
            or a.get("clock_in_at")
            or ""
        )
    if start or end:
        s = start[:19] if start else ""
        e = end[:19] if end else ""
        accs = [a for a in accs if (not s or _ts(a) >= s) and (not e or _ts(a) <= e)]
    acc_by_worker: dict = {}
    for a in accs:
        acc_by_worker.setdefault(a["worker_id"], []).append(a)

    rows: List[dict] = []
    for w in workers:
        a_list = acc_by_worker.get(w["user_id"], [])
        requested = len(a_list)
        approved = sum(1 for a in a_list if a.get("status") != "requested")
        completed = sum(1 for a in a_list if a.get("clock_out_at"))
        # No-show = approved but never clocked in
        no_show = sum(
            1 for a in a_list
            if a.get("status") not in ("requested",) and not a.get("clock_in_at")
        )
        total_hours = sum(float(a.get("hours_worked") or 0) for a in a_list)
        total_earned = sum(
            float(a.get("earnings") or 0)
            for a in a_list
            if a.get("timesheet_approved")
        )
        # Rating aggregates — combine admin + client stars across these accs
        stars = []
        for a in a_list:
            if isinstance(a.get("admin_rating"), (int, float)):
                stars.append(a["admin_rating"])
            if isinstance(a.get("client_rating"), (int, float)):
                stars.append(a["client_rating"])
        avg_rating = round(sum(stars) / len(stars), 2) if stars else None
        if requested == 0 and not worker_id:
            # Skip totally-inactive workers unless explicitly asked
            continue
        rows.append({
            "user_id": w["user_id"],
            "name": w.get("name") or "",
            "email": w.get("email") or "",
            "phone": w.get("phone") or "",
            "gigs_requested": requested,
            "gigs_approved": approved,
            "gigs_completed": completed,
            "no_shows": no_show,
            "total_hours": round(total_hours, 2),
            "total_earned": round(total_earned, 2),
            "avg_rating": avg_rating,
            "ratings_count": len(stars),
            "id_verified": "yes" if w.get("id_verified") else "no",
        })
    rows.sort(key=lambda r: r["gigs_completed"], reverse=True)
    return rows, _activity_cols()


def _activity_cols() -> List[dict]:
    return [
        {"key": "name", "label": "Worker"},
        {"key": "email", "label": "Email"},
        {"key": "phone", "label": "Phone"},
        {"key": "gigs_requested", "label": "Requested"},
        {"key": "gigs_approved", "label": "Approved"},
        {"key": "gigs_completed", "label": "Completed"},
        {"key": "no_shows", "label": "No-shows"},
        {"key": "total_hours", "label": "Total hours"},
        {"key": "total_earned", "label": "Total earned"},
        {"key": "avg_rating", "label": "Avg rating"},
        {"key": "ratings_count", "label": "# ratings"},
        {"key": "id_verified", "label": "ID verified"},
    ]


async def _build_earnings_report(
    start: Optional[str],
    end: Optional[str],
    only_approved: bool,
) -> tuple[List[dict], List[dict]]:
    """Payroll summary: one row per worker for the date range with total
    earnings, hours, gigs. only_approved=True restricts to approved
    timesheets (recommended for payroll)."""
    ts_rows = await _build_timesheet_rows(start, end, None, None, only_approved)
    by_w: dict = {}
    for r in ts_rows:
        wid = r["worker_id"]
        agg = by_w.setdefault(wid, {
            "user_id": wid,
            "name": r.get("worker_name") or "",
            "email": r.get("worker_email") or "",
            "gigs": 0,
            "total_hours": 0.0,
            "total_earned": 0.0,
            "approved_earned": 0.0,
            "pending_earned": 0.0,
        })
        agg["gigs"] += 1
        agg["total_hours"] += float(r.get("hours_worked") or 0)
        earn = float(r.get("earnings") or 0)
        agg["total_earned"] += earn
        if r.get("timesheet_approved"):
            agg["approved_earned"] += earn
        else:
            agg["pending_earned"] += earn
    rows = list(by_w.values())
    for r in rows:
        r["total_hours"] = round(r["total_hours"], 2)
        r["total_earned"] = round(r["total_earned"], 2)
        r["approved_earned"] = round(r["approved_earned"], 2)
        r["pending_earned"] = round(r["pending_earned"], 2)
    rows.sort(key=lambda r: r["approved_earned"], reverse=True)
    cols = [
        {"key": "name", "label": "Worker"},
        {"key": "email", "label": "Email"},
        {"key": "gigs", "label": "Gigs"},
        {"key": "total_hours", "label": "Total hours"},
        {"key": "approved_earned", "label": "Approved $"},
        {"key": "pending_earned", "label": "Pending $"},
        {"key": "total_earned", "label": "Total $"},
    ]
    return rows, cols


async def _build_timesheet_rows(
    start: Optional[str],
    end: Optional[str],
    worker_id: Optional[str],
    gig_id: Optional[str],
    only_approved: bool,
) -> List[dict]:
    """Return enriched timesheet rows, sorted by clock_in (newest first).

    A row is included only if the worker clocked OUT (completed). Filters by
    optional ISO date strings; only_approved=True restricts to approved
    timesheets (used for worker-facing endpoints)."""
    query: dict = {"clock_out_at": {"$ne": None}}
    if worker_id:
        query["worker_id"] = worker_id
    if gig_id:
        query["gig_id"] = gig_id
    if only_approved:
        query["timesheet_approved"] = True

    # Date filter on clock_in_at when provided
    if start or end:
        date_filter: dict = {}
        if start:
            date_filter["$gte"] = start
        if end:
            date_filter["$lte"] = end
        query["clock_in_at"] = date_filter

    rows = await db.gig_acceptances.find(query, {"_id": 0}).sort("clock_in_at", -1).to_list(5000)
    if not rows:
        return []
    gig_ids = list({r["gig_id"] for r in rows})
    worker_ids = list({r["worker_id"] for r in rows})
    gigs = await db.gigs.find({"gig_id": {"$in": gig_ids}}, {"_id": 0}).to_list(5000)
    gmap = {g["gig_id"]: g for g in gigs}
    workers = await db.users.find(
        {"user_id": {"$in": worker_ids}}, {"_id": 0, "password_hash": 0}
    ).to_list(5000)
    wmap = {w["user_id"]: w for w in workers}
    out: List[dict] = []
    for r in rows:
        g = gmap.get(r["gig_id"]) or {}
        w = wmap.get(r["worker_id"]) or {}
        br = _resolve_break_minutes(r, g)
        paid_hours = _compute_paid_hours(r.get("hours_worked"), br)
        # If earnings not snapshotted (legacy), compute on the fly using current rates
        earnings = r.get("earnings")
        rate = r.get("pay_rate_applied")
        ptype = r.get("pay_type_applied")
        if earnings is None:
            pay = _resolve_pay(r, w, g)
            rate, ptype = pay["pay_rate"], pay["pay_type"]
            earnings = _compute_earnings(rate, ptype, r.get("hours_worked"), br)
        out.append(
            {
                "acceptance_id": r["acceptance_id"],
                "gig_id": r["gig_id"],
                "gig_title": g.get("title"),
                "gig_category": g.get("category"),
                "gig_scheduled_date": g.get("scheduled_date"),
                "worker_id": r["worker_id"],
                "worker_name": w.get("name"),
                "worker_email": w.get("email"),
                "clock_in_at": r.get("clock_in_at"),
                "clock_out_at": r.get("clock_out_at"),
                "hours_worked": r.get("hours_worked"),
                "break_minutes": br,
                "paid_hours": paid_hours,
                "pay_rate_applied": rate,
                "pay_type_applied": ptype,
                "earnings": earnings,
                "timesheet_approved": bool(r.get("timesheet_approved")),
                "timesheet_approved_at": r.get("timesheet_approved_at"),
                "timesheet_approved_by": r.get("timesheet_approved_by"),
            }
        )
    return out


@api.get("/admin/reports/timesheets")
async def admin_reports_timesheets(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    worker_id: Optional[str] = Query(None),
    gig_id: Optional[str] = Query(None),
    only_approved: bool = Query(False),
    admin: dict = Depends(require_admin),
):
    """Return timesheet rows + totals."""
    rows = await _build_timesheet_rows(start, end, worker_id, gig_id, only_approved)
    total_hours = round(sum((r.get("hours_worked") or 0) for r in rows), 2)
    total_paid_hours = round(sum((r.get("paid_hours") or 0) for r in rows), 2)
    total_break_minutes = sum((r.get("break_minutes") or 0) for r in rows)
    total_earnings = round(sum((r.get("earnings") or 0) for r in rows), 2)
    approved_earnings = round(
        sum((r.get("earnings") or 0) for r in rows if r.get("timesheet_approved")), 2
    )
    return {
        "rows": rows,
        "totals": {
            "rows": len(rows),
            "hours": total_hours,
            "paid_hours": total_paid_hours,
            "break_minutes": total_break_minutes,
            "earnings": total_earnings,
            "approved_earnings": approved_earnings,
        },
        "filter": {"start": start, "end": end, "worker_id": worker_id, "gig_id": gig_id, "only_approved": only_approved},
    }


def _fmt_dt_for_csv(iso: Optional[str]) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso


def _csv_escape(v) -> str:
    if v is None:
        return ""
    s = str(v)
    if any(c in s for c in [",", '"', "\n", "\r"]):
        return '"' + s.replace('"', '""') + '"'
    return s


@api.get("/admin/reports/timesheets.csv")
async def admin_reports_timesheets_csv(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    worker_id: Optional[str] = Query(None),
    gig_id: Optional[str] = Query(None),
    only_approved: bool = Query(False),
    admin: dict = Depends(require_admin),
):
    """Download timesheet report as CSV."""
    rows = await _build_timesheet_rows(start, end, worker_id, gig_id, only_approved)
    header = [
        "Worker", "Worker email", "Gig", "Date", "Clock-in", "Clock-out",
        "Hours clocked", "Break (min)", "Paid hours", "Pay rate", "Pay type", "Earnings", "Timesheet approved",
    ]
    lines = [",".join(header)]
    for r in rows:
        rate = r.get("pay_rate_applied")
        rate_s = f"{rate:.2f}" if rate is not None else ""
        earnings = r.get("earnings")
        earnings_s = f"{earnings:.2f}" if earnings is not None else ""
        hours = r.get("hours_worked")
        hours_s = f"{hours:.2f}" if hours is not None else ""
        br = r.get("break_minutes")
        br_s = f"{br:d}" if br is not None else "0"
        paid = r.get("paid_hours")
        paid_s = f"{paid:.2f}" if paid is not None else ""
        lines.append(",".join(_csv_escape(c) for c in [
            r.get("worker_name") or "",
            r.get("worker_email") or "",
            r.get("gig_title") or "",
            r.get("gig_scheduled_date") or "",
            _fmt_dt_for_csv(r.get("clock_in_at")),
            _fmt_dt_for_csv(r.get("clock_out_at")),
            hours_s,
            br_s,
            paid_s,
            rate_s,
            r.get("pay_type_applied") or "",
            earnings_s,
            "yes" if r.get("timesheet_approved") else "no",
        ]))
    body = "\n".join(lines) + "\n"
    filename = f"hcob-timesheets-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    return FastAPIResponse(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ----------------------------------------------------------------------------
# Generic report dispatcher — workers / gigs / activity / earnings
# ----------------------------------------------------------------------------
async def _dispatch_report(report_type: str, params: dict) -> tuple[List[dict], List[dict], dict]:
    """Returns (rows, columns, totals) for the requested report type. Each
    report's totals dict has a `rows` count plus any meaningful sums."""
    if report_type == "workers":
        rows, cols = await _build_workers_report(
            skills=params.get("skills"),
            zip_code=params.get("zip_code"),
            zip_prefix=params.get("zip_prefix"),
            status=params.get("status"),
            profile_status=params.get("profile_status"),
            include_pii=bool(params.get("include_pii")),
        )
        totals = {
            "rows": len(rows),
            "jobs_completed": sum(r.get("jobs_completed", 0) for r in rows),
            "total_hours": round(sum(r.get("total_hours", 0) for r in rows), 2),
            "total_earned": round(sum(r.get("total_earned", 0) for r in rows), 2),
        }
        return rows, cols, totals
    if report_type == "gigs":
        rows, cols = await _build_gigs_report(
            start=params.get("start"),
            end=params.get("end"),
            category=params.get("category"),
            status=params.get("status"),
        )
        totals = {
            "rows": len(rows),
            "workers_assigned": sum(r.get("workers_assigned", 0) for r in rows),
            "workers_completed": sum(r.get("workers_completed", 0) for r in rows),
            "total_payout": round(sum(r.get("total_payout", 0) for r in rows), 2),
        }
        return rows, cols, totals
    if report_type == "activity":
        rows, cols = await _build_activity_report(
            start=params.get("start"),
            end=params.get("end"),
            worker_id=params.get("worker_id"),
        )
        totals = {
            "rows": len(rows),
            "completed": sum(r.get("gigs_completed", 0) for r in rows),
            "no_shows": sum(r.get("no_shows", 0) for r in rows),
            "total_hours": round(sum(r.get("total_hours", 0) for r in rows), 2),
            "total_earned": round(sum(r.get("total_earned", 0) for r in rows), 2),
        }
        return rows, cols, totals
    if report_type == "earnings":
        rows, cols = await _build_earnings_report(
            start=params.get("start"),
            end=params.get("end"),
            only_approved=bool(params.get("only_approved")),
        )
        totals = {
            "rows": len(rows),
            "approved_earned": round(sum(r.get("approved_earned", 0) for r in rows), 2),
            "pending_earned": round(sum(r.get("pending_earned", 0) for r in rows), 2),
            "total_earned": round(sum(r.get("total_earned", 0) for r in rows), 2),
            "total_hours": round(sum(r.get("total_hours", 0) for r in rows), 2),
        }
        return rows, cols, totals
    raise HTTPException(400, f"Unknown report_type: {report_type}")


REPORT_TYPES = {"workers", "gigs", "activity", "earnings"}
REPORT_TITLES = {
    "workers": "HCOB Workers",
    "gigs": "HCOB Gigs",
    "activity": "HCOB Worker Activity",
    "earnings": "HCOB Earnings",
}


def _params_from_query(
    start: Optional[str],
    end: Optional[str],
    worker_id: Optional[str],
    gig_id: Optional[str],
    skills: Optional[str],
    zip_code: Optional[str],
    zip_prefix: Optional[str],
    status: Optional[str],
    profile_status: Optional[str],
    category: Optional[str],
    only_approved: bool,
    include_pii: bool,
) -> dict:
    return {
        "start": start, "end": end,
        "worker_id": worker_id, "gig_id": gig_id,
        "skills": skills, "zip_code": zip_code, "zip_prefix": zip_prefix,
        "status": status, "profile_status": profile_status,
        "category": category, "only_approved": only_approved,
        "include_pii": include_pii,
    }


@api.get("/admin/reports/{report_type}.csv")
async def admin_reports_generic_csv(
    report_type: str,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    worker_id: Optional[str] = Query(None),
    gig_id: Optional[str] = Query(None),
    skills: Optional[str] = Query(None),
    zip_code: Optional[str] = Query(None),
    zip_prefix: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    profile_status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    only_approved: bool = Query(False),
    include_pii: bool = Query(False),
    admin: dict = Depends(require_admin),
):
    """Download any of the new report types as CSV."""
    if report_type == "timesheets":
        raise HTTPException(
            400,
            "Use /admin/reports/timesheets.csv directly for timesheets",
        )
    if report_type not in REPORT_TYPES:
        raise HTTPException(404, f"Unknown report_type: {report_type}")
    params = _params_from_query(
        start, end, worker_id, gig_id, skills, zip_code, zip_prefix, status,
        profile_status, category, only_approved, include_pii,
    )
    rows, cols, _totals = await _dispatch_report(report_type, params)
    header = ",".join(_csv_escape(c["label"]) for c in cols)
    lines = [header]
    for r in rows:
        lines.append(",".join(_csv_escape(r.get(c["key"], "")) for c in cols))
    body = "\n".join(lines) + "\n"
    filename = f"hcob-{report_type}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    return FastAPIResponse(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api.get("/admin/reports/{report_type}")
async def admin_reports_generic(
    report_type: str,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    worker_id: Optional[str] = Query(None),
    gig_id: Optional[str] = Query(None),
    skills: Optional[str] = Query(None),
    zip_code: Optional[str] = Query(None),
    zip_prefix: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    profile_status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    only_approved: bool = Query(False),
    include_pii: bool = Query(False),
    admin: dict = Depends(require_admin),
):
    """Generic JSON report. report_type ∈ {workers, gigs, activity, earnings}."""
    if report_type == "timesheets":
        raise HTTPException(
            400,
            "Use /admin/reports/timesheets directly for timesheets — this generic endpoint serves the newer report types",
        )
    if report_type not in REPORT_TYPES:
        raise HTTPException(404, f"Unknown report_type: {report_type}")
    params = _params_from_query(
        start, end, worker_id, gig_id, skills, zip_code, zip_prefix, status,
        profile_status, category, only_approved, include_pii,
    )
    rows, cols, totals = await _dispatch_report(report_type, params)
    return {"rows": rows, "columns": cols, "totals": totals, "filter": params}


@api.post("/admin/reports/export-google-sheets")
async def admin_reports_export_google_sheets(
    payload: dict,
    admin: dict = Depends(require_admin),
):
    """Export ANY report type to a new Google Sheet. Pass `report_type` in the
    body — defaults to `timesheets` for back-compat. Returns the sheet URL."""
    s = await _get_settings_doc()
    raw = s.get("google_service_account_json")
    if not raw:
        raise HTTPException(400, "Google service account JSON is not configured in admin settings")

    import json as _json
    try:
        info = _json.loads(raw)
    except Exception:
        raise HTTPException(400, "Saved Google service account JSON is invalid")

    report_type = (payload.get("report_type") or "timesheets").strip()
    start = payload.get("start")
    end = payload.get("end")

    # Build rows + columns based on the requested report
    if report_type == "timesheets":
        rows = await _build_timesheet_rows(
            start, end, payload.get("worker_id"), payload.get("gig_id"),
            bool(payload.get("only_approved")),
        )
        cols = [
            {"key": "worker_name", "label": "Worker"},
            {"key": "worker_email", "label": "Worker email"},
            {"key": "gig_title", "label": "Gig"},
            {"key": "gig_scheduled_date", "label": "Date"},
            {"key": "clock_in_at", "label": "Clock-in", "fmt": "dt"},
            {"key": "clock_out_at", "label": "Clock-out", "fmt": "dt"},
            {"key": "hours_worked", "label": "Hours", "fmt": "f2"},
            {"key": "pay_rate_applied", "label": "Pay rate", "fmt": "f2"},
            {"key": "pay_type_applied", "label": "Pay type"},
            {"key": "earnings", "label": "Earnings", "fmt": "f2"},
            {"key": "timesheet_approved", "label": "Timesheet approved", "fmt": "yesno"},
        ]
        sheet_tab = "Timesheets"
        totals_row = ["TOTALS"] + [""] * 5 + [
            round(sum(float(r.get("hours_worked") or 0) for r in rows), 2),
            "", "",
            round(sum(float(r.get("earnings") or 0) for r in rows), 2),
            "",
        ]
    else:
        if report_type not in REPORT_TYPES:
            raise HTTPException(400, f"Unknown report_type: {report_type}")
        params = {
            "start": start, "end": end,
            "worker_id": payload.get("worker_id"),
            "gig_id": payload.get("gig_id"),
            "skills": payload.get("skills"),
            "zip_code": payload.get("zip_code"),
            "zip_prefix": payload.get("zip_prefix"),
            "status": payload.get("status"),
            "profile_status": payload.get("profile_status"),
            "category": payload.get("category"),
            "only_approved": bool(payload.get("only_approved")),
            "include_pii": bool(payload.get("include_pii")),
        }
        rows, cols, totals = await _dispatch_report(report_type, params)
        sheet_tab = report_type.capitalize()
        # Build a totals row that fills only the numeric columns
        totals_row = []
        numeric_keys_to_total = {
            k for k in ("jobs_completed", "total_hours", "total_earned",
                        "workers_assigned", "workers_completed", "total_payout",
                        "gigs_requested", "gigs_approved", "gigs_completed", "no_shows",
                        "approved_earned", "pending_earned", "gigs", "slots")
        }
        for i, c in enumerate(cols):
            if i == 0:
                totals_row.append("TOTALS")
            elif c["key"] in numeric_keys_to_total:
                totals_row.append(
                    round(sum(float(r.get(c["key"]) or 0) for r in rows), 2)
                )
            else:
                totals_row.append("")

    title_parts = [REPORT_TITLES.get(report_type, "HCOB Report")]
    if start:
        title_parts.append(start[:10])
    if end:
        title_parts.append("→ " + end[:10])
    title_parts.append(datetime.now(timezone.utc).strftime("%H:%M UTC"))
    sheet_title = " ".join(title_parts)

    def _cell(r: dict, col: dict):
        v = r.get(col["key"])
        fmt = col.get("fmt")
        if v is None:
            return ""
        if fmt == "dt":
            return _fmt_dt_for_csv(v)
        if fmt == "f2":
            try:
                return float(v)
            except Exception:
                return v
        if fmt == "yesno":
            return "yes" if v else "no"
        return v

    def _build():
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
        drive = build("drive", "v3", credentials=creds, cache_discovery=False)

        spreadsheet = sheets.spreadsheets().create(body={
            "properties": {"title": sheet_title},
            "sheets": [{"properties": {"title": sheet_tab}}],
        }).execute()
        sheet_id = spreadsheet["spreadsheetId"]

        header = [c["label"] for c in cols]
        values = [header]
        for r in rows:
            values.append([_cell(r, c) for c in cols])
        values.append([])
        values.append(totals_row)

        sheets.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{sheet_tab}!A1",
            valueInputOption="RAW",
            body={"values": values},
        ).execute()

        share_email = s.get("google_sheets_share_email")
        if share_email:
            try:
                drive.permissions().create(
                    fileId=sheet_id,
                    body={"type": "user", "role": "writer", "emailAddress": share_email},
                    sendNotificationEmail=False,
                ).execute()
            except Exception as e:
                logger.warning(f"Could not share sheet with {share_email}: {e}")

        return {
            "spreadsheet_id": sheet_id,
            "url": f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit",
            "rows": len(rows),
            "report_type": report_type,
        }

    try:
        result = await asyncio.to_thread(_build)
    except Exception as e:
        logger.error(f"Google Sheets export failed: {e}")
        raise HTTPException(400, f"Google Sheets export failed: {e}")
    logger.info(f"Admin {admin['email']} exported {report_type} to {result['url']}")
    return result


@api.get("/me/earnings")
async def my_earnings(user: dict = Depends(get_current_user)):
    """Worker's own approved earnings — totals + per-gig list. Only APPROVED
    timesheets are released; pending timesheets are summarized separately."""
    if user.get("role") != "worker":
        raise HTTPException(403, "Workers only")
    rows = await db.gig_acceptances.find(
        {"worker_id": user["user_id"], "clock_out_at": {"$ne": None}}, {"_id": 0}
    ).sort("clock_out_at", -1).to_list(1000)
    if not rows:
        return {
            "approved": {"rows": [], "total_hours": 0, "total_earnings": 0},
            "pending": {"count": 0, "hours": 0},
        }
    gig_ids = list({r["gig_id"] for r in rows})
    gigs = await db.gigs.find({"gig_id": {"$in": gig_ids}}, {"_id": 0}).to_list(1000)
    gmap = {g["gig_id"]: g for g in gigs}

    approved_rows = []
    approved_hours = 0.0
    approved_paid_hours = 0.0
    approved_earnings = 0.0
    approved_break_minutes = 0
    pending_count = 0
    pending_hours = 0.0
    for r in rows:
        g = gmap.get(r["gig_id"]) or {}
        hours = r.get("hours_worked") or 0
        earnings = r.get("earnings")
        br = _resolve_break_minutes(r, g)
        paid_hours = _compute_paid_hours(r.get("hours_worked"), br) or 0.0
        if r.get("timesheet_approved"):
            approved_hours += float(hours)
            approved_paid_hours += float(paid_hours)
            approved_earnings += float(earnings or 0)
            approved_break_minutes += int(br)
            approved_rows.append({
                "acceptance_id": r["acceptance_id"],
                "gig_id": r["gig_id"],
                "gig_title": g.get("title"),
                "gig_category": g.get("category"),
                "gig_scheduled_date": g.get("scheduled_date"),
                "clock_in_at": r.get("clock_in_at"),
                "clock_out_at": r.get("clock_out_at"),
                "hours_worked": r.get("hours_worked"),
                "break_minutes": br,
                "paid_hours": paid_hours,
                "pay_rate_applied": r.get("pay_rate_applied"),
                "pay_type_applied": r.get("pay_type_applied"),
                "earnings": earnings,
                "timesheet_approved_at": r.get("timesheet_approved_at"),
            })
        else:
            pending_count += 1
            pending_hours += float(hours)
    return {
        "approved": {
            "rows": approved_rows,
            "total_hours": round(approved_hours, 2),
            "total_paid_hours": round(approved_paid_hours, 2),
            "total_break_minutes": approved_break_minutes,
            "total_earnings": round(approved_earnings, 2),
        },
        "pending": {
            "count": pending_count,
            "hours": round(pending_hours, 2),
        },
    }



# ---- Admin settings (Resend / Twilio) --------------------------------------
def _mask(value: Optional[str]) -> dict:
    v = (value or "").strip()
    if not v:
        return {"has_value": False, "last4": ""}
    return {"has_value": True, "last4": v[-4:] if len(v) >= 4 else v}


@api.get("/admin/settings")
async def get_settings(admin: dict = Depends(require_admin)):
    """Return masked settings + which channels are usable."""
    s = await _get_settings_doc()
    email = await _resolve_email_creds()
    sms = await _resolve_sms_creds()
    gs_json = s.get("google_service_account_json") or ""
    gs_email = ""
    if gs_json:
        try:
            import json as _json
            gs_email = _json.loads(gs_json).get("client_email", "")
        except Exception:
            gs_email = ""
    return {
        "resend_api_key": _mask(s.get("resend_api_key")),
        "sender_email": s.get("sender_email") or SENDER_EMAIL or "",
        "twilio_account_sid": _mask(s.get("twilio_account_sid")),
        "twilio_auth_token": _mask(s.get("twilio_auth_token")),
        "twilio_from_number": s.get("twilio_from_number") or TWILIO_FROM or "",
        "email_ready": bool(email["api_key"] and email["sender"]),
        "sms_ready": bool(sms["sid"] and sms["token"] and sms["from_"]),
        "google_sheets_ready": bool(gs_json),
        "google_sheets_service_email": gs_email,
        "google_sheets_share_email": s.get("google_sheets_share_email") or "",
        "updated_at": s.get("updated_at"),
        "updated_by": s.get("updated_by"),
    }


@api.put("/admin/settings")
async def update_settings(
    payload: SettingsIn, admin: dict = Depends(require_admin)
):
    """Update settings. Empty string clears a field; None leaves it unchanged."""
    incoming = payload.model_dump(exclude_unset=True)
    update_set: dict = {}
    unset: dict = {}
    for k, v in incoming.items():
        if v is None:
            continue
        v = v.strip()
        if v == "":
            unset[k] = ""
        else:
            update_set[k] = v

    if not update_set and not unset:
        return {"ok": True, "changed": 0}

    update_set["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_set["updated_by"] = admin["email"]
    ops: dict = {"$set": update_set}
    if unset:
        ops["$unset"] = unset

    await db.app_settings.update_one({"_id": "global"}, ops, upsert=True)
    return {"ok": True, "changed": len(update_set) + len(unset)}


@api.post("/admin/settings/test")
async def test_settings(
    payload: SettingsTestIn, admin: dict = Depends(require_admin)
):
    """Send a test email or SMS to verify saved credentials."""
    if payload.channel == "email":
        creds = await _resolve_email_creds()
        if not creds["api_key"]:
            raise HTTPException(400, "Resend API key not set")
        try:
            result = await asyncio.to_thread(
                _send_email_sync,
                creds["api_key"],
                creds["sender"],
                payload.to,
                "HCOB Network — test email",
                "<p>This is a test email from HCOB Network settings. If you see this, your Resend credentials are working.</p>",
            )
            return {"ok": True, "result": result}
        except Exception as e:
            raise HTTPException(400, f"Email test failed: {e}")

    if payload.channel == "sms":
        creds = await _resolve_sms_creds()
        if not (creds["sid"] and creds["token"] and creds["from_"]):
            raise HTTPException(400, "Twilio credentials incomplete")
        try:
            result = await asyncio.to_thread(
                _send_sms_sync,
                creds["sid"],
                creds["token"],
                creds["from_"],
                payload.to,
                "HCOB Network — test SMS. Your Twilio credentials are working.",
            )
            return {"ok": True, "result": result}
        except Exception as e:
            raise HTTPException(400, f"SMS test failed: {e}")


# ---- Startup ---------------------------------------------------------------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.sessions.create_index("session_token", unique=True)
    await db.gigs.create_index("gig_id", unique=True)
    await db.gig_acceptances.create_index([("gig_id", 1), ("worker_id", 1)], unique=True)
    await db.notifications.create_index("user_id")

    # Legacy backfill: ensure every gig has is_rush as a bool (not null) so
    # the public landing feed sorts correctly. Idempotent.
    await db.gigs.update_many(
        {"is_rush": {"$exists": False}},
        {"$set": {"is_rush": False, "rush_at": None}},
    )
    # Backfill tags array on legacy docs (any pre-tag-feature gig). If the
    # gig was previously flagged as rush, carry that into tags so the visual
    # treatment stays consistent.
    await db.gigs.update_many(
        {"tags": {"$exists": False}, "is_rush": True},
        {"$set": {"tags": ["rush"]}},
    )
    await db.gigs.update_many(
        {"tags": {"$exists": False}},
        {"$set": {"tags": []}},
    )
    # Backfill break_minutes on legacy gigs
    await db.gigs.update_many(
        {"break_minutes": {"$exists": False}},
        {"$set": {"break_minutes": 0}},
    )
    # Backfill payment_timeline on legacy gigs
    await db.gigs.update_many(
        {"payment_timeline": {"$exists": False}},
        {"$set": {"payment_timeline": "2_3_days", "payment_timeline_note": None}},
    )
    # Backfill project_id on legacy gigs
    await db.gigs.update_many(
        {"project_id": {"$exists": False}},
        {"$set": {"project_id": None}},
    )
    # Projects collection indices
    await db.projects.create_index("project_id", unique=True)
    await db.projects.create_index([("archived", 1), ("created_at", -1)])
    await db.gigs.create_index("project_id")

    # Seed admin
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@gigblast.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "GigBlast2026!")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one(
            {
                "user_id": f"user_{uuid.uuid4().hex[:12]}",
                "email": admin_email,
                "password_hash": hash_password(admin_password),
                "name": "Operations Admin",
                "role": "admin",
                "phone": "",
                "address": "",
                "bio": "",
                "skills": [],
                "avatar_path": None,
                "id_image_path": None,
                "id_verified": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "auth_provider": "local",
            }
        )
        logger.info(f"Seeded admin user {admin_email}")
    elif not verify_password(admin_password, existing.get("password_hash", "")):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password)}},
        )

    init_storage()


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
