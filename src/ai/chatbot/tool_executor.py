"""Executes chatbot tool calls, mapping tool names to backend services."""
from typing import Any, Dict

from src.common.logger import get_logger

logger = get_logger(__name__)


async def execute_tool(tool_name: str, args: Dict, session) -> Any:
    """Dispatch a tool call and return the result. Never raises — errors return dict."""
    try:
        if tool_name == "summarise_current_conversation":
            return await _summarise_conversation(args, session)
        if tool_name == "search_messages":
            return await _search_messages(args)
        if tool_name == "get_conversation_summary":
            return await _get_conversation_summary(args)
        if tool_name == "find_media":
            return await _find_media(args)
        if tool_name == "get_user_activity":
            return await _get_user_activity(args)
        if tool_name == "fetch_unread_images":
            return await _fetch_unread_images(session)
    except Exception as exc:
        logger.error("tool_execution_failed", tool=tool_name, error=str(exc))
        return {"error": str(exc)}
    return {"error": f"Unknown tool: {tool_name}"}


async def _summarise_conversation(args: Dict, session) -> Any:
    days = int(args.get("days", 14))
    if session.is_group and session.conv_id:
        from src.ai.rag_service import summarise_conversation
        summary = await summarise_conversation(session.conv_id, days=days, group_name=session.conv_name)
        return {"type": "group", "name": session.conv_name, "summary": summary, "days": days}
    if not session.is_group and session.other_user_id:
        from src.ai.rag_service import summarise_dm
        summary = await summarise_dm(
            session.user_id, session.other_user_id, days=days, other_user_name=session.conv_name
        )
        return {"type": "dm", "name": session.conv_name, "summary": summary, "days": days}
    return {"error": "No conversation context available."}


async def _search_messages(args: Dict) -> Any:
    from src.search.search_service import hybrid_search
    filters = {}
    if args.get("media_type"):
        filters["media_type"] = args["media_type"]
    results = await hybrid_search(args["query"], n_results=8, filters=filters)
    return [
        {
            "content": r["content"],
            "source": r.get("source_type", "message"),
            "filename": r.get("metadata", {}).get("filename", ""),
            "metadata": r.get("metadata", {}),
        }
        for r in results
    ]


async def _get_conversation_summary(args: Dict) -> Any:
    from src.common.database import get_pg_pool
    from src.ai.rag_service import summarise_conversation
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT group_id, group_name FROM groups WHERE group_name ILIKE $1",
            f"%{args['group_name']}%",
        )
    if not row:
        return {"error": f"Group '{args['group_name']}' not found"}
    days = int(args.get("days", "14"))
    summary = await summarise_conversation(str(row["group_id"]), days=days, group_name=row["group_name"])
    return {"group": row["group_name"], "summary": summary, "days": days}


async def _find_media(args: Dict) -> Any:
    from src.ai.vector_store import get_vector_store
    vs = get_vector_store()
    if not vs:
        return []
    keywords = args.get("keywords", args.get("media_type", ""))
    return vs.search_media(keywords, n_results=10, media_type=args.get("media_type"))


async def _get_user_activity(args: Dict) -> Any:
    from src.common.database import get_pg_pool
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT user_id, display_name, user_presence, last_seen "
            "FROM users WHERE display_name ILIKE $1",
            f"%{args['user_name']}%",
        )
    if not user:
        return {"error": f"User '{args['user_name']}' not found"}
    return {
        "user": user["display_name"],
        "presence": user["user_presence"],
        "last_seen": user["last_seen"].isoformat() if user["last_seen"] else None,
    }


async def _fetch_unread_images(session) -> Any:
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
