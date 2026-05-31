from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from src.common.logger import get_logger
from src.ai.gemini_client import generate_text

logger = get_logger(__name__)

CHUNK_SIZE = 50
SUMMARY_PROMPT = """You are an AI assistant summarising a chat conversation.
Provide a concise, structured summary covering:
- Main topics discussed
- Key decisions or outcomes
- Action items (if any)
- Important dates or deadlines mentioned

Be factual. Use bullet points. Keep it under 300 words."""

CATCHUP_PROMPT = """You are an AI assistant helping a user catch up on missed messages.
Summarise what they missed in each conversation concisely.
Format: "In [conversation name]: [key points]"
Be brief and highlight only the most important information."""


async def summarise_conversation(
    group_id: str, days: int = 14, group_name: str = "this group"
) -> str:
    from src.common.database import get_mongo_db
    db = get_mongo_db()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    cursor = db.messages.find(
        {"group_id": group_id, "timestamp": {"$gte": since}}
    ).sort("timestamp", 1)
    messages = await cursor.to_list(length=2000)

    if not messages:
        return f"No messages found in {group_name} in the last {days} days."

    logger.info("summarise_conversation", group_id=group_id, message_count=len(messages))

    chunks = _chunk_messages(messages, CHUNK_SIZE)
    chunk_summaries = []

    for i, chunk in enumerate(chunks):
        text = _format_messages(chunk)
        prompt = f"Summarise this portion of a group chat:\n\n{text}"
        summary = await generate_text(prompt, system_prompt=SUMMARY_PROMPT, max_tokens=512)
        chunk_summaries.append(summary)

    if len(chunk_summaries) == 1:
        return chunk_summaries[0]

    merge_prompt = f"Merge these {len(chunk_summaries)} partial summaries into one coherent summary:\n\n"
    merge_prompt += "\n\n---\n\n".join(chunk_summaries)
    final = await generate_text(merge_prompt, system_prompt=SUMMARY_PROMPT, max_tokens=1024)
    return final


async def catch_up_summary(user_id: str, offline_since: datetime) -> Dict[str, Any]:
    from src.common.database import get_mongo_db, get_pg_pool
    db = get_mongo_db()
    pool = get_pg_pool()

    direct_cursor = db.messages.find(
        {"receiver_id": user_id, "timestamp": {"$gte": offline_since}, "group_id": None}
    ).sort("timestamp", 1)
    direct_messages = await direct_cursor.to_list(length=500)

    async with pool.acquire() as conn:
        group_rows = await conn.fetch(
            "SELECT group_id, group_name FROM groups g "
            "JOIN group_members gm USING (group_id) WHERE gm.user_id=$1",
            user_id,
        )

    group_summaries = {}
    total_missed = len(direct_messages)

    for row in group_rows:
        gid = str(row["group_id"])
        cursor = db.messages.find(
            {"group_id": gid, "timestamp": {"$gte": offline_since}, "sender_id": {"$ne": user_id}}
        ).sort("timestamp", 1)
        msgs = await cursor.to_list(length=200)
        total_missed += len(msgs)
        if msgs:
            text = _format_messages(msgs[:30])
            prompt = f"Summarise missed messages in '{row['group_name']}':\n\n{text}"
            summary = await generate_text(prompt, system_prompt=CATCHUP_PROMPT, max_tokens=256)
            group_summaries[row["group_name"]] = {"count": len(msgs), "summary": summary}

    dm_summary = None
    if direct_messages:
        text = _format_messages(direct_messages[:20])
        prompt = f"Summarise these direct messages the user missed:\n\n{text}"
        dm_summary = await generate_text(prompt, system_prompt=CATCHUP_PROMPT, max_tokens=256)

    return {
        "total_missed": total_missed,
        "offline_since": offline_since.isoformat(),
        "direct_messages": {"count": len(direct_messages), "summary": dm_summary},
        "group_summaries": group_summaries,
    }


DM_SUMMARY_PROMPT = """You are an AI assistant summarising a direct message conversation.
Provide a concise, structured summary ALWAYS IN ENGLISH (regardless of the original message language):
- Main topics discussed
- Key decisions or outcomes
- Action items (if any)
- Important dates or deadlines mentioned

Be factual. Use bullet points. Keep it under 300 words. Output in English only."""


async def summarise_dm(
    user_id: str, other_user_id: str, days: int = 14, other_user_name: str = "the other person"
) -> str:
    from src.common.database import get_mongo_db
    db = get_mongo_db()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    cursor = db.messages.find({
        "$or": [
            {"sender_id": user_id, "receiver_id": other_user_id, "group_id": None},
            {"sender_id": other_user_id, "receiver_id": user_id, "group_id": None},
        ],
        "timestamp": {"$gte": since},
    }).sort("timestamp", 1)
    messages = await cursor.to_list(length=2000)

    if not messages:
        return f"No direct messages found with {other_user_name} in the last {days} days."

    logger.info("summarise_dm", user_id=user_id, other_user_id=other_user_id, message_count=len(messages))

    chunks = _chunk_messages(messages, CHUNK_SIZE)
    chunk_summaries = []
    for chunk in chunks:
        text = _format_messages(chunk)
        prompt = f"Summarise this DM conversation (output in English only):\n\n{text}"
        summary = await generate_text(prompt, system_prompt=DM_SUMMARY_PROMPT, max_tokens=512)
        chunk_summaries.append(summary)

    if len(chunk_summaries) == 1:
        return chunk_summaries[0]

    merge_prompt = (
        f"Merge these {len(chunk_summaries)} partial DM summaries into one coherent English summary:\n\n"
        + "\n\n---\n\n".join(chunk_summaries)
    )
    return await generate_text(merge_prompt, system_prompt=DM_SUMMARY_PROMPT, max_tokens=1024)


async def search_with_ai(query: str, user_id: str, filters: Optional[Dict] = None) -> Dict:
    from src.search.search_service import hybrid_search
    results = await hybrid_search(query, n_results=10, filters=filters or {})

    if not results:
        return {"answer": "No relevant messages found.", "sources": []}

    context = "\n".join([f"- {r['content']}" for r in results[:5]])
    prompt = f"""User query: "{query}"

Relevant messages found:
{context}

Answer the user's query based on these messages. Be specific and cite which message answers their question."""

    answer = await generate_text(prompt, max_tokens=512)
    return {"answer": answer, "sources": results[:5]}


def _chunk_messages(messages: List[Dict], size: int) -> List[List[Dict]]:
    return [messages[i: i + size] for i in range(0, len(messages), size)]


def _format_messages(messages: List[Dict]) -> str:
    lines = []
    for m in messages:
        ts = m.get("timestamp", "")
        if hasattr(ts, "strftime"):
            ts = ts.strftime("%Y-%m-%d %H:%M")
        sender = m.get("sender_id", "unknown")[:8]
        content = m.get("content", "")
        lines.append(f"[{ts}] {sender}: {content}")
    return "\n".join(lines)
