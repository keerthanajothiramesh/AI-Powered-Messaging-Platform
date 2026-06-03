"""Offline message queue helpers — track queued delivery status and expire stale messages."""
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from src.common.database import get_mongo_db
from src.common.logger import get_logger

logger = get_logger(__name__)


async def update_delivery_status(message_id: str, status: str) -> None:
    db = get_mongo_db()
    update: dict = {"$set": {"delivery_status": status}}
    if status == "queued":
        update["$set"]["queued_at"] = datetime.now(timezone.utc)
    else:
        update["$unset"] = {"queued_at": ""}
    await db.messages.update_one({"message_id": message_id}, update)


async def get_queued_messages(user_id: str) -> List[Dict]:
    db = get_mongo_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    cursor = db.messages.find(
        {"receiver_id": user_id, "delivery_status": "queued", "queued_at": {"$gte": cutoff}}
    ).sort("timestamp", 1)
    messages = await cursor.to_list(length=500)
    for m in messages:
        m.pop("_id", None)
    return messages


async def expire_stale_queued_messages() -> int:
    """Mark queued messages older than 30 days as expired."""
    db = get_mongo_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    result = await db.messages.update_many(
        {"delivery_status": "queued", "queued_at": {"$lt": cutoff}},
        {"$set": {"delivery_status": "expired"}, "$unset": {"queued_at": ""}},
    )
    if result.modified_count:
        logger.info("queued_messages_expired", count=result.modified_count)
    return result.modified_count


async def get_messages_since(user_id: str, since: datetime) -> List[Dict]:
    db = get_mongo_db()
    cursor = db.messages.find(
        {"receiver_id": user_id, "timestamp": {"$gte": since}}
    ).sort("timestamp", 1)
    messages = await cursor.to_list(length=1000)
    for m in messages:
        m.pop("_id", None)
    return messages
