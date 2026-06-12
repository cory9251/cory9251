"""
Iter23 helper: Seeds workers + pending acceptances + grabs session token cookies
for use in the Playwright UI test. Outputs JSON to /tmp/iter23_seed.json.
"""
import os
import json
import uuid
import asyncio
import secrets
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import requests

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://work-connect-147.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

OWNER_EMAIL = "admin@hcobcleaners.com"
OWNER_PASSWORD = "HcobAdmin2026!"


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # 1. Create admin gig
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD})
    assert r.status_code == 200, r.text
    sched_future = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    gig_payload = {
        "title": f"ITER23 UI Gig {uuid.uuid4().hex[:6]}",
        "description": "iter23 UI test",
        "category": "cleaning",
        "subcategory": "deep",
        "location": "Baltimore",
        "scheduled_date": "Fri Jun 17 · 9am",
        "scheduled_at": sched_future,
        "pay_rate": 25.0,
        "pay_type": "hourly",
        "slots": 1,
        "backup_slots": 2,
    }
    r = s.post(f"{API}/gigs", json=gig_payload)
    assert r.status_code == 200, r.text
    gig = r.json()
    gid = gig["gig_id"]
    print(f"[seed] Created gig: {gid}, backup_slots={gig['backup_slots']}")

    # 2. Seed worker A (approved, has pending acceptance on gig)
    worker_a = f"user_{uuid.uuid4().hex[:12]}"
    email_a = f"iter23_a_{uuid.uuid4().hex[:6]}@example.com"
    await db.users.insert_one({
        "user_id": worker_a, "email": email_a, "name": "Iter23 WorkerA",
        "role": "worker", "worker_status": "approved", "phone": "5551234567",
        "address": "100 Main", "zip_code": "21201", "city": "Baltimore", "state": "MD",
        "date_of_birth": "1990-01-01", "tshirt_size": "L",
        "emergency_contact_name": "Mom", "emergency_contact_phone": "5559999999",
        "skills": ["cleaning"], "availability": ["weekdays"],
        "id_image_path": "test.png", "id_verified": True, "has_car": True,
        "experience_level": "intermediate", "auth_provider": "local",
        "password_hash": "$2b$12$dummy",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    acc_a = f"acc_{uuid.uuid4().hex[:12]}"
    await db.gig_acceptances.insert_one({
        "acceptance_id": acc_a, "gig_id": gid, "worker_id": worker_a,
        "status": "requested", "is_backup": False, "backup_order": None,
        "requested_at": datetime.now(timezone.utc).isoformat(),
    })
    print(f"[seed] WorkerA={worker_a} acc_a={acc_a} pending on gig")

    # 3. Seed worker B (approved + accepted as primary already on a different gig — for cancel-shift testing)
    worker_b = f"user_{uuid.uuid4().hex[:12]}"
    email_b = f"iter23_b_{uuid.uuid4().hex[:6]}@example.com"
    await db.users.insert_one({
        "user_id": worker_b, "email": email_b, "name": "Iter23 WorkerB",
        "role": "worker", "worker_status": "approved", "phone": "5551234567",
        "address": "200 Main", "zip_code": "21201", "city": "Baltimore", "state": "MD",
        "date_of_birth": "1990-01-01", "tshirt_size": "M",
        "emergency_contact_name": "Mom", "emergency_contact_phone": "5559999999",
        "skills": ["cleaning"], "availability": ["weekdays"],
        "id_image_path": "test.png", "id_verified": True, "has_car": True,
        "experience_level": "intermediate", "auth_provider": "local",
        "password_hash": "$2b$12$dummy",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Create a second gig where worker B is already accepted (for cancel-shift)
    r2 = s.post(f"{API}/gigs", json={**gig_payload, "title": f"ITER23 Cancel Gig {uuid.uuid4().hex[:6]}", "slots": 2, "backup_slots": 0})
    gig2 = r2.json()
    gid2 = gig2["gig_id"]
    acc_b = f"acc_{uuid.uuid4().hex[:12]}"
    await db.gig_acceptances.insert_one({
        "acceptance_id": acc_b, "gig_id": gid2, "worker_id": worker_b,
        "status": "accepted", "is_backup": False, "backup_order": None,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "accepted_at": datetime.now(timezone.utc).isoformat(),
        "approved_by": "iter23-seed",
    })
    await db.gigs.update_one({"gig_id": gid2}, {"$set": {"slots_filled": 1}})
    print(f"[seed] WorkerB={worker_b} accepted on gig2={gid2}")

    # 4. Issue session tokens for both workers (mirrors test_backups_and_cancel.py pattern)
    token_a = secrets.token_urlsafe(32)
    token_b = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(days=7)).isoformat()
    await db.sessions.insert_many([
        {"session_token": token_a, "user_id": worker_a, "expires_at": expires, "created_at": now.isoformat()},
        {"session_token": token_b, "user_id": worker_b, "expires_at": expires, "created_at": now.isoformat()},
    ])

    out = {
        "gig_id_backup": gid,
        "gig_id_cancel": gid2,
        "acceptance_id_a_pending": acc_a,
        "acceptance_id_b_accepted": acc_b,
        "worker_a_id": worker_a,
        "worker_a_token": token_a,
        "worker_b_id": worker_b,
        "worker_b_token": token_b,
        "base_url": BASE_URL,
    }
    with open("/tmp/iter23_seed.json", "w") as f:
        json.dump(out, f, indent=2)
    print("[seed] wrote /tmp/iter23_seed.json")
    print(json.dumps(out, indent=2))
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
