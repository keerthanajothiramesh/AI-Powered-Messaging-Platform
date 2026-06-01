"""Core group and DM summarisation with token-aware chunking."""
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from src.ai.gemini_client import generate_text
from src.ai.rag.chunking import chunk_by_tokens, count_tokens, _MAX_MESSAGES
from src.ai.rag.formatting import build_user_map, format_messages
from src.ai.rag.parallel import hierarchical_merge, summarise_chunks_parallel
from src.ai.rag.prompts import DM_SUMMARY_PROMPT, SUMMARY_PROMPT
from src.common.logger import get_logger

logger = get_logger(__name__)


async def _get_fewshot_prefix(group_id: str) -> str:
    try:
        from src.agents.feedback_store import get_top_summaries
        examples = await get_top_summaries(group_id=group_id, limit=2)
        if not examples:
            return ""
        lines = ["Here are examples of high-quality summaries to guide your style:\n"]
        for ex in examples:
            lines.append(f"Example summary (score {ex['average_score']:.1f}/10):\n{ex['summary']}\n")
        lines.append("---\nNow produce a summary of similar quality for the conversation below.\n\n")
        return "\n".join(lines)
    except Exception:
        return ""


async def summarise_with_stats(
    group_id: str, days: int = 14, group_name: str = "this group"
) -> Dict:
    """Full group summarisation — returns summary + token stats."""
    from src.common.database import get_mongo_db
    db = get_mongo_db()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    cursor = db.messages.find(
        {"group_id": group_id, "timestamp": {"$gte": since}, "deleted": {"$ne": True}}
    ).sort("timestamp", 1)
    messages = await cursor.to_list(length=_MAX_MESSAGES)

    if not messages:
        return {
            "summary": f"No messages found in {group_name} in the last {days} days.",
            "token_stats": {"message_count": 0, "approx_tokens": 0,
                            "chunks_used": 0, "strategy": "none", "capped": False},
        }

    capped = len(messages) == _MAX_MESSAGES
    if capped:
        logger.warning("summarise_cap_hit", group_id=group_id, cap=_MAX_MESSAGES)

    user_map = await build_user_map(messages)
    formatted_all = format_messages(messages, user_map)
    approx_tokens = count_tokens(formatted_all)
    chunks = chunk_by_tokens(messages)
    fewshot_prefix = await _get_fewshot_prefix(group_id)

    logger.info("summarise_with_stats", group_id=group_id,
                messages=len(messages), tokens=approx_tokens, chunks=len(chunks))

    if len(chunks) == 1:
        prompt = f"{fewshot_prefix}Summarise this group chat '{group_name}':\n\n{formatted_all}"
        summary = await generate_text(prompt, system_prompt=SUMMARY_PROMPT, max_tokens=1024)
        strategy = "single-pass"
    else:
        chunk_summaries = await summarise_chunks_parallel(
            chunks,
            prompt_fn=lambda t: f"{fewshot_prefix}Summarise this portion of '{group_name}':\n\n{t}",
            system_prompt=SUMMARY_PROMPT,
            user_map=user_map,
        )
        summary = await hierarchical_merge(chunk_summaries, SUMMARY_PROMPT, label=group_name)
        strategy = "hierarchical"

    return {
        "summary": summary,
        "token_stats": {
            "message_count": len(messages), "approx_tokens": approx_tokens,
            "chunks_used": len(chunks), "strategy": strategy, "capped": capped,
        },
    }


async def summarise_conversation(
    group_id: str, days: int = 14, group_name: str = "this group"
) -> str:
    """Backward-compatible wrapper — returns just the summary string."""
    result = await summarise_with_stats(group_id, days=days, group_name=group_name)
    return result["summary"]


async def extract_action_items(summary: str) -> List[str]:
    """Extract concrete action items from a conversation summary."""
    prompt = (
        "Extract all concrete action items from this conversation summary. "
        "Return ONLY a raw JSON array of short strings (max 10). "
        "If none found, return []. No markdown.\n\nSummary:\n" + summary
    )
    try:
        raw = await generate_text(prompt, temperature=0.2, max_tokens=300)
        raw = re.sub(r"```[a-z]*\n?", "", raw).strip()
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            items = json.loads(match.group())
            return [str(s).strip() for s in items if str(s).strip()][:10]
    except Exception:
        pass
    return []


async def summarise_dm(
    user_id: str, other_user_id: str,
    days: int = 14, other_user_name: str = "the other person",
) -> str:
    """Summarise a direct message conversation."""
    from src.common.database import get_mongo_db
    db = get_mongo_db()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    cursor = db.messages.find({
        "$or": [
            {"sender_id": user_id, "receiver_id": other_user_id, "group_id": None},
            {"sender_id": other_user_id, "receiver_id": user_id, "group_id": None},
        ],
        "timestamp": {"$gte": since},
        "deleted": {"$ne": True},
    }).sort("timestamp", 1)
    messages = await cursor.to_list(length=_MAX_MESSAGES)

    if not messages:
        return f"No direct messages found with {other_user_name} in the last {days} days."
    if len(messages) == _MAX_MESSAGES:
        logger.warning("summarise_dm_cap_hit", cap=_MAX_MESSAGES)

    user_map = await build_user_map(messages)
    chunks = chunk_by_tokens(messages)
    logger.info("summarise_dm", user_id=user_id, message_count=len(messages))

    if len(chunks) == 1:
        text = format_messages(messages, user_map)
        prompt = f"Summarise this DM conversation with {other_user_name} (output in English only):\n\n{text}"
        return await generate_text(prompt, system_prompt=DM_SUMMARY_PROMPT, max_tokens=1024)

    chunk_summaries = await summarise_chunks_parallel(
        chunks,
        prompt_fn=lambda t: f"Summarise DM with {other_user_name} (English only):\n\n{t}",
        system_prompt=DM_SUMMARY_PROMPT,
        user_map=user_map,
    )
    return await hierarchical_merge(chunk_summaries, DM_SUMMARY_PROMPT, label=f"DM with {other_user_name}")
