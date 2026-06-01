"""Link a real user account to the synthetic dataset.

1. Adds the user to all synthetic groups (group summaries + catch-up work)
2. Remaps 100 synthetic DM messages to receiver_id = real user UUID

Usage:
    python dataset/link_user.py --email your@email.com
"""
import asyncio
import argparse
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, quote_plus, urlunparse

import asyncpg
import motor.motor_asyncio
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from src.common.logger import configure_logging, get_logger
configure_logging("INFO")
logger = get_logger(__name__)


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
    pg_url = os.getenv("NEON_DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
    if not pg_url:
        logger.error("missing_env", var="NEON_DATABASE_URL")
        return

    pool = await asyncpg.create_pool(pg_url, min_size=2, max_size=5)

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT user_id, display_name FROM users WHERE email = $1", email
        )

    if not user:
        logger.error("user_not_found", email=email)
        logger.info("hint", msg="Register this account in the app first, then re-run this script.")
        await pool.close()
        return

    real_user_id = user["user_id"]
    real_user_id_str = str(real_user_id)
    logger.info("user_found", display_name=user["display_name"], user_id=real_user_id_str)

    async with pool.acquire() as conn:
        groups = await conn.fetch("SELECT group_id, group_name FROM groups")

    logger.info("adding_to_groups", total=len(groups))
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
            except Exception as exc:
                logger.warning("group_add_failed", group=g["group_name"], error=str(exc))
    logger.info("groups_added", added=added, total=len(groups))

    mongo_url = os.getenv("MONGODB_URL", "")
    if not mongo_url:
        logger.error("missing_env", var="MONGODB_URL", note="skipping DM remap")
        await pool.close()
        return

    mongo_client = motor.motor_asyncio.AsyncIOMotorClient(_encode_mongo_url(mongo_url))
    db = mongo_client["messaging"]

    since = datetime.now(timezone.utc) - timedelta(days=90)
    cursor = db.messages.find(
        {"group_id": None, "receiver_id": {"$exists": True, "$ne": real_user_id_str},
         "timestamp": {"$gte": since}},
        {"message_id": 1},
    ).limit(200)
    dm_messages = await cursor.to_list(length=200)

    if not dm_messages:
        logger.warning("no_dm_messages_found")
    else:
        sample = random.sample(dm_messages, min(100, len(dm_messages)))
        ids = [m["message_id"] for m in sample]
        result = await db.messages.update_many(
            {"message_id": {"$in": ids}},
            {"$set": {"receiver_id": real_user_id_str}},
        )
        logger.info("dms_remapped", count=result.modified_count)

    await pool.close()
    mongo_client.close()
    logger.info("link_user_complete", email=email,
                groups_joined=len(groups), dms_remapped=min(100, len(dm_messages)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Link a real user to the synthetic dataset")
    parser.add_argument("--email", required=True, help="Your registered email address")
    args = parser.parse_args()
    asyncio.run(link_user(args.email))
