"""VA AI Objection Coach (`POST /api/va/leads/{lead_id}/objection-coach`).

VA taps a quick-pick objection ("too expensive", "have someone", etc.) or
types a free-form one into the lead card popover. Backend assembles a
prompt using:
  - The lead's service_type / property_size / notes
  - Any active pitch templates tagged for objections in this category
  - The VA's display name (so responses sound natural)

…and asks Claude Sonnet 4.6 for 3 short on-brand responses the VA can
copy-paste into SMS/email/DM.

Hard rate limit: 20 calls per VA per hour. LLM is expensive at scale; this
is generous enough that no one feels throttled in real use but blocks a
runaway loop / abuse.
"""
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from auth_deps import _get_user_by_id  # noqa: F401  (future)
from config import db, logger
from va_commission import require_va_active, _log_lead_activity

router = APIRouter()

# --------------------------------------------------------------------------
# Quick-pick objections — these are the most common ones HCOB VAs hear.
# `prompt_label` is what we send to the LLM ("re-frame this objection: ...").
# --------------------------------------------------------------------------
QUICK_OBJECTIONS = {
    "too_expensive": "The price is too high / they want a cheaper quote.",
    "have_someone": "They already have a cleaning / service provider.",
    "call_back": "They want us to call/follow up later — not now.",
    "not_now": "Bad timing — not ready to book this week.",
    "trust": "They've never heard of us, hesitant to commit.",
    "ghost": "They went quiet after we sent the quote.",
    "spouse": "They need to check with a partner before booking.",
}

# 20 objection-coach calls per VA per hour. Plenty of room for normal use.
COACH_RATE_LIMIT_PER_HOUR = 20


class ObjectionIn(BaseModel):
    objection_key: Optional[str] = Field(
        default=None, description="One of the QUICK_OBJECTIONS keys"
    )
    custom_text: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Free-form objection in the VA's own words",
    )


async def _check_rate_limit(va_user_id: str) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    used = await db.va_objection_calls.count_documents({
        "va_user_id": va_user_id,
        "called_at": {"$gt": cutoff},
    })
    if used >= COACH_RATE_LIMIT_PER_HOUR:
        raise HTTPException(
            429,
            f"You've used the Objection Coach {used} times in the last hour. "
            "Take a breath — you can run it again in a few minutes.",
        )


async def _gather_template_context(service_type: Optional[str], max_items: int = 6) -> str:
    """Pull a handful of relevant pitch templates so the LLM sounds on-brand.
    We don't dump everything — just service-relevant + the universal ones."""
    q: dict = {"active": True, "deleted_at": {"$in": [None, ""]}}
    cur = db.pitch_templates.find(q).limit(40)
    blobs: list[str] = []
    async for t in cur:
        if len(blobs) >= max_items:
            break
        cat = (t.get("category") or "").lower()
        # Light filter — pull objection-handling templates first, then a few
        # service-relevant ones. Falls through gracefully if the seed is empty.
        if any(kw in cat for kw in ("objection", "follow-up", "follow_up", "close")):
            blobs.append(f"- {t.get('title', '?')}: {t.get('body') or ''}")
            continue
        if service_type and service_type.lower() in cat:
            blobs.append(f"- {t.get('title', '?')}: {t.get('body') or ''}")
    return "\n".join(blobs) if blobs else "(no internal templates configured yet)"


SYSTEM_PROMPT = (
    "You are HCOB Network's Objection Coach — a sharp, friendly sales mentor "
    "helping virtual assistants who GENERATE and WARM service-business "
    "leads (cleaning, project staffing, multi-service projects). "
    "Important context: the VA's job is to find prospects, talk to them, "
    "gather the brief (square footage / frequency / special asks), and "
    "hand the lead to Ops who issues the actual quote. The VA does NOT "
    "quote prices themselves. Responses should reflect this — never "
    "commit to a price, never promise a specific number, but DO commit to "
    "getting Ops to put together a custom quote fast.\n\n"
    "When a VA reports an objection from a prospect, return THREE "
    "different on-brand response options the VA can copy-paste into SMS, "
    "email, or DM. Each response must:\n"
    "  - Be 2-4 sentences max (short enough to send on a phone)\n"
    "  - Acknowledge the objection without being defensive\n"
    "  - Use the VA's first name as a signature\n"
    "  - Sound like a real human — no corporate fluff, no 'I hope this email "
    "    finds you well', no '<br>' / no HTML tags\n"
    "  - Move the conversation FORWARD — usually toward 'let me get you a "
    "    custom quote from our team' or 'let me grab a couple more details "
    "    so Ops can scope this right'\n"
    "Return STRICT JSON only — no preamble, no markdown fences. Shape:\n"
    '{"responses":[{"angle":"<one-sentence label of the move>",'
    '"body":"<the actual reply text the VA can copy>"}, x3]}'
)


def _build_user_prompt(
    *,
    objection_label: str,
    va_first_name: str,
    service_type: Optional[str],
    property_size: Optional[str],
    lead_notes: Optional[str],
    template_context: str,
) -> str:
    parts = [
        f"VA's first name: {va_first_name}",
        f"Service type the prospect was inquiring about: {service_type or 'unspecified'}",
        f"Property size: {property_size or 'unspecified'}",
        f"VA's notes from prior conversations: {(lead_notes or '(none)')[:600]}",
        "",
        "HCOB internal pitch templates (for tone reference — don't quote verbatim):",
        template_context,
        "",
        f"Objection to handle: \"{objection_label}\"",
        "",
        "Give me 3 response options across DIFFERENT angles "
        "(e.g. value reframe / curiosity hook / soft ask).",
    ]
    return "\n".join(parts)


def _extract_json_block(text: str) -> dict:
    """Tolerant JSON parse — strip ```json fences, leading/trailing prose."""
    s = (text or "").strip()
    # Strip code fences if the model added them despite instructions.
    if s.startswith("```"):
        s = s.lstrip("`")
        if s.lower().startswith("json"):
            s = s[4:]
        s = s.strip()
        if s.endswith("```"):
            s = s[:-3].strip()
    # Find the first { and last }.
    if "{" in s and "}" in s:
        s = s[s.find("{"): s.rfind("}") + 1]
    return json.loads(s)


@router.post("/va/leads/{lead_id}/objection-coach")
async def objection_coach(
    lead_id: str,
    payload: ObjectionIn = Body(...),
    user: dict = Depends(require_va_active),
):
    # 1. Resolve the objection — either a quick-pick key or free-form text
    label: Optional[str] = None
    if payload.objection_key:
        label = QUICK_OBJECTIONS.get(payload.objection_key)
        if not label:
            raise HTTPException(
                400, f"Unknown objection_key. Allowed: {list(QUICK_OBJECTIONS.keys())}"
            )
    elif payload.custom_text:
        label = payload.custom_text.strip()
    if not label:
        raise HTTPException(400, "Provide either objection_key or custom_text")

    # 2. Resolve the lead and confirm ownership
    lead = await db.va_leads.find_one({"lead_id": lead_id, "va_user_id": user["user_id"]})
    if not lead:
        raise HTTPException(404, "Lead not found")
    if lead.get("deleted_at"):
        raise HTTPException(400, "Lead is deleted")

    # 3. Rate limit before we spend LLM credits
    await _check_rate_limit(user["user_id"])

    # 4. Build the prompt
    va_first_name = (user.get("name") or "").split(" ")[0] or "your VA"
    template_context = await _gather_template_context(lead.get("service_type"))
    prompt = _build_user_prompt(
        objection_label=label,
        va_first_name=va_first_name,
        service_type=lead.get("service_type"),
        property_size=lead.get("property_size"),
        lead_notes=lead.get("notes"),
        template_context=template_context,
    )

    # 5. Call the LLM (Claude Sonnet 4.6 via Emergent universal key)
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(503, "LLM is not configured on this environment.")
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=api_key,
            session_id=f"objcoach::{user['user_id']}::{lead_id}::{uuid.uuid4().hex[:8]}",
            system_message=SYSTEM_PROMPT,
        ).with_model("anthropic", "claude-sonnet-4-6")
        # Blocking send is the right call here — we need the full JSON to
        # parse before returning. Streaming would buy us nothing because the
        # consumer can't render partial JSON.
        raw = await chat.send_message(UserMessage(text=prompt))
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Objection coach LLM call failed: {e}")
        raise HTTPException(502, "Could not reach the AI coach. Try again in a minute.")

    # 6. Parse JSON. Be tolerant — log the raw on parse fail.
    try:
        parsed = _extract_json_block(raw)
        responses = parsed.get("responses") or []
        clean = [
            {
                "angle": str(r.get("angle") or "").strip()[:120],
                "body": str(r.get("body") or "").strip()[:1200],
            }
            for r in responses
            if (r.get("body") or "").strip()
        ][:3]
        if not clean:
            raise ValueError("no usable responses returned")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Objection coach parse failed: {e}; raw={raw[:200]}")
        raise HTTPException(502, "AI returned an unexpected format. Try a different objection.")

    # 7. Log the call (rate limit + audit + cost-tracking later)
    now = datetime.now(timezone.utc).isoformat()
    await db.va_objection_calls.insert_one({
        "va_user_id": user["user_id"],
        "va_name": user.get("name"),
        "lead_id": lead_id,
        "objection_key": payload.objection_key,
        "objection_label": label,
        "responses_count": len(clean),
        "called_at": now,
    })
    await _log_lead_activity(
        lead_id=lead_id,
        kind="objection_coach",
        actor=user,
        detail={"objection_label": label[:120]},
    )
    return {
        "responses": clean,
        "objection_label": label,
        "calls_used_last_hour": (
            await db.va_objection_calls.count_documents({
                "va_user_id": user["user_id"],
                "called_at": {
                    "$gt": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
                },
            })
        ),
        "rate_limit_per_hour": COACH_RATE_LIMIT_PER_HOUR,
    }


@router.get("/va/objection-coach/objections")
async def list_quick_objections(user: dict = Depends(require_va_active)):
    """Front-end uses this to render the quick-pick buttons."""
    return {
        "objections": [
            {"key": k, "label": v} for k, v in QUICK_OBJECTIONS.items()
        ],
        "rate_limit_per_hour": COACH_RATE_LIMIT_PER_HOUR,
    }
