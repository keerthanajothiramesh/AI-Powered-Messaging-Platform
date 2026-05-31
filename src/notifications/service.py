import uuid
from typing import List, Dict, Any
from datetime import datetime, timezone
from src.common.logger import get_logger

logger = get_logger(__name__)


async def create_notification(
    user_id: str,
    notification_type: str,
    title: str,
    body: str,
    data: Dict = None,
) -> Dict[str, Any]:
    from src.common.database import get_mongo_db
    db = get_mongo_db()
    notif = {
        "notification_id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": notification_type,
        "title": title,
        "body": body,
        "data": data or {},
        "is_read": False,
        "created_at": datetime.now(timezone.utc),
    }
    await db.notifications.insert_one(notif)

    from src.messaging.websocket_manager import get_connection_manager
    manager = get_connection_manager()
    notif_copy = {k: v for k, v in notif.items() if k != "_id"}
    if hasattr(notif_copy.get("created_at"), "isoformat"):
        notif_copy["created_at"] = notif_copy["created_at"].isoformat()
    await manager.send_to_user(user_id, {"type": "notification", "data": notif_copy})

    logger.info("notification_created", user_id=user_id, type=notification_type)
    return notif_copy


async def get_user_notifications(user_id: str, limit: int = 50) -> List[Dict]:
    from src.common.database import get_mongo_db
    db = get_mongo_db()
    cursor = db.notifications.find({"user_id": user_id}).sort("created_at", -1).limit(limit)
    notifs = await cursor.to_list(length=limit)
    for n in notifs:
        n.pop("_id", None)
        if hasattr(n.get("created_at"), "isoformat"):
            n["created_at"] = n["created_at"].isoformat()
    return notifs


async def mark_notifications_read(user_id: str) -> int:
    from src.common.database import get_mongo_db
    db = get_mongo_db()
    result = await db.notifications.update_many(
        {"user_id": user_id, "is_read": False},
        {"$set": {"is_read": True}},
    )
    return result.modified_count
