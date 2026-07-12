"""Pipeline regression: pool_agent + ops_share + team_override must all flow
through PM approval → owner approval → mark paid; VA earnings shows agent doc."""
import asyncio, os, uuid
from datetime import datetime, timezone
import pytest, requests
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://work-connect-147.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL, DB_NAME = "mongodb://localhost:27017", "test_database"

def _login(e,p):
    s=requests.Session(); r=s.post(f"{API}/auth/login",json={"email":e,"password":p},timeout=20)
    assert r.status_code==200; return s

_cleanup_users=[]; _cleanup_leads=[]

def _reg(pref):
    email=f"TEST_pl_{pref}_{uuid.uuid4().hex[:6]}@example.com"
    s=requests.Session()
    r=s.post(f"{API}/auth/register",json={"email":email,"password":"password123","name":f"TEST_{pref}",
        "role":"va","va_phone":f"9{uuid.uuid4().int%10**9:09d}",
        "va_address":f"{uuid.uuid4().hex[:6]} test street baltimore md 21230"},timeout=20)
    assert r.status_code==200
    me=r.json(); _cleanup_users.append(me["user_id"]); return s,me

async def _seed_paid(uid,n):
    c=AsyncIOMotorClient(MONGO_URL); db=c[DB_NAME]
    now=datetime.now(timezone.utc).isoformat()
    docs=[{"lead_id":f"TESTsp_{uuid.uuid4().hex[:10]}","va_user_id":uid,"va_name":"seed",
        "prospect_name":f"s{i}","prospect_phone_norm":f"ps_{uid}_{i}","prospect_email_norm":"",
        "service_type":"routine","property_size":"2br","stage":"paid","stage_changed_at":now,
        "created_at":now,"deleted_at":None,"is_recurring":False,"job_profit":100} for i in range(n)]
    await db.va_leads.insert_many(docs)
    for d in docs: _cleanup_leads.append(d["lead_id"])
    c.close()

def test_full_approval_pipeline():
    mechie=_login("mechiebadlong77@gmail.com","Mechie2026!")
    owner=_login("admin@hcobcleaners.com","HcobAdmin2026!")
    # Build senior TL + team member
    _,tl=_reg("tlp"); mechie.post(f"{API}/pm/vas/{tl['user_id']}/approve",json={},timeout=20)
    asyncio.run(_seed_paid(tl["user_id"],25))
    r=mechie.put(f"{API}/pm/vas/{tl['user_id']}/team-lead",json={"is_team_lead":True},timeout=20)
    assert r.status_code==200
    s_m,m=_reg("mem"); mechie.post(f"{API}/pm/vas/{m['user_id']}/approve",json={},timeout=20)
    mechie.put(f"{API}/pm/vas/{m['user_id']}/team",json={"team_lead_id":tl["user_id"]},timeout=20)
    # Submit + walk to paid
    lead=s_m.post(f"{API}/va/leads",json={"prospect_name":"TESTclient",
        "prospect_phone":f"3{uuid.uuid4().int%10**9:09d}","service_type":"routine",
        "property_size":"2br","source":"other"},timeout=20).json()
    _cleanup_leads.append(lead["lead_id"])
    for st in ("contacted","quoted","booked","completed"):
        mechie.put(f"{API}/pm/leads/{lead['lead_id']}/stage",json={"stage":st},timeout=20)
    r=mechie.put(f"{API}/pm/leads/{lead['lead_id']}/stage",
                 json={"stage":"paid","job_profit":200},timeout=20)
    assert r.status_code==200
    rows=mechie.get(f"{API}/pm/commissions",timeout=20).json()["items"]
    lead_rows=[c for c in rows if c.get("lead_id")==lead["lead_id"]]
    assert len(lead_rows)==3, lead_rows
    # PM approve all 3
    for c in lead_rows:
        r=mechie.post(f"{API}/pm/commissions/{c['commission_id']}/approve",json={},timeout=20)
        assert r.status_code==200 and r.json()["status"]=="pm_approved"
    # Owner queue contains all 3
    oq=owner.get(f"{API}/owner/payouts/queue",timeout=20).json()["items"]
    ids={c["commission_id"] for c in lead_rows}
    assert ids.issubset({c["commission_id"] for c in oq})
    # Owner approve + mark paid each
    for c in lead_rows:
        r=owner.post(f"{API}/owner/payouts/{c['commission_id']}/approve",timeout=20)
        assert r.status_code==200
        r=owner.post(f"{API}/owner/payouts/{c['commission_id']}/mark-paid",
                     json={"payout_reference":"ref","payout_method":"venmo"},timeout=20)
        assert r.status_code==200 and r.json()["status"]=="paid"
    # VA earnings shows pool_agent doc
    earn=s_m.get(f"{API}/va/earnings",timeout=20).json()
    assert any(i["kind"]=="pool_agent" for i in earn["items"])
    assert earn["totals"]["all_time"]>=15.0

@pytest.fixture(scope="session",autouse=True)
def _clean():
    yield
    async def _do():
        c=AsyncIOMotorClient(MONGO_URL); db=c[DB_NAME]
        if _cleanup_leads:
            await db.va_leads.delete_many({"lead_id":{"$in":_cleanup_leads}})
            await db.commissions.delete_many({"lead_id":{"$in":_cleanup_leads}})
        if _cleanup_users:
            await db.users.delete_many({"user_id":{"$in":_cleanup_users}})
            await db.commissions.delete_many({"va_user_id":{"$in":_cleanup_users}})
            await db.va_leads.delete_many({"va_user_id":{"$in":_cleanup_users}})
        c.close()
    asyncio.run(_do())
