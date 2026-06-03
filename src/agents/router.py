"""Agents REST API — run orchestrator, rate summaries, trigger delivery recovery, RCA, and moderation scans."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict

from src.auth.dependencies import get_current_user
from src.agents.orchestrator import orchestrate
from src.common.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])


class AgentRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    context: Optional[Dict] = None


class FeedbackRateRequest(BaseModel):
    rating: int = Field(..., ge=-1, le=1)  # 1 = thumbs-up, -1 = thumbs-down


@router.post("/run")
async def run_agent(data: AgentRequest, current_user=Depends(get_current_user)):
    context = data.context or {}
    context["user_id"] = current_user.user_id
    result = await orchestrate(data.query, context)
    return result


@router.post("/feedback/{feedback_id}/rate")
async def rate_feedback(
    feedback_id: str,
    data: FeedbackRateRequest,
    _=Depends(get_current_user),
):
    """Record a user thumbs-up (1) or thumbs-down (-1) for a summary or chatbot response."""
    from src.agents.feedback_store import set_user_rating
    updated = await set_user_rating(feedback_id, data.rating)
    if not updated:
        raise HTTPException(status_code=404, detail="Feedback entry not found")
    return {"status": "ok", "feedback_id": feedback_id, "rating": data.rating}


@router.get("/feedback/stats")
async def feedback_stats(_=Depends(get_current_user)):
    """Aggregated quality stats for the observability dashboard."""
    from src.agents.feedback_store import get_feedback_stats
    return await get_feedback_stats()


@router.post("/delivery/recover")
async def trigger_delivery_recovery(current_user=Depends(get_current_user)):
    from src.agents.delivery_agent import DeliveryAgent
    agent = DeliveryAgent()
    result = await agent.run({})
    return result


@router.get("/delivery/rca")
async def delivery_rca(hours: int = 72, _=Depends(get_current_user)):
    """Root cause analysis for failed/queued messages in the last N hours."""
    from src.agents.rca_agent import RCAAgent
    agent = RCAAgent()
    return await agent.run({"hours": hours})


@router.get("/moderation/cross-group")
async def cross_group_moderation(_=Depends(get_current_user)):
    """Scan all groups for coordinated toxic patterns using cross-group intelligence."""
    from src.agents.cross_group_agent import CrossGroupModerationAgent
    agent = CrossGroupModerationAgent()
    return await agent.run({})
