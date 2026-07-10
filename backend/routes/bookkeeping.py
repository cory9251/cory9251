"""Bookkeeping — admin-only expenses & income ledger.

Collections:
    ledger_entries     {entry_id, type, amount, category, date, description,
                        vendor, project_id, project_title, gig_id, gig_title,
                        receipt_path, receipt_filename, recurring_id,
                        created_by, created_by_name, created_at, updated_at}
    recurring_expenses {recurring_id, amount, category, description, vendor,
                        day_of_month, active, last_generated_period, ...}
"""
import asyncio
import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response as FastAPIResponse
from pydantic import BaseModel, Field

from config import db, APP_NAME, logger
from auth_deps import require_admin
from storage import put_object, validate_upload

router = APIRouter()

EXPENSE_CATEGORIES = [
    "supplies", "travel_fuel", "equipment", "software", "contractor_pay",
    "payroll", "marketing", "insurance", "rent_utilities", "taxes_fees", "other",
]
INCOME_CATEGORIES = [
    "assignment_income", "project_income", "digital_income", "referral_income", "other_income",
]

RECEIPT_MAX_BYTES = 10 * 1024 * 1024


def _validate_date(d: str) -> str:
    try:
        datetime.strptime(d, "%Y-%m-%d")
    except (ValueError, TypeError):
        raise HTTPException(400, "Date must be YYYY-MM-DD")
    return d


def _validate_category(entry_type: str, category: str) -> None:
    valid = EXPENSE_CATEGORIES if entry_type == "expense" else INCOME_CATEGORIES
    if category not in valid:
        raise HTTPException(400, f"Invalid category '{category}' for {entry_type}")


async def _resolve_links(project_id: Optional[str], gig_id: Optional[str]) -> dict:
    out = {"project_id": None, "project_title": None, "gig_id": None, "gig_title": None}
    if project_id:
        p = await db.projects.find_one({"project_id": project_id}, {"_id": 0, "title": 1})
        if not p:
            raise HTTPException(400, "Linked project not found")
        out["project_id"] = project_id
        out["project_title"] = p.get("title")
    if gig_id:
        g = await db.gigs.find_one({"gig_id": gig_id}, {"_id": 0, "title": 1})
        if not g:
            raise HTTPException(400, "Linked assignment not found")
        out["gig_id"] = gig_id
        out["gig_title"] = g.get("title")
    return out


def _clean(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k != "_id"}


async def log_commission_payroll_expense(commission: dict) -> Optional[dict]:
    """Auto-create a 'payroll' expense ledger entry when a commission is paid.
    Idempotent — keyed on commission_id, so a re-run never double-logs.
    Covers VA lead commissions and digital-job payouts (same pipeline)."""
    commission_id = commission.get("commission_id")
    if not commission_id:
        return None
    existing = await db.ledger_entries.find_one({"source_commission_id": commission_id})
    if existing:
        return _clean(existing)

    amount = round(float(commission.get("amount") or 0), 2)
    if amount <= 0:
        return None

    is_job = commission.get("kind") == "digital_job"
    va_name = commission.get("va_name") or "VA"
    subject = commission.get("prospect_name") or ("digital job" if is_job else "lead")
    label = "Digital job payout" if is_job else "VA commission"
    paid_iso = commission.get("paid_at") or datetime.now(timezone.utc).isoformat()
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "entry_id": f"led_{uuid.uuid4().hex[:12]}",
        "type": "expense",
        "amount": amount,
        "category": "payroll",
        "date": paid_iso[:10],
        "description": f"{label} — {va_name} · {subject}",
        "vendor": va_name,
        "project_id": None,
        "project_title": None,
        "gig_id": None,
        "gig_title": None,
        "receipt_path": None,
        "receipt_filename": None,
        "recurring_id": None,
        "source": "commission_payout",
        "source_commission_id": commission_id,
        "payout_method": commission.get("payout_method"),
        "payout_reference": commission.get("payout_reference"),
        "created_by": "system",
        "created_by_name": "Auto (payroll)",
        "created_at": now,
        "updated_at": now,
    }
    await db.ledger_entries.insert_one(doc)
    return _clean(doc)



class LedgerEntryIn(BaseModel):
    type: Literal["expense", "income"]
    amount: float = Field(gt=0)
    category: str
    date: str
    description: str = Field(min_length=1, max_length=500)
    vendor: Optional[str] = Field(default=None, max_length=200)
    project_id: Optional[str] = None
    gig_id: Optional[str] = None


class LedgerEntryPatch(BaseModel):
    type: Optional[Literal["expense", "income"]] = None
    amount: Optional[float] = Field(default=None, gt=0)
    category: Optional[str] = None
    date: Optional[str] = None
    description: Optional[str] = Field(default=None, min_length=1, max_length=500)
    vendor: Optional[str] = Field(default=None, max_length=200)  # "" clears
    project_id: Optional[str] = None  # "" clears
    gig_id: Optional[str] = None  # "" clears


class RecurringIn(BaseModel):
    amount: float = Field(gt=0)
    category: str
    description: str = Field(min_length=1, max_length=500)
    vendor: Optional[str] = Field(default=None, max_length=200)
    day_of_month: int = Field(ge=1, le=28)


class RecurringPatch(BaseModel):
    amount: Optional[float] = Field(default=None, gt=0)
    category: Optional[str] = None
    description: Optional[str] = Field(default=None, min_length=1, max_length=500)
    vendor: Optional[str] = None
    day_of_month: Optional[int] = Field(default=None, ge=1, le=28)
    active: Optional[bool] = None


def _ledger_query(
    entry_type: Optional[str],
    category: Optional[str],
    project_id: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    q: Optional[str],
) -> dict:
    query: dict = {}
    if entry_type in ("expense", "income"):
        query["type"] = entry_type
    if category:
        query["category"] = category
    if project_id:
        query["project_id"] = project_id
    date_cond = {}
    if date_from:
        date_cond["$gte"] = _validate_date(date_from)
    if date_to:
        date_cond["$lte"] = _validate_date(date_to)
    if date_cond:
        query["date"] = date_cond
    if q and q.strip():
        rx = {"$regex": q.strip(), "$options": "i"}
        query["$or"] = [{"description": rx}, {"vendor": rx}, {"project_title": rx}, {"gig_title": rx}]
    return query


def _totals(items: list) -> dict:
    income = sum(e["amount"] for e in items if e["type"] == "income")
    expenses = sum(e["amount"] for e in items if e["type"] == "expense")
    return {"income": round(income, 2), "expenses": round(expenses, 2), "net": round(income - expenses, 2)}


async def log_worker_payout_expense(
    acceptance: dict, gig_title: str, amount: float, worker_name: Optional[str] = None
) -> Optional[dict]:
    """Auto-create a 'payroll' expense when a worker shift payout is marked paid.
    Idempotent — keyed on acceptance_id."""
    acceptance_id = acceptance.get("acceptance_id")
    if not acceptance_id or amount <= 0:
        return None
    existing = await db.ledger_entries.find_one({"source_acceptance_id": acceptance_id})
    if existing:
        return _clean(existing)
    worker_name = (worker_name or "").strip() or acceptance.get("worker_name") or "Worker"
    paid_iso = acceptance.get("paid_at") or datetime.now(timezone.utc).isoformat()
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "entry_id": f"led_{uuid.uuid4().hex[:12]}",
        "type": "expense",
        "amount": round(float(amount), 2),
        "category": "payroll",
        "date": paid_iso[:10],
        "description": f"Worker payout — {worker_name} · {gig_title}",
        "vendor": worker_name,
        "project_id": None,
        "project_title": None,
        "gig_id": acceptance.get("gig_id"),
        "gig_title": gig_title,
        "receipt_path": None,
        "receipt_filename": None,
        "recurring_id": None,
        "source": "worker_payout",
        "source_acceptance_id": acceptance_id,
        "payout_method": acceptance.get("payout_method"),
        "payout_reference": acceptance.get("payout_reference"),
        "created_by": "system",
        "created_by_name": "Auto (payroll)",
        "created_at": now,
        "updated_at": now,
    }
    await db.ledger_entries.insert_one(doc)
    return _clean(doc)


async def backfill_paid_commission_payroll() -> int:
    """One-time-safe: log payroll expenses for commissions already marked paid
    that predate this feature. Idempotent via source_commission_id."""
    logged = set(
        await db.ledger_entries.distinct(
            "source_commission_id", {"source": "commission_payout"}
        )
    )
    count = 0
    async for c in db.commissions.find({"status": "paid"}):
        if c.get("commission_id") in logged:
            continue
        if await log_commission_payroll_expense(c):
            count += 1
    return count


@router.get("/admin/ledger/meta")
async def ledger_meta(admin: dict = Depends(require_admin)):
    projects = await db.projects.find(
        {"archived": {"$ne": True}}, {"_id": 0, "project_id": 1, "title": 1}
    ).sort("created_at", -1).to_list(300)
    gigs = await db.gigs.find(
        {}, {"_id": 0, "gig_id": 1, "title": 1, "scheduled_at": 1, "status": 1}
    ).sort("created_at", -1).to_list(300)
    return {
        "expense_categories": EXPENSE_CATEGORIES,
        "income_categories": INCOME_CATEGORIES,
        "projects": projects,
        "gigs": gigs,
    }


@router.get("/admin/ledger")
async def list_ledger(
    type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    admin: dict = Depends(require_admin),
):
    query = _ledger_query(type, category, project_id, date_from, date_to, q)
    docs = await db.ledger_entries.find(query, {"_id": 0}).sort(
        [("date", -1), ("created_at", -1)]
    ).to_list(2000)
    return {"items": docs, "totals": _totals(docs)}


@router.post("/admin/ledger")
async def create_ledger_entry(payload: LedgerEntryIn, admin: dict = Depends(require_admin)):
    _validate_date(payload.date)
    _validate_category(payload.type, payload.category)
    links = await _resolve_links(payload.project_id, payload.gig_id)
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "entry_id": f"led_{uuid.uuid4().hex[:12]}",
        "type": payload.type,
        "amount": round(float(payload.amount), 2),
        "category": payload.category,
        "date": payload.date,
        "description": payload.description.strip(),
        "vendor": (payload.vendor or "").strip() or None,
        **links,
        "receipt_path": None,
        "receipt_filename": None,
        "recurring_id": None,
        "created_by": admin["user_id"],
        "created_by_name": admin.get("name"),
        "created_at": now,
        "updated_at": now,
    }
    await db.ledger_entries.insert_one(doc)
    return _clean(doc)


@router.put("/admin/ledger/{entry_id}")
async def update_ledger_entry(entry_id: str, payload: LedgerEntryPatch, admin: dict = Depends(require_admin)):
    entry = await db.ledger_entries.find_one({"entry_id": entry_id})
    if not entry:
        raise HTTPException(404, "Entry not found")
    updates: dict = {}
    new_type = payload.type or entry["type"]
    if payload.type is not None:
        updates["type"] = payload.type
    if payload.category is not None:
        _validate_category(new_type, payload.category)
        updates["category"] = payload.category
    elif payload.type is not None:
        _validate_category(new_type, entry["category"])
    if payload.amount is not None:
        updates["amount"] = round(float(payload.amount), 2)
    if payload.date is not None:
        updates["date"] = _validate_date(payload.date)
    if payload.description is not None:
        updates["description"] = payload.description.strip()
    if payload.vendor is not None:
        updates["vendor"] = payload.vendor.strip() or None
    if payload.project_id is not None or payload.gig_id is not None:
        pid = entry.get("project_id") if payload.project_id is None else (payload.project_id or None)
        gid = entry.get("gig_id") if payload.gig_id is None else (payload.gig_id or None)
        updates.update(await _resolve_links(pid, gid))
    if not updates:
        return _clean(entry)
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.ledger_entries.update_one({"entry_id": entry_id}, {"$set": updates})
    fresh = await db.ledger_entries.find_one({"entry_id": entry_id})
    return _clean(fresh)


@router.delete("/admin/ledger/{entry_id}")
async def delete_ledger_entry(entry_id: str, admin: dict = Depends(require_admin)):
    res = await db.ledger_entries.delete_one({"entry_id": entry_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Entry not found")
    return {"ok": True}


@router.post("/admin/ledger/{entry_id}/receipt")
async def upload_receipt(entry_id: str, file: UploadFile = File(...), admin: dict = Depends(require_admin)):
    entry = await db.ledger_entries.find_one({"entry_id": entry_id})
    if not entry:
        raise HTTPException(404, "Entry not found")
    data = await file.read()
    if len(data) > RECEIPT_MAX_BYTES:
        raise HTTPException(400, "Receipt too large (max 10MB)")
    ext, ct = validate_upload(data, file.filename or "", allow_pdf=True)
    path = f"{APP_NAME}/receipts/{entry_id}/{uuid.uuid4().hex}.{ext}"
    result = await asyncio.to_thread(put_object, path, data, ct)
    now = datetime.now(timezone.utc).isoformat()
    await db.files.insert_one({
        "file_id": str(uuid.uuid4()),
        "storage_path": result["path"],
        "original_filename": file.filename,
        "content_type": ct,
        "size": result.get("size"),
        "owner_id": admin["user_id"],
        "kind": "receipt",
        "created_at": now,
    })
    await db.ledger_entries.update_one(
        {"entry_id": entry_id},
        {"$set": {"receipt_path": result["path"], "receipt_filename": file.filename, "updated_at": now}},
    )
    return {"receipt_path": result["path"], "receipt_filename": file.filename}


@router.get("/admin/ledger/summary")
async def ledger_summary(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    admin: dict = Depends(require_admin),
):
    query = _ledger_query(None, None, None, date_from, date_to, None)
    docs = await db.ledger_entries.find(query, {"_id": 0}).to_list(10000)

    expenses_by_cat: dict = {}
    income_by_cat: dict = {}
    by_month: dict = {}
    by_project: dict = {}
    for e in docs:
        month = (e.get("date") or "")[:7]
        m = by_month.setdefault(month, {"month": month, "income": 0, "expenses": 0})
        if e["type"] == "income":
            income_by_cat[e["category"]] = income_by_cat.get(e["category"], 0) + e["amount"]
            m["income"] += e["amount"]
        else:
            expenses_by_cat[e["category"]] = expenses_by_cat.get(e["category"], 0) + e["amount"]
            m["expenses"] += e["amount"]
        if e.get("project_id"):
            p = by_project.setdefault(
                e["project_id"],
                {"project_id": e["project_id"], "title": e.get("project_title"), "income": 0, "expenses": 0},
            )
            p["income" if e["type"] == "income" else "expenses"] += e["amount"]

    months = sorted(by_month.values(), key=lambda x: x["month"])
    for m in months:
        m["income"] = round(m["income"], 2)
        m["expenses"] = round(m["expenses"], 2)
        m["net"] = round(m["income"] - m["expenses"], 2)
    projects = sorted(by_project.values(), key=lambda x: -(x["income"] + x["expenses"]))
    for p in projects:
        p["income"] = round(p["income"], 2)
        p["expenses"] = round(p["expenses"], 2)
        p["net"] = round(p["income"] - p["expenses"], 2)

    return {
        "totals": _totals(docs),
        "entry_count": len(docs),
        "expenses_by_category": [
            {"category": k, "amount": round(v, 2)} for k, v in sorted(expenses_by_cat.items(), key=lambda x: -x[1])
        ],
        "income_by_category": [
            {"category": k, "amount": round(v, 2)} for k, v in sorted(income_by_cat.items(), key=lambda x: -x[1])
        ],
        "by_month": months,
        "by_project": projects,
    }


@router.get("/admin/ledger/export")
async def export_ledger_csv(
    type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    admin: dict = Depends(require_admin),
):
    query = _ledger_query(type, category, project_id, date_from, date_to, q)
    docs = await db.ledger_entries.find(query, {"_id": 0}).sort(
        [("date", -1), ("created_at", -1)]
    ).to_list(10000)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date", "Type", "Category", "Amount", "Description", "Vendor/Payer",
                "Project", "Assignment", "Receipt", "Recorded by", "Entry ID"])
    for e in docs:
        w.writerow([
            e.get("date"), e.get("type"), e.get("category"),
            f"{e.get('amount', 0):.2f}", e.get("description"), e.get("vendor") or "",
            e.get("project_title") or "", e.get("gig_title") or "",
            "yes" if e.get("receipt_path") else "no",
            e.get("created_by_name") or "", e.get("entry_id"),
        ])
    totals = _totals(docs)
    w.writerow([])
    w.writerow(["", "", "Income total", f"{totals['income']:.2f}"])
    w.writerow(["", "", "Expenses total", f"{totals['expenses']:.2f}"])
    w.writerow(["", "", "Net", f"{totals['net']:.2f}"])
    filename = f"hcob-ledger-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return FastAPIResponse(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Recurring expenses
# ---------------------------------------------------------------------------
@router.get("/admin/recurring-expenses")
async def list_recurring(admin: dict = Depends(require_admin)):
    docs = await db.recurring_expenses.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"items": docs}


@router.post("/admin/recurring-expenses")
async def create_recurring(payload: RecurringIn, admin: dict = Depends(require_admin)):
    _validate_category("expense", payload.category)
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "recurring_id": f"rec_{uuid.uuid4().hex[:12]}",
        "amount": round(float(payload.amount), 2),
        "category": payload.category,
        "description": payload.description.strip(),
        "vendor": (payload.vendor or "").strip() or None,
        "day_of_month": payload.day_of_month,
        "active": True,
        "last_generated_period": None,
        "created_by": admin["user_id"],
        "created_at": now,
        "updated_at": now,
    }
    await db.recurring_expenses.insert_one(doc)
    await _generate_due_recurring()
    fresh = await db.recurring_expenses.find_one({"recurring_id": doc["recurring_id"]}, {"_id": 0})
    return fresh


@router.put("/admin/recurring-expenses/{recurring_id}")
async def update_recurring(recurring_id: str, payload: RecurringPatch, admin: dict = Depends(require_admin)):
    rec = await db.recurring_expenses.find_one({"recurring_id": recurring_id})
    if not rec:
        raise HTTPException(404, "Recurring expense not found")
    updates: dict = {}
    if payload.amount is not None:
        updates["amount"] = round(float(payload.amount), 2)
    if payload.category is not None:
        _validate_category("expense", payload.category)
        updates["category"] = payload.category
    if payload.description is not None:
        updates["description"] = payload.description.strip()
    if payload.vendor is not None:
        updates["vendor"] = payload.vendor.strip() or None
    if payload.day_of_month is not None:
        updates["day_of_month"] = payload.day_of_month
    if payload.active is not None:
        updates["active"] = payload.active
    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.recurring_expenses.update_one({"recurring_id": recurring_id}, {"$set": updates})
    fresh = await db.recurring_expenses.find_one({"recurring_id": recurring_id}, {"_id": 0})
    return fresh


@router.delete("/admin/recurring-expenses/{recurring_id}")
async def delete_recurring(recurring_id: str, admin: dict = Depends(require_admin)):
    res = await db.recurring_expenses.delete_one({"recurring_id": recurring_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Recurring expense not found")
    return {"ok": True}


async def _generate_due_recurring() -> int:
    """Create ledger entries for active recurring expenses due this period."""
    now = datetime.now(timezone.utc)
    period = now.strftime("%Y-%m")
    created = 0
    cur = db.recurring_expenses.find({"active": True})
    async for r in cur:
        if r.get("last_generated_period") == period:
            continue
        if now.day < int(r.get("day_of_month") or 1):
            continue
        iso = datetime.now(timezone.utc).isoformat()
        entry = {
            "entry_id": f"led_{uuid.uuid4().hex[:12]}",
            "type": "expense",
            "amount": r["amount"],
            "category": r["category"],
            "date": f"{period}-{int(r['day_of_month']):02d}",
            "description": r["description"],
            "vendor": r.get("vendor"),
            "project_id": None, "project_title": None,
            "gig_id": None, "gig_title": None,
            "receipt_path": None, "receipt_filename": None,
            "recurring_id": r["recurring_id"],
            "created_by": "system",
            "created_by_name": "Recurring (auto)",
            "created_at": iso,
            "updated_at": iso,
        }
        await db.ledger_entries.insert_one(entry)
        await db.recurring_expenses.update_one(
            {"recurring_id": r["recurring_id"]},
            {"$set": {"last_generated_period": period, "updated_at": iso}},
        )
        created += 1
    return created


async def recurring_expenses_runner() -> None:
    """Background loop — auto-logs recurring expenses monthly."""
    while True:
        try:
            n = await _generate_due_recurring()
            if n:
                logger.info(f"Recurring expenses: generated {n} ledger entries")
        except Exception as e:
            logger.error(f"recurring_expenses_runner error: {e}")
        await asyncio.sleep(6 * 3600)
