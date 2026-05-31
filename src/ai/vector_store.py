from typing import List, Dict, Any, Optional
from src.common.logger import get_logger

logger = get_logger(__name__)

_store = None


class VectorStore:
    def __init__(self, pool):
        self._pool = pool
        logger.info("vector_store_initialized", backend="pgvector-neon")

    async def add_message_async(self, message_id: str, content: str, metadata: Dict[str, Any]) -> None:
        if not content or not content.strip():
            return
        from src.ai.embedding_service import get_embedding_service
        svc = get_embedding_service()
        if not svc:
            return
        embedding = await svc.generate_embedding_async(content)
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO message_embeddings
                       (message_id, embedding, content, sender_id, group_id, receiver_id, media_type, language)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                       ON CONFLICT (message_id) DO NOTHING""",
                    message_id, embedding, content,
                    metadata.get("sender_id", ""),
                    metadata.get("group_id", ""),
                    metadata.get("receiver_id", ""),
                    metadata.get("media_type", "text"),
                    metadata.get("language", "en"),
                )
        except Exception as e:
            logger.warning("pgvector_add_failed", message_id=message_id, error=str(e))

    async def search_similar(
        self,
        query: str,
        n_results: int = 10,
        filters: Optional[Dict] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        from src.ai.embedding_service import get_embedding_service
        svc = get_embedding_service()
        if not svc:
            return []
        if query_embedding is None:
            query_embedding = await svc.generate_query_embedding_async(query)

        where_clauses: List[str] = []
        params: List[Any] = [query_embedding, n_results]
        idx = 3

        if filters:
            if filters.get("sender_id"):
                where_clauses.append(f"sender_id = ${idx}")
                params.append(filters["sender_id"])
                idx += 1
            if filters.get("group_id"):
                where_clauses.append(f"group_id = ${idx}")
                params.append(filters["group_id"])
                idx += 1

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        sql = f"""
            SELECT message_id, content, sender_id, group_id, receiver_id, media_type, language,
                   1 - (embedding <=> $1) AS score
            FROM message_embeddings
            {where_sql}
            ORDER BY embedding <=> $1
            LIMIT $2
        """
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)
            return [
                {
                    "message_id": r["message_id"],
                    "content": r["content"],
                    "score": float(r["score"]),
                    "metadata": {
                        "sender_id": r["sender_id"],
                        "group_id": r["group_id"],
                        "receiver_id": r["receiver_id"],
                        "media_type": r["media_type"],
                        "language": r["language"],
                    },
                }
                for r in rows
            ]
        except Exception as e:
            logger.error("pgvector_search_failed", error=str(e))
            return []

    def add_media(self, media_id: str, description: str, metadata: Dict) -> None:
        pass  # media falls back to MongoDB in search_service.search_media

    def search_media(self, query: str, n_results: int = 10, media_type: Optional[str] = None) -> List[Dict]:
        return []  # triggers MongoDB fallback in search_service


def init_vector_store(pool) -> None:
    global _store
    try:
        _store = VectorStore(pool)
    except Exception as e:
        logger.error("vector_store_init_failed", error=str(e))


def get_vector_store() -> Optional[VectorStore]:
    return _store
