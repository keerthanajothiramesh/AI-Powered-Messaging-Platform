"""Load messages and events from JSON into MongoDB Atlas."""
import asyncio
import json
from pathlib import Path
from datetime import datetime
import motor.motor_asyncio
from dotenv import load_dotenv
import os

load_dotenv()
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
        print("ERROR: MONGODB_URL not set in .env")
        return

    url = _encode_mongo_url(url)
    client = motor.motor_asyncio.AsyncIOMotorClient(url)
    db = client["messaging"]
    print("Connected to MongoDB")

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
        except Exception as e:
            if "duplicate" in str(e).lower():
                print(f"  Some duplicates skipped in {f.name}")
            else:
                print(f"  Error in {f.name}: {e}")

    print(f"Messages loaded: {total:,}")

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
            print(f"Events loaded: {len(result.inserted_ids):,}")
        except Exception as e:
            print(f"Events warning: {e}")

    await db.messages.create_index([("sender_id", 1), ("timestamp", -1)])
    await db.messages.create_index([("receiver_id", 1), ("timestamp", -1)])
    await db.messages.create_index([("group_id", 1), ("timestamp", -1)])
    print("Indexes created")

    client.close()
    print("MongoDB loading complete!")


if __name__ == "__main__":
    asyncio.run(load_data())
