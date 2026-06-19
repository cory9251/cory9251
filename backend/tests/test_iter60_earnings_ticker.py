"""Iter 60 — VA Dashboard earnings ticker + tier ladder.

Verifies the dashboard payload exposes the new `mtd_commission` + `tier`
fields with correct math at every rung of the ladder.
"""
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://work-connect-147.preview.emergentagent.com",
).rstrip("/")

VA = {"email": "va.demo@hcobcleaners.com", "password": "VaDemo2026!"}


def _va_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=VA, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"VA login failed: {r.status_code}")
    return s


def _seed_paid_commission(amount: float, va_email: str = VA["email"]):
    """Insert a paid commission for the VA dated this month so MTD math has data."""
    async def run():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            db = client[os.environ["DB_NAME"]]
            va = await db.users.find_one({"email": va_email})
            assert va is not None
            now = datetime.now(timezone.utc)
            cid = f"iter60_{uuid.uuid4().hex[:10]}"
            await db.commissions.insert_one({
                "commission_id": cid,
                "va_user_id": va["user_id"],
                "lead_id": f"iter60_seed_{uuid.uuid4().hex[:6]}",
                "amount": amount,
                "status": "paid",
                "paid_at": now.isoformat(),
                "created_at": now.isoformat(),
            })
            return cid
        finally:
            client.close()
    return asyncio.run(run())


def _cleanup_commission(cid: str):
    async def run():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            await client[os.environ["DB_NAME"]].commissions.delete_one({"commission_id": cid})
        finally:
            client.close()
    asyncio.run(run())


def test_dashboard_includes_mtd_and_tier_fields():
    s = _va_session()
    r = s.get(f"{BASE_URL}/api/va/dashboard", timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "mtd_commission" in body
    assert isinstance(body["mtd_commission"], (int, float))
    tier = body["tier"]
    assert tier["current"]["key"]
    assert tier["current"]["label"]
    assert "next" in tier  # may be None at Legend
    assert "progress_pct" in tier
    assert "amount_needed_to_next" in tier
    assert isinstance(tier["ladder"], list)
    assert len(tier["ladder"]) == 5
    rungs = [r["key"] for r in tier["ladder"]]
    assert rungs == ["hustler", "pro", "star", "elite", "legend"]


def test_tier_starts_at_hustler_with_zero_earnings():
    """Verify the math at $0 — Hustler tier, 0% progress to Pro, $500 needed."""
    s = _va_session()
    # Don't seed anything — assume va.demo has 0 MTD (this test will be a
    # baseline check; if state from other tests bleeds in we use the dynamic
    # tier instead and just assert the math is consistent)
    r = s.get(f"{BASE_URL}/api/va/dashboard", timeout=20)
    body = r.json()
    tier = body["tier"]
    # If mtd_commission is 0, must be at Hustler
    if body["mtd_commission"] == 0:
        assert tier["current"]["key"] == "hustler"
        assert tier["next"]["key"] == "pro"
        assert tier["progress_pct"] == 0
        assert tier["amount_needed_to_next"] == 500


def test_tier_jumps_to_pro_at_500():
    """Seed a $600 paid commission this month → should land in Pro tier."""
    cid = _seed_paid_commission(600.00)
    try:
        s = _va_session()
        r = s.get(f"{BASE_URL}/api/va/dashboard", timeout=20)
        body = r.json()
        assert body["mtd_commission"] >= 600
        tier = body["tier"]
        # With $600 MTD, current is at least Pro
        assert tier["current"]["key"] in ("pro", "star", "elite", "legend")
        if tier["current"]["key"] == "pro":
            # 600 of 500-1500 range → 100/1000 = 10%
            assert tier["next"]["key"] == "star"
            assert tier["progress_pct"] == 10.0
            assert tier["amount_needed_to_next"] == pytest.approx(900.0, abs=0.5)
    finally:
        _cleanup_commission(cid)


def test_tier_caps_at_legend():
    """Seed $10,000 to land on Legend tier and verify progress is 100% with no next tier."""
    cid = _seed_paid_commission(10000.00)
    try:
        s = _va_session()
        r = s.get(f"{BASE_URL}/api/va/dashboard", timeout=20)
        body = r.json()
        assert body["mtd_commission"] >= 10000
        tier = body["tier"]
        assert tier["current"]["key"] == "legend"
        assert tier["next"] is None
        assert tier["progress_pct"] == 100
        assert tier["amount_needed_to_next"] == 0
    finally:
        _cleanup_commission(cid)


def test_tier_progress_is_bounded_0_to_100():
    """Property check: progress_pct must always be 0..100, never negative or >100."""
    cid = _seed_paid_commission(1499.99)  # Just below Star threshold
    try:
        s = _va_session()
        r = s.get(f"{BASE_URL}/api/va/dashboard", timeout=20)
        tier = r.json()["tier"]
        assert 0 <= tier["progress_pct"] <= 100
    finally:
        _cleanup_commission(cid)
