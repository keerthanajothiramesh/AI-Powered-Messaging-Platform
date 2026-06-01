"""Link a real user account to the synthetic dataset.

Does two things:
1. Adds the user to all 25 synthetic groups in group_members
   (so group catch-up, group summaries, and group messages all work)
2. Remaps 100 synthetic DM messages to have receiver_id = real user's UUID
   (so DM catch-up and direct message summaries work)

Usage:
    python dataset/link_user.py --email your@email.com
"""
import asyncio
import asyncpg
import motor.motor_asyncio
import argparse
import random
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import os
from urllib.parse import urlparse, quote_plus, urlunparse

load_dotenv()


def _encode_mongo_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.username or parsed.password:
        encoded = parsed._replace(
            netloc="{user}:{pw}@{host}".format(
                user=quote_plus(parsed.username or ""),
                pw=quote_plus(parsed.password or ""),
                host=parsed.hostname + (f":{parsed.port}" if parsed.port else ""),
            )
        )
        return urlunparse(encoded)
    return url


async def link_user(email: str):
    # ── PostgreSQL ────────────────────────────────────────────────────────────
    pg_url = os.getenv("NEON_DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
    if not pg_url:
        print("ERROR: NEON_DATABASE_URL not set in .env")
        return

    pool = await asyncpg.create_pool(pg_url, min_size=2, max_size=5)

    # Find the real user by email
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT user_id, display_name FROM users WHERE email = $1", email
        )

    if not user:
        print(f"ERROR: No user found with email '{email}'")
        print("Register this account in the app first, then re-run this script.")
        await pool.close()
        return

    real_user_id = user["user_id"]          # UUID object
    real_user_id_str = str(real_user_id)    # string for MongoDB
    print(f"Found: {user['display_name']} ({real_user_id_str})")

    # ── Step 1: Add to all groups ─────────────────────────────────────────────
    async with pool.acquire() as conn:
        groups = await conn.fetch("SELECT group_id, group_name FROM groups")

    print(f"\nAdding to {len(groups)} groups...")
    added = 0
    async with pool.acquire() as conn:
        for g in groups:
            try:
                await conn.execute(
                    """INSERT INTO group_members (group_id, user_id, role, joined_at)
                       VALUES ($1, $2, 'member', NOW())
                       ON CONFLICT (group_id, user_id) DO NOTHING""",
                    g["group_id"], real_user_id,
                )
                added += 1
            except Exception as e:
                print(f"  Warning ({g['group_name']}): {e}")

    print(f"  Done — added to {added}/{len(groups)} groups ✓")

    # ── Step 2: Remap DM messages in MongoDB ──────────────────────────────────
    mongo_url = os.getenv("MONGODB_URL", "")
    if not mongo_url:
        print("\nERROR: MONGODB_URL not set in .env — skipping DM remap")
        await pool.close()
        return

    mongo_client = motor.motor_asyncio.AsyncIOMotorClient(_encode_mongo_url(mongo_url))
    db = mongo_client["messaging"]

    # Pick DM messages (group_id=null, not already addressed to real user)
    since = datetime.now(timezone.utc) - timedelta(days=90)
    cursor = db.messages.find(
        {
            "group_id": None,
            "receiver_id": {"$exists": True, "$ne": real_user_id_str},
            "timestamp": {"$gte": since},
        },
        {"message_id": 1}
    ).limit(200)

    dm_messages = await cursor.to_list(length=200)

    if not dm_messages:
        print("\nNo DM messages found in dataset to remap.")
    else:
        sample = random.sample(dm_messages, min(100, len(dm_messages)))
        ids = [m["message_id"] for m in sample]

        result = await db.messages.update_many(
            {"message_id": {"$in": ids}},
            {"$set": {"receiver_id": real_user_id_str}}
        )
        print(f"\nRemapped {result.modified_count} DM messages to your inbox ✓")

    await pool.close()
    mongo_client.close()

    print(f"""
Done! Your account is now linked to the synthetic dataset.

Login: {email}
Groups: all {len(groups)} synthetic groups joined
DMs: 100 messages remapped to your inbox

Catch-up summary, group summaries, and AI features will now
work when you log in with your own credentials.
""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Link a real user to the synthetic dataset")
    parser.add_argument("--email", required=True, help="Your registered email address")
    args = parser.parse_args()
    asyncio.run(link_user(args.email))
