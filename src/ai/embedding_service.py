import asyncio
from typing import List, Optional
from src.common.logger import get_logger

logger = get_logger(__name__)

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2
MODEL_NAME = "all-MiniLM-L6-v2"

_service: Optional["EmbeddingService"] = None


class EmbeddingService:
    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(MODEL_NAME)
        logger.info("embedding_service_initialized", backend=MODEL_NAME, dim=EMBEDDING_DIM)

    def generate_embedding(self, text: str) -> List[float]:
        try:
            vec = self._model.encode(text, normalize_embeddings=True)
            return vec.tolist()
        except Exception as e:
            logger.error("embedding_generation_failed", error=str(e))
            return [0.0] * EMBEDDING_DIM

    def generate_query_embedding(self, text: str) -> List[float]:
        return self.generate_embedding(text)

    def batch_embed(self, texts: List[str]) -> List[List[float]]:
        try:
            vecs = self._model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
            return [v.tolist() for v in vecs]
        except Exception as e:
            logger.error("batch_embed_failed", error=str(e))
            return [[0.0] * EMBEDDING_DIM for _ in texts]

    async def generate_embedding_async(self, text: str) -> List[float]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.generate_embedding, text)

    async def generate_query_embedding_async(self, text: str) -> List[float]:
        return await self.generate_embedding_async(text)


def get_embedding_service() -> Optional[EmbeddingService]:
    return _service


def init_embedding_service() -> None:
    global _service
    try:
        _service = EmbeddingService()
    except Exception as e:
        logger.error("embedding_service_init_failed", error=str(e))
