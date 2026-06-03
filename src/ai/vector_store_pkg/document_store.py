"""pgvector mixin for document-chunk embedding upsert and semantic similarity search over uploaded files."""
from typing import Any, Dict, List, Optional

from src.common.logger import get_logger

logger = get_logger(__name__)


class DocumentVectorMixin:
    """Handles document-chunk embedding upsert and similarity search."""

    async def add_document_chunks(
        self, media_id: str, text: str, metadata: Dict[str, Any]
    ) -> int:
        """Chunk text, embed each chunk, store in document_chunks. Returns chunk count."""
        from src.ai.vector_store_pkg.chunking import chunk_text
        chunks = chunk_text(text, size=800, overlap=150)
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
                        metadata.get("filename", ""), metadata.get("media_type", "document"),
                        metadata.get("uploader_id", ""), metadata.get("group_id", ""),
                        metadata.get("receiver_id", ""),
                    )
                    inserted += 1
            logger.info("document_chunks_indexed", media_id=media_id, chunks=inserted)
        except Exception as exc:
            logger.error("document_chunk_insert_failed", media_id=media_id, error=str(exc))
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
            FROM document_chunks {where_sql}
            ORDER BY embedding <=> $1 LIMIT $2
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
                        "filename": r["filename"], "media_type": r["media_type"],
                        "uploader_id": r["uploader_id"], "group_id": r["group_id"],
                        "source_type": "document",
                    },
                }
                for r in rows
            ]
        except Exception as exc:
            logger.error("document_chunk_search_failed", error=str(exc))
            return []
