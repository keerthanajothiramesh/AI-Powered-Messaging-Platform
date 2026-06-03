"""Generates structured catch-up summaries for users returning from offline across DMs and groups."""
import asyncio
from datetime import datetime
from typing import Dict

from src.ai.gemini_client import generate_text
from src.ai.rag.chunking import chunk_by_tokens
from src.ai.rag.formatting import build_user_map, format_messages
from src.ai.rag.parallel import hierarchical_merge, summarise_chunks_parallel
from src.ai.rag.prompts import CATCHUP_PROMPT
from src.common.logger import get_logger

logger = get_logger(__name__)


async def catch_up_summary(user_id: str, offline_since: datetime) -> Dict:
    """Build a structured catch-up summary for a user returning from offline."""
    from src.common.database import get_mongo_db, get_pg_pool
    db = get_mongo_db()
    pool = get_pg_pool()

    direct_cursor = db.messages.find({
        "receiver_id": user_id,
        "timestamp": {"$gte": offline_since},
        "group_id": None,
        "deleted": {"$ne": True},
    }).sort("timestamp", 1)
    direct_messages = await direct_cursor.to_list(length=500)

    async with pool.acquire() as conn:
        group_rows = await conn.fetch(
            "SELECT group_id, group_name FROM groups g "
            "JOIN group_members gm USING (group_id) WHERE gm.user_id=$1",
            user_id,
        )

    group_summaries: Dict = {}
    total_missed = len(direct_messages)

    async def _summarise_group(row) -> tuple:
        gid = str(row["group_id"])
        cursor = db.messages.find({
            "group_id": gid,
            "timestamp": {"$gte": offline_since},
            "sender_id": {"$ne": user_id},
            "deleted": {"$ne": True},
        }).sort("timestamp", 1)
        msgs = await cursor.to_list(length=200)
        if not msgs:
            return row["group_name"], None, None, 0

        umap = await build_user_map(msgs)
        chunks = chunk_by_tokens(msgs)

        if len(chunks) == 1:
            text = format_messages(msgs, umap)
            summary = await generate_text(
                f"Summarise missed messages in '{row['group_name']}':\n\n{text}",
                system_prompt=CATCHUP_PROMPT, max_tokens=256,
            )
        else:
            chunk_sums = await summarise_chunks_parallel(
                chunks,
                prompt_fn=lambda t: f"Summarise missed messages in '{row['group_name']}':\n\n{t}",
                system_prompt=CATCHUP_PROMPT, max_tokens=256, user_map=umap,
            )
            summary = await hierarchical_merge(chunk_sums, CATCHUP_PROMPT, label=row["group_name"])

        return row["group_name"], str(row["group_id"]), summary, len(msgs)

    group_results = await asyncio.gather(
        *[_summarise_group(r) for r in group_rows],
        return_exceptions=True,
    )

    for item in group_results:
        if isinstance(item, Exception):
            logger.warning("group_catchup_failed", error=str(item))
            continue
        name, gid, summary, count = item
        if summary:
            group_summaries[name] = {"count": count, "summary": summary, "group_id": gid}
            total_missed += count

    dm_summary = None
    if direct_messages:
        try:
            umap = await build_user_map(direct_messages)
            chunks = chunk_by_tokens(direct_messages)
            if len(chunks) == 1:
                text = format_messages(direct_messages, umap)
                dm_summary = await generate_text(
                    f"Summarise these direct messages the user missed:\n\n{text}",
                    system_prompt=CATCHUP_PROMPT, max_tokens=256,
                )
            else:
                chunk_sums = await summarise_chunks_parallel(
                    chunks,
                    prompt_fn=lambda t: f"Summarise these direct messages the user missed:\n\n{t}",
                    system_prompt=CATCHUP_PROMPT, max_tokens=256, user_map=umap,
                )
                dm_summary = await hierarchical_merge(chunk_sums, CATCHUP_PROMPT, label="direct messages")
        except Exception as exc:
            logger.warning("dm_catchup_failed", error=str(exc))

    return {
        "total_missed": total_missed,
        "offline_since": offline_since.isoformat(),
        "direct_messages": {"count": len(direct_messages), "summary": dm_summary},
        "group_summaries": group_summaries,
    }
