"""AI-enhanced search over message history."""
from typing import Dict, Optional

from src.ai.gemini_client import generate_text
from src.common.logger import get_logger

logger = get_logger(__name__)


async def search_with_ai(
    query: str, user_id: str, filters: Optional[Dict] = None
) -> Dict:
    """Hybrid search + LLM answer synthesis."""
    from src.search.search_service import hybrid_search
    results = await hybrid_search(query, n_results=10, filters=filters or {})

    if not results:
        return {"answer": "No relevant messages found.", "sources": []}

    context = "\n".join([f"- {r['content']}" for r in results[:5]])
    prompt = (
        f'User query: "{query}"\n\n'
        f"Relevant messages found:\n{context}\n\n"
        "Answer the user's query based on these messages. "
        "Be specific and cite which message answers their question."
    )
    answer = await generate_text(prompt, max_tokens=512)
    return {"answer": answer, "sources": results[:5]}
