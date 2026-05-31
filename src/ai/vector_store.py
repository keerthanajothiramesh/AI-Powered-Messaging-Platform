import asyncio
from typing import List, Dict, Any, Optional
from src.common.logger import get_logger

logger = get_logger(__name__)

_store = None


class _LocalEmbeddingFunction:
    """ChromaDB embedding function backed by the local sentence-transformers model."""

    def __call__(self, input: List[str]) -> List[List[float]]:
        from src.ai.embedding_service import get_embedding_service, EMBEDDING_DIM
        svc = get_embedding_service()
        if svc:
            return svc.batch_embed(input)
        return [[0.0] * EMBEDDING_DIM for _ in input]


_local_ef = _LocalEmbeddingFunction()


class VectorStore:
    def __init__(self, chroma_path: str):
        import chromadb
        self._client = chromadb.PersistentClient(path=chroma_path)
        self.messages_collection = self._client.get_or_create_collection(
            name="messages",
            embedding_function=_local_ef,
            metadata={"hnsw:space": "cosine"},
        )
        self.media_collection = self._client.get_or_create_collection(
            name="media_metadata",
            embedding_function=_local_ef,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "vector_store_initialized",
            message_count=self.messages_collection.count(),
        )

    def add_message(
        self,
        message_id: str,
        content: str,
        metadata: Dict[str, Any],
        embedding: Optional[List[float]] = None,
    ) -> None:
        try:
            clean_meta = {k: str(v) if v is not None else "" for k, v in metadata.items()}
            kwargs = {
                "documents": [content],
                "ids": [message_id],
                "metadatas": [clean_meta],
            }
            if embedding:
                kwargs["embeddings"] = [embedding]
            self.messages_collection.add(**kwargs)
        except Exception as e:
            if "already exists" in str(e).lower():
                pass
            else:
                logger.warning("vector_add_failed", message_id=message_id, error=str(e))

    async def add_message_async(
        self,
        message_id: str,
        content: str,
        metadata: Dict[str, Any],
    ) -> None:
        if not content or not content.strip():
            return
        from src.ai.embedding_service import get_embedding_service
        svc = get_embedding_service()
        embedding = None
        if svc:
            embedding = await svc.generate_embedding_async(content)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.add_message, message_id, content, metadata, embedding)

    def search_similar(
        self,
        query: str,
        n_results: int = 10,
        filters: Optional[Dict] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        try:
            where = _build_where(filters) if filters else None
            count = self.messages_collection.count()
            if count == 0:
                return []
            actual_n = min(n_results, count)

            kwargs = {
                "n_results": actual_n,
                "include": ["documents", "metadatas", "distances"],
            }
            if where:
                kwargs["where"] = where

            if query_embedding:
                kwargs["query_embeddings"] = [query_embedding]
            else:
                kwargs["query_texts"] = [query]

            results = self.messages_collection.query(**kwargs)
            return _format_results(results)
        except Exception as e:
            logger.error("vector_search_failed", error=str(e))
            return []

    def search_media(
        self, query: str, n_results: int = 10, media_type: Optional[str] = None
    ) -> List[Dict]:
        try:
            count = self.media_collection.count()
            if count == 0:
                return []
            where = {"media_type": media_type} if media_type else None
            kwargs = {
                "query_texts": [query],
                "n_results": min(n_results, count),
                "include": ["documents", "metadatas", "distances"],
            }
            if where:
                kwargs["where"] = where
            results = self.media_collection.query(**kwargs)
            return _format_results(results)
        except Exception as e:
            logger.error("media_search_failed", error=str(e))
            return []

    def add_media(self, media_id: str, description: str, metadata: Dict) -> None:
        try:
            clean_meta = {k: str(v) if v is not None else "" for k, v in metadata.items()}
            self.media_collection.add(
                documents=[description],
                ids=[media_id],
                metadatas=[clean_meta],
            )
        except Exception as e:
            logger.warning("media_add_failed", media_id=media_id, error=str(e))


def _build_where(filters: Dict) -> Optional[Dict]:
    conditions = []
    if filters.get("sender_id"):
        conditions.append({"sender_id": {"$eq": filters["sender_id"]}})
    if filters.get("group_id"):
        conditions.append({"group_id": {"$eq": filters["group_id"]}})
    if filters.get("media_type"):
        conditions.append({"media_type": {"$eq": filters["media_type"]}})
    if filters.get("language"):
        conditions.append({"language": {"$eq": filters["language"]}})
    if not conditions:
        return None
    return {"$and": conditions} if len(conditions) > 1 else conditions[0]


def _format_results(results: Dict) -> List[Dict]:
    output = []
    if not results or not results.get("ids") or not results["ids"][0]:
        return output
    for i, msg_id in enumerate(results["ids"][0]):
        output.append({
            "message_id": msg_id,
            "content": results["documents"][0][i] if results.get("documents") else "",
            "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
            "score": 1 - results["distances"][0][i] if results.get("distances") else 0,
        })
    return output


def init_vector_store(chroma_path: str) -> None:
    global _store
    try:
        _store = VectorStore(chroma_path)
    except Exception as e:
        logger.error("vector_store_init_failed", error=str(e))


def get_vector_store() -> Optional[VectorStore]:
    return _store
