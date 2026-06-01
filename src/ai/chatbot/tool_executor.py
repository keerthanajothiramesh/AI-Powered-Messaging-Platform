"""Executes chatbot tool calls, mapping tool names to backend services."""
from typing import Any, Dict

from src.ai.chatbot.tool_executor_extras import (
    fetch_unread_images as _fetch_unread_images_impl,
    send_message as _send_message_impl,
    get_group_members_status as _get_group_members_status_impl,
)
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
            return await _fetch_unread_images_impl(session)
        if tool_name == "send_message":
            return await _send_message_impl(args, session)
        if tool_name == "get_group_members_status":
            return await _get_group_members_status_impl(args)
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


