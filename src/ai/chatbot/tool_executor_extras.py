"""Extra chatbot tool handlers: unread images, send message, group member status."""
from typing import Any, Dict

from src.common.logger import get_logger

logger = get_logger(__name__)


async def fetch_unread_images(session) -> Any:
    from src.common.database import get_mongo_db, get_pg_pool
    db = get_mongo_db()
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT g.group_id, g.group_name FROM groups g "
            "JOIN group_members gm ON g.group_id = gm.group_id WHERE gm.user_id = $1",
            session.user_id,
        )
    group_map = {str(r["group_id"]): r["group_name"] for r in rows}
    group_ids = list(group_map.keys())

    cursor = db.messages.find(
        {
            "media_type": "image",
            "$or": [
                {"receiver_id": session.user_id, "read_status": "unread"},
                {"group_id": {"$in": group_ids}, "sender_id": {"$ne": session.user_id},
                 "read_by": {"$not": {"$elemMatch": {"$eq": session.user_id}}}},
            ],
        },
        {"message_id": 1, "media_url": 1, "content": 1, "sender_id": 1,
         "group_id": 1, "receiver_id": 1, "timestamp": 1},
    ).limit(20).sort("timestamp", -1)

    results = []
    async for msg in cursor:
        gid = str(msg.get("group_id") or "")
        ts = msg.get("timestamp")
        results.append({
            "message_id": str(msg.get("message_id") or str(msg["_id"])),
            "media_url": msg.get("media_url") or "",
            "content": msg.get("content") or "",
            "sender_id": str(msg.get("sender_id") or ""),
            "group_id": gid,
            "receiver_id": str(msg.get("receiver_id") or ""),
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts or ""),
            "group_name": group_map.get(gid, ""),
        })
    return results


async def send_message(args: Dict, session) -> Any:
    from src.common.database import get_pg_pool
    from src.messaging.message_service import save_message
    from src.messaging.websocket_manager import get_connection_manager

    pool = get_pg_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT user_id, display_name FROM users WHERE display_name ILIKE $1",
            f"%{args['recipient_name']}%",
        )
    if not user:
        return {"error": f"User '{args['recipient_name']}' not found"}

    recipient_id = str(user["user_id"])
    content = args["message"]
    manager = get_connection_manager()
    status = "delivered" if manager.is_online(recipient_id) else "sent"
    msg = await save_message(
        sender_id=str(session.user_id), content=content,
        receiver_id=recipient_id, delivery_status=status,
    )
    event = {"type": "message", "data": {k: str(v) if hasattr(v, "hex") else v
                                          for k, v in msg.items() if k != "_id"}}
    await manager.send_to_user(recipient_id, event)
    await manager.send_to_user(str(session.user_id), event)
    logger.info("chatbot_sent_message", to=user["display_name"], sender=session.user_id)
    return {"sent": True, "recipient": user["display_name"], "message": content}


async def get_group_members_status(args: Dict) -> Any:
    from src.common.database import get_pg_pool
    from src.messaging.websocket_manager import get_connection_manager

    pool = get_pg_pool()
    async with pool.acquire() as conn:
        group = await conn.fetchrow(
            "SELECT group_id, group_name FROM groups WHERE group_name ILIKE $1",
            f"%{args['group_name']}%",
        )
        if not group:
            return {"error": f"Group '{args['group_name']}' not found"}
        members = await conn.fetch(
            "SELECT u.user_id, u.display_name, u.user_presence, u.last_seen "
            "FROM users u JOIN group_members gm ON u.user_id = gm.user_id "
            "WHERE gm.group_id = $1 ORDER BY u.display_name",
            group["group_id"],
        )

    manager = get_connection_manager()
    result = [
        {
            "name": m["display_name"],
            "status": "online" if manager.is_online(str(m["user_id"])) else "offline",
            "last_seen": m["last_seen"].isoformat() if m["last_seen"] else None,
        }
        for m in members
    ]
    online_count = sum(1 for r in result if r["status"] == "online")
    return {
        "group": group["group_name"],
        "total_members": len(result),
        "online_count": online_count,
        "members": result,
    }
