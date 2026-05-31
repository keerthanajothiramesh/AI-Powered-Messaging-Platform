from fastapi import APIRouter, Depends
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


@router.post("/run")
async def run_agent(data: AgentRequest, current_user=Depends(get_current_user)):
    context = data.context or {}
    context["user_id"] = current_user.user_id
    result = await orchestrate(data.query, context)
    return result


@router.post("/delivery/recover")
async def trigger_delivery_recovery(current_user=Depends(get_current_user)):
    from src.agents.delivery_agent import DeliveryAgent
    agent = DeliveryAgent()
    result = await agent.run({})
    return result
