"""All Pydantic request/response models — shared across routes.

Type aliases (GigCategory, PayType, etc.) live here too so they're available
to anyone importing models.
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field

# ----- Type aliases ----------------------------------------------------------
GigCategory = Literal["cleaning", "labor", "driver"]
PayType = Literal["hourly", "flat"]
GigRecurrence = Literal["none", "daily", "weekly", "biweekly", "monthly"]
GigTag = Literal["rush", "priority_need", "same_day", "top_pay"]
WorkerStatus = Literal["pending", "approved", "rejected", "suspended"]


# ----- Auth ------------------------------------------------------------------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str
    role: Optional[Literal["worker", "admin", "va"]] = "worker"
    # VA-only optional fields captured at signup
    va_phone: Optional[str] = None
    va_address: Optional[str] = None  # registered home address — self-referral check


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class GoogleSessionIn(BaseModel):
    session_id: str


class AdminResetPasswordIn(BaseModel):
    new_password: Optional[str] = None  # If None/blank, server generates a temp password


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=10)
    new_password: str = Field(min_length=6)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


# ----- Profile ---------------------------------------------------------------
class ProfileUpdateIn(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    bio: Optional[str] = None
    skills: Optional[List[str]] = None
    # Extended profile fields
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
    # Payout method — one preferred per worker. We don't validate identifier
    # format strictly (Zelle accepts phone OR email, Chime uses $username) —
    # admin eyeballs it before sending money.
    payout_method: Optional[Literal["zelle", "apple_cash", "chime"]] = None
    payout_handle: Optional[str] = Field(default=None, max_length=120)


# ----- Gigs ------------------------------------------------------------------
class GigIn(BaseModel):
    title: str
    description: str
    category: GigCategory
    subcategory: Optional[str] = None
    location: str  # PUBLIC preview — e.g. "Oak Ave · 94110" — visible to all workers
    address_line: Optional[str] = None  # SENSITIVE — revealed only after accept
    scheduled_date: str  # display string (kept for backwards compat / human display)
    scheduled_at: Optional[str] = None  # ISO 8601 datetime — drives the calendar
    # Wall-clock at the job site (TZ-free). Format: "YYYY-MM-DDTHH:mm".
    # Single source of truth — same string is shown to admin and workers in any TZ.
    scheduled_local: Optional[str] = None
    pay_rate: float
    pay_type: PayType
    slots: int = 1
    # Optional backup pool. Workers approved as backups get auto-promoted to
    # primary when an approved worker cancels (or admin manually promotes).
    backup_slots: int = 0
    duration_hours: Optional[float] = None
    # Unpaid break minutes deducted from each worker's clocked time. Default
    # is 0 — admin sets it per-gig in the Create/Edit dialog. Per-worker
    # override lives on the acceptance.
    break_minutes: Optional[int] = 0
    # When workers can expect payment.
    payment_timeline: Optional[
        Literal["same_day", "2_3_days", "weekly", "custom"]
    ] = "2_3_days"
    payment_timeline_note: Optional[str] = None
    contact_phone: Optional[str] = None
    # Optional link to a parent project. When set, this gig is shown alongside
    # its sibling gigs in the worker UI so the crews can coordinate.
    project_id: Optional[str] = None
    # Recurrence — optional. If recurrence != 'none', the create endpoint
    # generates `repeat_count` gig instances spaced by the chosen period.
    recurrence: Optional[GigRecurrence] = "none"
    repeat_count: Optional[int] = 1  # ignored when recurrence == 'none'
    # Optional "Coming soon" → "Open" toggle.
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
    scheduled_local: Optional[str] = None
    pay_rate: Optional[float] = None
    pay_type: Optional[PayType] = None
    slots: Optional[int] = None
    backup_slots: Optional[int] = None
    duration_hours: Optional[float] = None
    break_minutes: Optional[int] = None
    payment_timeline: Optional[
        Literal["same_day", "2_3_days", "weekly", "custom"]
    ] = None
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


class GigTagsIn(BaseModel):
    """Replace the gig's `tags` array entirely. Any tag pins the gig to the
    top of the feed. Pass an empty list to clear all tags."""
    tags: List[GigTag]


class AssignWorkerIn(BaseModel):
    worker_id: str


class CancelShiftIn(BaseModel):
    reason: Literal["sick", "conflict", "transportation", "other"]
    note: Optional[str] = None


# ----- Pay / Timesheets ------------------------------------------------------
class WorkerPayIn(BaseModel):
    """Set a worker's default pay rate/type. Either field can be cleared with
    `null` by sending an explicit JSON `null`."""
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
    """Admin edits raw clock-in/out times. Passing `clear_clock_out=true`
    reverts the acceptance back to on-the-clock state."""
    clock_in_at: Optional[str] = None
    clock_out_at: Optional[str] = None
    clear_clock_out: Optional[bool] = False
    break_minutes: Optional[int] = None
    # Free-text admin note attached to the acceptance — visible to admins on
    # the worker detail page. When provided, also recorded with the editing
    # admin's email + ISO timestamp.
    admin_note: Optional[str] = Field(default=None, max_length=2000)


class AcceptanceNoShowIn(BaseModel):
    """Mark an acceptance as a no-show. Reason is required so the audit log
    captures WHY (separate from the 'rule #1: first no-show = auto-delete'
    rule, which fires elsewhere)."""
    reason: str = Field(..., min_length=1, max_length=500)
    admin_note: Optional[str] = Field(default=None, max_length=2000)


class AcceptanceMarkCompletedIn(BaseModel):
    """Force-mark an acceptance as completed (worker forgot to clock out but
    finished the gig). If clock_in_at is missing we'll fall back to the gig's
    scheduled start. clock_out_at defaults to gig start + duration_hours."""
    clock_in_at: Optional[str] = None
    clock_out_at: Optional[str] = None
    admin_note: Optional[str] = Field(default=None, max_length=2000)


class AcceptanceRemoveIn(BaseModel):
    """Optional metadata sent when an admin removes a worker from a gig."""
    reason: Optional[Literal[
        "worker_requested", "no_show", "admin_decision", "scheduling_conflict", "other"
    ]] = None
    admin_note: Optional[str] = Field(default=None, max_length=2000)


# ----- Projects --------------------------------------------------------------
class ProjectDefaults(BaseModel):
    """Pre-fill values when adding a new gig under a project."""
    location: Optional[str] = None
    address_line: Optional[str] = None
    scheduled_date: Optional[str] = None
    scheduled_at: Optional[str] = None
    payment_timeline: Optional[
        Literal["same_day", "2_3_days", "weekly", "custom"]
    ] = None
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
    sync_defaults: Optional[bool] = False


# ----- Ratings ---------------------------------------------------------------
class AdminRatingIn(BaseModel):
    """Admin sets a 1-5 star rating for a worker on a specific gig."""
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


# ----- Settings --------------------------------------------------------------
class SettingsIn(BaseModel):
    resend_api_key: Optional[str] = None
    sender_email: Optional[str] = None
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_from_number: Optional[str] = None
    google_service_account_json: Optional[str] = None
    google_sheets_share_email: Optional[str] = None


class SettingsTestIn(BaseModel):
    channel: Literal["email", "sms"]
    to: str


# ----- Public quote leads ----------------------------------------------------
class QuoteRequestIn(BaseModel):
    """Public lead capture from /customers — a prospective client requesting a
    quote. Honeypot field 'website' silently rejected."""
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=7, max_length=40)
    email: Optional[str] = None
    service: str = Field(min_length=2, max_length=120)
    timeline: str = Field(min_length=1, max_length=60)
    message: Optional[str] = Field(default=None, max_length=2000)
    address: Optional[str] = Field(default=None, max_length=240)
    website: Optional[str] = None  # honeypot


class QuoteRequestPatch(BaseModel):
    status: Optional[Literal["new", "contacted", "won", "lost", "dismissed"]] = None
    admin_note: Optional[str] = None


# ----- Web push --------------------------------------------------------------
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


# ----- Worker status / admin moderation --------------------------------------
class WorkerStatusIn(BaseModel):
    note: Optional[str] = None  # Optional internal note for the action


# ----- Messenger -------------------------------------------------------------
class MessageSendIn(BaseModel):
    text: Optional[str] = Field(default=None, max_length=4000)
    attachment_paths: Optional[List[str]] = None
    # Optional companion channels (in addition to in-app delivery, which is
    # always done). Defaults to None / empty == in-app only.
    # Allowed values: "email", "sms". Only admins/owners/PMs may set this;
    # the server ignores it from workers/VAs.
    channels: Optional[List[str]] = None


class OpenDMIn(BaseModel):
    user_id: str



# ----- Worker Agreement (gig accept gate) ------------------------------------
# Canonical, versioned set of rules a worker must agree to EVERY time they
# request a gig. Bumping the version (v2, v3, …) forces the frontend to surface
# the new ruleset and stores the version on each agreement record so we always
# know which rules a worker actually signed.
WORKER_AGREEMENT_VERSION = "v1"
WORKER_AGREEMENT_RULES_V1 = [
    "No-shows on first gigs are an automatic deletion from the platform.",
    "You will be professional when on your gig site.",
    "You must clock in on your shift, or you may not be paid.",
]


class WorkerAgreementIn(BaseModel):
    """Body the worker submits when requesting a gig. The frontend renders the
    rules returned by GET /worker/agreement-rules and echoes them back here so
    we can detect tampering. Typed name must match the worker's account name
    (case-insensitive, whitespace-trimmed)."""

    typed_name: str = Field(..., min_length=1, max_length=200)
    agreed_rules: List[str] = Field(..., min_items=1, max_items=20)
    version: str = Field(default=WORKER_AGREEMENT_VERSION, max_length=10)
