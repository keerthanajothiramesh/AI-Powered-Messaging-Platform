from typing import List, Dict, Any, Optional
from src.common.logger import get_logger

logger = get_logger(__name__)


def _chunk_text(text: str, size: int = 800, overlap: int = 150) -> List[str]:
    """Split text into overlapping chunks, breaking at sentence/word boundaries."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            for sep in (".", "\n", " "):
                pos = text.rfind(sep, start + size // 2, end)
                if pos != -1:
                    end = pos + 1
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        next_start = end - overlap
        if next_start <= start:
            next_start = start + max(1, size - overlap)
        start = next_start
    return chunks

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

    async def add_document_chunks(
        self, media_id: str, text: str, metadata: Dict[str, Any]
    ) -> int:
        """Chunk text, embed each chunk, and store in document_chunks. Returns chunk count."""
        chunks = _chunk_text(text, size=800, overlap=150)
        if not chunks:
            return 0
        from src.ai.embedding_service import get_embedding_service
        svc = get_embedding_service()
        if not svc:
            return 0
        embeddings = svc.batch_embed(chunks)
        inserted = 0
        try:
            async with self._pool.acquire() as conn:
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    await conn.execute(
                        """INSERT INTO document_chunks
                           (media_id, chunk_index, content, embedding,
                            filename, media_type, uploader_id, group_id, receiver_id)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                           ON CONFLICT (media_id, chunk_index) DO NOTHING""",
                        media_id, i, chunk, embedding,
                        metadata.get("filename", ""),
                        metadata.get("media_type", "document"),
                        metadata.get("uploader_id", ""),
                        metadata.get("group_id", ""),
                        metadata.get("receiver_id", ""),
                    )
                    inserted += 1
            logger.info("document_chunks_indexed", media_id=media_id, chunks=inserted)
        except Exception as e:
            logger.error("document_chunk_insert_failed", media_id=media_id, error=str(e))
        return inserted

    async def search_document_chunks(
        self,
        query: str,
        n_results: int = 5,
        filters: Optional[Dict] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """Semantic search over document chunks stored in pgvector."""
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
            if filters.get("group_id"):
                where_clauses.append(f"group_id = ${idx}")
                params.append(filters["group_id"])
                idx += 1
            if filters.get("uploader_id"):
                where_clauses.append(f"uploader_id = ${idx}")
                params.append(filters["uploader_id"])
                idx += 1
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        sql = f"""
            SELECT media_id, chunk_index, content, filename, media_type, uploader_id, group_id,
                   1 - (embedding <=> $1) AS score
            FROM document_chunks
            {where_sql}
            ORDER BY embedding <=> $1
            LIMIT $2
        """
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)
            return [
                {
                    "message_id": f"doc::{r['media_id']}::{r['chunk_index']}",
                    "content": r["content"],
                    "score": float(r["score"]),
                    "source_type": "document",
                    "metadata": {
                        "filename": r["filename"],
                        "media_type": r["media_type"],
                        "uploader_id": r["uploader_id"],
                        "group_id": r["group_id"],
                        "source_type": "document",
                    },
                }
                for r in rows
            ]
        except Exception as e:
            logger.error("document_chunk_search_failed", error=str(e))
            return []

    def add_media(self, media_id: str, description: str, metadata: Dict) -> None:
        pass  # kept for backward compatibility — use add_document_chunks instead

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
