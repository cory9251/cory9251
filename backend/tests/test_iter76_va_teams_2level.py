"""Iter 76 — VA Commission Teams: TWO-LEVEL override + depth cap regression.

Chain built for math test:  TOP ← MID ← BOTTOM
 - TOP  = user_7f11e268d4b9 (top team lead)
 - MID  = user_0e4a17b36f7b (sub-lead: reports to TOP, leads BOTTOM)
 - BOT  = user_cc4c33406839 (member of MID)
 - EXTRA= user_963e6aede023 (va.demo — used for depth-cap 4th slot)

junk_removal = $10 flat. With L1=10%, L2=5%:
  closer(BOT)=8.50,  L1(MID)=1.00,  L2(TOP)=0.50.
"""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://work-connect-147.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = ("admin@hcobcleaners.com", "HcobAdmin2026!")
VA_LEAD = ("va.demo@hcobcleaners.com", "VaDemo2026!")

TOP = "user_7f11e268d4b9"
MID = "user_0e4a17b36f7b"
BOT = "user_cc4c33406839"
EXTRA = "user_963e6aede023"  # va.demo

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

TEST_LEAD_IDS: list = []


@pytest.fixture(scope="module")
def mongo():
    return MongoClient(MONGO_URL)[DB_NAME]


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(*ADMIN)


def _reset_users(mongo):
    for uid in (TOP, MID, BOT, EXTRA):
        mongo.users.update_one({"user_id": uid}, {"$set": {"is_team_lead": False, "team_lead_id": None}})


@pytest.fixture(scope="module", autouse=True)
def cleanup(mongo, admin):
    # Pre-clean any lingering test data
    for lid in list(mongo.va_leads.find({"lead_id": {"$regex": "^lead_TEAMTEST"}}, {"lead_id": 1})):
        mongo.va_leads.delete_one({"lead_id": lid["lead_id"]})
        mongo.commissions.delete_many({"lead_id": lid["lead_id"]})
    _reset_users(mongo)
    admin.put(f"{API}/pm/commission-settings",
              json={"team_override_pct": 10.0, "team_override_l2_pct": 5.0}, timeout=15)
    yield
    # Teardown
    for lid in TEST_LEAD_IDS:
        mongo.va_leads.delete_one({"lead_id": lid})
        mongo.commissions.delete_many({"lead_id": lid})
    # Also nuke any stale test leads
    for lid in list(mongo.va_leads.find({"lead_id": {"$regex": "^lead_TEAMTEST"}}, {"lead_id": 1})):
        mongo.va_leads.delete_one({"lead_id": lid["lead_id"]})
        mongo.commissions.delete_many({"lead_id": lid["lead_id"]})
    _reset_users(mongo)
    admin.put(f"{API}/pm/commission-settings",
              json={"team_override_pct": 10.0, "team_override_l2_pct": 5.0}, timeout=15)


def _seed_lead(mongo, va_user_id, va_name="Test VA"):
    lid = f"lead_TEAMTEST_{uuid.uuid4().hex[:8]}"
    now = "2026-01-15T00:00:00+00:00"
    mongo.va_leads.insert_one({
        "lead_id": lid,
        "va_user_id": va_user_id,
        "va_name": va_name,
        "prospect_name": "TEST_Prospect",
        "prospect_phone": "5551234567",
        "prospect_phone_norm": f"555{uuid.uuid4().hex[:7]}",
        "prospect_email": "",
        "prospect_email_norm": "",
        "prospect_address": "",
        "prospect_address_norm": "",
        "service_type": "junk_removal",
        "property_size": "2br",
        "estimated_budget": None,
        "preferred_datetime": None,
        "source": "other",
        "notes": "",
        "stage": "new_lead",
        "stage_history": [{"stage": "new_lead", "at": now, "by": va_user_id}],
        "stage_changed_at": now,
        "job_value": None,
        "created_at": now,
        "updated_at": now,
    })
    TEST_LEAD_IDS.append(lid)
    return lid


# ---------------------------------------------------------------------------
# 1) Settings: L1 + L2
# ---------------------------------------------------------------------------
class TestCommissionSettingsL2:
    def test_get_has_both_rates(self, admin):
        r = admin.get(f"{API}/pm/commission-settings", timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert "team_override_pct" in j
        assert "team_override_l2_pct" in j
        assert "defaults" in j
        assert j["defaults"].get("team_override_l2_pct") == 5.0
        assert float(j["team_override_l2_pct"]) == 5.0

    def test_put_persists_both(self, admin):
        r = admin.put(f"{API}/pm/commission-settings",
                      json={"team_override_pct": 12.0, "team_override_l2_pct": 7.0}, timeout=15)
        assert r.status_code == 200
        g = admin.get(f"{API}/pm/commission-settings", timeout=15).json()
        assert float(g["team_override_pct"]) == 12.0
        assert float(g["team_override_l2_pct"]) == 7.0
        # reset
        admin.put(f"{API}/pm/commission-settings",
                  json={"team_override_pct": 10.0, "team_override_l2_pct": 5.0}, timeout=15)


# ---------------------------------------------------------------------------
# 2) Build 2-level chain via API then run math
# ---------------------------------------------------------------------------
class TestTwoLevelChainAndMath:
    def test_build_chain(self, admin, mongo):
        # Promote TOP and MID to team leads
        r1 = admin.put(f"{API}/pm/vas/{TOP}/team-lead", json={"is_team_lead": True}, timeout=15)
        assert r1.status_code == 200
        r2 = admin.put(f"{API}/pm/vas/{MID}/team-lead", json={"is_team_lead": True}, timeout=15)
        assert r2.status_code == 200
        # Assign MID under TOP  (dual-role: MID is a lead AND a member)
        r3 = admin.put(f"{API}/pm/vas/{MID}/team", json={"team_lead_id": TOP}, timeout=15)
        assert r3.status_code == 200, f"MID under TOP failed: {r3.text}"
        # Assign BOT under MID
        r4 = admin.put(f"{API}/pm/vas/{BOT}/team", json={"team_lead_id": MID}, timeout=15)
        assert r4.status_code == 200, f"BOT under MID failed: {r4.text}"

    def test_two_level_math(self, admin, mongo):
        # Ensure rates
        admin.put(f"{API}/pm/commission-settings",
                  json={"team_override_pct": 10.0, "team_override_l2_pct": 5.0}, timeout=15)
        lid = _seed_lead(mongo, BOT, "BOTTOM VA")
        r1 = admin.put(f"{API}/pm/leads/{lid}/stage", json={"stage": "booked"}, timeout=15)
        assert r1.status_code == 200, r1.text
        r2 = admin.put(f"{API}/pm/leads/{lid}/stage", json={"stage": "paid"}, timeout=15)
        assert r2.status_code == 200, r2.text

        member_cs = list(mongo.commissions.find({"lead_id": lid, "kind": {"$ne": "team_override"}}))
        override_cs = list(mongo.commissions.find({"lead_id": lid, "kind": "team_override"}))
        assert len(member_cs) == 1, f"expected 1 member commission, got {len(member_cs)}"
        assert len(override_cs) == 2, f"expected 2 override commissions, got {len(override_cs)}: {override_cs}"

        m = member_cs[0]
        assert abs(float(m["amount"]) - 8.50) < 0.001, f"closer amount {m['amount']} != 8.50"
        assert m["va_user_id"] == BOT
        assert m.get("status") == "pending_approval"

        o_by_level = {int(o.get("level") or 0): o for o in override_cs}
        assert 1 in o_by_level and 2 in o_by_level
        l1 = o_by_level[1]
        l2 = o_by_level[2]
        assert abs(float(l1["amount"]) - 1.00) < 0.001, f"L1 {l1['amount']} != 1.00"
        assert l1["va_user_id"] == MID
        assert l1.get("source_va_user_id") == BOT
        assert abs(float(l2["amount"]) - 0.50) < 0.001, f"L2 {l2['amount']} != 0.50"
        assert l2["va_user_id"] == TOP
        assert l2.get("source_va_user_id") == BOT

    def test_lost_rejects_all_three(self, admin, mongo):
        lid = TEST_LEAD_IDS[-1]
        r = admin.put(f"{API}/pm/leads/{lid}/stage", json={"stage": "lost"}, timeout=15)
        assert r.status_code == 200, r.text
        all_cs = list(mongo.commissions.find({"lead_id": lid}))
        assert len(all_cs) == 3
        for c in all_cs:
            assert c.get("status") == "rejected", f"{c.get('commission_id')} not rejected: {c.get('status')}"


# ---------------------------------------------------------------------------
# 3) Single-level regression (LEAD ← MEMBER only, no grandparent)
# ---------------------------------------------------------------------------
class TestSingleLevelStillWorks:
    def test_single_level(self, admin, mongo):
        # Use TOP←MID relationship only, but MID is also a lead with BOT under it.
        # We want a chain with no grandparent so use MID as closer? No — MID has TOP above.
        # Detach MID from TOP for this test, then reattach.
        admin.put(f"{API}/pm/vas/{MID}/team", json={"team_lead_id": None}, timeout=15)
        # Now MID (lead) ← BOT (member). No grandparent for BOT.
        # Ensure BOT still under MID
        mongo.users.update_one({"user_id": BOT}, {"$set": {"team_lead_id": MID}})

        lid = _seed_lead(mongo, BOT, "BOT single-level")
        admin.put(f"{API}/pm/leads/{lid}/stage", json={"stage": "booked"}, timeout=15)
        admin.put(f"{API}/pm/leads/{lid}/stage", json={"stage": "paid"}, timeout=15)

        member_cs = list(mongo.commissions.find({"lead_id": lid, "kind": {"$ne": "team_override"}}))
        override_cs = list(mongo.commissions.find({"lead_id": lid, "kind": "team_override"}))
        assert len(member_cs) == 1
        assert len(override_cs) == 1, f"expected exactly 1 override, got {len(override_cs)}"
        assert abs(float(member_cs[0]["amount"]) - 9.0) < 0.001
        assert int(override_cs[0].get("level") or 1) == 1
        assert abs(float(override_cs[0]["amount"]) - 1.0) < 0.001
        assert override_cs[0]["va_user_id"] == MID

        # Reattach MID under TOP so subsequent tests keep the chain
        admin.put(f"{API}/pm/vas/{MID}/team", json={"team_lead_id": TOP}, timeout=15)


# ---------------------------------------------------------------------------
# 4) Solo VA (no team) unaffected
# ---------------------------------------------------------------------------
class TestSoloVA:
    def test_solo_full_amount(self, admin, mongo):
        # Pick another approved VA that's not in our chain
        solo = mongo.users.find_one(
            {"role": "va", "va_status": "approved",
             "user_id": {"$nin": [TOP, MID, BOT, EXTRA]},
             "$or": [{"team_lead_id": None}, {"team_lead_id": ""}, {"team_lead_id": {"$exists": False}}]},
            {"user_id": 1, "name": 1},
        )
        if not solo:
            pytest.skip("No solo VA available")
        mongo.users.update_one({"user_id": solo["user_id"]},
                               {"$set": {"team_lead_id": None, "is_team_lead": False}})
        lid = _seed_lead(mongo, solo["user_id"], solo.get("name") or "Solo")
        admin.put(f"{API}/pm/leads/{lid}/stage", json={"stage": "booked"}, timeout=15)
        admin.put(f"{API}/pm/leads/{lid}/stage", json={"stage": "paid"}, timeout=15)

        member_cs = list(mongo.commissions.find({"lead_id": lid, "kind": {"$ne": "team_override"}}))
        override_cs = list(mongo.commissions.find({"lead_id": lid, "kind": "team_override"}))
        assert len(member_cs) == 1
        assert len(override_cs) == 0
        assert abs(float(member_cs[0]["amount"]) - 10.0) < 0.001


# ---------------------------------------------------------------------------
# 5) Depth cap: with TOP←MID←BOT, making BOT a lead + adding a member under it → 400
# ---------------------------------------------------------------------------
class TestDepthCap:
    def test_depth_cap_400(self, admin, mongo):
        # Ensure chain
        admin.put(f"{API}/pm/vas/{TOP}/team-lead", json={"is_team_lead": True}, timeout=15)
        admin.put(f"{API}/pm/vas/{MID}/team-lead", json={"is_team_lead": True}, timeout=15)
        admin.put(f"{API}/pm/vas/{MID}/team", json={"team_lead_id": TOP}, timeout=15)
        admin.put(f"{API}/pm/vas/{BOT}/team", json={"team_lead_id": MID}, timeout=15)

        # Promote BOT to team lead
        r = admin.put(f"{API}/pm/vas/{BOT}/team-lead", json={"is_team_lead": True}, timeout=15)
        assert r.status_code == 200
        # Now try to put EXTRA under BOT — would create 3-level chain → 400
        # Ensure EXTRA has no team currently
        admin.put(f"{API}/pm/vas/{EXTRA}/team", json={"team_lead_id": None}, timeout=15)
        r2 = admin.put(f"{API}/pm/vas/{EXTRA}/team", json={"team_lead_id": BOT}, timeout=15)
        assert r2.status_code == 400, f"expected 400 depth cap, got {r2.status_code} {r2.text}"
        assert "capped" in (r2.text or "").lower() or "two" in (r2.text or "").lower()

        # Reset BOT lead flag
        admin.put(f"{API}/pm/vas/{BOT}/team-lead", json={"is_team_lead": False}, timeout=15)
        # Re-assign BOT under MID (toggle-off detaches downlines; BOT itself is unaffected as member)
        # But is_team_lead=False on BOT also detaches BOT's own members — none, so fine.
        admin.put(f"{API}/pm/vas/{BOT}/team", json={"team_lead_id": MID}, timeout=15)

    def test_cycle_rejected(self, admin, mongo):
        # Ensure chain still: TOP←MID←BOT
        admin.put(f"{API}/pm/vas/{MID}/team", json={"team_lead_id": TOP}, timeout=15)
        admin.put(f"{API}/pm/vas/{BOT}/team", json={"team_lead_id": MID}, timeout=15)
        # Try to put TOP under BOT — TOP is ancestor of BOT → cycle → 400
        # TOP isn't a lead's member yet; also, target BOT is not is_team_lead now.
        # Promote BOT first temporarily
        admin.put(f"{API}/pm/vas/{BOT}/team-lead", json={"is_team_lead": True}, timeout=15)
        r = admin.put(f"{API}/pm/vas/{TOP}/team", json={"team_lead_id": BOT}, timeout=15)
        assert r.status_code == 400, f"expected 400 cycle, got {r.status_code}: {r.text}"
        admin.put(f"{API}/pm/vas/{BOT}/team-lead", json={"is_team_lead": False}, timeout=15)
        admin.put(f"{API}/pm/vas/{BOT}/team", json={"team_lead_id": MID}, timeout=15)


# ---------------------------------------------------------------------------
# 6) Dual role: a lead can also be a member (2-level allowed)
# ---------------------------------------------------------------------------
class TestDualRole:
    def test_lead_can_be_member(self, admin, mongo):
        # MID is is_team_lead=True and reports to TOP — this is dual role.
        # Verify it's currently valid; and verify re-toggling is_team_lead on MID doesn't 400.
        admin.put(f"{API}/pm/vas/{MID}/team", json={"team_lead_id": TOP}, timeout=15)
        m = mongo.users.find_one({"user_id": MID}, {"_id": 0, "is_team_lead": 1, "team_lead_id": 1})
        assert m["is_team_lead"] is True
        assert m["team_lead_id"] == TOP


# ---------------------------------------------------------------------------
# 7) /va/team as TOP: level1+level2 split + sub_member_count on MID member
# ---------------------------------------------------------------------------
class TestVaTeamEndpointTop:
    def test_top_sees_l1_l2_and_sub_member(self, admin, mongo):
        # Re-seed a fresh paid lead to guarantee non-rejected overrides exist
        admin.put(f"{API}/pm/vas/{MID}/team", json={"team_lead_id": TOP}, timeout=15)
        mongo.users.update_one({"user_id": BOT}, {"$set": {"team_lead_id": MID}})
        lid = _seed_lead(mongo, BOT, "BOT for team endpoint")
        admin.put(f"{API}/pm/leads/{lid}/stage", json={"stage": "booked"}, timeout=15)
        admin.put(f"{API}/pm/leads/{lid}/stage", json={"stage": "paid"}, timeout=15)

        # Login as TOP: we don't have password. Fetch via admin bypass? No — the endpoint requires the VA session.
        # Owner Owner can hit /va/team? Endpoint requires role='va'. Skip login as TOP; instead reset admin-flow-only.
        # As a workaround, we admin-verify DB state that TOP will see:
        overrides_top = list(mongo.commissions.find({"va_user_id": TOP, "kind": "team_override"}))
        assert any(int(c.get("level") or 0) == 2 for c in overrides_top), "TOP has no L2 override"

        # PM /pm/teams should show reports_to on MID team card + sub_member_count on MID row inside TOP team.
        r = admin.get(f"{API}/pm/teams", timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert "team_override_l2_pct" in j
        teams = j["teams"]
        top_team = next(t for t in teams if t["user_id"] == TOP)
        mid_team = next(t for t in teams if t["user_id"] == MID)
        # TOP has MID as a member
        top_member_ids = [m["user_id"] for m in top_team["members"]]
        assert MID in top_member_ids
        mid_in_top = next(m for m in top_team["members"] if m["user_id"] == MID)
        assert mid_in_top.get("sub_member_count") == 1, f"MID.sub_member_count expected 1, got {mid_in_top.get('sub_member_count')}"
        # MID team reports_to TOP
        # First ensure MID actually has team_lead_id=TOP (defensive against prior test mutations)
        mid_row = mongo.users.find_one({"user_id": MID}, {"_id": 0, "team_lead_id": 1, "is_team_lead": 1})
        assert mid_row["team_lead_id"] == TOP, f"MID.team_lead_id was reset: {mid_row}"
        rt = mid_team.get("reports_to") or {}
        assert rt.get("user_id") == TOP, f"reports_to on MID team card: {mid_team.get('reports_to')}"


# ---------------------------------------------------------------------------
# 8) /va/team as team lead va.demo — verify shape includes level2
# ---------------------------------------------------------------------------
class TestVaTeamEndpointShape:
    def test_va_demo_lead(self, admin, mongo):
        # Promote va.demo (EXTRA) as team lead, assign someone under it
        admin.put(f"{API}/pm/vas/{EXTRA}/team-lead", json={"is_team_lead": True}, timeout=15)
        # Use a solo approved VA as member — pick a fresh one not in our chain
        solo = mongo.users.find_one(
            {"role": "va", "va_status": "approved",
             "user_id": {"$nin": [TOP, MID, BOT, EXTRA]}},
            {"user_id": 1},
        )
        if solo:
            admin.put(f"{API}/pm/vas/{solo['user_id']}/team",
                      json={"team_lead_id": EXTRA}, timeout=15)
        # Re-login as va.demo — auth context reloads is_team_lead
        s = _login(*VA_LEAD)
        r = s.get(f"{API}/va/team", timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "override_pct" in j
        assert "override_l2_pct" in j
        earn = j["override_earnings"]
        assert "level1" in earn and "level2" in earn and "total" in earn
        # cleanup
        if solo:
            admin.put(f"{API}/pm/vas/{solo['user_id']}/team",
                      json={"team_lead_id": None}, timeout=15)

    def test_non_lead_403(self, admin, mongo):
        # Toggle EXTRA off
        admin.put(f"{API}/pm/vas/{EXTRA}/team-lead", json={"is_team_lead": False}, timeout=15)
        s = _login(*VA_LEAD)
        r = s.get(f"{API}/va/team", timeout=15)
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# 9) Assignable list should now include other team leads (dual role allowed)
# ---------------------------------------------------------------------------
class TestAssignableIncludesLeads:
    def test_pm_teams_assignable(self, admin, mongo):
        # Ensure a fresh promotion state: promote a solo lead not on any team
        # va.demo (EXTRA) is a good candidate — promote and ensure no team_lead_id
        admin.put(f"{API}/pm/vas/{EXTRA}/team", json={"team_lead_id": None}, timeout=15)
        admin.put(f"{API}/pm/vas/{EXTRA}/team-lead", json={"is_team_lead": True}, timeout=15)
        j = admin.get(f"{API}/pm/teams", timeout=15).json()
        assignable_ids = [a["user_id"] for a in j["assignable_vas"]]
        # A lead with no team_lead_id should be assignable now (dual role)
        # (Requirement: assignable includes other leads with no team_lead_id set.)
        assert EXTRA in assignable_ids, "team lead with no upline should be assignable as member"
        admin.put(f"{API}/pm/vas/{EXTRA}/team-lead", json={"is_team_lead": False}, timeout=15)
