"""Seed a worker + approved gig acceptance for iter24 UI tests. Writes /tmp/iter24_seed.json."""
import asyncio, json, os, uuid
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    now = datetime.now(timezone.utc)
    uid = f"user_{uuid.uuid4().hex[:12]}"
    email = f"iter24_worker_{uid[-6:]}@example.com"
    await db.users.insert_one({
        "user_id": uid,
        "email": email,
        "name": f"Iter24 Worker {uid[-6:]}",
        "role": "worker",
        "worker_status": "approved",
        "id_verified": True,
        "auth_provider": "local",
        "password_hash": "$2b$12$dummy",
        "created_at": now.isoformat(),
    })
    token = uuid.uuid4().hex
    await db.sessions.insert_one({
        "session_token": token,
        "user_id": uid,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(days=7)).isoformat(),
    })

    # Create a gig + approve worker on it (use existing admin user to be assigner)
    gig_id = f"gig_{uuid.uuid4().hex[:12]}"
    sched = (now + timedelta(hours=48)).isoformat()
    await db.gigs.insert_one({
        "gig_id": gig_id,
        "title": f"ITER24 group chat gig {gig_id[-6:]}",
        "description": "iter24 test",
        "category": "cleaning",
        "subcategory": "deep",
        "location": "Test St",
        "scheduled_date": "Fri",
        "scheduled_at": sched,
        "pay_rate": 30.0,
        "pay_type": "hourly",
        "slots": 2,
        "slots_filled": 1,
        "status": "open",
        "created_at": now.isoformat(),
        "created_by": "admin",
    })
    acc_id = f"acc_{uuid.uuid4().hex[:12]}"
    await db.gig_acceptances.insert_one({
        "acceptance_id": acc_id,
        "gig_id": gig_id,
        "worker_id": uid,
        "status": "accepted",
        "is_backup": False,
        "requested_at": now.isoformat(),
        "accepted_at": now.isoformat(),
        "approved_by": "admin",
    })

    # Also seed a VA user with session
    va_uid = f"user_{uuid.uuid4().hex[:12]}"
    await db.users.insert_one({
        "user_id": va_uid,
        "email": f"iter24_va_{va_uid[-6:]}@example.com",
        "name": f"Iter24 VA {va_uid[-6:]}",
        "role": "va",
        "va_status": "approved",
        "auth_provider": "local",
        "password_hash": "$2b$12$dummy",
        "created_at": now.isoformat(),
    })
    va_token = uuid.uuid4().hex
    await db.sessions.insert_one({
        "session_token": va_token,
        "user_id": va_uid,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(days=7)).isoformat(),
    })

    out = {
        "worker_id": uid,
        "worker_email": email,
        "worker_token": token,
        "gig_id": gig_id,
        "acceptance_id": acc_id,
        "va_id": va_uid,
        "va_token": va_token,
    }
    with open("/tmp/iter24_seed.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))
    client.close()


asyncio.run(main())
