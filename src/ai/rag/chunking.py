"""Token-aware message chunking for RAG summarisation."""
from typing import List, Dict

_CHUNK_TOKEN_LIMIT = 3_000
_MERGE_TOKEN_LIMIT = 6_000
_PARALLEL_BATCH    = 5
_MAX_MESSAGES      = 5_000
_CHUNK_OVERLAP     = 3


def count_tokens(text: str) -> int:
    """Approximate token count. Uses tiktoken when available, else len//4."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)


def chunk_by_tokens(
    messages: List[Dict], limit: int = _CHUNK_TOKEN_LIMIT
) -> List[List[Dict]]:
    """
    Split messages into token-budget chunks with overlap.

    Each chunk stays within `limit` tokens. The last _CHUNK_OVERLAP messages
    of chunk N are repeated at the start of chunk N+1 for context continuity.
    """
    if not messages:
        return []

    from src.ai.rag.formatting import format_messages
    msg_tokens = [count_tokens(format_messages([m])) for m in messages]

    chunks: List[List[Dict]] = []
    i = 0
    while i < len(messages):
        current: List[Dict] = []
        current_tokens = 0
        chunk_start = i
        while i < len(messages):
            if current and current_tokens + msg_tokens[i] > limit:
                break
            current.append(messages[i])
            current_tokens += msg_tokens[i]
            i += 1
        if current:
            chunks.append(current)
        if i < len(messages):
            i = max(chunk_start + 1, i - _CHUNK_OVERLAP)

    return chunks


def chunk_messages_legacy(messages: List[Dict], size: int = 50) -> List[List[Dict]]:
    """Legacy fixed-size chunking — kept for external callers."""
    return [messages[i: i + size] for i in range(0, len(messages), size)]
