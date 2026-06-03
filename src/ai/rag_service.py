"""Backward-compatible re-export stub — delegates RAG summarisation functions to src/ai/rag/."""
from src.ai.rag import (  # noqa: F401
    summarise_with_stats,
    summarise_conversation,
    extract_action_items,
    summarise_dm,
    catch_up_summary,
    search_with_ai,
)
from src.ai.rag.chunking import chunk_messages_legacy as _chunk_messages  # noqa: F401
