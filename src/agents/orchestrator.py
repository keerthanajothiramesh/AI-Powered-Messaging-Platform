from typing import Any, Dict, Optional

from src.common.logger import get_logger

logger = get_logger(__name__)


async def orchestrate(query: str, context: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Public entrypoint for agent orchestration.
    Delegates to the LangGraph StateGraph in graph.py.
    """
    from src.agents.graph import run_agent_graph
    context = context or {}
    logger.info("orchestrate", query=query[:60])
    return await run_agent_graph(query, context)
