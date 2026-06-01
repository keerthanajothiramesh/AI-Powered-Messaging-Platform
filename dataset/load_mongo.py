"""Load messages and events from JSON into MongoDB Atlas."""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import motor.motor_asyncio
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from src.common.logger import configure_logging, get_logger
configure_logging("INFO")
logger = get_logger(__name__)

DATA_DIR = Path(__file__).parent


def _encode_mongo_url(url: str) -> str:
    from urllib.parse import urlparse, quote_plus, urlunparse
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


async def load_data():
    url = os.getenv("MONGODB_URL", "")
    if not url:
        logger.error("missing_env", var="MONGODB_URL")
        return

    client = motor.motor_asyncio.AsyncIOMotorClient(_encode_mongo_url(url))
    db = client["messaging"]
    logger.info("mongodb_connected")

    msg_files = sorted(DATA_DIR.glob("messages_*.json"))
    total = 0
    for f in msg_files:
        messages = json.loads(f.read_text(encoding="utf-8"))
        if not messages:
            continue
        for m in messages:
            if "timestamp" in m and isinstance(m["timestamp"], str):
                try:
                    m["timestamp"] = datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00"))
                except Exception:
                    pass
        try:
            result = await db.messages.insert_many(messages, ordered=False)
            total += len(result.inserted_ids)
        except Exception as exc:
            if "duplicate" in str(exc).lower():
                logger.warning("duplicates_skipped", file=f.name)
            else:
                logger.error("insert_failed", file=f.name, error=str(exc))

    logger.info("messages_loaded", total=total)

    events_file = DATA_DIR / "events.json"
    if events_file.exists():
        events = json.loads(events_file.read_text(encoding="utf-8"))
        for e in events:
            if "timestamp" in e and isinstance(e["timestamp"], str):
                try:
                    e["timestamp"] = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
                except Exception:
                    pass
        try:
            result = await db.delivery_events.insert_many(events, ordered=False)
            logger.info("events_loaded", count=len(result.inserted_ids))
        except Exception as exc:
            logger.warning("events_warning", error=str(exc))

    await db.messages.create_index([("sender_id", 1), ("timestamp", -1)])
    await db.messages.create_index([("receiver_id", 1), ("timestamp", -1)])
    await db.messages.create_index([("group_id", 1), ("timestamp", -1)])
    logger.info("indexes_created")

    client.close()
    logger.info("mongodb_load_complete")


if __name__ == "__main__":
    asyncio.run(load_data())
