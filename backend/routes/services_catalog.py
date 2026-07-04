"""Service catalog — the full menu of physical + digital services HCOB offers.

VAs read it as a sales reference (`GET /services/catalog`); admins manage it
from the Ops console (`/admin/services/catalog` CRUD). Seeded once on startup.
"""
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth_deps import get_current_user, require_admin
from config import db

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ServiceIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    category: Literal["physical", "digital"]
    description: str = Field("", max_length=500)
    price_display: str = Field("", max_length=60)
    sort_order: int = 0
    active: bool = True


@router.get("/services/catalog")
async def list_services(user: dict = Depends(get_current_user)):
    items = (
        await db.service_catalog.find({"active": True}, {"_id": 0})
        .sort([("category", 1), ("sort_order", 1), ("name", 1)])
        .to_list(200)
    )
    return {"items": items}


@router.get("/admin/services/catalog")
async def admin_list_services(admin: dict = Depends(require_admin)):
    items = (
        await db.service_catalog.find({}, {"_id": 0})
        .sort([("category", 1), ("sort_order", 1), ("name", 1)])
        .to_list(200)
    )
    return {"items": items}


@router.post("/admin/services/catalog")
async def admin_create_service(payload: ServiceIn, admin: dict = Depends(require_admin)):
    now = _now_iso()
    doc = {
        "service_id": f"svc_{uuid.uuid4().hex[:12]}",
        **payload.model_dump(),
        "created_at": now,
        "updated_at": now,
    }
    await db.service_catalog.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/admin/services/catalog/{service_id}")
async def admin_update_service(
    service_id: str, payload: ServiceIn, admin: dict = Depends(require_admin)
):
    result = await db.service_catalog.update_one(
        {"service_id": service_id},
        {"$set": {**payload.model_dump(), "updated_at": _now_iso()}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Service not found")
    return await db.service_catalog.find_one({"service_id": service_id}, {"_id": 0})


@router.delete("/admin/services/catalog/{service_id}")
async def admin_delete_service(service_id: str, admin: dict = Depends(require_admin)):
    result = await db.service_catalog.delete_one({"service_id": service_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Service not found")
    return {"ok": True}


_SEED = [
    # ---- Physical --------------------------------------------------------
    ("physical", "Routine House Cleaning", "Recurring weekly or bi-weekly cleaning — kitchens, baths, floors, dusting. The bread-and-butter subscription service.", "From $120 / visit"),
    ("physical", "Deep Cleaning", "Top-to-bottom detail clean: baseboards, inside appliances, grout, vents. Great first visit before a routine plan.", "$200 – $400"),
    ("physical", "Move-In / Move-Out Cleaning", "Empty-home turnover clean for tenants, landlords, and home sales. Deposit-back guarantee pitch.", "$250 – $500"),
    ("physical", "Apartment Turnover", "Unit flips for property managers — clean, patch-ready, photo-ready between tenants. Volume pricing available.", "$180 – $350 / unit"),
    ("physical", "Carpet Cleaning", "Hot-water extraction / steam cleaning for carpets and rugs. Add-on friendly with any cleaning job.", "$99 – $250"),
    ("physical", "Junk Removal", "Haul-away of furniture, appliances, debris — loaded, disposed, and swept. Priced by load size.", "$150 – $600 / load"),
    ("physical", "Estate Cleanout", "Full-property clearing for estates, hoarding situations, and foreclosures. Includes sorting and donation runs.", "$500 – $2,500"),
    ("physical", "Pressure Washing", "Siding, decks, driveways, and concrete restored. Seasonal upsell for every homeowner lead.", "$150 – $450"),
    ("physical", "Landscaping & Lawn Care", "Mowing, edging, seasonal cleanups, and mulching on a recurring schedule.", "From $75 / visit"),
    ("physical", "Handyman Services", "Repairs, TV mounting, furniture assembly, fixture swaps — licensed and insured pros.", "$85 – $150 / hr"),
    ("physical", "Painting", "Interior and exterior painting — rooms, trim, decks, full repaints. Free color consult.", "$300 – $3,500 / job"),
    ("physical", "Maintenance Bundle", "Cleaning + lawn + handyman rolled into one monthly plan. One invoice, one point of contact.", "From $299 / mo"),
    ("physical", "Commercial Cleaning Programs", "Offices, retail, and multi-site routine programs with QC checks and emergency response.", "Custom — from $500 / mo"),
    ("physical", "Specialty / Medical-Grade Cleaning", "Clinics, labs, and sensitive environments cleaned to disinfection protocols.", "Custom quote"),
    ("physical", "Project Staffing & Labor", "Vetted crews for move-outs, post-construction, warehouse, and event teardown.", "$25 – $45 / hr per worker"),
    # ---- Digital ---------------------------------------------------------
    ("digital", "Product Sourcing", "Supplier sourcing, sample checks, and fulfillment coordination for e-commerce sellers.", "Custom quote"),
    ("digital", "Web Development", "Business websites and landing pages — designed, built, and launched fast.", "$750 – $5,000"),
    ("digital", "App Development", "Web and mobile apps, from MVP to production — scoped and quoted per project.", "From $2,500"),
    ("digital", "Social Media Marketing", "Content creation, posting, and account management to keep businesses visible.", "$400 – $1,500 / mo"),
    ("digital", "SEO & Content", "Local SEO, Google Business Profile optimization, and blog content that ranks.", "$300 – $1,000 / mo"),
    ("digital", "Graphic Design", "Logos, branding kits, flyers, and social graphics — quick turnaround.", "$50 – $500"),
    ("digital", "Other Digital Services", "Something else digital? We scope it and quote it — bring us the lead.", "Custom quote"),
]


async def seed_service_catalog() -> int:
    """Idempotent — only seeds when the collection is empty."""
    if await db.service_catalog.count_documents({}) > 0:
        return 0
    now = _now_iso()
    docs = [
        {
            "service_id": f"svc_{uuid.uuid4().hex[:12]}",
            "name": name,
            "category": category,
            "description": description,
            "price_display": price,
            "sort_order": i,
            "active": True,
            "created_at": now,
            "updated_at": now,
        }
        for i, (category, name, description, price) in enumerate(_SEED)
    ]
    await db.service_catalog.insert_many(docs)
    return len(docs)
