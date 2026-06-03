"""Message formatting and user-name resolution helpers that prepare conversation text for LLM prompts."""
import uuid as _uuid_mod
from typing import Dict, List, Optional

from src.common.logger import get_logger

logger = get_logger(__name__)


async def build_user_map(messages: List[Dict]) -> Dict[str, str]:
    """
    Single PostgreSQL query mapping sender_id → display_name for all senders
    in `messages`. Returns empty dict on failure so formatting always has a fallback.
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


def format_messages(
    messages: List[Dict], user_map: Optional[Dict[str, str]] = None
) -> str:
    """Format messages as readable text for LLM prompts.
    Uses display names when user_map provided; falls back to UUID prefix."""
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
