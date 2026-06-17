"""One-time migration (Iter 47): downgrade workers whose worker_status='approved'
but who have unresolved approval_blockers (missing ID or incomplete profile)
back to 'pending', so the admin queue reflects reality and the booking gate
matches the badge.

Idempotent: re-runs are safe — workers who get re-approved by an admin AFTER
finishing setup won't be touched, because they'll no longer have blockers.

Run with:
    cd /app/backend && python -m scripts.migrate_downgrade_incomplete_approvals
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Add the parent dir so we can import auth_deps helpers when running as a module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth_deps import _worker_approval_blockers  # noqa: E402


async def migrate(dry_run: bool = False):
    load_dotenv()
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    cursor = db.users.find(
        {"role": "worker", "worker_status": "approved"},
    )

    examined = 0
    downgraded = 0
    skipped_fully_active = 0
    examples_downgraded = []

    now_iso = datetime.now(timezone.utc).isoformat()
    actor = "system:migration:iter47-truthful-approval"

    async for w in cursor:
        examined += 1
        blockers = _worker_approval_blockers(w)
        if not blockers:
            skipped_fully_active += 1
            continue
        if dry_run:
            if len(examples_downgraded) < 5:
                examples_downgraded.append(
                    {
                        "email": w.get("email"),
                        "name": w.get("name"),
                        "blockers": blockers,
                    }
                )
            downgraded += 1
            continue
        await db.users.update_one(
            {"_id": w["_id"]},
            {
                "$set": {
                    "worker_status": "pending",
                    "worker_status_at": now_iso,
                    "worker_status_by": actor,
                    "auto_downgraded_at": now_iso,
                    "auto_downgrade_blockers": blockers,
                }
            },
        )
        downgraded += 1
        if len(examples_downgraded) < 5:
            examples_downgraded.append(
                {
                    "email": w.get("email"),
                    "name": w.get("name"),
                    "blockers": blockers,
                }
            )

    print(f"Examined approved workers: {examined}")
    print(f"  Already fully active (untouched): {skipped_fully_active}")
    print(f"  Downgraded to pending: {downgraded}")
    if examples_downgraded:
        print("\nFirst few examples:")
        for ex in examples_downgraded:
            print(
                f"  - {ex.get('name') or '?':<25} {ex.get('email') or '?':<40} "
                f"blockers={ex['blockers']}"
            )
    client.close()
    return downgraded


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what WOULD be downgraded, but don't write to the DB.",
    )
    args = parser.parse_args()
    n = asyncio.run(migrate(dry_run=args.dry_run))
    if args.dry_run:
        print(f"\nDRY RUN — {n} workers would be downgraded.")
    else:
        print(f"\nDone — downgraded {n} workers.")
