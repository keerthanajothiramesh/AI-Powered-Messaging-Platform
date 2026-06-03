"""Flan-T5-small CPU fallback for text generation when the OpenAI circuit breaker is open."""

import asyncio
from src.common.logger import get_logger

logger = get_logger(__name__)

_MODEL_ID = "google/flan-t5-small"
_pipeline = None
_load_attempted = False


def _load_pipeline():
    global _pipeline, _load_attempted
    if _load_attempted:
        return _pipeline
    _load_attempted = True
    try:
        from transformers import pipeline as hf_pipeline
        _pipeline = hf_pipeline(
            "text2text-generation",
            model=_MODEL_ID,
            device=-1,          # CPU
            max_new_tokens=256,
        )
        logger.info("flan_t5_loaded", model=_MODEL_ID)
    except Exception as exc:
        logger.warning("flan_t5_load_failed", error=str(exc), reason="transformers/torch not installed or model unavailable")
        _pipeline = None
    return _pipeline


async def generate_local(prompt: str, max_tokens: int = 256) -> str:
    """
    Generate text using Flan-T5 Small on CPU.
    Falls back to an extractive stub if the model cannot be loaded.
    """
    pipe = await asyncio.get_event_loop().run_in_executor(None, _load_pipeline)

    if pipe is None:
        # Last-resort stub — deterministic, no randomness
        words = prompt.split()
        excerpt = " ".join(words[:20])
        return f"[Local fallback — Gemini unavailable] {excerpt}..."

    try:
        truncated = prompt[:512]   # Flan-T5 Small max input tokens ~512
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: pipe(truncated, max_new_tokens=max_tokens),
        )
        text = result[0]["generated_text"]
        logger.info("flan_t5_generated", output_length=len(text))
        return text
    except Exception as exc:
        logger.error("flan_t5_generate_failed", error=str(exc))
        words = prompt.split()
        return f"[Local fallback] {' '.join(words[:20])}..."
