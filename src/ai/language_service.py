from typing import Optional
from src.common.logger import get_logger

logger = get_logger(__name__)


def detect_language(text: str) -> str:
    try:
        from langdetect import detect
        lang = detect(text)
        return lang if lang in ("en", "ja") else "en"
    except Exception:
        return "en"


def is_japanese(text: str) -> bool:
    return detect_language(text) == "ja"
