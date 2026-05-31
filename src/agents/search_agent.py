from typing import Dict, Any
from src.agents.base_agent import BaseAgent
from src.common.logger import get_logger

logger = get_logger(__name__)


class SearchAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="SearchAgent",
            system_prompt="""You are a search specialist agent. Your job is to:
1. Analyse search queries and expand them for better retrieval
2. Rank and filter search results by relevance
3. Identify the most relevant messages matching the user's intent
Be precise and return only the most relevant results.""",
        )

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        query = input_data.get("query", "")
        filters = input_data.get("filters", {})
        n_results = input_data.get("n_results", 10)

        logger.info("search_agent_run", query=query)

        from src.search.search_service import hybrid_search
        results = await hybrid_search(query, n_results=n_results, filters=filters)

        if results:
            context = "\n".join([f"- {r['content'][:100]}" for r in results[:5]])
            enhanced_prompt = f"""Analyse these search results for query: "{query}"

Results:
{context}

Identify which result best answers the query and explain why."""
            analysis = await self._generate(enhanced_prompt, max_tokens=256)
        else:
            analysis = "No results found for this query."

        return {
            "agent": self.name,
            "query": query,
            "results": results,
            "analysis": analysis,
            "count": len(results),
        }
