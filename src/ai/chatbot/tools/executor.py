"""Dispatches all chatbot tool calls to their handler functions."""
from typing import Any, Dict

from src.ai.chatbot.tools.info import (
    get_my_action_items as _action_items,
    get_group_activity_stats as _group_stats,
    get_unread_count as _unread_count,
    extract_meetings as _meetings,
)
from src.ai.chatbot.tools.compose import (
    draft_reply as _draft_reply,
    translate_message as _translate,
    set_my_status as _set_status,
    schedule_reminder as _schedule_reminder,
    get_reminders as _get_reminders,
)
from src.ai.chatbot.tools.search import (
    search_messages_by_time as _search_by_time,
    list_shared_documents as _list_docs,
    catchup_for_group as _catchup,
    summarize_document as _summarize_document,
)
from src.ai.chatbot.tools.messaging import (
    fetch_unread_images as _fetch_images,
    send_message as _send_message,
    get_group_members_status as _group_members,
)
from src.ai.chatbot.tools.multilingual import (
    suggest_replies_in_language as _suggest_replies,
    decode_voice_message as _decode_voice,
    compose_message_in_language as _compose,
    explain_message_context as _explain,
    cross_language_catchup as _cross_catchup,
    multilingual_group_summary as _ml_summary,
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
            return await _fetch_images(session)
        if tool_name == "send_message":
            return await _send_message(args, session)
        if tool_name == "get_group_members_status":
            return await _group_members(args)
        if tool_name == "get_my_action_items":
            return await _action_items(args, session)
        if tool_name == "get_group_activity_stats":
            return await _group_stats(args)
        if tool_name == "set_my_status":
            return await _set_status(args, session)
        if tool_name == "get_unread_count":
            return await _unread_count(session)
        if tool_name == "draft_reply":
            return await _draft_reply(args)
        if tool_name == "search_messages_by_time":
            return await _search_by_time(args, session)
        if tool_name == "list_shared_documents":
            return await _list_docs(args)
        if tool_name == "summarize_document":
            return await _summarize_document(args)
        if tool_name == "translate_message":
            return await _translate(args)
        if tool_name == "schedule_reminder":
            return await _schedule_reminder(args, session)
        if tool_name == "get_reminders":
            return await _get_reminders(session)
        if tool_name == "extract_meetings":
            return await _meetings(args)
        if tool_name == "catchup_for_group":
            return await _catchup(args, session)
        if tool_name == "suggest_replies_in_language":
            return await _suggest_replies(args, session)
        if tool_name == "decode_voice_message":
            return await _decode_voice(args, session)
        if tool_name == "compose_message_in_language":
            return await _compose(args, session)
        if tool_name == "explain_message_context":
            return await _explain(args, session)
        if tool_name == "cross_language_catchup":
            return await _cross_catchup(args, session)
        if tool_name == "multilingual_group_summary":
            return await _ml_summary(args, session)
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
