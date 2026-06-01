"""Builds and compiles the LangGraph agent graph.

Flow:
  START → moderate → (block→finalise | route→router)
  router → search|summarise|delivery|notify
  search/summarise → judge → (retry|finalise)
  delivery/notify → finalise → END
"""
from __future__ import annotations
from typing import Any, Dict, Literal, Optional

from langgraph.graph import END, StateGraph

from src.agents.graph.state import AgentState
from src.agents.graph.nodes import (
    moderate_node, router_node, search_node, summarise_node,
    delivery_node, notification_node, judge_node, finalise_node,
)
from src.common.logger import get_logger

logger = get_logger(__name__)


def _after_moderation(state: AgentState) -> Literal["blocked", "route"]:
    action = (state.get("moderation_result") or {}).get("action", "allow")
    return "blocked" if action == "block" else "route"


def _by_intent(state: AgentState) -> Literal["search", "summarise", "delivery", "notify"]:
    return state.get("intent", "search")  # type: ignore[return-value]


def _after_judge(state: AgentState) -> Literal["retry_search", "retry_summarise", "finalise"]:
    score = (state.get("judge_result") or {}).get("average_score", 10)
    retry_count = state.get("retry_count", 0)
    if score < 7 and retry_count < 2:
        return "retry_summarise" if state.get("intent") == "summarise" else "retry_search"
    return "finalise"


def _build_graph() -> StateGraph:
    g = StateGraph(AgentState)
    g.add_node("moderate",  moderate_node)
    g.add_node("router",    router_node)
    g.add_node("search",    search_node)
    g.add_node("summarise", summarise_node)
    g.add_node("delivery",  delivery_node)
    g.add_node("notify",    notification_node)
    g.add_node("judge",     judge_node)
    g.add_node("finalise",  finalise_node)
    g.set_entry_point("moderate")
    g.add_conditional_edges("moderate", _after_moderation, {"blocked": "finalise", "route": "router"})
    g.add_conditional_edges("router", _by_intent,
                            {"search": "search", "summarise": "summarise",
                             "delivery": "delivery", "notify": "notify"})
    g.add_edge("search",    "judge")
    g.add_edge("summarise", "judge")
    g.add_edge("delivery",  "finalise")
    g.add_edge("notify",    "finalise")
    g.add_conditional_edges("judge", _after_judge,
                            {"retry_search": "search", "retry_summarise": "summarise", "finalise": "finalise"})
    g.add_edge("finalise", END)
    return g


_graph = _build_graph().compile()


async def run_agent_graph(query: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Run the full agent graph for a query. Returns status/intent/data dict."""
    initial_state: AgentState = {
        "query": query,
        "user_id": context.get("user_id", ""),
        "context": context,
        "intent": "",
        "retry_query": None,
        "moderation_result": None,
        "search_result": None,
        "summarisation_result": None,
        "delivery_result": None,
        "notification_result": None,
        "judge_result": None,
        "retry_count": 0,
        "final_response": None,
        "error": None,
    }
    try:
        result = await _graph.ainvoke(initial_state)
        return result.get("final_response") or {
            "status": "error", "error": "Graph completed but produced no output"
        }
    except Exception as exc:
        logger.error("graph_run_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}
