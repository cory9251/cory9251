"""Professional Certification Badges + Testing system.

Workers take a one-shot multiple-choice test per badge, upload proof
(certifications / portfolio), and an admin approves after internal review.
Certified badges unlock specialty gigs (gig.required_badge_id gate).
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from config import db, logger, APP_NAME, EMERGENT_LLM_KEY
from auth_deps import get_current_user, require_admin
from storage import put_object, validate_upload

router = APIRouter()

MAX_DOC_BYTES = 10 * 1024 * 1024
MAX_DOCS = 10

QUIZ_SYSTEM_PROMPT = """You write multiple-choice certification test questions for skilled-trade workers on a dispatch platform (cleaning, electrical, plumbing, drywall, painting, box-truck driving, etc.).
Return ONLY a raw JSON array — no markdown fences, no commentary. Each element must be exactly:
{"q": "question text", "options": ["A", "B", "C", "D"], "correct_index": 0}
Rules: exactly 4 options per question; correct_index is 0-3; questions must be practical, safety- and field-knowledge focused at a working-professional level; no trick questions; vary which index holds the correct answer."""


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class BadgeIn(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#0044FF"
    pass_pct: int = 80
    questions: List[dict] = []
    active: bool = True


class BadgePatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    pass_pct: Optional[int] = None
    questions: Optional[List[dict]] = None
    active: Optional[bool] = None


class QuizGenIn(BaseModel):
    topic: str
    description: Optional[str] = None
    num_questions: int = 8


class TestSubmitIn(BaseModel):
    answers: List[int]


class BadgeSubmitIn(BaseModel):
    portfolio_links: List[str] = []
    notes: Optional[str] = None


class ReviewIn(BaseModel):
    note: Optional[str] = None


def _validate_questions(questions: List[dict]) -> List[dict]:
    if not isinstance(questions, list):
        raise HTTPException(400, "questions must be a list")
    clean = []
    for i, q in enumerate(questions):
        text = str(q.get("q") or "").strip()
        options = q.get("options")
        if not text:
            raise HTTPException(400, f"Question {i + 1} is missing its text")
        if not isinstance(options, list) or not (2 <= len(options) <= 6):
            raise HTTPException(400, f"Question {i + 1} needs 2-6 options")
        options = [str(o).strip() for o in options]
        if any(not o for o in options):
            raise HTTPException(400, f"Question {i + 1} has an empty option")
        try:
            ci = int(q.get("correct_index"))
        except (TypeError, ValueError):
            raise HTTPException(400, f"Question {i + 1} is missing the correct answer")
        if not (0 <= ci < len(options)):
            raise HTTPException(400, f"Question {i + 1} correct answer is out of range")
        clean.append({"q": text[:500], "options": [o[:300] for o in options], "correct_index": ci})
    return clean


def _require_worker(user: dict) -> None:
    if user.get("role") != "worker":
        raise HTTPException(403, "Only workers can use certifications")


async def _get_application(badge_id: str, user_id: str) -> Optional[dict]:
    return await db.badge_applications.find_one(
        {"badge_id": badge_id, "user_id": user_id}, {"_id": 0}
    )


async def _notify(user_id: str, title: str, body: str) -> None:
    await db.notifications.insert_one({
        "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "gig_id": None,
        "title": title,
        "body": body,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


# ---------------------------------------------------------------------------
# Worker endpoints
# ---------------------------------------------------------------------------
@router.get("/worker/badges")
async def worker_badges(user: dict = Depends(get_current_user)):
    _require_worker(user)
    badges = await db.badges.find({"active": True}, {"_id": 0}).sort("name", 1).to_list(200)
    apps = await db.badge_applications.find(
        {"user_id": user["user_id"]}, {"_id": 0, "answers": 0}
    ).to_list(200)
    amap = {a["badge_id"]: a for a in apps}
    certified = set(user.get("certified_badges") or [])
    out = []
    for b in badges:
        out.append({
            "badge_id": b["badge_id"],
            "name": b["name"],
            "description": b.get("description"),
            "color": b.get("color") or "#0044FF",
            "pass_pct": int(b.get("pass_pct") or 80),
            "question_count": len(b.get("questions") or []),
            "certified": b["badge_id"] in certified,
            "application": amap.get(b["badge_id"]),
        })
    return out


@router.get("/worker/badges/{badge_id}/test")
async def worker_get_test(badge_id: str, user: dict = Depends(get_current_user)):
    _require_worker(user)
    badge = await db.badges.find_one({"badge_id": badge_id, "active": True}, {"_id": 0})
    if not badge:
        raise HTTPException(404, "Certification not found")
    questions = badge.get("questions") or []
    if not questions:
        raise HTTPException(400, "This certification's test isn't ready yet — check back soon")
    if await _get_application(badge_id, user["user_id"]):
        raise HTTPException(400, "You've already taken this test — retakes require HCOB approval")
    return {
        "badge_id": badge_id,
        "name": badge["name"],
        "pass_pct": int(badge.get("pass_pct") or 80),
        "questions": [{"q": q["q"], "options": q["options"]} for q in questions],
    }


@router.post("/worker/badges/{badge_id}/test")
async def worker_submit_test(
    badge_id: str, payload: TestSubmitIn, user: dict = Depends(get_current_user)
):
    _require_worker(user)
    badge = await db.badges.find_one({"badge_id": badge_id, "active": True}, {"_id": 0})
    if not badge:
        raise HTTPException(404, "Certification not found")
    questions = badge.get("questions") or []
    if not questions:
        raise HTTPException(400, "This certification's test isn't ready yet")
    if await _get_application(badge_id, user["user_id"]):
        raise HTTPException(400, "You've already taken this test — retakes require HCOB approval")
    if len(payload.answers) != len(questions):
        raise HTTPException(400, "Answer every question before submitting")

    correct = sum(
        1 for i, q in enumerate(questions) if payload.answers[i] == q["correct_index"]
    )
    score = round(correct / len(questions) * 100)
    pass_pct = int(badge.get("pass_pct") or 80)
    passed = score >= pass_pct
    now = datetime.now(timezone.utc).isoformat()
    app_doc = {
        "application_id": f"bapp_{uuid.uuid4().hex[:12]}",
        "badge_id": badge_id,
        "user_id": user["user_id"],
        "status": "test_passed" if passed else "test_failed",
        "score_pct": score,
        "answers": payload.answers,
        "test_submitted_at": now,
        "documents": [],
        "portfolio_links": [],
        "notes": None,
        "created_at": now,
    }
    await db.badge_applications.insert_one(app_doc)
    return {"score_pct": score, "passed": passed, "pass_pct": pass_pct,
            "status": app_doc["status"]}


@router.post("/worker/badges/{badge_id}/documents")
async def worker_upload_doc(
    badge_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)
):
    _require_worker(user)
    app = await _get_application(badge_id, user["user_id"])
    if not app:
        badge = await db.badges.find_one({"badge_id": badge_id, "active": True}, {"_id": 0})
        if badge is not None and not (badge.get("questions") or []):
            # Doc-only certification (Forklift / CDL) — no test, straight to upload.
            app = {
                "application_id": f"bap_{uuid.uuid4().hex[:12]}",
                "badge_id": badge_id,
                "user_id": user["user_id"],
                "status": "test_passed",
                "score_pct": None,
                "doc_only": True,
                "documents": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.badge_applications.insert_one(dict(app))
        else:
            raise HTTPException(400, "Pass the test first, then upload your credentials")
    elif app.get("status") != "test_passed":
        raise HTTPException(400, "Pass the test first, then upload your credentials")
    if len(app.get("documents") or []) >= MAX_DOCS:
        raise HTTPException(400, f"Max {MAX_DOCS} documents per application")
    data = await file.read()
    if len(data) > MAX_DOC_BYTES:
        raise HTTPException(400, "File too large (max 10MB)")
    ext, ct = validate_upload(data, file.filename or "", allow_pdf=True)
    path = f"{APP_NAME}/badges/{user['user_id']}/{badge_id}/{uuid.uuid4().hex}.{ext}"
    result = await asyncio.to_thread(put_object, path, data, ct)
    now = datetime.now(timezone.utc).isoformat()
    await db.files.insert_one({
        "file_id": str(uuid.uuid4()),
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": ct,
        "size": result.get("size"),
        "owner_id": user["user_id"],
        "kind": "badge_doc",
        "created_at": now,
    })
    doc = {"path": result["path"], "filename": file.filename or "document", "content_type": ct}
    await db.badge_applications.update_one(
        {"application_id": app["application_id"]}, {"$push": {"documents": doc}}
    )
    return {"documents": (app.get("documents") or []) + [doc]}


@router.delete("/worker/badges/{badge_id}/documents")
async def worker_remove_doc(
    badge_id: str, path: str = Query(...), user: dict = Depends(get_current_user)
):
    _require_worker(user)
    app = await _get_application(badge_id, user["user_id"])
    if not app or app.get("status") != "test_passed":
        raise HTTPException(400, "Documents can only be changed before you submit for review")
    await db.badge_applications.update_one(
        {"application_id": app["application_id"]}, {"$pull": {"documents": {"path": path}}}
    )
    return {"ok": True}


@router.post("/worker/badges/{badge_id}/submit")
async def worker_submit_review(
    badge_id: str, payload: BadgeSubmitIn, user: dict = Depends(get_current_user)
):
    _require_worker(user)
    app = await _get_application(badge_id, user["user_id"])
    if not app:
        raise HTTPException(400, "Take the test first")
    if app.get("status") != "test_passed":
        raise HTTPException(400, "This application can't be submitted right now")
    links = [l.strip()[:300] for l in (payload.portfolio_links or []) if l and l.strip()][:10]
    if not (app.get("documents") or []) and not links:
        raise HTTPException(400, "Add at least one certification document or portfolio link")
    now = datetime.now(timezone.utc).isoformat()
    await db.badge_applications.update_one(
        {"application_id": app["application_id"]},
        {"$set": {
            "status": "pending_review",
            "portfolio_links": links,
            "notes": (payload.notes or "").strip()[:1000] or None,
            "submitted_at": now,
        }},
    )
    return await _get_application(badge_id, user["user_id"])


# ---------------------------------------------------------------------------
# Admin — badge management
# ---------------------------------------------------------------------------
@router.get("/admin/badges")
async def admin_list_badges(admin: dict = Depends(require_admin)):
    badges = await db.badges.find({}, {"_id": 0}).sort("name", 1).to_list(200)
    counts = await db.badge_applications.aggregate([
        {"$group": {"_id": {"b": "$badge_id", "s": "$status"}, "n": {"$sum": 1}}}
    ]).to_list(1000)
    cmap: dict = {}
    for c in counts:
        cmap.setdefault(c["_id"]["b"], {})[c["_id"]["s"]] = c["n"]
    for b in badges:
        b["holders"] = await db.users.count_documents({"certified_badges": b["badge_id"]})
        b["pending_review"] = (cmap.get(b["badge_id"]) or {}).get("pending_review", 0)
    return badges


@router.post("/admin/badges")
async def admin_create_badge(payload: BadgeIn, admin: dict = Depends(require_admin)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "Name is required")
    if not (0 < payload.pass_pct <= 100):
        raise HTTPException(400, "Pass % must be between 1 and 100")
    doc = {
        "badge_id": f"bdg_{uuid.uuid4().hex[:12]}",
        "name": name[:100],
        "description": (payload.description or "").strip()[:500] or None,
        "color": payload.color or "#0044FF",
        "pass_pct": payload.pass_pct,
        "questions": _validate_questions(payload.questions),
        "active": payload.active,
        "created_by": admin["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.badges.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/admin/badges/{badge_id}")
async def admin_update_badge(
    badge_id: str, payload: BadgePatch, admin: dict = Depends(require_admin)
):
    badge = await db.badges.find_one({"badge_id": badge_id})
    if not badge:
        raise HTTPException(404, "Badge not found")
    updates = payload.model_dump(exclude_unset=True)
    if "questions" in updates:
        updates["questions"] = _validate_questions(updates["questions"])
    if "pass_pct" in updates and not (0 < int(updates["pass_pct"]) <= 100):
        raise HTTPException(400, "Pass % must be between 1 and 100")
    if "name" in updates:
        updates["name"] = str(updates["name"]).strip()[:100]
    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.badges.update_one({"badge_id": badge_id}, {"$set": updates})
    return await db.badges.find_one({"badge_id": badge_id}, {"_id": 0})


@router.delete("/admin/badges/{badge_id}")
async def admin_delete_badge(badge_id: str, admin: dict = Depends(require_admin)):
    badge = await db.badges.find_one({"badge_id": badge_id})
    if not badge:
        raise HTTPException(404, "Badge not found")
    await db.badges.delete_one({"badge_id": badge_id})
    await db.badge_applications.delete_many({"badge_id": badge_id})
    await db.users.update_many({}, {"$pull": {"certified_badges": badge_id}})
    await db.gigs.update_many(
        {"required_badge_id": badge_id}, {"$set": {"required_badge_id": None}}
    )
    return {"ok": True}


@router.post("/admin/badges/generate-quiz")
async def admin_generate_quiz(payload: QuizGenIn, admin: dict = Depends(require_admin)):
    if not payload.topic.strip():
        raise HTTPException(400, "Give the AI a topic")
    n = max(3, min(20, payload.num_questions))
    if not EMERGENT_LLM_KEY:
        raise HTTPException(503, "AI is not configured on this environment")

    from emergentintegrations.llm.chat import LlmChat, UserMessage

    prompt = f"Write {n} certification test questions for the trade/specialty: {payload.topic.strip()}."
    if payload.description and payload.description.strip():
        prompt += f"\nContext about this certification: {payload.description.strip()[:1000]}"
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"badge-quiz::{admin['user_id']}::{uuid.uuid4().hex[:8]}",
        system_message=QUIZ_SYSTEM_PROMPT,
    ).with_model("anthropic", "claude-sonnet-4-6")
    try:
        raw = await chat.send_message(UserMessage(text=prompt))
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Badge quiz generation failed: {e}")
        raise HTTPException(502, "Could not reach the AI right now — try again in a minute")

    s = str(raw).strip()
    start, end = s.find("["), s.rfind("]")
    if start == -1 or end <= start:
        raise HTTPException(502, "The AI returned an unreadable quiz — try again")
    try:
        questions = json.loads(s[start:end + 1])
    except json.JSONDecodeError:
        raise HTTPException(502, "The AI returned an unreadable quiz — try again")
    return {"questions": _validate_questions(questions)}


# ---------------------------------------------------------------------------
# Admin — application review
# ---------------------------------------------------------------------------
@router.get("/admin/badge-applications")
async def admin_list_applications(
    status: str = Query("pending_review"), admin: dict = Depends(require_admin)
):
    query = {} if status == "all" else {"status": status}
    apps = await db.badge_applications.find(query, {"_id": 0, "answers": 0}).sort(
        "created_at", -1
    ).to_list(500)
    if not apps:
        return []
    uids = list({a["user_id"] for a in apps})
    bids = list({a["badge_id"] for a in apps})
    users = await db.users.find(
        {"user_id": {"$in": uids}}, {"_id": 0, "user_id": 1, "name": 1, "email": 1, "phone": 1}
    ).to_list(500)
    badges = await db.badges.find(
        {"badge_id": {"$in": bids}}, {"_id": 0, "badge_id": 1, "name": 1, "color": 1, "pass_pct": 1}
    ).to_list(200)
    umap = {u["user_id"]: u for u in users}
    bmap = {b["badge_id"]: b for b in badges}
    for a in apps:
        u = umap.get(a["user_id"]) or {}
        b = bmap.get(a["badge_id"]) or {}
        a["worker_name"] = u.get("name")
        a["worker_email"] = u.get("email")
        a["worker_phone"] = u.get("phone")
        a["badge_name"] = b.get("name")
        a["badge_color"] = b.get("color")
        a["pass_pct"] = b.get("pass_pct")
    return apps


async def _load_app_and_badge(application_id: str):
    app = await db.badge_applications.find_one({"application_id": application_id}, {"_id": 0})
    if not app:
        raise HTTPException(404, "Application not found")
    badge = await db.badges.find_one({"badge_id": app["badge_id"]}, {"_id": 0, "name": 1})
    return app, (badge or {}).get("name") or "certification"


@router.post("/admin/badge-applications/{application_id}/approve")
async def admin_approve_application(
    application_id: str, payload: ReviewIn, admin: dict = Depends(require_admin)
):
    app, badge_name = await _load_app_and_badge(application_id)
    if app.get("status") != "pending_review":
        raise HTTPException(400, "Only submitted applications can be approved")
    now = datetime.now(timezone.utc).isoformat()
    await db.badge_applications.update_one(
        {"application_id": application_id},
        {"$set": {"status": "approved", "reviewed_by": admin["email"],
                  "reviewed_at": now, "admin_note": (payload.note or "").strip()[:500] or None}},
    )
    await db.users.update_one(
        {"user_id": app["user_id"]}, {"$addToSet": {"certified_badges": app["badge_id"]}}
    )
    # Cert-tag badges (Forklift / CDL) also feed the dispatch skill tags.
    badge_doc = await db.badges.find_one({"badge_id": app["badge_id"]}, {"_id": 0, "skill_tag": 1})
    tag = (badge_doc or {}).get("skill_tag")
    if tag:
        await db.users.update_one(
            {"user_id": app["user_id"]}, {"$pull": {"cert_tags": {"tag": tag}}}
        )
        await db.users.update_one(
            {"user_id": app["user_id"]},
            {"$push": {"cert_tags": {"tag": tag, "verified": True, "grace_until": None, "source": "badge"}}},
        )
        from worker_taxonomy import sync_user_skills
        await sync_user_skills(app["user_id"])
    await _notify(
        app["user_id"],
        f"You're certified: {badge_name}",
        f"HCOB approved your {badge_name} certification. You now get first access to specialty assignments that require it.",
    )
    return {"ok": True, "status": "approved"}


@router.post("/admin/badge-applications/{application_id}/reject")
async def admin_reject_application(
    application_id: str, payload: ReviewIn, admin: dict = Depends(require_admin)
):
    app, badge_name = await _load_app_and_badge(application_id)
    if app.get("status") != "pending_review":
        raise HTTPException(400, "Only submitted applications can be rejected")
    now = datetime.now(timezone.utc).isoformat()
    note = (payload.note or "").strip()[:500] or None
    await db.badge_applications.update_one(
        {"application_id": application_id},
        {"$set": {"status": "rejected", "reviewed_by": admin["email"],
                  "reviewed_at": now, "admin_note": note}},
    )
    await _notify(
        app["user_id"],
        f"Certification not approved: {badge_name}",
        (note or "HCOB reviewed your application and it wasn't approved this time.")
        + " Contact HCOB if you have questions.",
    )
    return {"ok": True, "status": "rejected"}


@router.post("/admin/badge-applications/{application_id}/reset")
async def admin_reset_application(
    application_id: str, admin: dict = Depends(require_admin)
):
    """Delete the application so the worker can retake the test. Revokes the
    badge if it had been approved."""
    app, badge_name = await _load_app_and_badge(application_id)
    await db.badge_applications.delete_one({"application_id": application_id})
    if app.get("status") == "approved":
        await db.users.update_one(
            {"user_id": app["user_id"]}, {"$pull": {"certified_badges": app["badge_id"]}}
        )
    await _notify(
        app["user_id"],
        f"Certification reset: {badge_name}",
        f"HCOB reset your {badge_name} application — you can retake the test from your Certifications page.",
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Seed — 6 specialty badges with pre-written tests (idempotent)
# ---------------------------------------------------------------------------
def _q(q, options, ci):
    return {"q": q, "options": options, "correct_index": ci}


SEED_BADGES = [
    {
        # Doc-only certification (FRD Addendum A) — no test, upload the card.
        "seed_key": "forklift_cert",
        "name": "Forklift Certification",
        "description": "Upload your current forklift operator certification card. No test required — HCOB verifies the document.",
        "color": "#F97316",
        "skill_tag": "forklift",
        "questions": [],
    },
    {
        # Doc-only certification — CDL lives here ONLY (removed from Vehicle).
        "seed_key": "cdl_license",
        "name": "CDL (Commercial Driver's License)",
        "description": "Upload a photo of your valid CDL. No test required — HCOB verifies the license.",
        "color": "#0044FF",
        "skill_tag": "cdl",
        "questions": [],
    },
    {
        "seed_key": "cleaning_pro",
        "name": "Certified Cleaning Pro",
        "description": "Residential & commercial cleaning: chemicals, cross-contamination, deep-clean methods, and site safety.",
        "color": "#0EA5E9",
        "questions": [
            _q("Which product should NEVER be mixed with bleach?", ["Dish soap", "Ammonia-based cleaner", "Baking soda", "Plain water"], 1),
            _q("When deep cleaning a room, the correct order is:", ["Floors first, then surfaces", "Top to bottom", "Bathroom last, always", "Whatever is dirtiest first"], 1),
            _q("Disinfectant 'dwell time' means:", ["How long the bottle lasts", "Time to wipe immediately after spraying", "Keeping the surface visibly wet for the label-listed time", "Time between restocking supplies"], 2),
            _q("Color-coded microfiber cloths are used to:", ["Look professional", "Prevent cross-contamination between areas", "Match the client's decor", "Track which cloths are newest"], 1),
            _q("Which surface should NOT be cleaned with an acidic cleaner like vinegar?", ["Glass", "Stainless steel", "Natural stone (marble/granite)", "Ceramic tile"], 2),
            _q("Before wet-mopping a commercial floor you should:", ["Turn off the lights", "Place wet floor signs and dust mop/sweep first", "Apply wax", "Soak the entire floor at once"], 1),
            _q("The correct restroom cleaning approach is:", ["Toilet first, sink last", "Cleanest to dirtiest — fixtures before toilet", "Spray everything and wipe in any order", "Only what looks dirty"], 1),
            _q("OSHA requires which document be available for chemicals on site?", ["A purchase receipt", "Safety Data Sheet (SDS)", "The manufacturer's catalog", "A cleaning checklist"], 1),
        ],
    },
    {
        "seed_key": "electrician",
        "name": "Certified Electrician",
        "description": "Electrical work: circuits, grounding, GFCI, lockout/tagout, and safe de-energizing practices.",
        "color": "#F59E0B",
        "questions": [
            _q("Standard US residential branch-circuit voltage is:", ["12V", "48V", "120V", "480V"], 2),
            _q("The ground wire in US wiring is:", ["Black", "Red", "White", "Green or bare copper"], 3),
            _q("GFCI protection is required:", ["Only in bedrooms", "Near water — bathrooms, kitchens, outdoors", "Only on 240V circuits", "Nowhere in residences"], 1),
            _q("Before working on a circuit you must:", ["Wear rubber boots only", "Work quickly with one hand", "De-energize and verify dead with a tester (lockout/tagout)", "Ask the homeowner to hold the breaker"], 2),
            _q("A 15-amp branch circuit typically uses which copper wire gauge?", ["18 AWG", "16 AWG", "14 AWG", "10 AWG"], 2),
            _q("A breaker that keeps tripping means:", ["Replace it with a bigger breaker", "Overload or fault — investigate the cause", "Normal wear, ignore it", "The utility has a problem"], 1),
            _q("The neutral conductor in US wiring is typically:", ["Green", "White", "Black", "Bare copper"], 1),
            _q("Which tool confirms a circuit is de-energized?", ["A flashlight", "Non-contact voltage tester or multimeter", "A wire stripper", "Touching it briefly"], 1),
        ],
    },
    {
        "seed_key": "plumber",
        "name": "Certified Plumber",
        "description": "Plumbing: supply & drain systems, traps, water heaters, and leak-safe repair practices.",
        "color": "#3B82F6",
        "questions": [
            _q("Standard slope for horizontal drain piping is:", ["Dead level", "1/4 inch per foot", "2 inches per foot", "Whatever fits the joists"], 1),
            _q("The purpose of a P-trap is to:", ["Increase water pressure", "Catch jewelry", "Block sewer gases from entering the building", "Filter sediment"], 2),
            _q("First step before repairing a supply line:", ["Open all faucets", "Shut off the water supply", "Heat the pipe", "Remove the water meter"], 1),
            _q("PTFE (Teflon) tape is wrapped around threads:", ["Counter-clockwise, 1 wrap", "Clockwise, in the direction of the threads", "Any direction, 10+ wraps", "Only on plastic fittings"], 1),
            _q("A water heater's T&P valve:", ["Boosts water temperature", "Relieves excess temperature and pressure", "Filters hard water", "Controls gas flow"], 1),
            _q("Rigid copper pipe is traditionally joined by:", ["Duct tape", "Soldering (sweating)", "Hot glue", "Friction fit"], 1),
            _q("A constantly running toilet is most often caused by:", ["A broken handle", "A faulty flapper valve", "High water pressure", "A clogged vent"], 1),
            _q("A key advantage of PEX over rigid copper is:", ["It's always cheaper to insure", "Flexible runs with fewer fittings and better freeze resistance", "It conducts electricity", "It needs no supports"], 1),
        ],
    },
    {
        "seed_key": "truck_operator",
        "name": "Cargo Van / Box Truck Operator",
        "description": "Commercial driving: pre-trip inspections, load securement, clearances, and safe maneuvering.",
        "color": "#10B981",
        "questions": [
            _q("Before every trip you should:", ["Check fuel only", "Do a pre-trip inspection — lights, tires, brakes, mirrors", "Warm the engine for 20 minutes", "Load first, inspect later"], 1),
            _q("Heavy cargo should be loaded:", ["High and toward the rear doors", "Low, evenly distributed, and secured against shifting", "Loose so it's faster to unload", "All on one side"], 1),
            _q("Following distance in a loaded box truck vs a car should be:", ["The same", "Shorter — brakes are stronger", "Longer — stopping distance increases with weight", "Doesn't matter under 45 mph"], 2),
            _q("Regarding overhead clearance you should:", ["Trust GPS to route around bridges", "Know your vehicle height and check posted clearances", "Low bridges always have warning alarms", "Only worry over 14 feet"], 1),
            _q("The safest way to back a box truck is:", ["Quickly, to clear traffic", "Rely on the backup camera alone", "GOAL — Get Out And Look, and use a spotter when possible", "Open the rear doors for visibility"], 2),
            _q("Cargo straps should be checked:", ["Once a week", "Only when loading", "Before departure and again shortly into the drive", "Only for loads over 1 ton"], 2),
            _q("A 26-foot box truck under 26,001 lbs GVWR requires:", ["A Class A CDL", "A Class B CDL", "No CDL — a standard license (check your state)", "A motorcycle endorsement"], 2),
            _q("When making a right turn in a truck you should:", ["Hug the curb tightly", "Signal early, swing appropriately wide, and watch the rear wheels", "Turn from the far left lane without signaling", "Speed up through the turn"], 1),
        ],
    },
    {
        "seed_key": "drywall",
        "name": "Drywall Specialist",
        "description": "Drywall: hanging, fastening, taping, finishing levels, and moisture/fire-rated board selection.",
        "color": "#8B5CF6",
        "questions": [
            _q("Standard drywall thickness for interior walls is:", ["1/4 inch", "3/8 inch", "1/2 inch", "1 inch"], 2),
            _q("For 1/2\" drywall on wood studs, use screws that are:", ["3/4 inch fine thread", "1-1/4 inch coarse thread", "3 inch deck screws", "Any nail"], 1),
            _q("Joint tape exists to:", ["Hold boards while glue dries", "Reinforce seams so they don't crack", "Mark stud locations", "Cover screw heads only"], 1),
            _q("A typical smooth finish takes how many compound coats?", ["1", "2", "3 — tape, fill, finish", "5 minimum"], 2),
            _q("Moisture-resistant (green board) drywall belongs in:", ["Bedrooms", "Bathrooms and high-humidity areas", "Garages only", "Ceilings only"], 1),
            _q("Drywall screws should be driven:", ["Flush and no deeper", "Slightly dimpled below the surface without breaking the paper", "Through the board for grip", "Halfway in"], 1),
            _q("A 'Level 5' finish means:", ["Bare taped joints", "Textured spray finish", "A skim coat over the entire surface — the smoothest standard", "Five layers of primer"], 2),
            _q("Fire-rated drywall is commonly called:", ["Blue board", "Green board", "Type X (5/8 inch)", "Cement board"], 2),
        ],
    },
    {
        "seed_key": "painting",
        "name": "Painting Pro",
        "description": "Painting: prep, priming, cutting in, sheen selection, and lead-safe practices in older homes.",
        "color": "#EF4444",
        "questions": [
            _q("Before painting interior walls you should:", ["Just start rolling", "Clean, patch, sand, and prime as needed", "Wet the walls", "Remove all drywall texture"], 1),
            _q("Primer's main job is:", ["Adding color depth", "Adhesion and sealing so the topcoat lays evenly", "Making paint dry slower", "Replacing a second coat"], 1),
            _q("'Cutting in' means:", ["Cutting tape into strips", "Painting edges and corners with a brush before rolling", "Scraping old paint", "Mixing two colors"], 1),
            _q("Best sheen for high-traffic, washable walls:", ["Flat", "Satin or semi-gloss", "Textured", "Chalkboard"], 1),
            _q("Oil-based paint cleanup requires:", ["Water and soap", "Vinegar", "Mineral spirits / paint thinner", "Bleach"], 2),
            _q("Recoat timing should follow:", ["Whenever it looks dry", "One hour, always", "The manufacturer's dry/recoat times on the can", "48 hours minimum"], 2),
            _q("To avoid lap marks when rolling:", ["Roll as fast as possible", "Keep a wet edge and work in sections", "Use a nearly dry roller", "Roll only vertically"], 1),
            _q("Disturbing paint in pre-1978 homes may involve:", ["No special rules", "Lead paint — follow EPA RRP lead-safe practices", "Only asbestos concerns", "Extra primer"], 1),
        ],
    },
]


async def seed_badges() -> None:
    now = datetime.now(timezone.utc).isoformat()
    for s in SEED_BADGES:
        await db.badges.update_one(
            {"seed_key": s["seed_key"]},
            {"$setOnInsert": {
                "badge_id": f"bdg_{uuid.uuid4().hex[:12]}",
                "seed_key": s["seed_key"],
                "name": s["name"],
                "description": s["description"],
                "color": s["color"],
                "skill_tag": s.get("skill_tag"),
                "pass_pct": 80,
                "questions": s["questions"],
                "active": True,
                "created_by": "seed",
                "created_at": now,
            }},
            upsert=True,
        )
