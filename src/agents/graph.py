"""
LangGraph-based multi-agent orchestration.

Flow:
  START
    └─► moderate  ──(blocked)──► finalise ──► END
              └──(allowed)──► router
                                 ├─► search    ──► judge ──(pass)──► finalise ──► END
                                 │                     └──(fail,retry<2)──► search
                                 ├─► summarise ──► judge ──(pass)──► finalise ──► END
                                 │                     └──(fail,retry<2)──► summarise
                                 ├─► delivery ──────────────────────► finalise ──► END
                                 └─► notify   ──────────────────────► finalise ──► END
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional, TypedDict

from langgraph.graph import END, StateGraph

from src.common.logger import get_logger

logger = get_logger(__name__)


# ── Typed state shared across every node ──────────────────────────────────────

class AgentState(TypedDict):
    # inputs
    query: str
    user_id: str
    context: Dict[str, Any]
    # routing
    intent: str
    # per-agent outputs (None until that node runs)
    moderation_result: Optional[Dict[str, Any]]
    search_result: Optional[Dict[str, Any]]
    summarisation_result: Optional[Dict[str, Any]]
    delivery_result: Optional[Dict[str, Any]]
    notification_result: Optional[Dict[str, Any]]
    judge_result: Optional[Dict[str, Any]]
    # control
    retry_count: int
    final_response: Optional[Dict[str, Any]]
    error: Optional[str]


# ── Node functions (each returns only the keys it mutates) ────────────────────

async def _moderate_node(state: AgentState) -> dict:
    """Safety gate — always the first node. Blocks harmful content immediately."""
    from src.agents.moderation_agent import ModerationAgent
    result = await ModerationAgent().run({"content": state["query"], "message_id": ""})
    logger.info("graph_moderate", is_flagged=result["is_flagged"], action=result["action"])
    return {"moderation_result": result}


async def _router_node(state: AgentState) -> dict:
    """Classifies the query into one of four intents via a single Gemini call."""
    from src.ai.gemini_client import generate_text
    prompt = (
        "Classify this query into exactly one word — search, summarise, delivery, or notify.\n"
        f'Query: "{state["query"]}"\n'
        "Reply with just the single word, nothing else."
    )
    raw = (await generate_text(prompt, max_tokens=10)).strip().lower()

    if "summar" in raw:
        intent = "summarise"
    elif "deliver" in raw:
        intent = "delivery"
    elif "notif" in raw:
        intent = "notify"
    else:
        intent = "search"

    logger.info("graph_router", intent=intent)
    return {"intent": intent}


async def _search_node(state: AgentState) -> dict:
    """Runs hybrid semantic + BM25 search and analyses top results."""
    from src.agents.search_agent import SearchAgent
    result = await SearchAgent().run({
        "query": state["query"],
        "filters": state["context"].get("filters", {}),
        "n_results": state["context"].get("n_results", 10),
    })
    logger.info("graph_search", count=result.get("count", 0))
    return {"search_result": result}


async def _summarise_node(state: AgentState) -> dict:
    """RAG-based conversation summarisation; internal quality score already set."""
    from src.agents.summarisation_agent import SummarisationAgent
    result = await SummarisationAgent().run({
        "group_id": state["context"].get("group_id"),
        "days": state["context"].get("days", 14),
        "group_name": state["context"].get("group_name", "the group"),
    })
    logger.info("graph_summarise", quality=result.get("quality_score"))
    return {"summarisation_result": result}


async def _delivery_node(state: AgentState) -> dict:
    """Finds failed messages and re-delivers them if the receiver is now online."""
    from src.agents.delivery_agent import DeliveryAgent
    result = await DeliveryAgent().run(state["context"])
    logger.info("graph_delivery", recovered=result.get("recovered", 0))
    return {"delivery_result": result}


async def _notification_node(state: AgentState) -> dict:
    """Determines notification urgency and optimal delivery timing."""
    from src.agents.notification_agent import NotificationAgent
    result = await NotificationAgent().run({
        "user_id": state["user_id"],
        "content": state["query"],
        "sender_id": state["context"].get("sender_id", ""),
    })
    logger.info("graph_notify", urgency=result.get("urgency"))
    return {"notification_result": result}


async def _judge_node(state: AgentState) -> dict:
    """
    Quality gate for search and summarise outputs.

    - For summarise: reuses the quality_score already produced by SummarisationAgent
      to avoid a redundant Gemini call.
    - For search: calls JudgeAgent to score the top result.
    - Increments retry_count so the conditional edge can cap retries at 1.
    """
    retry_count = state.get("retry_count", 0)

    # Summarise already ran JudgeAgent internally — reuse that score.
    summ = state.get("summarisation_result") or {}
    if summ and "quality_score" in summ:
        judgment = {
            "average_score": summ["quality_score"],
            "feedback": "score from summarisation agent internal evaluation",
        }
        logger.info("graph_judge_reuse", score=summ["quality_score"])
        return {"judge_result": judgment, "retry_count": retry_count + 1}

    # Fresh evaluation for search results.
    results = (state.get("search_result") or {}).get("results", [])
    content = results[0]["content"] if results else ""

    if not content:
        logger.info("graph_judge_skip", reason="no content")
        return {
            "judge_result": {"average_score": 8, "feedback": "no content to evaluate"},
            "retry_count": retry_count + 1,
        }

    from src.agents.judge_agent import JudgeAgent
    judgment = await JudgeAgent().evaluate(content, state.get("context", {}))
    logger.info("graph_judge", score=judgment.get("average_score"))
    return {"judge_result": judgment, "retry_count": retry_count + 1}


async def _finalise_node(state: AgentState) -> dict:
    """Assembles the unified response from whichever agent(s) ran."""
    mod = state.get("moderation_result") or {}

    if mod.get("action") == "block":
        response: Dict[str, Any] = {
            "status": "blocked",
            "reason": "Content violates platform policy",
            "flags": mod.get("flags", []),
            "assessment": mod.get("assessment", ""),
        }
    elif state.get("search_result"):
        response = {
            "status": "ok",
            "intent": "search",
            "data": state["search_result"],
            "quality": state.get("judge_result"),
        }
    elif state.get("summarisation_result"):
        response = {
            "status": "ok",
            "intent": "summarise",
            "data": state["summarisation_result"],
            "quality": state.get("judge_result"),
        }
    elif state.get("delivery_result"):
        response = {
            "status": "ok",
            "intent": "delivery",
            "data": state["delivery_result"],
        }
    elif state.get("notification_result"):
        response = {
            "status": "ok",
            "intent": "notify",
            "data": state["notification_result"],
        }
    else:
        response = {
            "status": "error",
            "error": state.get("error") or "No agent produced a result",
        }

    return {"final_response": response}


# ── Conditional edge functions ─────────────────────────────────────────────────

def _after_moderation(state: AgentState) -> Literal["blocked", "route"]:
    if (state.get("moderation_result") or {}).get("action") == "block":
        return "blocked"
    return "route"


def _by_intent(
    state: AgentState,
) -> Literal["search", "summarise", "delivery", "notify"]:
    return state.get("intent", "search")  # type: ignore[return-value]


def _after_judge(
    state: AgentState,
) -> Literal["retry_search", "retry_summarise", "finalise"]:
    score = (state.get("judge_result") or {}).get("average_score", 10)
    # retry_count was already incremented by _judge_node; cap at 1 retry
    retry_count = state.get("retry_count", 0)
    if score < 7 and retry_count < 2:
        intent = state.get("intent", "search")
        return "retry_summarise" if intent == "summarise" else "retry_search"
    return "finalise"


# ── Graph construction ─────────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("moderate",  _moderate_node)
    g.add_node("router",    _router_node)
    g.add_node("search",    _search_node)
    g.add_node("summarise", _summarise_node)
    g.add_node("delivery",  _delivery_node)
    g.add_node("notify",    _notification_node)
    g.add_node("judge",     _judge_node)
    g.add_node("finalise",  _finalise_node)

    # Entry point — moderation always runs first
    g.set_entry_point("moderate")

    # Moderation gate
    g.add_conditional_edges(
        "moderate",
        _after_moderation,
        {"blocked": "finalise", "route": "router"},
    )

    # Intent routing
    g.add_conditional_edges(
        "router",
        _by_intent,
        {
            "search":    "search",
            "summarise": "summarise",
            "delivery":  "delivery",
            "notify":    "notify",
        },
    )

    # Quality gate: search + summarise go through judge
    g.add_edge("search",    "judge")
    g.add_edge("summarise", "judge")

    # Delivery + notify skip quality gate — go straight to finalise
    g.add_edge("delivery", "finalise")
    g.add_edge("notify",   "finalise")

    # Judge: pass → finalise, fail → retry (once) → back to specialist
    g.add_conditional_edges(
        "judge",
        _after_judge,
        {
            "retry_search":    "search",
            "retry_summarise": "summarise",
            "finalise":        "finalise",
        },
    )

    g.add_edge("finalise", END)
    return g


# Compiled once at module load — reused across all requests
_graph = _build_graph().compile()


# ── Public API ─────────────────────────────────────────────────────────────────

async def run_agent_graph(query: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the full agent graph for a query.

    Args:
        query:   The user's input text.
        context: Arbitrary key/value context (user_id, group_id, filters, etc.)

    Returns:
        A dict with keys: status, intent, data, quality (where applicable).
    """
    initial_state: AgentState = {
        "query": query,
        "user_id": context.get("user_id", ""),
        "context": context,
        "intent": "",
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
            "status": "error",
            "error": "Graph completed but produced no output",
        }
    except Exception as exc:
        logger.error("graph_run_failed", error=str(exc))
        return {"status": "error", "error": str(exc)}
