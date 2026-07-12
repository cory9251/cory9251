"""Backend tests for VA Commission — Fixed Pool Model v2.0 (iter78).

Covers pool split (75/15/10), category mapping (A-G), tier promotion,
Cat D recurring tail, same-VA repeat allowed / cross-VA blocked,
paid-stage validation (profit vs revenue), team lead auto-qualification,
commission-settings API, commercial log-revenue split, legacy freeze.
"""
import asyncio
import os
import re
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://work-connect-147.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

OWNER_EMAIL = "admin@hcobcleaners.com"
OWNER_PW = "HcobAdmin2026!"
MECHIE_EMAIL = "mechiebadlong77@gmail.com"
MECHIE_PW = "Mechie2026!"

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

# ---- fixture data to clean up (populated during tests)
_created_va_ids: list = []
_created_lead_ids: list = []
_created_commission_ids: list = []
_created_account_ids: list = []


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="session")
def owner():
    return _login(OWNER_EMAIL, OWNER_PW)


@pytest.fixture(scope="session")
def mechie():
    return _login(MECHIE_EMAIL, MECHIE_PW)


def _reg_va(prefix="pv2", phone_seed=None):
    email = f"TEST_{prefix}_{uuid.uuid4().hex[:6]}@example.com"
    phone = phone_seed or f"9{uuid.uuid4().int % 10**9:09d}"
    s = requests.Session()
    r = s.post(f"{API}/auth/register", json={
        "email": email, "password": "vapass123",
        "name": f"TEST {prefix} {email.split('@')[0][:6]}",
        "role": "va", "va_phone": phone,
        "va_address": f"999 TestSt {uuid.uuid4().hex[:4]} Baltimore MD",
    }, timeout=20)
    assert r.status_code == 200, r.text
    me = r.json()
    _created_va_ids.append(me["user_id"])
    return s, me


def _approve(mechie, uid):
    r = mechie.post(f"{API}/pm/vas/{uid}/approve", json={}, timeout=20)
    assert r.status_code == 200, r.text


def _submit_lead(s, **kw):
    payload = {
        "prospect_name": kw.get("name", "TESTclient"),
        "prospect_phone": kw.get("phone") or f"3{uuid.uuid4().int % 10**9:09d}",
        "prospect_email": kw.get("email") or f"lead+{uuid.uuid4().hex[:6]}@example.com",
        "service_type": kw.get("service", "routine"),
        "property_size": kw.get("size", "2br"),
        "source": kw.get("source", "other"),
        "is_recurring": kw.get("is_recurring", False),
    }
    r = s.post(f"{API}/va/leads", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    lead = r.json()
    _created_lead_ids.append(lead["lead_id"])
    return lead


def _walk_to_paid(mechie, lead_id, *, job_profit=None, job_value=None,
                  stop_at="paid"):
    stages = ["contacted", "quoted", "booked", "completed", "paid"]
    for st in stages:
        body = {"stage": st}
        if st == "paid":
            if job_profit is not None:
                body["job_profit"] = job_profit
            if job_value is not None:
                body["job_value"] = job_value
        r = mechie.put(f"{API}/pm/leads/{lead_id}/stage", json=body, timeout=20)
        if st == stop_at:
            return r
        assert r.status_code == 200, f"walk to {st} failed: {r.text}"
    return r


# ---------------- Basic pool split (Cat A) ------------------------------------
def test_pool_A_split_routine(mechie, owner):
    """Cat A routine, agent tier: $200 profit → $20 pool → $15/$2/$3-retained."""
    s, me = _reg_va("Aagent")
    _approve(mechie, me["user_id"])
    lead = _submit_lead(s, service="routine", size="2br")
    r = _walk_to_paid(mechie, lead["lead_id"], job_profit=200)
    assert r.status_code == 200
    # fetch commissions
    q = mechie.get(f"{API}/pm/commissions", timeout=20).json()
    rows = [c for c in q["items"] if c.get("lead_id") == lead["lead_id"]]
    kinds = {c["kind"]: c for c in rows}
    assert "pool_agent" in kinds, f"no pool_agent found: {rows}"
    ag = kinds["pool_agent"]
    assert ag["pool_amount"] == 20.0, ag
    assert ag["amount"] == 15.0, ag
    assert ag["category"] == "A"
    assert ag["tier"] == "agent"
    assert ag["engine"] == "pool_v2"
    # Ops share
    assert "ops_share" in kinds
    assert kinds["ops_share"]["amount"] == 2.0
    # No qualified team lead → team_override should NOT exist as a commission
    assert "team_override" not in kinds
    # Retained tracked on agent doc
    assert abs(float(ag.get("lead_share_retained") or 0) - 3.0) < 0.01
    assert ag.get("lead_share_reason") == "no_team_lead"
    _created_commission_ids.extend([c["commission_id"] for c in rows])


# ---------------- Paid-stage validation ----------------------------------------
def test_paid_requires_job_profit(mechie):
    s, me = _reg_va("Prof")
    _approve(mechie, me["user_id"])
    lead = _submit_lead(s, service="deep")
    # walk to completed
    for st in ("contacted", "quoted", "booked", "completed"):
        mechie.put(f"{API}/pm/leads/{lead['lead_id']}/stage", json={"stage": st}, timeout=20)
    r = mechie.put(f"{API}/pm/leads/{lead['lead_id']}/stage",
                   json={"stage": "paid"}, timeout=20)
    assert r.status_code == 400
    assert "profit" in r.json()["detail"].lower()


def test_paid_commercial_requires_revenue(mechie):
    s, me = _reg_va("Comm")
    _approve(mechie, me["user_id"])
    lead = _submit_lead(s, service="commercial", size="commercial")
    for st in ("contacted", "quoted", "booked", "completed"):
        mechie.put(f"{API}/pm/leads/{lead['lead_id']}/stage", json={"stage": st}, timeout=20)
    r = mechie.put(f"{API}/pm/leads/{lead['lead_id']}/stage",
                   json={"stage": "paid"}, timeout=20)
    assert r.status_code == 400
    assert "revenue" in r.json()["detail"].lower()
    # Now with job_value → succeeds
    r2 = mechie.put(f"{API}/pm/leads/{lead['lead_id']}/stage",
                    json={"stage": "paid", "job_value": 1000}, timeout=20)
    assert r2.status_code == 200


# ---------------- Category mapping smoke ---------------------------------------
def test_category_mapping_smoke(mechie):
    """Verify B/C/F/G/D resolution via calc through paid-flow of one lead each."""
    for svc, cat, is_rec in [
        ("deep", "B", False),
        ("handyman", "C", False),
        ("web_development", "F", False),
        ("web_development", "G", True),
    ]:
        s, me = _reg_va(f"Cat{cat}")
        _approve(mechie, me["user_id"])
        lead = _submit_lead(s, service=svc, size="2br", is_recurring=is_rec)
        if cat == "G":
            _walk_to_paid(mechie, lead["lead_id"], job_value=100)
        else:
            _walk_to_paid(mechie, lead["lead_id"], job_profit=100)
        rows = mechie.get(f"{API}/pm/commissions", timeout=20).json()["items"]
        ag = next((c for c in rows if c.get("lead_id") == lead["lead_id"] and c["kind"] == "pool_agent"), None)
        assert ag is not None, f"no pool_agent for svc={svc} cat={cat}"
        assert ag["category"] == cat, f"expected {cat} for {svc} rec={is_rec}, got {ag['category']}"


# ---------------- Tier promotion via DB fixture --------------------------------
async def _bulk_seed_paid(uid, n):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    docs = []
    now = datetime.now(timezone.utc).isoformat()
    for i in range(n):
        docs.append({
            "lead_id": f"TESTseed_{uuid.uuid4().hex[:10]}",
            "va_user_id": uid,
            "va_name": "TEST seed",
            "prospect_name": f"seed{i}",
            "prospect_phone_norm": f"seed_{uid}_{i}",
            "prospect_email_norm": "",
            "service_type": "routine",
            "property_size": "2br",
            "stage": "paid",
            "stage_changed_at": now,
            "created_at": now,
            "deleted_at": None,
            "is_recurring": False,
            "job_profit": 100,
        })
    await db.va_leads.insert_many(docs)
    for d in docs:
        _created_lead_ids.append(d["lead_id"])
    client.close()


def test_tier_promotion_senior(mechie):
    s, me = _reg_va("Sen")
    _approve(mechie, me["user_id"])
    asyncio.run(_bulk_seed_paid(me["user_id"], 25))
    # Now submit a NEW cat B lead
    lead = _submit_lead(s, service="deep", size="3br")
    _walk_to_paid(mechie, lead["lead_id"], job_profit=100)
    rows = mechie.get(f"{API}/pm/commissions", timeout=20).json()["items"]
    ag = next(c for c in rows if c.get("lead_id") == lead["lead_id"] and c["kind"] == "pool_agent")
    assert ag["tier"] == "senior", ag
    assert ag["pool_rate"] == 15.0, ag  # senior B = 15
    assert ag["pool_amount"] == 15.0
    assert ag["amount"] == round(15.0 * 0.75, 2)  # 11.25
    # dashboard shows tier
    dash = s.get(f"{API}/va/dashboard", timeout=20).json()
    t = dash.get("agent_tier") or {}
    assert t.get("tier") == "senior", dash
    assert t.get("paid_jobs") >= 25


# ---------------- Cat D visit 4 mid phase --------------------------------------
async def _seed_recurring_history(uid, va_name, phone_norm, n_paid):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    docs = []
    now = datetime.now(timezone.utc).isoformat()
    for i in range(n_paid):
        docs.append({
            "lead_id": f"TESTrec_{uuid.uuid4().hex[:10]}",
            "va_user_id": uid,
            "va_name": va_name,
            "prospect_name": "rec client",
            "prospect_phone_norm": phone_norm,
            "prospect_email_norm": "",
            "service_type": "routine",
            "property_size": "2br",
            "stage": "paid",
            "is_recurring": True,
            "stage_changed_at": now,
            "created_at": now,
            "deleted_at": None,
            "job_profit": 100,
        })
    await db.va_leads.insert_many(docs)
    for d in docs:
        _created_lead_ids.append(d["lead_id"])
    client.close()


def test_cat_D_visit_4_mid_phase(mechie):
    s, me = _reg_va("Drec")
    _approve(mechie, me["user_id"])
    phone = f"3{uuid.uuid4().int % 10**9:09d}"
    phone_norm = re.sub(r"[^\d]", "", phone)
    # Seed 3 completed recurring paid leads for same client
    asyncio.run(_seed_recurring_history(me["user_id"], me.get("name") or "seed", phone_norm, 3))
    # Now submit visit 4
    lead = _submit_lead(s, service="routine", size="2br",
                       phone=phone, is_recurring=True)
    _walk_to_paid(mechie, lead["lead_id"], job_profit=100)
    rows = mechie.get(f"{API}/pm/commissions", timeout=20).json()["items"]
    ag = next(c for c in rows if c.get("lead_id") == lead["lead_id"] and c["kind"] == "pool_agent")
    assert ag["category"] == "D"
    assert ag["visit_number"] == 4, ag
    assert ag["tail_phase"] == "mid"
    assert ag["pool_rate"] == 10.0
    assert ag["pool_amount"] == 10.0


# ---------------- Same-VA repeat allowed / different-VA blocked ----------------
def test_same_va_repeat_allowed_diff_va_blocked(mechie):
    s1, va1 = _reg_va("Rep1")
    _approve(mechie, va1["user_id"])
    phone = f"3{uuid.uuid4().int % 10**9:09d}"
    lead = _submit_lead(s1, service="routine", phone=phone)
    # walk to paid so it becomes completed/paid — allowable for same-VA resub
    _walk_to_paid(mechie, lead["lead_id"], job_profit=100)
    # Same VA resubmits with is_recurring=True → should succeed
    r_ok = s1.post(f"{API}/va/leads", json={
        "prospect_name": "Repeat",
        "prospect_phone": phone,
        "service_type": "routine",
        "property_size": "2br",
        "source": "other",
        "is_recurring": True,
    }, timeout=20)
    assert r_ok.status_code == 200, f"same-VA resubmit should be allowed: {r_ok.text}"
    _created_lead_ids.append(r_ok.json()["lead_id"])
    # Different VA within 90 days → blocked 409
    s2, va2 = _reg_va("Rep2")
    _approve(mechie, va2["user_id"])
    r_block = s2.post(f"{API}/va/leads", json={
        "prospect_name": "Other",
        "prospect_phone": phone,
        "service_type": "routine",
        "property_size": "2br",
        "source": "other",
    }, timeout=20)
    assert r_block.status_code == 409, r_block.text


# ---------------- Team lead qualification --------------------------------------
def test_team_lead_reject_below_senior(mechie):
    s, me = _reg_va("TL_junior")
    _approve(mechie, me["user_id"])
    r = mechie.put(f"{API}/pm/vas/{me['user_id']}/team-lead",
                   json={"is_team_lead": True}, timeout=20)
    assert r.status_code == 400
    assert "senior" in r.json()["detail"].lower()


def test_team_lead_promote_senior_and_override(mechie, owner):
    # Create senior TL
    s_tl, tl = _reg_va("TL_sen")
    _approve(mechie, tl["user_id"])
    asyncio.run(_bulk_seed_paid(tl["user_id"], 25))
    # Promote to team lead
    r = mechie.put(f"{API}/pm/vas/{tl['user_id']}/team-lead",
                   json={"is_team_lead": True}, timeout=20)
    assert r.status_code == 200
    # Reject self-assign
    rs = mechie.put(f"{API}/pm/vas/{tl['user_id']}/team",
                    json={"team_lead_id": tl["user_id"]}, timeout=20)
    assert rs.status_code == 400
    # Reject TL joining a team
    s_tl2, tl2 = _reg_va("TL_sen2")
    _approve(mechie, tl2["user_id"])
    asyncio.run(_bulk_seed_paid(tl2["user_id"], 25))
    mechie.put(f"{API}/pm/vas/{tl2['user_id']}/team-lead",
               json={"is_team_lead": True}, timeout=20)
    rj = mechie.put(f"{API}/pm/vas/{tl2['user_id']}/team",
                    json={"team_lead_id": tl["user_id"]}, timeout=20)
    assert rj.status_code == 400
    # Create a member VA and assign
    s_m, m = _reg_va("TL_mem")
    _approve(mechie, m["user_id"])
    ra = mechie.put(f"{API}/pm/vas/{m['user_id']}/team",
                    json={"team_lead_id": tl["user_id"]}, timeout=20)
    assert ra.status_code == 200
    # Member closes a paid Cat A lead → team_override should be created
    lead = _submit_lead(s_m, service="routine")
    _walk_to_paid(mechie, lead["lead_id"], job_profit=200)
    rows = mechie.get(f"{API}/pm/commissions", timeout=20).json()["items"]
    lead_rows = [c for c in rows if c.get("lead_id") == lead["lead_id"]]
    kinds = {c["kind"]: c for c in lead_rows}
    assert "team_override" in kinds, f"expected override, got {kinds.keys()}"
    ovr = kinds["team_override"]
    assert ovr["amount"] == 3.0, ovr  # 15% of 20 pool
    assert ovr["va_user_id"] == tl["user_id"]
    # Agent still gets full 75%
    assert kinds["pool_agent"]["amount"] == 15.0
    # Ops still 10%
    assert kinds["ops_share"]["amount"] == 2.0


def test_team_cap_5(mechie):
    # Create senior TL
    s_tl, tl = _reg_va("TL_cap")
    _approve(mechie, tl["user_id"])
    asyncio.run(_bulk_seed_paid(tl["user_id"], 25))
    mechie.put(f"{API}/pm/vas/{tl['user_id']}/team-lead",
               json={"is_team_lead": True}, timeout=20)
    # Add 5 members
    for i in range(5):
        _, mem = _reg_va(f"cap{i}")
        _approve(mechie, mem["user_id"])
        r = mechie.put(f"{API}/pm/vas/{mem['user_id']}/team",
                       json={"team_lead_id": tl["user_id"]}, timeout=20)
        assert r.status_code == 200
    # 6th should be rejected
    _, mem6 = _reg_va("cap6")
    _approve(mechie, mem6["user_id"])
    r6 = mechie.put(f"{API}/pm/vas/{mem6['user_id']}/team",
                    json={"team_lead_id": tl["user_id"]}, timeout=20)
    assert r6.status_code == 400
    assert "cap" in r6.json()["detail"].lower() or "5" in r6.json()["detail"]


# ---------------- Commission settings API --------------------------------------
def test_commission_settings_get_and_put(mechie):
    r = mechie.get(f"{API}/pm/commission-settings", timeout=20)
    assert r.status_code == 200
    j = r.json()
    for key in ("pool_rates", "pool_split", "tier_thresholds", "category_labels", "defaults"):
        assert key in j, f"missing {key}"
    assert j["pool_split"] == {"agent": 75.0, "lead": 15.0, "ops": 10.0}
    for cat in ("A", "B", "C", "D", "E", "F", "G"):
        assert cat in j["pool_rates"]
    # Unknown category → 400
    r_bad = mechie.put(f"{API}/pm/commission-settings",
                      json={"pool_rates": {"Z": {"agent": 10}}}, timeout=20)
    assert r_bad.status_code == 400
    # >100 rate → 400
    r_bad2 = mechie.put(f"{API}/pm/commission-settings",
                       json={"pool_rates": {"A": {"agent": 150}}}, timeout=20)
    assert r_bad2.status_code == 400
    # Valid update persists
    r_ok = mechie.put(f"{API}/pm/commission-settings",
                     json={"pool_rates": {"A": {"agent": 11.0}}}, timeout=20)
    assert r_ok.status_code == 200
    assert r_ok.json()["pool_rates"]["A"]["agent"] == 11.0
    # Reset back to default
    mechie.put(f"{API}/pm/commission-settings",
               json={"pool_rates": {"A": {"agent": 10.0}}}, timeout=20)


# ---------------- Commercial log-revenue split ---------------------------------
def test_commercial_log_revenue_pool_split(mechie):
    s, me = _reg_va("ComRev")
    _approve(mechie, me["user_id"])
    r = mechie.post(f"{API}/pm/commercial-accounts", json={
        "account_name": f"TEST Acme {uuid.uuid4().hex[:4]}",
        "va_user_id": me["user_id"],
        "monthly_revenue": 1000.0,
    }, timeout=20)
    assert r.status_code == 200, r.text
    acct = r.json()
    _created_account_ids.append(acct["account_id"])
    # Log $2000 revenue → 5% pool = $100 → agent 75=$75, ops 10=$10
    r2 = mechie.post(f"{API}/pm/commercial-accounts/{acct['account_id']}/log-revenue",
                    json={"revenue": 2000, "period": "2026-07"}, timeout=20)
    assert r2.status_code == 200, r2.text
    j = r2.json()
    # Response could be either the agent doc or aggregate — check agent commission via query
    rows = mechie.get(f"{API}/pm/commissions", timeout=20).json()["items"]
    period_rows = [c for c in rows if c.get("commercial_account_id") == acct["account_id"]]
    kinds = {c["kind"]: c for c in period_rows}
    assert "pool_agent" in kinds
    assert kinds["pool_agent"]["amount"] == 75.0
    assert kinds["pool_agent"]["pool_amount"] == 100.0
    assert kinds["pool_agent"]["category"] == "E"
    assert "ops_share" in kinds
    assert kinds["ops_share"]["amount"] == 10.0


def test_commercial_log_revenue_rejects_unapproved(mechie):
    s, me = _reg_va("ComRev2")
    _approve(mechie, me["user_id"])
    r = mechie.post(f"{API}/pm/commercial-accounts", json={
        "account_name": f"TEST Susp {uuid.uuid4().hex[:4]}",
        "va_user_id": me["user_id"],
        "monthly_revenue": 500.0,
    }, timeout=20)
    acct = r.json()
    _created_account_ids.append(acct["account_id"])
    # Suspend VA
    mechie.post(f"{API}/pm/vas/{me['user_id']}/suspend", json={"note": "test"}, timeout=20)
    r2 = mechie.post(f"{API}/pm/commercial-accounts/{acct['account_id']}/log-revenue",
                    json={"revenue": 1000, "period": "2026-07"}, timeout=20)
    assert r2.status_code == 400, r2.text


# ---------------- Legacy commission frozen -------------------------------------
async def _seed_legacy_commission(uid):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    now = datetime.now(timezone.utc).isoformat()
    lead_id = f"TESTleg_{uuid.uuid4().hex[:10]}"
    lead_doc = {
        "lead_id": lead_id, "va_user_id": uid, "va_name": "TESTleg",
        "prospect_name": "legacy client",
        "prospect_phone_norm": f"legacy_{uid}",
        "prospect_email_norm": "",
        "service_type": "routine", "property_size": "2br",
        "stage": "completed", "stage_changed_at": now, "created_at": now,
        "deleted_at": None, "is_recurring": False, "job_profit": 100,
    }
    await db.va_leads.insert_one(lead_doc)
    _created_lead_ids.append(lead_id)
    comm_id = f"TESTcomm_{uuid.uuid4().hex[:10]}"
    await db.commissions.insert_one({
        "commission_id": comm_id, "lead_id": lead_id,
        "va_user_id": uid, "kind": "one_time",  # old kind
        "amount": 25.0, "status": "pending_approval",
        # no 'engine' field — pre-pool
        "created_at": now, "updated_at": now,
        "prospect_name": "legacy client",
        "service_type": "routine",
    })
    _created_commission_ids.append(comm_id)
    client.close()
    return lead_id, comm_id


def test_legacy_commission_frozen(mechie):
    s, me = _reg_va("Leg")
    _approve(mechie, me["user_id"])
    lead_id, comm_id = asyncio.run(_seed_legacy_commission(me["user_id"]))
    # Re-mark paid with job_profit=500 → pool recalc would produce $50 pool
    # for cat A. But legacy commission must stay at $25.
    r = mechie.put(f"{API}/pm/leads/{lead_id}/stage",
                  json={"stage": "paid", "job_profit": 500}, timeout=20)
    assert r.status_code == 200, r.text
    # Query DB directly
    async def _get():
        client = AsyncIOMotorClient(MONGO_URL)
        c = await client[DB_NAME].commissions.find_one({"commission_id": comm_id})
        client.close()
        return c
    doc = asyncio.run(_get())
    assert doc["amount"] == 25.0, doc
    assert doc.get("engine") != "pool_v2"


# ---------------- Cleanup fixture ----------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _cleanup():
    yield
    async def _do():
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        if _created_lead_ids:
            await db.va_leads.delete_many({"lead_id": {"$in": _created_lead_ids}})
            await db.commissions.delete_many({"lead_id": {"$in": _created_lead_ids}})
            await db.va_lead_activity.delete_many({"lead_id": {"$in": _created_lead_ids}})
        if _created_commission_ids:
            await db.commissions.delete_many({"commission_id": {"$in": _created_commission_ids}})
        if _created_account_ids:
            await db.commercial_accounts.delete_many({"account_id": {"$in": _created_account_ids}})
            await db.commissions.delete_many({"commercial_account_id": {"$in": _created_account_ids}})
        if _created_va_ids:
            await db.users.delete_many({"user_id": {"$in": _created_va_ids}})
            await db.va_violations.delete_many({"va_user_id": {"$in": _created_va_ids}})
            await db.commissions.delete_many({"va_user_id": {"$in": _created_va_ids}})
            await db.va_leads.delete_many({"va_user_id": {"$in": _created_va_ids}})
        client.close()
    asyncio.run(_do())
