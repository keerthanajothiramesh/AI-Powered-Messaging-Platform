"""Character-level overlapping text chunker for splitting documents before embedding."""
from typing import List


def chunk_text(text: str, size: int = 800, overlap: int = 150) -> List[str]:
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
