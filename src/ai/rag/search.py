"""AI-enhanced search over message history."""
from typing import Dict, Optional

from src.ai.gemini_client import generate_text
from src.common.logger import get_logger

logger = get_logger(__name__)


async def search_with_ai(
    query: str, user_id: str, filters: Optional[Dict] = None
) -> Dict:
    """Semantic-only vector search + LLM answer synthesis (no keyword/BM25 matching)."""
    from src.ai.vector_store import get_vector_store
    vs = get_vector_store()

    msg_results, doc_results = [], []
    if vs:
        try:
            msg_results = await vs.search_similar(query, n_results=8, filters=filters or {})
        except Exception as exc:
            logger.warning("ai_search_msg_failed", error=str(exc))
        try:
            doc_results = await vs.search_document_chunks(query, n_results=8)
        except Exception as exc:
            logger.warning("ai_search_doc_failed", error=str(exc))

    # Merge, deduplicate, sort by semantic relevance score
    seen: set = set()
    combined = []
    for r in msg_results + doc_results:
        if r["message_id"] not in seen:
            seen.add(r["message_id"])
            combined.append(r)
    combined.sort(key=lambda r: r.get("score", 0), reverse=True)
    top = combined[:8]

    if not top:
        return {"answer": "No relevant content found for your query.", "sources": []}

    context = "\n".join([f"- {r['content']}" for r in top[:5]])
    prompt = (
        f'User query: "{query}"\n\n'
        f"Relevant content:\n{context}\n\n"
        "Answer the user's query based on this content. "
        "Be specific and reference the source that best answers their question."
    )
    answer = await generate_text(prompt, max_tokens=512)
    return {"answer": answer, "sources": top[:5]}
