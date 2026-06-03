"""Sentence-embedding service using BAAI/bge-small-en-v1.5 via fastembed-ONNX (384-dim vectors)."""
import asyncio
from typing import List, Optional
from src.common.logger import get_logger

logger = get_logger(__name__)

EMBEDDING_DIM = 384
MODEL_NAME = "BAAI/bge-small-en-v1.5"

_service: Optional["EmbeddingService"] = None


class EmbeddingService:
    def __init__(self):
        from fastembed import TextEmbedding
        self._model = TextEmbedding(MODEL_NAME)
        logger.info("embedding_service_initialized", backend="fastembed-onnx", model=MODEL_NAME, dim=EMBEDDING_DIM)

    def generate_embedding(self, text: str) -> List[float]:
        try:
            return list(self._model.embed([text]))[0].tolist()
        except Exception as e:
            logger.error("embedding_generation_failed", error=str(e))
            return [0.0] * EMBEDDING_DIM

    def generate_query_embedding(self, text: str) -> List[float]:
        try:
            return list(self._model.query_embed([text]))[0].tolist()
        except Exception as e:
            logger.error("query_embedding_failed", error=str(e))
            return [0.0] * EMBEDDING_DIM

    def batch_embed(self, texts: List[str]) -> List[List[float]]:
        try:
            return [v.tolist() for v in self._model.embed(texts)]
        except Exception as e:
            logger.error("batch_embed_failed", error=str(e))
            return [[0.0] * EMBEDDING_DIM for _ in texts]

    async def generate_embedding_async(self, text: str) -> List[float]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.generate_embedding, text)

    async def generate_query_embedding_async(self, text: str) -> List[float]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.generate_query_embedding, text)


def get_embedding_service() -> Optional[EmbeddingService]:
    return _service


def init_embedding_service() -> None:
    global _service
    try:
        _service = EmbeddingService()
    except Exception as e:
        logger.error("embedding_service_init_failed", error=str(e))
