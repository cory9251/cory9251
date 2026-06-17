"""
Iteration 41 — Lead Edit / Soft-Delete / Restore / Lead Detail page.

Coverage:
  - PM list with trash/include_trashed filters
  - PM get lead detail (lead, activity, commission shape)
  - PM PATCH edit lead (normalization, va reassign, activity log)
  - PM PATCH edit lead error cases (bad VA, trashed lead)
  - PM DELETE soft delete + idempotency + commission rejection
  - PM POST restore + restore non-trashed -> 400
  - VA list hides trashed
  - VA GET another VA's lead -> 404
  - VA PATCH own new_lead OK
  - VA PATCH after stage moved -> 403
  - VA PATCH with job_value or va_user_id -> 403
  - VA DELETE own new_lead OK
  - VA DELETE after stage moved -> 403
  - VA DELETE with commission existing -> 403
  - stage_changed activity row written on PUT /pm/leads/{id}/stage
"""
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL missing"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@hcobcleaners.com"
ADMIN_PW = "HcobAdmin2026!"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN_EMAIL, ADMIN_PW)


@pytest.fixture(scope="module")
def va_session(admin_session):
    """Seed a fresh approved VA, return (session, user_id, name)."""
    em = f"iter41-va-{uuid.uuid4().hex[:8]}@example.com"
    pw = "VaTest2026!"
    r = admin_session.post(
        f"{API}/pm/vas",
        json={"email": em, "name": "Iter41 VA", "password": pw, "auto_approve": True},
        timeout=20,
    )
    assert r.status_code == 200, f"VA seed failed {r.status_code} {r.text}"
    va_user_id = r.json()["user_id"]
    s = _login(em, pw)
    return s, va_user_id, em


@pytest.fixture(scope="module")
def va2_session(admin_session):
    em = f"iter41-va2-{uuid.uuid4().hex[:8]}@example.com"
    pw = "VaTest2026!"
    r = admin_session.post(
        f"{API}/pm/vas",
        json={"email": em, "name": "Iter41 VA2", "password": pw, "auto_approve": True},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    return _login(em, pw), r.json()["user_id"]


def _new_lead_payload(suffix=""):
    return {
        "prospect_name": f"TEST Prospect {suffix or uuid.uuid4().hex[:6]}",
        "prospect_phone": f"555{uuid.uuid4().int % 10000000:07d}",
        "prospect_email": f"prospect-{uuid.uuid4().hex[:8]}@example.com",
        "prospect_address": f"{uuid.uuid4().hex[:4]} TEST St",
        "service_type": "deep",
        "property_size": "2br",
        "source": "referral",
        "notes": "iter41 seed",
    }


def _seed_lead(va_sess):
    r = va_sess.post(f"{API}/va/leads", json=_new_lead_payload(), timeout=20)
    assert r.status_code == 200, f"seed lead failed {r.status_code} {r.text}"
    return r.json()


# ---------------- PM list + filters ----------------
class TestPMListAndTrashFilters:
    def test_trash_filter_basic(self, admin_session, va_session):
        va_s, _, _ = va_session
        lead = _seed_lead(va_s)
        # default: should be visible (active)
        r = admin_session.get(f"{API}/pm/leads", timeout=20)
        assert r.status_code == 200
        ids = [item["lead_id"] for item in r.json()["items"]]
        assert lead["lead_id"] in ids

        # Soft delete via admin
        d = admin_session.delete(f"{API}/pm/leads/{lead['lead_id']}", json={"reason": "iter41 trash"}, timeout=20)
        assert d.status_code == 200
        assert d.json().get("deleted_at")

        # Default list (active only) must NOT include trashed
        r = admin_session.get(f"{API}/pm/leads", timeout=20)
        ids = [i["lead_id"] for i in r.json()["items"]]
        assert lead["lead_id"] not in ids

        # ?trash=true only trashed
        r = admin_session.get(f"{API}/pm/leads?trash=true", timeout=20)
        assert r.status_code == 200
        ids = [i["lead_id"] for i in r.json()["items"]]
        assert lead["lead_id"] in ids
        for i in r.json()["items"]:
            assert i.get("deleted_at")

        # ?include_trashed=true mixes both
        r = admin_session.get(f"{API}/pm/leads?include_trashed=true", timeout=20)
        ids = [i["lead_id"] for i in r.json()["items"]]
        assert lead["lead_id"] in ids


# ---------------- PM lead detail / edit / activity ----------------
class TestPMEditAndActivity:
    def test_pm_get_detail_shape(self, admin_session, va_session):
        va_s, _, _ = va_session
        lead = _seed_lead(va_s)
        r = admin_session.get(f"{API}/pm/leads/{lead['lead_id']}", timeout=20)
        assert r.status_code == 200
        body = r.json()
        assert "lead" in body and "activity" in body and "commission" in body
        assert body["lead"]["lead_id"] == lead["lead_id"]

    def test_pm_edit_logs_diff_and_normalizes(self, admin_session, va_session):
        va_s, _, _ = va_session
        lead = _seed_lead(va_s)
        r = admin_session.patch(
            f"{API}/pm/leads/{lead['lead_id']}",
            json={"prospect_name": "TEST Renamed", "prospect_phone": "(555) 111-2222", "reason": "typo"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        upd = r.json()
        assert upd["prospect_name"] == "TEST Renamed"
        assert upd["prospect_phone"] == "(555) 111-2222"
        assert upd["prospect_phone_norm"] == "5551112222"

        # Activity should contain an 'edited' row with changes
        r = admin_session.get(f"{API}/pm/leads/{lead['lead_id']}", timeout=20)
        acts = r.json()["activity"]
        edited = [a for a in acts if a["kind"] == "edited"]
        assert edited, "expected an 'edited' activity row"
        assert "changes" in edited[0]["detail"]
        assert "prospect_name" in edited[0]["detail"]["changes"]

    def test_pm_edit_bad_va_user_id_400(self, admin_session, va_session):
        va_s, _, _ = va_session
        lead = _seed_lead(va_s)
        # Pass an existing admin user id (admin user is NOT role='va')
        r = admin_session.get(f"{API}/auth/me", timeout=10)
        admin_uid = r.json()["user_id"]
        r = admin_session.patch(
            f"{API}/pm/leads/{lead['lead_id']}",
            json={"va_user_id": admin_uid},
            timeout=20,
        )
        assert r.status_code == 400, r.text

    def test_pm_reassign_to_valid_va_also_moves_commission(self, admin_session, va_session, va2_session):
        va_s, _, _ = va_session
        _, va2_uid = va2_session
        lead = _seed_lead(va_s)
        # Move stage to booked → ensures commission exists for reassignment test
        rb = admin_session.put(
            f"{API}/pm/leads/{lead['lead_id']}/stage",
            json={"stage": "booked", "job_value": 200},
            timeout=20,
        )
        assert rb.status_code == 200

        r = admin_session.patch(
            f"{API}/pm/leads/{lead['lead_id']}",
            json={"va_user_id": va2_uid},
            timeout=20,
        )
        assert r.status_code == 200
        assert r.json()["va_user_id"] == va2_uid

        det = admin_session.get(f"{API}/pm/leads/{lead['lead_id']}", timeout=20).json()
        if det.get("commission"):
            assert det["commission"]["va_user_id"] == va2_uid

    def test_pm_edit_trashed_lead_400(self, admin_session, va_session):
        va_s, _, _ = va_session
        lead = _seed_lead(va_s)
        admin_session.delete(f"{API}/pm/leads/{lead['lead_id']}", json={"reason": "x"}, timeout=20)
        r = admin_session.patch(
            f"{API}/pm/leads/{lead['lead_id']}",
            json={"prospect_name": "won't stick"},
            timeout=20,
        )
        assert r.status_code == 400

    def test_pm_delete_idempotent_and_rejects_non_paid_commission(self, admin_session, va_session):
        va_s, _, _ = va_session
        lead = _seed_lead(va_s)
        admin_session.put(
            f"{API}/pm/leads/{lead['lead_id']}/stage",
            json={"stage": "booked", "job_value": 250},
            timeout=20,
        )
        d = admin_session.delete(f"{API}/pm/leads/{lead['lead_id']}", json={"reason": "iter41"}, timeout=20)
        assert d.status_code == 200
        # idempotent - second call OK
        d2 = admin_session.delete(f"{API}/pm/leads/{lead['lead_id']}", json={"reason": "twice"}, timeout=20)
        assert d2.status_code == 200
        assert d2.json().get("deleted_at")

        det = admin_session.get(f"{API}/pm/leads/{lead['lead_id']}", timeout=20).json()
        if det.get("commission"):
            assert det["commission"]["status"] == "rejected"

    def test_pm_restore(self, admin_session, va_session):
        va_s, _, _ = va_session
        lead = _seed_lead(va_s)
        admin_session.delete(f"{API}/pm/leads/{lead['lead_id']}", json={"reason": "x"}, timeout=20)
        r = admin_session.post(f"{API}/pm/leads/{lead['lead_id']}/restore", timeout=20)
        assert r.status_code == 200
        assert r.json().get("deleted_at") in (None, "")

        # restore non-trashed -> 400
        r2 = admin_session.post(f"{API}/pm/leads/{lead['lead_id']}/restore", timeout=20)
        assert r2.status_code == 400

        # activity contains 'restored'
        det = admin_session.get(f"{API}/pm/leads/{lead['lead_id']}", timeout=20).json()
        assert any(a["kind"] == "restored" for a in det["activity"])

    def test_stage_change_logged(self, admin_session, va_session):
        va_s, _, _ = va_session
        lead = _seed_lead(va_s)
        admin_session.put(
            f"{API}/pm/leads/{lead['lead_id']}/stage",
            json={"stage": "contacted"},
            timeout=20,
        )
        det = admin_session.get(f"{API}/pm/leads/{lead['lead_id']}", timeout=20).json()
        assert any(a["kind"] == "stage_changed" for a in det["activity"])


# ---------------- VA permission boundaries ----------------
class TestVAPermissions:
    def test_va_list_hides_trashed(self, admin_session, va_session):
        va_s, _, _ = va_session
        lead = _seed_lead(va_s)
        admin_session.delete(f"{API}/pm/leads/{lead['lead_id']}", json={"reason": "x"}, timeout=20)
        r = va_s.get(f"{API}/va/leads", timeout=20)
        assert r.status_code == 200
        ids = [i["lead_id"] for i in r.json()["items"]]
        assert lead["lead_id"] not in ids

    def test_va_cannot_view_others_lead(self, va_session, va2_session):
        va_s, _, _ = va_session
        va2_s, _ = va2_session
        lead = _seed_lead(va_s)
        r = va2_s.get(f"{API}/va/leads/{lead['lead_id']}", timeout=20)
        assert r.status_code == 404

    def test_va_edit_own_new_lead_ok(self, va_session):
        va_s, _, _ = va_session
        lead = _seed_lead(va_s)
        r = va_s.patch(
            f"{API}/va/leads/{lead['lead_id']}",
            json={"prospect_name": "TEST VA Renamed", "reason": "fix"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        assert r.json()["prospect_name"] == "TEST VA Renamed"

    def test_va_edit_after_stage_move_403(self, admin_session, va_session):
        va_s, _, _ = va_session
        lead = _seed_lead(va_s)
        admin_session.put(
            f"{API}/pm/leads/{lead['lead_id']}/stage",
            json={"stage": "contacted"},
            timeout=20,
        )
        r = va_s.patch(
            f"{API}/va/leads/{lead['lead_id']}",
            json={"prospect_name": "blocked"},
            timeout=20,
        )
        assert r.status_code == 403

    def test_va_edit_with_admin_only_fields_403(self, va_session):
        va_s, _, _ = va_session
        lead = _seed_lead(va_s)
        r1 = va_s.patch(f"{API}/va/leads/{lead['lead_id']}", json={"job_value": 500}, timeout=20)
        assert r1.status_code == 403
        r2 = va_s.patch(f"{API}/va/leads/{lead['lead_id']}", json={"va_user_id": "user_other"}, timeout=20)
        assert r2.status_code == 403

    def test_va_delete_own_new_lead_ok(self, va_session):
        va_s, _, _ = va_session
        lead = _seed_lead(va_s)
        r = va_s.delete(f"{API}/va/leads/{lead['lead_id']}", json={"reason": "wrong"}, timeout=20)
        assert r.status_code == 200
        assert r.json().get("deleted_at")

    def test_va_delete_after_stage_move_403(self, admin_session, va_session):
        va_s, _, _ = va_session
        lead = _seed_lead(va_s)
        admin_session.put(
            f"{API}/pm/leads/{lead['lead_id']}/stage",
            json={"stage": "contacted"},
            timeout=20,
        )
        r = va_s.delete(f"{API}/va/leads/{lead['lead_id']}", json={"reason": "nope"}, timeout=20)
        assert r.status_code == 403

    def test_va_delete_with_commission_403(self, admin_session, va_session):
        va_s, _, _ = va_session
        lead = _seed_lead(va_s)
        admin_session.put(
            f"{API}/pm/leads/{lead['lead_id']}/stage",
            json={"stage": "booked", "job_value": 200},
            timeout=20,
        )
        # Even if we hypothetically moved back to 'new_lead', commission exists; first the stage check would block.
        # Move stage back to new_lead via admin to isolate the commission check.
        admin_session.put(
            f"{API}/pm/leads/{lead['lead_id']}/stage",
            json={"stage": "new_lead"},
            timeout=20,
        )
        r = va_s.delete(f"{API}/va/leads/{lead['lead_id']}", json={"reason": "nope"}, timeout=20)
        assert r.status_code == 403
        assert "commission" in r.text.lower()
