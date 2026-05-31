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
            {"_id": 0, "gig_id": 1, "title": 1, "category": 1, "scheduled_date": 1},
        ).to_list(500)
        gmap = {g["gig_id"]: g for g in gigs}
        for a in accepted:
            g = gmap.get(a["gig_id"]) or {}
            a["gig_title"] = g.get("title")
            a["gig_category"] = g.get("category")
            a["gig_scheduled_date"] = g.get("scheduled_date")
    w["accepted_gigs"] = accepted
    return w


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
    await db.gig_acceptances.update_one(
        {"acceptance_id": acceptance["acceptance_id"]},
        {
            "$set": {
                "clock_out_at": now.isoformat(),
                "hours_worked": hours,
                "status": "completed",
            }
        },
    )
    return {"ok": True, "clock_out_at": now.isoformat(), "hours_worked": hours}


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
    return {
        "resend_api_key": _mask(s.get("resend_api_key")),
        "sender_email": s.get("sender_email") or SENDER_EMAIL or "",
        "twilio_account_sid": _mask(s.get("twilio_account_sid")),
        "twilio_auth_token": _mask(s.get("twilio_auth_token")),
        "twilio_from_number": s.get("twilio_from_number") or TWILIO_FROM or "",
        "email_ready": bool(email["api_key"] and email["sender"]),
        "sms_ready": bool(sms["sid"] and sms["token"] and sms["from_"]),
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
