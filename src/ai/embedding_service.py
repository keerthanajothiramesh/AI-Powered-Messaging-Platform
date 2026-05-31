import asyncio
from typing import List, Optional
from src.common.logger import get_logger

logger = get_logger(__name__)

EMBEDDING_DIM = 3072  # gemini-embedding-001 default dimension

_service: Optional["EmbeddingService"] = None


class EmbeddingService:
    def __init__(self, api_key: str):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._genai = genai
        logger.info("embedding_service_initialized", backend="gemini-embedding-001-3072d")

    def generate_embedding(self, text: str) -> List[float]:
        try:
            result = self._genai.embed_content(
                model="models/gemini-embedding-001",
                content=text,
                task_type="retrieval_document",
            )
            return result["embedding"]
        except Exception as e:
            logger.error("embedding_generation_failed", error=str(e))
            return [0.0] * EMBEDDING_DIM

    def generate_query_embedding(self, text: str) -> List[float]:
        try:
            result = self._genai.embed_content(
                model="models/gemini-embedding-001",
                content=text,
                task_type="retrieval_query",
            )
            return result["embedding"]
        except Exception as e:
            logger.error("query_embedding_failed", error=str(e))
            return [0.0] * EMBEDDING_DIM

    def batch_embed(self, texts: List[str]) -> List[List[float]]:
        return [self.generate_embedding(t) for t in texts]

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
    from src.config import settings
    if not settings.GEMINI_API_KEY:
        logger.warning("embedding_service_skipped", reason="GEMINI_API_KEY not set")
        return
    try:
        _service = EmbeddingService(settings.GEMINI_API_KEY)
    except Exception as e:
        logger.error("embedding_service_init_failed", error=str(e))
