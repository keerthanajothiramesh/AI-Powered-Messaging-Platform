"""Core message persistence and retrieval."""
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.common.database import get_mongo_db
from src.common.logger import get_logger

logger = get_logger(__name__)


async def save_message(
    sender_id: str,
    content: str,
    media_type: str = "text",
    media_url: Optional[str] = None,
    receiver_id: Optional[str] = None,
    group_id: Optional[str] = None,
    language: str = "en",
    delivery_status: str = "sent",
) -> Dict:
    db = get_mongo_db()
    message = {
        "message_id": str(uuid.uuid4()),
        "sender_id": sender_id, "receiver_id": receiver_id, "group_id": group_id,
        "content": content, "media_type": media_type, "media_url": media_url,
        "delivery_status": delivery_status, "read_status": "unread",
        "reactions": {}, "read_by": [], "language": language,
        "timestamp": datetime.now(timezone.utc), "conversation_summary": None,
    }
    await db.messages.insert_one(message)
    message.pop("_id", None)
    logger.info("message_saved", message_id=message["message_id"], sender_id=sender_id)
    return message


async def get_direct_messages(
    user_id: str, other_user_id: str, limit: int = 50, skip: int = 0
) -> List[Dict]:
    db = get_mongo_db()
    cursor = db.messages.find(
        {"$or": [
            {"sender_id": user_id, "receiver_id": other_user_id},
            {"sender_id": other_user_id, "receiver_id": user_id},
        ], "group_id": None},
    ).sort("timestamp", -1).skip(skip).limit(limit)
    messages = await cursor.to_list(length=limit)
    for m in messages:
        m.pop("_id", None)
    return list(reversed(messages))


async def get_dm_conversation_list(user_id: str) -> List[Dict]:
    db = get_mongo_db()
    pipeline = [
        {"$match": {"$or": [{"sender_id": user_id}, {"receiver_id": user_id}], "group_id": None}},
        {"$addFields": {"other_user_id": {"$cond": {
            "if": {"$eq": ["$sender_id", user_id]}, "then": "$receiver_id", "else": "$sender_id"
        }}}},
        {"$sort": {"timestamp": -1}},
        {"$group": {"_id": "$other_user_id",
                    "last_message": {"$first": "$content"},
                    "last_timestamp": {"$first": "$timestamp"}}},
        {"$sort": {"last_timestamp": -1}},
        {"$limit": 50},
    ]
    results = await db.messages.aggregate(pipeline).to_list(length=50)
    return [
        {
            "user_id": r["_id"],
            "last_message": r.get("last_message", ""),
            "last_timestamp": r["last_timestamp"].isoformat() if r.get("last_timestamp") else None,
        }
        for r in results if r["_id"]
    ]


async def get_group_messages(group_id: str, limit: int = 50, skip: int = 0) -> List[Dict]:
    db = get_mongo_db()
    cursor = db.messages.find({"group_id": group_id}).sort("timestamp", -1).skip(skip).limit(limit)
    messages = await cursor.to_list(length=limit)
    for m in messages:
        m.pop("_id", None)
    return list(reversed(messages))


async def mark_message_read(message_id: str, user_id: str) -> None:
    db = get_mongo_db()
    await db.messages.update_one(
        {"message_id": message_id},
        {"$set": {"read_status": "read"}, "$addToSet": {"read_by": user_id}},
    )


async def add_reaction(message_id: str, user_id: str, emoji: str) -> None:
    db = get_mongo_db()
    await db.messages.update_one(
        {"message_id": message_id}, {"$addToSet": {f"reactions.{emoji}": user_id}}
    )


async def edit_message(message_id: str, user_id: str, new_content: str) -> Optional[Dict]:
    db = get_mongo_db()
    result = await db.messages.update_one(
        {"message_id": message_id, "sender_id": user_id, "deleted": {"$ne": True}},
        {"$set": {"content": new_content, "edited": True, "edited_at": datetime.now(timezone.utc)}},
    )
    if result.modified_count == 0:
        return None
    msg = await db.messages.find_one({"message_id": message_id})
    if msg:
        msg.pop("_id", None)
    return msg


async def soft_delete_message(message_id: str, user_id: str) -> bool:
    db = get_mongo_db()
    result = await db.messages.update_one(
        {"message_id": message_id, "sender_id": user_id},
        {"$set": {"content": "[Message deleted]", "deleted": True}},
    )
    return result.modified_count > 0


# Re-export queue helpers for backward compat
from src.messaging.message_queue import (  # noqa: F401, E402
    update_delivery_status, get_queued_messages,
    expire_stale_queued_messages, get_messages_since,
)
