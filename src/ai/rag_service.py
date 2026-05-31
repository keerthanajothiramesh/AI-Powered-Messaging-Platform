"""
RAG-based conversation summarisation with token-aware chunking.

Strategy for large histories:
  1. Fetch messages (up to _MAX_MESSAGES cap, logged when hit)
  2. Resolve sender UUIDs → display names (single PG query per call)
  3. Split into token-budget chunks with overlap for context continuity
  4. Summarise all chunks in parallel batches (up to _PARALLEL_BATCH concurrent calls)
  5. Hierarchically merge summaries until a single final summary remains

Token counting uses tiktoken (cl100k_base) with a character-length fallback
(len // 4) if tiktoken is unavailable.
"""

import asyncio
import uuid as _uuid_mod
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional

from src.ai.gemini_client import generate_text
from src.common.logger import get_logger

logger = get_logger(__name__)

# ── Tunable constants ─────────────────────────────────────────────────────────
_CHUNK_TOKEN_LIMIT    = 3_000   # max tokens of raw messages per chunk
_MERGE_TOKEN_LIMIT    = 6_000   # max tokens of summaries passed to one merge call
_PARALLEL_BATCH       = 5       # concurrent Gemini calls (rate-limit headroom)
_MAX_MESSAGES         = 5_000   # safety cap per summarisation request
_CHUNK_OVERLAP        = 3       # messages carried from previous chunk for context continuity

# ── Prompts ───────────────────────────────────────────────────────────────────
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

DM_SUMMARY_PROMPT = """You are an AI assistant summarising a direct message conversation.
Provide a concise, structured summary ALWAYS IN ENGLISH (regardless of the original message language):
- Main topics discussed
- Key decisions or outcomes
- Action items (if any)
- Important dates or deadlines mentioned

Be factual. Use bullet points. Keep it under 300 words. Output in English only."""


# ── Sender name resolution ────────────────────────────────────────────────────

async def _build_user_map(messages: List[Dict]) -> Dict[str, str]:
    """
    Single PostgreSQL query that maps sender_id → display_name for all
    senders present in `messages`. Returns empty dict on failure so
    formatting always has a fallback.
    """
    raw_ids = {str(m.get("sender_id", "")) for m in messages if m.get("sender_id")}
    if not raw_ids:
        return {}

    uuid_list = []
    for sid in raw_ids:
        try:
            uuid_list.append(_uuid_mod.UUID(sid))
        except (ValueError, AttributeError):
            pass

    if not uuid_list:
        return {}

    try:
        from src.common.database import get_pg_pool
        pool = get_pg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT user_id, display_name FROM users WHERE user_id = ANY($1::uuid[])",
                uuid_list,
            )
        return {str(r["user_id"]): r["display_name"] for r in rows}
    except Exception as exc:
        logger.warning("user_map_lookup_failed", error=str(exc))
        return {}


# ── Token utilities ───────────────────────────────────────────────────────────

def _count_tokens(text: str) -> int:
    """Approximate token count. Uses tiktoken when available, else len//4."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)


def _chunk_by_tokens(
    messages: List[Dict], limit: int = _CHUNK_TOKEN_LIMIT
) -> List[List[Dict]]:
    """
    Split messages into token-budget chunks with overlap.

    Each chunk stays within `limit` tokens. The last _CHUNK_OVERLAP messages
    of chunk N are repeated at the start of chunk N+1 so the LLM has context
    continuity at boundaries (e.g. a thought split across two chunks).
    We always advance by at least one new message to guarantee termination.
    """
    if not messages:
        return []

    # Pre-compute per-message token cost once (avoids repeated tiktoken calls)
    msg_tokens = [_count_tokens(_format_messages([m])) for m in messages]

    chunks: List[List[Dict]] = []
    i = 0

    while i < len(messages):
        current: List[Dict] = []
        current_tokens = 0
        chunk_start = i

        while i < len(messages):
            # Always add at least one message even if it exceeds the limit
            if current and current_tokens + msg_tokens[i] > limit:
                break
            current.append(messages[i])
            current_tokens += msg_tokens[i]
            i += 1

        if current:
            chunks.append(current)

        # Step back by _CHUNK_OVERLAP so next chunk starts with context from this one,
        # but never go back past chunk_start + 1 (guarantee forward progress).
        if i < len(messages):
            i = max(chunk_start + 1, i - _CHUNK_OVERLAP)

    return chunks


# ── Parallel chunk summarisation ──────────────────────────────────────────────

async def _summarise_chunks_parallel(
    chunks: List[List[Dict]],
    prompt_fn: Callable[[str], str],
    system_prompt: str,
    max_tokens: int = 512,
    user_map: Optional[Dict[str, str]] = None,
) -> List[str]:
    """
    Summarise all chunks, running up to _PARALLEL_BATCH at a time.
    Returns summaries in the same order as chunks.
    user_map is used so summaries reference real names, not UUIDs.
    """
    _user_map = user_map or {}

    async def _one(chunk: List[Dict]) -> str:
        text = _format_messages(chunk, _user_map)
        return await generate_text(
            prompt_fn(text), system_prompt=system_prompt, max_tokens=max_tokens
        )

    results: List[str] = []
    total_batches = (len(chunks) + _PARALLEL_BATCH - 1) // _PARALLEL_BATCH

    for i in range(0, len(chunks), _PARALLEL_BATCH):
        batch = chunks[i : i + _PARALLEL_BATCH]
        batch_results = await asyncio.gather(*[_one(c) for c in batch])
        results.extend(batch_results)
        logger.info(
            "summarise_batch_done",
            batch=i // _PARALLEL_BATCH + 1,
            total_batches=total_batches,
        )

    return results


# ── Hierarchical merge ────────────────────────────────────────────────────────

async def _hierarchical_merge(
    summaries: List[str],
    system_prompt: str,
    label: str = "conversation",
) -> str:
    """
    Recursively merge summaries until a single string remains.

    - All summaries fit within _MERGE_TOKEN_LIMIT → one merge call.
    - Otherwise → group into sub-batches, merge each in parallel, recurse.
    """
    if len(summaries) == 1:
        return summaries[0]

    combined = "\n\n---\n\n".join(summaries)

    if _count_tokens(combined) <= _MERGE_TOKEN_LIMIT:
        prompt = (
            f"Merge these {len(summaries)} partial summaries of '{label}' "
            f"into one coherent final summary:\n\n{combined}"
        )
        return await generate_text(prompt, system_prompt=system_prompt, max_tokens=1024)

    # Too large for a single merge — group summaries into sub-batches
    groups: List[List[str]] = []
    current_group: List[str] = []
    current_tokens = 0

    for s in summaries:
        tokens = _count_tokens(s)
        if current_group and current_tokens + tokens > _MERGE_TOKEN_LIMIT:
            groups.append(current_group)
            current_group = [s]
            current_tokens = tokens
        else:
            current_group.append(s)
            current_tokens += tokens

    if current_group:
        groups.append(current_group)

    logger.info("hierarchical_merge", label=label, groups=len(groups))

    async def _merge_group(group: List[str]) -> str:
        text = "\n\n---\n\n".join(group)
        prompt = (
            f"Merge these partial summaries of '{label}' into one coherent summary:\n\n{text}"
        )
        return await generate_text(prompt, system_prompt=system_prompt, max_tokens=1024)

    merged = await asyncio.gather(*[_merge_group(g) for g in groups])
    return await _hierarchical_merge(list(merged), system_prompt, label)


# ── Core summarisation (single DB query, returns stats) ───────────────────────

async def summarise_with_stats(
    group_id: str, days: int = 14, group_name: str = "this group"
) -> Dict:
    """
    Full group summarisation in one DB round-trip.
    Returns {"summary": str, "token_stats": {...}} so callers get both
    the text and the metadata without a second query.
    """
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
            "token_stats": {
                "message_count": 0, "approx_tokens": 0,
                "chunks_used": 0, "strategy": "none", "capped": False,
            },
        }

    capped = len(messages) == _MAX_MESSAGES
    if capped:
        logger.warning("summarise_cap_hit", group_id=group_id, cap=_MAX_MESSAGES)

    # Resolve sender UUIDs → display names (one PG query)
    user_map = await _build_user_map(messages)

    formatted_all = _format_messages(messages, user_map)
    approx_tokens = _count_tokens(formatted_all)
    chunks = _chunk_by_tokens(messages)

    logger.info(
        "summarise_with_stats",
        group_id=group_id,
        messages=len(messages),
        tokens=approx_tokens,
        chunks=len(chunks),
    )

    if len(chunks) == 1:
        prompt = f"Summarise this group chat '{group_name}':\n\n{formatted_all}"
        summary = await generate_text(prompt, system_prompt=SUMMARY_PROMPT, max_tokens=1024)
        strategy = "single-pass"
    else:
        chunk_summaries = await _summarise_chunks_parallel(
            chunks,
            prompt_fn=lambda text: (
                f"Summarise this portion of the '{group_name}' group chat:\n\n{text}"
            ),
            system_prompt=SUMMARY_PROMPT,
            user_map=user_map,
        )
        summary = await _hierarchical_merge(chunk_summaries, SUMMARY_PROMPT, label=group_name)
        strategy = "hierarchical"

    return {
        "summary": summary,
        "token_stats": {
            "message_count": len(messages),
            "approx_tokens": approx_tokens,
            "chunks_used": len(chunks),
            "strategy": strategy,
            "capped": capped,
        },
    }


# ── Public summarisation functions ────────────────────────────────────────────

async def summarise_conversation(
    group_id: str, days: int = 14, group_name: str = "this group"
) -> str:
    """Backward-compatible wrapper — returns just the summary string."""
    result = await summarise_with_stats(group_id, days=days, group_name=group_name)
    return result["summary"]


async def summarise_dm(
    user_id: str,
    other_user_id: str,
    days: int = 14,
    other_user_name: str = "the other person",
) -> str:
    from src.common.database import get_mongo_db
    db = get_mongo_db()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    cursor = db.messages.find({
        "$or": [
            {"sender_id": user_id,       "receiver_id": other_user_id, "group_id": None},
            {"sender_id": other_user_id, "receiver_id": user_id,       "group_id": None},
        ],
        "timestamp": {"$gte": since},
        "deleted":   {"$ne": True},
    }).sort("timestamp", 1)
    messages = await cursor.to_list(length=_MAX_MESSAGES)

    if not messages:
        return f"No direct messages found with {other_user_name} in the last {days} days."

    if len(messages) == _MAX_MESSAGES:
        logger.warning("summarise_dm_cap_hit", cap=_MAX_MESSAGES)

    user_map = await _build_user_map(messages)
    formatted_all = _format_messages(messages, user_map)

    logger.info(
        "summarise_dm",
        user_id=user_id,
        other_user_id=other_user_id,
        message_count=len(messages),
        approx_tokens=_count_tokens(formatted_all),
    )

    chunks = _chunk_by_tokens(messages)

    if len(chunks) == 1:
        prompt = (
            f"Summarise this DM conversation with {other_user_name} "
            f"(output in English only):\n\n{formatted_all}"
        )
        return await generate_text(prompt, system_prompt=DM_SUMMARY_PROMPT, max_tokens=1024)

    logger.info("summarise_dm_chunked", chunks=len(chunks))

    chunk_summaries = await _summarise_chunks_parallel(
        chunks,
        prompt_fn=lambda text: (
            f"Summarise this portion of a DM conversation with {other_user_name} "
            f"(output in English only):\n\n{text}"
        ),
        system_prompt=DM_SUMMARY_PROMPT,
        user_map=user_map,
    )
    return await _hierarchical_merge(
        chunk_summaries, DM_SUMMARY_PROMPT, label=f"DM with {other_user_name}"
    )


async def catch_up_summary(user_id: str, offline_since: datetime) -> Dict:
    from src.common.database import get_mongo_db, get_pg_pool
    db = get_mongo_db()
    pool = get_pg_pool()

    direct_cursor = db.messages.find({
        "receiver_id": user_id,
        "timestamp":   {"$gte": offline_since},
        "group_id":    None,
        "deleted":     {"$ne": True},
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
            "group_id":  gid,
            "timestamp": {"$gte": offline_since},
            "sender_id": {"$ne": user_id},
            "deleted":   {"$ne": True},
        }).sort("timestamp", 1)
        msgs = await cursor.to_list(length=200)
        if not msgs:
            return row["group_name"], None, 0

        umap = await _build_user_map(msgs)
        chunks = _chunk_by_tokens(msgs)

        if len(chunks) == 1:
            text = _format_messages(msgs, umap)
            summary = await generate_text(
                f"Summarise missed messages in '{row['group_name']}':\n\n{text}",
                system_prompt=CATCHUP_PROMPT,
                max_tokens=256,
            )
        else:
            chunk_sums = await _summarise_chunks_parallel(
                chunks,
                prompt_fn=lambda t: (
                    f"Summarise missed messages in '{row['group_name']}':\n\n{t}"
                ),
                system_prompt=CATCHUP_PROMPT,
                max_tokens=256,
                user_map=umap,
            )
            summary = await _hierarchical_merge(
                chunk_sums, CATCHUP_PROMPT, label=row["group_name"]
            )

        return row["group_name"], summary, len(msgs)

    group_results = await asyncio.gather(*[_summarise_group(r) for r in group_rows])

    for name, summary, count in group_results:
        if summary:
            group_summaries[name] = {"count": count, "summary": summary}
            total_missed += count

    dm_summary = None
    if direct_messages:
        umap = await _build_user_map(direct_messages)
        chunks = _chunk_by_tokens(direct_messages)
        if len(chunks) == 1:
            text = _format_messages(direct_messages, umap)
            dm_summary = await generate_text(
                f"Summarise these direct messages the user missed:\n\n{text}",
                system_prompt=CATCHUP_PROMPT,
                max_tokens=256,
            )
        else:
            chunk_sums = await _summarise_chunks_parallel(
                chunks,
                prompt_fn=lambda t: (
                    f"Summarise these direct messages the user missed:\n\n{t}"
                ),
                system_prompt=CATCHUP_PROMPT,
                max_tokens=256,
                user_map=umap,
            )
            dm_summary = await _hierarchical_merge(
                chunk_sums, CATCHUP_PROMPT, label="direct messages"
            )

    return {
        "total_missed": total_missed,
        "offline_since": offline_since.isoformat(),
        "direct_messages": {"count": len(direct_messages), "summary": dm_summary},
        "group_summaries": group_summaries,
    }


async def search_with_ai(
    query: str, user_id: str, filters: Optional[Dict] = None
) -> Dict:
    from src.search.search_service import hybrid_search
    results = await hybrid_search(query, n_results=10, filters=filters or {})

    if not results:
        return {"answer": "No relevant messages found.", "sources": []}

    context = "\n".join([f"- {r['content']}" for r in results[:5]])
    prompt = (
        f'User query: "{query}"\n\n'
        f"Relevant messages found:\n{context}\n\n"
        "Answer the user's query based on these messages. "
        "Be specific and cite which message answers their question."
    )
    answer = await generate_text(prompt, max_tokens=512)
    return {"answer": answer, "sources": results[:5]}


# ── Formatting helpers ────────────────────────────────────────────────────────

def _format_messages(
    messages: List[Dict], user_map: Optional[Dict[str, str]] = None
) -> str:
    """
    Format messages as readable text for LLM prompts.
    Uses display names when user_map is provided; falls back to UUID prefix.
    """
    _map = user_map or {}
    lines = []
    for m in messages:
        ts = m.get("timestamp", "")
        if hasattr(ts, "strftime"):
            ts = ts.strftime("%Y-%m-%d %H:%M")
        sender_id = str(m.get("sender_id", "unknown"))
        sender = _map.get(sender_id, sender_id[:8])
        content = m.get("content", "")
        lines.append(f"[{ts}] {sender}: {content}")
    return "\n".join(lines)


# Legacy alias — kept for any external callers
def _chunk_messages(messages: List[Dict], size: int = 50) -> List[List[Dict]]:
    return [messages[i : i + size] for i in range(0, len(messages), size)]
