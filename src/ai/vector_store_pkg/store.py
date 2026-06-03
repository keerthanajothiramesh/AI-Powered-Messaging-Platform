"""VectorStore class — composes message and document pgvector mixins and exposes a module-level singleton."""
from typing import Dict, List, Optional

from src.ai.vector_store_pkg.message_store import MessageVectorMixin
from src.ai.vector_store_pkg.document_store import DocumentVectorMixin
from src.common.logger import get_logger

logger = get_logger(__name__)

_store = None


class VectorStore(MessageVectorMixin, DocumentVectorMixin):
    """pgvector-backed store for messages and document chunks."""

    def __init__(self, pool):
        self._pool = pool
        logger.info("vector_store_initialized", backend="pgvector-neon")

    def add_media(self, media_id: str, description: str, metadata: Dict) -> None:
        pass  # backward compat — use add_document_chunks instead

    def search_media(
        self, query: str, n_results: int = 10, media_type: Optional[str] = None
    ) -> List[Dict]:
        return []  # triggers MongoDB fallback in search_service


def init_vector_store(pool) -> None:
    global _store
    try:
        _store = VectorStore(pool)
    except Exception as exc:
        logger.error("vector_store_init_failed", error=str(exc))


def get_vector_store() -> Optional[VectorStore]:
    return _store
