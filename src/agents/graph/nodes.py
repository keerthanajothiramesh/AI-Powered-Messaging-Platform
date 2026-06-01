"""LangGraph node functions — each returns only the state keys it mutates."""
from __future__ import annotations
from typing import Any, Dict, Optional

from src.agents.graph.state import AgentState
from src.common.logger import get_logger

logger = get_logger(__name__)


def _keyword_intent(query: str) -> str:
    """Keyword-based intent fallback when LLM is unavailable."""
    q = query.lower()
    if any(w in q for w in ["summar", "recap", "overview", "tldr", "what was discussed"]):
        return "summarise"
    if any(w in q for w in ["deliver", "failed", "recover", "undelivered", "retry"]):
        return "delivery"
    if any(w in q for w in ["notif", "alert", "ping", "remind", "notify"]):
        return "notify"
    return "search"


async def moderate_node(state: AgentState) -> dict:
    from src.agents.moderation_agent import ModerationAgent
    result = await ModerationAgent().run({"content": state["query"], "message_id": ""})
    logger.info("graph_moderate", action=result["action"], severity=result.get("severity", 0))
    return {"moderation_result": result}


async def router_node(state: AgentState) -> dict:
    try:
        from src.ai.gemini_client import generate_text
        prompt = (
            "Classify this query into exactly one word — search, summarise, delivery, or notify.\n"
            f'Query: "{state["query"]}"\nReply with just the single word, nothing else.'
        )
        raw = (await generate_text(prompt, max_tokens=10)).strip().lower()
    except Exception as exc:
        logger.warning("graph_router_gemini_failed", error=str(exc), fallback="keyword")
        raw = _keyword_intent(state["query"])

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


async def search_node(state: AgentState) -> dict:
    query = state.get("retry_query") or state["query"]
    if state.get("retry_query"):
        logger.info("graph_search_retry", rephrased_query=query[:60])
    from src.agents.search_agent import SearchAgent
    result = await SearchAgent().run({
        "query": query,
        "filters": state["context"].get("filters", {}),
        "n_results": state["context"].get("n_results", 10),
    })
    logger.info("graph_search", count=result.get("count", 0))
    return {"search_result": result}


async def summarise_node(state: AgentState) -> dict:
    from src.agents.summarisation_agent import SummarisationAgent
    result = await SummarisationAgent().run({
        "group_id": state["context"].get("group_id"),
        "days": state["context"].get("days", 14),
        "group_name": state["context"].get("group_name", "the group"),
    })
    logger.info("graph_summarise", quality=result.get("quality_score"))
    return {"summarisation_result": result}


async def delivery_node(state: AgentState) -> dict:
    from src.agents.delivery_agent import DeliveryAgent
    result = await DeliveryAgent().run(state["context"])
    logger.info("graph_delivery", recovered=result.get("recovered", 0), escalated=result.get("escalated", 0))
    return {"delivery_result": result}


async def notification_node(state: AgentState) -> dict:
    from src.agents.notification_agent import NotificationAgent
    result = await NotificationAgent().run({
        "user_id": state["user_id"],
        "content": state["query"],
        "sender_id": state["context"].get("sender_id", ""),
    })
    logger.info("graph_notify", urgency=result.get("urgency"))
    return {"notification_result": result}


async def judge_node(state: AgentState) -> dict:
    retry_count = state.get("retry_count", 0)

    summ = state.get("summarisation_result") or {}
    if summ and "quality_score" in summ:
        judgment = {"average_score": summ["quality_score"], "feedback": "pre-computed score"}
        logger.info("graph_judge_reuse", score=summ["quality_score"])
        return {"judge_result": judgment, "retry_count": retry_count + 1}

    results = (state.get("search_result") or {}).get("results", [])
    content = results[0]["content"] if results else ""
    if not content:
        return {
            "judge_result": {"average_score": 8, "feedback": "no content to evaluate"},
            "retry_count": retry_count + 1, "retry_query": None,
        }

    from src.agents.judge_agent import JudgeAgent
    judgment = await JudgeAgent().evaluate(content, state.get("context", {}))
    score = judgment.get("average_score", 10)
    logger.info("graph_judge", score=score)

    retry_query: Optional[str] = None
    if score < 7 and retry_count < 1:
        try:
            from src.ai.gemini_client import generate_text
            expand_prompt = (
                f'The search query "{state["query"]}" returned poor results (score {score:.1f}/10). '
                "Rewrite it to be more specific. Reply with just the improved query."
            )
            retry_query = (await generate_text(expand_prompt, max_tokens=60)).strip()
            logger.info("graph_judge_rephrase", retry_query=retry_query[:60])
        except Exception as exc:
            logger.warning("graph_judge_rephrase_failed", error=str(exc))

    return {"judge_result": judgment, "retry_count": retry_count + 1, "retry_query": retry_query}


async def finalise_node(state: AgentState) -> dict:
    mod = state.get("moderation_result") or {}

    if mod.get("action") == "block":
        response: Dict[str, Any] = {
            "status": "blocked",
            "reason": "Content violates platform policy",
            "severity": mod.get("severity", 0),
            "flags": mod.get("flags", []),
            "assessment": mod.get("assessment", ""),
        }
    else:
        if state.get("search_result"):
            response = {"status": "ok", "intent": "search",
                        "data": state["search_result"], "quality": state.get("judge_result")}
        elif state.get("summarisation_result"):
            response = {"status": "ok", "intent": "summarise",
                        "data": state["summarisation_result"], "quality": state.get("judge_result")}
        elif state.get("delivery_result"):
            response = {"status": "ok", "intent": "delivery", "data": state["delivery_result"]}
        elif state.get("notification_result"):
            response = {"status": "ok", "intent": "notify", "data": state["notification_result"]}
        else:
            response = {"status": "error", "error": state.get("error") or "No agent produced a result"}

        if mod.get("action") == "warn":
            response["moderation_warning"] = mod.get("assessment", "Content flagged for review")

    return {"final_response": response}
