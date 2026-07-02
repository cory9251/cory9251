"""Iter51 — Bookkeeping (ledger + recurring) backend tests."""
import os
import io
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@hcobcleaners.com", "password": "HcobAdmin2026!"}
VA = {"email": "va.demo@hcobcleaners.com", "password": "VaDemo2026!"}


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def va_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=VA, timeout=20)
    assert r.status_code == 200, f"va login failed: {r.status_code} {r.text}"
    return s


# ---- meta + list ---------------------------------------------------------
def test_meta_endpoint(admin_session):
    r = admin_session.get(f"{API}/admin/ledger/meta", timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert "expense_categories" in d and "supplies" in d["expense_categories"]
    assert "income_categories" in d and "assignment_income" in d["income_categories"]
    assert "projects" in d and "gigs" in d


def test_list_ledger(admin_session):
    r = admin_session.get(f"{API}/admin/ledger", timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert "items" in d and "totals" in d
    assert all(k in d["totals"] for k in ("income", "expenses", "net"))


# ---- create + get + edit + delete ---------------------------------------
def test_create_expense_and_income(admin_session):
    payload = {
        "type": "expense", "amount": 42.5, "category": "supplies",
        "date": "2026-01-10", "description": f"TEST iter51 exp {uuid.uuid4().hex[:6]}",
        "vendor": "TEST_VendorA",
    }
    r = admin_session.post(f"{API}/admin/ledger", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    e1 = r.json()
    assert e1["type"] == "expense" and e1["amount"] == 42.5
    assert e1["category"] == "supplies"
    assert e1["entry_id"].startswith("led_")

    inc = {
        "type": "income", "amount": 500.0, "category": "project_income",
        "date": "2026-01-11", "description": f"TEST iter51 inc {uuid.uuid4().hex[:6]}",
    }
    r2 = admin_session.post(f"{API}/admin/ledger", json=inc, timeout=20)
    assert r2.status_code == 200, r2.text
    e2 = r2.json()
    assert e2["type"] == "income" and e2["amount"] == 500.0

    # verify persisted via list + search
    r3 = admin_session.get(f"{API}/admin/ledger", params={"q": "TEST iter51"}, timeout=20)
    assert r3.status_code == 200
    ids = [x["entry_id"] for x in r3.json()["items"]]
    assert e1["entry_id"] in ids and e2["entry_id"] in ids

    # edit expense amount
    upd = admin_session.put(f"{API}/admin/ledger/{e1['entry_id']}", json={"amount": 99.99}, timeout=20)
    assert upd.status_code == 200
    assert upd.json()["amount"] == 99.99

    # delete both
    d1 = admin_session.delete(f"{API}/admin/ledger/{e1['entry_id']}", timeout=20)
    d2 = admin_session.delete(f"{API}/admin/ledger/{e2['entry_id']}", timeout=20)
    assert d1.status_code == 200 and d2.status_code == 200

    # verify deletion — should not appear anymore
    r4 = admin_session.put(f"{API}/admin/ledger/{e1['entry_id']}", json={"amount": 1}, timeout=20)
    assert r4.status_code == 404


# ---- validation ----------------------------------------------------------
def test_invalid_category_for_income(admin_session):
    r = admin_session.post(f"{API}/admin/ledger", json={
        "type": "income", "amount": 10, "category": "software",
        "date": "2026-01-10", "description": "TEST invalid cat",
    }, timeout=20)
    assert r.status_code == 400


def test_invalid_date(admin_session):
    r = admin_session.post(f"{API}/admin/ledger", json={
        "type": "expense", "amount": 10, "category": "supplies",
        "date": "2026-13-99", "description": "TEST bad date",
    }, timeout=20)
    assert r.status_code == 400


def test_amount_zero_rejected(admin_session):
    r = admin_session.post(f"{API}/admin/ledger", json={
        "type": "expense", "amount": 0, "category": "supplies",
        "date": "2026-01-10", "description": "TEST zero amount",
    }, timeout=20)
    assert r.status_code == 422


# ---- authorization -------------------------------------------------------
def test_va_forbidden_on_admin_ledger(va_session):
    r = va_session.get(f"{API}/admin/ledger", timeout=20)
    assert r.status_code == 403


# ---- summary + export ----------------------------------------------------
def test_summary_shape(admin_session):
    r = admin_session.get(f"{API}/admin/ledger/summary", timeout=20)
    assert r.status_code == 200
    d = r.json()
    for k in ("totals", "entry_count", "expenses_by_category",
              "income_by_category", "by_month", "by_project"):
        assert k in d


def test_csv_export(admin_session):
    r = admin_session.get(f"{API}/admin/ledger/export", timeout=20)
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    body = r.text
    assert "Date,Type,Category,Amount" in body
    assert "Income total" in body and "Expenses total" in body and "Net" in body


def test_csv_export_with_filter(admin_session):
    r = admin_session.get(f"{API}/admin/ledger/export", params={"q": "TEST"}, timeout=20)
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")


# ---- receipt upload ------------------------------------------------------
def test_receipt_upload_and_download(admin_session):
    # create entry
    payload = {
        "type": "expense", "amount": 7.5, "category": "supplies",
        "date": "2026-01-12", "description": f"TEST iter51 receipt {uuid.uuid4().hex[:6]}",
    }
    r = admin_session.post(f"{API}/admin/ledger", json=payload, timeout=20)
    assert r.status_code == 200
    eid = r.json()["entry_id"]

    # 1x1 png
    png = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
           b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\x00\x01"
           b"\x00\x00\x05\x00\x01\r\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
    files = {"file": ("t.png", io.BytesIO(png), "image/png")}
    up = admin_session.post(f"{API}/admin/ledger/{eid}/receipt", files=files, timeout=30)
    assert up.status_code == 200, up.text
    path = up.json()["receipt_path"]
    assert path

    # download via /api/files/{path}
    dl = admin_session.get(f"{API}/files/{path}", timeout=30)
    assert dl.status_code == 200, f"receipt download failed: {dl.status_code}"

    # cleanup
    admin_session.delete(f"{API}/admin/ledger/{eid}", timeout=20)


# ---- recurring expenses --------------------------------------------------
def test_recurring_create_generates_entry_and_toggle_delete(admin_session):
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).day
    dom = min(today, 28)
    period = datetime.now(timezone.utc).strftime("%Y-%m")

    payload = {
        "amount": 33.33, "category": "software",
        "description": f"TEST iter51 recurring {uuid.uuid4().hex[:6]}",
        "day_of_month": dom,
    }
    r = admin_session.post(f"{API}/admin/recurring-expenses", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    rec = r.json()
    rid = rec["recurring_id"]
    assert rec["active"] is True

    # since day_of_month <= today, auto-generated ledger entry should exist for this period
    r2 = admin_session.get(f"{API}/admin/ledger",
                           params={"q": payload["description"]}, timeout=20)
    assert r2.status_code == 200
    items = r2.json()["items"]
    matches = [it for it in items if it.get("recurring_id") == rid]
    assert len(matches) >= 1, f"expected auto-logged entry for recurring, got {items}"
    auto = matches[0]
    assert auto["created_by_name"] == "Recurring (auto)"
    assert auto["date"].startswith(period)

    # toggle pause
    upd = admin_session.put(f"{API}/admin/recurring-expenses/{rid}",
                            json={"active": False}, timeout=20)
    assert upd.status_code == 200 and upd.json()["active"] is False

    # delete recurring
    dl = admin_session.delete(f"{API}/admin/recurring-expenses/{rid}", timeout=20)
    assert dl.status_code == 200

    # cleanup auto entry
    admin_session.delete(f"{API}/admin/ledger/{auto['entry_id']}", timeout=20)


# ---- regression smoke ----------------------------------------------------
def test_regression_ops_dashboard(admin_session):
    r = admin_session.get(f"{API}/auth/me", timeout=20)
    assert r.status_code == 200
    assert r.json().get("role") == "admin"
