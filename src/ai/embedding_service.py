import asyncio
from typing import List, Optional
from functools import lru_cache
from src.common.logger import get_logger

logger = get_logger(__name__)

_model = None


def load_embedding_model() -> None:
    global _model
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("embedding_model_loaded", model="all-MiniLM-L6-v2")
    except Exception as e:
        logger.error("embedding_model_load_failed", error=str(e))


class EmbeddingService:
    def __init__(self, model):
        self._model = model
        self._cache: dict = {}

    def generate_embedding(self, text: str) -> List[float]:
        if text in self._cache:
            return self._cache[text]
        try:
            embedding = self._model.encode(text, normalize_embeddings=True).tolist()
            if len(self._cache) < 1000:
                self._cache[text] = embedding
            return embedding
        except Exception as e:
            logger.error("embedding_generation_failed", error=str(e))
            return [0.0] * 384

    def batch_embed(self, texts: List[str]) -> List[List[float]]:
        try:
            embeddings = self._model.encode(texts, normalize_embeddings=True, batch_size=64)
            return embeddings.tolist()
        except Exception as e:
            logger.error("batch_embed_failed", error=str(e))
            return [[0.0] * 384 for _ in texts]

    async def generate_embedding_async(self, text: str) -> List[float]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.generate_embedding, text)


_service: Optional[EmbeddingService] = None


def get_embedding_service() -> Optional[EmbeddingService]:
    return _service


def init_embedding_service() -> None:
    global _service
    load_embedding_model()
    if _model:
        _service = EmbeddingService(_model)
        logger.info("embedding_service_initialized")
