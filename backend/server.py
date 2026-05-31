"""HCOB Network — Gig Opportunity Management Platform."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import logging
import secrets
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal

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
)
from fastapi.responses import Response as FastAPIResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from twilio.rest import Client as TwilioClient

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
    contact_phone: Optional[str] = None
    # Recurrence — optional. If recurrence != 'none', the create endpoint generates
    # `repeat_count` gig instances spaced by the chosen period.
    recurrence: Optional[GigRecurrence] = "none"
    repeat_count: Optional[int] = 1  # ignored when recurrence == 'none'


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
    contact_phone: Optional[str] = None


class BlastIn(BaseModel):
    channels: List[Literal["in_app", "email", "sms"]]


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


class TimesheetEditIn(BaseModel):
    """Admin edits raw clock-in/out times. Either field accepts an ISO datetime
    string. Passing `clear_clock_out=true` reverts the acceptance back to
    on-the-clock state. Editing always recomputes hours+earnings and resets
    timesheet_approved=false."""
    clock_in_at: Optional[str] = None
    clock_out_at: Optional[str] = None
    clear_clock_out: Optional[bool] = False


class SettingsTestIn(BaseModel):
    channel: Literal["email", "sms"]
    to: str


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
    return await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})


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


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
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
    if not user or not user.get("password_hash"):
        raise HTTPException(401, "Invalid email or password")
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
@api.put("/profile")
async def update_profile(payload: ProfileUpdateIn, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
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
        "contact_phone": payload.contact_phone,
        "status": "open",
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
    # Workers see only open gigs by default unless they explicitly ask for "all"
    if user.get("role") != "admin" and status is None:
        query["status"] = "open"

    gigs = await db.gigs.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)

    # For workers, attach acceptance state + hide sensitive address until accepted
    if user.get("role") == "worker":
        accepted = await db.gig_acceptances.find(
            {"worker_id": user["user_id"]}, {"_id": 0}
        ).to_list(1000)
        accepted_map = {a["gig_id"]: a for a in accepted}
        out = []
        for g in gigs:
            a = accepted_map.get(g["gig_id"])
            g = _strip_sensitive_for_worker(g, a)
            g["my_acceptance"] = a
            out.append(g)
        return out
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
                    a["projected_earnings"] = _compute_earnings(
                        pay["pay_rate"], pay["pay_type"], a.get("hours_worked")
                    )
        gig["pending_requests"] = [a for a in all_rows if a.get("status") == "requested"]
        gig["acceptances"] = [a for a in all_rows if a.get("status") != "requested"]
    else:
        my = await db.gig_acceptances.find_one(
            {"gig_id": gig_id, "worker_id": user["user_id"]}, {"_id": 0}
        )
        gig = _strip_sensitive_for_worker(gig, my)
        gig["my_acceptance"] = my
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
        "contact_phone": src.get("contact_phone"),
        "status": "open",
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


def _compute_earnings(pay_rate: Optional[float], pay_type: Optional[str], hours: Optional[float]) -> Optional[float]:
    if pay_rate is None or pay_type is None:
        return None
    if pay_type == "hourly":
        return round(float(pay_rate) * float(hours or 0), 2)
    # flat / fixed rate — full posted amount regardless of hours
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

    gig = await db.gigs.find_one({"gig_id": gig_id})
    if not gig:
        raise HTTPException(404, "Gig not found")
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


# ---- Blast -----------------------------------------------------------------
def _format_gig_email(gig: dict) -> str:
    pay = (
        f"${gig['pay_rate']:.2f}/hr"
        if gig["pay_type"] == "hourly"
        else f"${gig['pay_rate']:.2f} flat"
    )
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
            <p style="margin-top:24px;color:#4B5563;font-size:13px;">Open the app to accept this gig before it fills up.</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
    """


def _format_gig_sms(gig: dict) -> str:
    pay = (
        f"${gig['pay_rate']:.0f}/hr"
        if gig["pay_type"] == "hourly"
        else f"${gig['pay_rate']:.0f}"
    )
    return f"[HCOB Network] {gig['title']} — {gig['location']} — {gig['scheduled_date']} — {pay}. Open the app to accept."


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
    gig_id: str, payload: BlastIn, admin: dict = Depends(require_admin)
):
    gig = await db.gigs.find_one({"gig_id": gig_id}, {"_id": 0})
    if not gig:
        raise HTTPException(404, "Gig not found")

    workers = await db.users.find(
        {"role": "worker"}, {"_id": 0, "password_hash": 0}
    ).to_list(1000)

    email_creds = await _resolve_email_creds() if "email" in payload.channels else None
    sms_creds = await _resolve_sms_creds() if "sms" in payload.channels else None

    counts = {"in_app": 0, "email": 0, "sms": 0, "email_failed": 0, "sms_failed": 0}
    subject = f"New Gig: {gig['title']}"
    html = _format_gig_email(gig)
    sms_body = _format_gig_sms(gig)

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

    if notif_docs:
        await db.notifications.insert_many(notif_docs)

    await db.gigs.update_one(
        {"gig_id": gig_id},
        {
            "$set": {
                "last_blast_at": datetime.now(timezone.utc).isoformat(),
                "blast_channels": payload.channels,
            },
            "$inc": {"blast_count": 1},
        },
    )

    return {"ok": True, "counts": counts, "workers_targeted": len(workers)}


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
    workers = await db.users.find(
        query, {"_id": 0, "password_hash": 0}
    ).sort("created_at", -1).to_list(1000)
    return workers


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
                a["projected_earnings"] = _compute_earnings(
                    pay["pay_rate"], pay["pay_type"], a.get("hours_worked")
                )
    w["accepted_gigs"] = accepted
    return w


@api.get("/admin/requests")
async def list_pending_requests(admin: dict = Depends(require_admin)):
    """Return ALL pending gig requests across the platform, flat, sorted oldest first.

    Enriched with gig and worker fields so the admin can decide without opening each gig.
    """
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
    return rows


@api.post("/admin/workers/{user_id}/verify-id")
async def verify_worker_id(user_id: str, admin: dict = Depends(require_admin)):
    await db.users.update_one(
        {"user_id": user_id}, {"$set": {"id_verified": True}}
    )
    return {"ok": True}


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
    earnings = _compute_earnings(pay["pay_rate"], pay["pay_type"], hours)

    await db.gig_acceptances.update_one(
        {"acceptance_id": acceptance["acceptance_id"]},
        {
            "$set": {
                "clock_out_at": now.isoformat(),
                "hours_worked": hours,
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
        new_earnings = _compute_earnings(pay["pay_rate"], pay["pay_type"], refreshed.get("hours_worked"))
        await db.gig_acceptances.update_one(
            {"acceptance_id": acceptance_id},
            {
                "$set": {
                    "pay_rate_applied": pay["pay_rate"],
                    "pay_type_applied": pay["pay_type"],
                    "pay_rate_source": pay["pay_rate_source"],
                    "pay_type_source": pay["pay_type_source"],
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
    elif payload.hours_worked is not None:
        # Recompute earnings using existing rate snapshot, with the new hours
        rate = acceptance.get("pay_rate_applied")
        ptype = acceptance.get("pay_type_applied")
        # Fallback to a fresh resolution if not snapshotted yet
        if rate is None or ptype is None:
            gig = await db.gigs.find_one({"gig_id": gig_id})
            worker = await db.users.find_one({"user_id": acceptance["worker_id"]})
            pay = _resolve_pay(acceptance, worker, gig)
            rate, ptype = pay["pay_rate"], pay["pay_type"]
            set_ops["pay_rate_applied"] = rate
            set_ops["pay_type_applied"] = ptype
        set_ops["earnings"] = _compute_earnings(rate, ptype, set_ops["hours_worked"])

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
        unset_ops["earnings"] = ""
        set_ops["status"] = "accepted"
    else:
        set_ops["clock_in_at"] = new_in.isoformat()

    if new_out is None:
        unset_ops["clock_out_at"] = ""
        unset_ops["hours_worked"] = ""
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
        set_ops["pay_rate_applied"] = pay["pay_rate"]
        set_ops["pay_type_applied"] = pay["pay_type"]
        set_ops["pay_rate_source"] = pay["pay_rate_source"]
        set_ops["pay_type_source"] = pay["pay_type_source"]
        set_ops["earnings"] = _compute_earnings(pay["pay_rate"], pay["pay_type"], hours)
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
        # If earnings not snapshotted (legacy), compute on the fly using current rates
        earnings = r.get("earnings")
        rate = r.get("pay_rate_applied")
        ptype = r.get("pay_type_applied")
        if earnings is None:
            pay = _resolve_pay(r, w, g)
            rate, ptype = pay["pay_rate"], pay["pay_type"]
            earnings = _compute_earnings(rate, ptype, r.get("hours_worked"))
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
    total_earnings = round(sum((r.get("earnings") or 0) for r in rows), 2)
    approved_earnings = round(
        sum((r.get("earnings") or 0) for r in rows if r.get("timesheet_approved")), 2
    )
    return {
        "rows": rows,
        "totals": {
            "rows": len(rows),
            "hours": total_hours,
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
        "Hours", "Pay rate", "Pay type", "Earnings", "Timesheet approved",
    ]
    lines = [",".join(header)]
    for r in rows:
        rate = r.get("pay_rate_applied")
        rate_s = f"{rate:.2f}" if rate is not None else ""
        earnings = r.get("earnings")
        earnings_s = f"{earnings:.2f}" if earnings is not None else ""
        hours = r.get("hours_worked")
        hours_s = f"{hours:.2f}" if hours is not None else ""
        lines.append(",".join(_csv_escape(c) for c in [
            r.get("worker_name") or "",
            r.get("worker_email") or "",
            r.get("gig_title") or "",
            r.get("gig_scheduled_date") or "",
            _fmt_dt_for_csv(r.get("clock_in_at")),
            _fmt_dt_for_csv(r.get("clock_out_at")),
            hours_s,
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


@api.post("/admin/reports/export-google-sheets")
async def admin_reports_export_google_sheets(
    payload: dict,
    admin: dict = Depends(require_admin),
):
    """Export timesheet report to a brand-new Google Sheet using the configured
    service account JSON in admin settings. Returns the sheet URL."""
    s = await _get_settings_doc()
    raw = s.get("google_service_account_json")
    if not raw:
        raise HTTPException(400, "Google service account JSON is not configured in admin settings")

    import json as _json
    try:
        info = _json.loads(raw)
    except Exception:
        raise HTTPException(400, "Saved Google service account JSON is invalid")

    start = payload.get("start")
    end = payload.get("end")
    worker_id = payload.get("worker_id")
    gig_id = payload.get("gig_id")
    only_approved = bool(payload.get("only_approved"))
    rows = await _build_timesheet_rows(start, end, worker_id, gig_id, only_approved)

    title_parts = ["HCOB Timesheets"]
    if start:
        title_parts.append(start[:10])
    if end:
        title_parts.append("→ " + end[:10])
    title_parts.append(datetime.now(timezone.utc).strftime("%H:%M UTC"))
    sheet_title = " ".join(title_parts)

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
            "sheets": [{"properties": {"title": "Timesheets"}}],
        }).execute()
        sheet_id = spreadsheet["spreadsheetId"]

        header = [
            "Worker", "Worker email", "Gig", "Date", "Clock-in", "Clock-out",
            "Hours", "Pay rate", "Pay type", "Earnings", "Timesheet approved",
        ]
        values = [header]
        total_hours = 0.0
        total_earnings = 0.0
        for r in rows:
            hours = r.get("hours_worked") or 0
            earnings = r.get("earnings") or 0
            total_hours += float(hours)
            total_earnings += float(earnings)
            values.append([
                r.get("worker_name") or "",
                r.get("worker_email") or "",
                r.get("gig_title") or "",
                r.get("gig_scheduled_date") or "",
                _fmt_dt_for_csv(r.get("clock_in_at")),
                _fmt_dt_for_csv(r.get("clock_out_at")),
                float(hours),
                float(r.get("pay_rate_applied") or 0),
                r.get("pay_type_applied") or "",
                float(earnings),
                "yes" if r.get("timesheet_approved") else "no",
            ])
        values.append([])
        values.append(["TOTALS", "", "", "", "", "", round(total_hours, 2), "", "", round(total_earnings, 2), ""])

        sheets.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="Timesheets!A1",
            valueInputOption="RAW",
            body={"values": values},
        ).execute()

        # Share with the admin email so they can open it
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
            "total_hours": round(total_hours, 2),
            "total_earnings": round(total_earnings, 2),
        }

    try:
        result = await asyncio.to_thread(_build)
    except Exception as e:
        logger.error(f"Google Sheets export failed: {e}")
        raise HTTPException(400, f"Google Sheets export failed: {e}")
    logger.info(f"Admin {admin['email']} exported timesheets to {result['url']}")
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
    approved_earnings = 0.0
    pending_count = 0
    pending_hours = 0.0
    for r in rows:
        g = gmap.get(r["gig_id"]) or {}
        hours = r.get("hours_worked") or 0
        earnings = r.get("earnings")
        if r.get("timesheet_approved"):
            approved_hours += float(hours)
            approved_earnings += float(earnings or 0)
            approved_rows.append({
                "acceptance_id": r["acceptance_id"],
                "gig_id": r["gig_id"],
                "gig_title": g.get("title"),
                "gig_category": g.get("category"),
                "gig_scheduled_date": g.get("scheduled_date"),
                "clock_in_at": r.get("clock_in_at"),
                "clock_out_at": r.get("clock_out_at"),
                "hours_worked": r.get("hours_worked"),
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
