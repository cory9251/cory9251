"""Iter 75 — VA Commission Teams: override math + lifecycle + endpoints.

Covers:
- GET/PUT /api/pm/commission-settings (team_override_pct default 10, persist)
- PUT /api/pm/vas/{id}/team-lead (promote/demote, 400 if already in team)
- GET /api/pm/teams (assignable_vas, member_count)
- PUT /api/pm/vas/{id}/team (assign/unassign, validation 400s)
- Override math (SPLIT $10→$9+$1) via booked→paid stage moves
- Regression: exactly one member commission + one override, correct kinds
- Lost recovery: both member + override rejected
- /va/team returns members/earnings for lead, 403 for non-lead
- No-override case: solo VA gets full amount, no team_override row
"""
import os
import time
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://work-connect-147.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = ("admin@hcobcleaners.com", "HcobAdmin2026!")
VA_LEAD = ("va.demo@hcobcleaners.com", "VaDemo2026!")
LEAD_USER_ID = "user_963e6aede023"
MEMBER_USER_ID = "user_7f11e268d4b9"

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"

TEST_LEAD_IDS: list = []


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    return c[DB_NAME]


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(*ADMIN)


@pytest.fixture(scope="module", autouse=True)
def cleanup(mongo, admin):
    """Ensure clean starting state and restore after."""
    # Pre-clean: any lingering test leads/commissions
    for lid in list(mongo.va_leads.find({"lead_id": {"$regex": "^lead_TEAMTEST"}}, {"lead_id": 1})):
        mongo.va_leads.delete_one({"lead_id": lid["lead_id"]})
        mongo.commissions.delete_many({"lead_id": lid["lead_id"]})
    # Ensure baseline: both users not team related
    mongo.users.update_one({"user_id": LEAD_USER_ID}, {"$set": {"is_team_lead": False, "team_lead_id": None}})
    mongo.users.update_one({"user_id": MEMBER_USER_ID}, {"$set": {"is_team_lead": False, "team_lead_id": None}})
    # Ensure override pct = 10
    admin.put(f"{API}/pm/commission-settings", json={"team_override_pct": 10.0}, timeout=15)

    yield

    # Teardown
    for lid in TEST_LEAD_IDS:
        mongo.va_leads.delete_one({"lead_id": lid})
        mongo.commissions.delete_many({"lead_id": lid})
    mongo.users.update_one({"user_id": LEAD_USER_ID}, {"$set": {"is_team_lead": False, "team_lead_id": None}})
    mongo.users.update_one({"user_id": MEMBER_USER_ID}, {"$set": {"is_team_lead": False, "team_lead_id": None}})
    admin.put(f"{API}/pm/commission-settings", json={"team_override_pct": 10.0}, timeout=15)


# ---------------------------------------------------------------------------
# Commission settings
# ---------------------------------------------------------------------------
class TestCommissionSettings:
    def test_get_has_team_override(self, admin):
        r = admin.get(f"{API}/pm/commission-settings", timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert "team_override_pct" in j
        assert "defaults" in j and "team_override_pct" in j["defaults"]
        assert j["defaults"]["team_override_pct"] == 10.0
        assert float(j["team_override_pct"]) == 10.0

    def test_put_persists(self, admin):
        r = admin.put(f"{API}/pm/commission-settings", json={"team_override_pct": 15.0}, timeout=15)
        assert r.status_code == 200
        g = admin.get(f"{API}/pm/commission-settings", timeout=15).json()
        assert float(g["team_override_pct"]) == 15.0
        # reset
        admin.put(f"{API}/pm/commission-settings", json={"team_override_pct": 10.0}, timeout=15)
        g2 = admin.get(f"{API}/pm/commission-settings", timeout=15).json()
        assert float(g2["team_override_pct"]) == 10.0


# ---------------------------------------------------------------------------
# Team-lead toggle + GET /pm/teams
# ---------------------------------------------------------------------------
class TestTeamLeadToggle:
    def test_promote_lead_and_list(self, admin, mongo):
        r = admin.put(f"{API}/pm/vas/{LEAD_USER_ID}/team-lead",
                      json={"is_team_lead": True}, timeout=15)
        assert r.status_code == 200
        assert r.json()["is_team_lead"] is True

        teams = admin.get(f"{API}/pm/teams", timeout=15)
        assert teams.status_code == 200
        j = teams.json()
        assert "teams" in j
        lead_row = next((t for t in j["teams"] if t["user_id"] == LEAD_USER_ID), None)
        assert lead_row is not None, "promoted lead not in teams list"
        assert lead_row["member_count"] == 0
        assert "assignable_vas" in j
        # Member should be in assignable_vas (has no team + not a lead)
        assignable_ids = [a["user_id"] for a in j["assignable_vas"]]
        assert MEMBER_USER_ID in assignable_ids

    def test_toggle_member_can_now_be_lead(self, admin, mongo):
        # Dual role allowed since 2-level teams (iter76): a member may also lead.
        mongo.users.update_one({"user_id": MEMBER_USER_ID}, {"$set": {"team_lead_id": LEAD_USER_ID}})
        r = admin.put(f"{API}/pm/vas/{MEMBER_USER_ID}/team-lead",
                      json={"is_team_lead": True}, timeout=15)
        assert r.status_code == 200
        # Cleanup — reset both flags
        admin.put(f"{API}/pm/vas/{MEMBER_USER_ID}/team-lead", json={"is_team_lead": False}, timeout=15)
        mongo.users.update_one({"user_id": MEMBER_USER_ID}, {"$set": {"team_lead_id": None}})


# ---------------------------------------------------------------------------
# Team assignment
# ---------------------------------------------------------------------------
class TestTeamAssignment:
    def test_assign_member_to_lead(self, admin, mongo):
        # ensure lead promoted (previous test does it; make idempotent)
        admin.put(f"{API}/pm/vas/{LEAD_USER_ID}/team-lead", json={"is_team_lead": True}, timeout=15)
        r = admin.put(f"{API}/pm/vas/{MEMBER_USER_ID}/team",
                      json={"team_lead_id": LEAD_USER_ID}, timeout=15)
        assert r.status_code == 200
        m = mongo.users.find_one({"user_id": MEMBER_USER_ID})
        assert m.get("team_lead_id") == LEAD_USER_ID

    def test_assign_lead_as_member_400(self, admin):
        # LEAD_USER_ID is a lead — try to make it a member of itself/another lead
        # Try assigning LEAD to itself → non-lead target check: LEAD is a lead so error
        r = admin.put(f"{API}/pm/vas/{LEAD_USER_ID}/team",
                      json={"team_lead_id": LEAD_USER_ID}, timeout=15)
        assert r.status_code == 400

    def test_assign_to_non_lead_400(self, admin, mongo):
        # Assigning a VA to a target that is NOT a team lead must 400.
        mongo.users.update_one({"user_id": MEMBER_USER_ID}, {"$set": {"is_team_lead": False}})
        third = mongo.users.find_one(
            {"role": "va", "va_status": "approved", "is_team_lead": {"$ne": True},
             "user_id": {"$nin": [LEAD_USER_ID, MEMBER_USER_ID]}},
            {"user_id": 1},
        )
        if not third:
            pytest.skip("No third approved VA available")
        r = admin.put(f"{API}/pm/vas/{third['user_id']}/team",
                      json={"team_lead_id": MEMBER_USER_ID}, timeout=15)
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Override math: seed lead directly then run booked → paid via admin API
# ---------------------------------------------------------------------------
def _seed_lead(mongo, va_user_id: str, va_name: str = "Test Member VA") -> str:
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


class TestOverrideMath:
    def test_split_10_to_9_plus_1(self, admin, mongo):
        # Ensure setup: lead flagged is_team_lead=True, member has team_lead_id=LEAD
        mongo.users.update_one({"user_id": LEAD_USER_ID},
                               {"$set": {"is_team_lead": True, "va_status": "approved"}})
        mongo.users.update_one({"user_id": MEMBER_USER_ID},
                               {"$set": {"team_lead_id": LEAD_USER_ID}})

        lid = _seed_lead(mongo, MEMBER_USER_ID)

        # Move to booked
        r1 = admin.put(f"{API}/pm/leads/{lid}/stage", json={"stage": "booked"}, timeout=15)
        assert r1.status_code == 200, r1.text
        # Move to paid
        r2 = admin.put(f"{API}/pm/leads/{lid}/stage", json={"stage": "paid"}, timeout=15)
        assert r2.status_code == 200, r2.text

        # Assert exactly 1 member commission + 1 override commission
        member_cs = list(mongo.commissions.find({"lead_id": lid, "kind": {"$ne": "team_override"}}))
        override_cs = list(mongo.commissions.find({"lead_id": lid, "kind": "team_override"}))
        assert len(member_cs) == 1, f"expected 1 member commission, got {len(member_cs)}: {member_cs}"
        assert len(override_cs) == 1, f"expected 1 override commission, got {len(override_cs)}"

        m = member_cs[0]
        o = override_cs[0]
        # Member: $9, override_amount $1, team_lead_id set, status pending_approval, kind != team_override
        assert abs(float(m["amount"]) - 9.0) < 0.001, f"member amount {m['amount']}"
        assert abs(float(m.get("override_amount") or 0) - 1.0) < 0.001
        assert m.get("team_lead_id") == LEAD_USER_ID
        assert m.get("status") == "pending_approval"
        assert m.get("kind") != "team_override"
        assert m.get("va_user_id") == MEMBER_USER_ID

        # Override: $1, va_user_id = lead, source = member, status pending_approval
        assert abs(float(o["amount"]) - 1.0) < 0.001
        assert o.get("va_user_id") == LEAD_USER_ID
        assert o.get("source_va_user_id") == MEMBER_USER_ID
        assert o.get("status") == "pending_approval"

    def test_lost_rejects_both(self, admin, mongo):
        # Reuse from previous test — find the last seeded lead in paid state
        # Move it to 'lost'
        lid = TEST_LEAD_IDS[-1]
        r = admin.put(f"{API}/pm/leads/{lid}/stage", json={"stage": "lost"}, timeout=15)
        assert r.status_code == 200, r.text
        m = mongo.commissions.find_one({"lead_id": lid, "kind": {"$ne": "team_override"}})
        o = mongo.commissions.find_one({"lead_id": lid, "kind": "team_override"})
        assert m and m.get("status") == "rejected", f"member not rejected: {m}"
        assert o and o.get("status") == "rejected", f"override not rejected: {o}"


# ---------------------------------------------------------------------------
# /va/team endpoint
# ---------------------------------------------------------------------------
class TestVATeamEndpoint:
    def test_lead_gets_team_payload(self, admin, mongo):
        # Ensure LEAD is is_team_lead=True and member assigned (from previous tests)
        mongo.users.update_one({"user_id": LEAD_USER_ID},
                               {"$set": {"is_team_lead": True}})
        mongo.users.update_one({"user_id": MEMBER_USER_ID},
                               {"$set": {"team_lead_id": LEAD_USER_ID}})
        # Login as team lead VA
        va_sess = _login(*VA_LEAD)
        r = va_sess.get(f"{API}/va/team", timeout=15)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        j = r.json()
        assert "members" in j and "member_count" in j
        assert "override_pct" in j
        assert "override_earnings" in j and "total" in j["override_earnings"]
        assert j["member_count"] >= 1
        member_ids = [m["user_id"] for m in j["members"]]
        assert MEMBER_USER_ID in member_ids
        m = next(m for m in j["members"] if m["user_id"] == MEMBER_USER_ID)
        assert "lead_count" in m and "booked_count" in m and "override_earned" in m

    def test_non_lead_gets_403(self, mongo):
        # Ensure MEMBER is not a team lead
        mongo.users.update_one({"user_id": MEMBER_USER_ID}, {"$set": {"is_team_lead": False}})
        # Look up member's email to log in
        member = mongo.users.find_one({"user_id": MEMBER_USER_ID}, {"email": 1})
        if not member or not member.get("email"):
            pytest.skip("Cannot resolve member email for login")
        # We don't know password; instead test with va.demo temporarily un-flagged.
        # Alternative: temp toggle va.demo off, re-login, expect 403, restore.
        mongo.users.update_one({"user_id": LEAD_USER_ID}, {"$set": {"is_team_lead": False}})
        try:
            s = _login(*VA_LEAD)
            r = s.get(f"{API}/va/team", timeout=15)
            assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"
        finally:
            mongo.users.update_one({"user_id": LEAD_USER_ID}, {"$set": {"is_team_lead": True}})


# ---------------------------------------------------------------------------
# Solo VA regression: no override, full amount, only ONE commission
# ---------------------------------------------------------------------------
class TestSoloVANoOverride:
    def test_solo_va_full_amount_no_override(self, admin, mongo):
        # Find any approved VA with no team_lead_id
        solo = mongo.users.find_one(
            {"role": "va", "va_status": "approved",
             "user_id": {"$nin": [LEAD_USER_ID, MEMBER_USER_ID]},
             "team_lead_id": {"$in": [None, ""]}},
            {"user_id": 1, "name": 1},
        )
        if not solo:
            pytest.skip("No solo approved VA available")
        # Make sure this VA is not accidentally a member from prior tests
        mongo.users.update_one({"user_id": solo["user_id"]},
                               {"$set": {"team_lead_id": None, "is_team_lead": False}})
        lid = _seed_lead(mongo, solo["user_id"], solo.get("name") or "Solo VA")
        r1 = admin.put(f"{API}/pm/leads/{lid}/stage", json={"stage": "booked"}, timeout=15)
        assert r1.status_code == 200, r1.text
        r2 = admin.put(f"{API}/pm/leads/{lid}/stage", json={"stage": "paid"}, timeout=15)
        assert r2.status_code == 200, r2.text

        member_cs = list(mongo.commissions.find({"lead_id": lid, "kind": {"$ne": "team_override"}}))
        override_cs = list(mongo.commissions.find({"lead_id": lid, "kind": "team_override"}))
        assert len(member_cs) == 1
        assert len(override_cs) == 0, f"solo should have NO override, got: {override_cs}"
        assert abs(float(member_cs[0]["amount"]) - 10.0) < 0.001, f"expected $10, got {member_cs[0]['amount']}"


# ---------------------------------------------------------------------------
# Regression: /va/earnings still lists team_override rows for lead
# ---------------------------------------------------------------------------
class TestEarningsRegression:
    def test_earnings_includes_team_override(self, mongo):
        # LEAD is the recipient of an override from earlier tests
        mongo.users.update_one({"user_id": LEAD_USER_ID}, {"$set": {"is_team_lead": True}})
        s = _login(*VA_LEAD)
        r = s.get(f"{API}/va/earnings", timeout=15)
        assert r.status_code == 200
        items = r.json().get("items", [])
        # Should have at least one team_override row from earlier test (even if rejected)
        override_rows = [i for i in items if i.get("kind") == "team_override"]
        assert len(override_rows) >= 1, "expected team_override rows in VA earnings"
