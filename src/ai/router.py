"""Core AI REST endpoints — semantic search, group summarisation, catch-up summary, and chatbot."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.ai.chatbot_service import clear_session, get_or_create_session
from src.ai.rag_service import catch_up_summary, extract_action_items, search_with_ai
from src.auth.dependencies import get_current_user
from src.common.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/ai", tags=["ai"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    filters: Optional[dict] = None


class SummariseRequest(BaseModel):
    group_id: str
    days: int = Field(default=14, ge=1, le=90)


class CatchupRequest(BaseModel):
    hours_offline: int = Field(default=72, ge=1, le=720)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    reset_session: bool = False
    session_id: Optional[str] = None
    conv_id: Optional[str] = None
    is_group: bool = False
    conv_name: Optional[str] = None
    other_user_id: Optional[str] = None


@router.post("/search")
async def ai_search(data: SearchRequest, current_user=Depends(get_current_user)):
    return await search_with_ai(data.query, current_user.user_id, data.filters)


@router.post("/summarise")
async def summarise(data: SummariseRequest, current_user=Depends(get_current_user)):
    from src.agents.summarisation_agent import SummarisationAgent
    from src.common.database import get_pg_pool
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        member = await conn.fetchrow(
            "SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2",
            data.group_id, current_user.user_id,
        )
        if not member:
            raise HTTPException(status_code=403, detail="Not a group member")
        group = await conn.fetchrow("SELECT group_name FROM groups WHERE group_id=$1", data.group_id)
    group_name = group["group_name"] if group else "the group"
    result = await SummarisationAgent().run(
        {"group_id": data.group_id, "group_name": group_name, "days": data.days}
    )
    action_items = await extract_action_items(result["summary"])
    return {
        "group_id": data.group_id, "group_name": group_name, "days": data.days,
        "summary": result["summary"],
        "quality_score": round(result.get("quality_score", 0), 1),
        "feedback_id": result.get("feedback_id"),
        "action_items": action_items,
    }


@router.post("/catchup")
async def catchup_summary(data: CatchupRequest, current_user=Depends(get_current_user)):
    offline_since = datetime.now(timezone.utc) - timedelta(hours=data.hours_offline)
    return await catch_up_summary(current_user.user_id, offline_since)


@router.post("/chat")
async def chat(data: ChatRequest, current_user=Depends(get_current_user)):
    sid = data.session_id or data.conv_id or "default"
    if data.reset_session:
        clear_session(current_user.user_id, sid)
    session = get_or_create_session(
        user_id=current_user.user_id, session_id=sid,
        conv_id=data.conv_id, is_group=data.is_group,
        conv_name=data.conv_name, other_user_id=data.other_user_id,
    )
    return await session.chat(data.message)


@router.delete("/chat/session")
async def reset_chat_session(current_user=Depends(get_current_user)):
    clear_session(current_user.user_id)
    return {"message": "All sessions cleared"}


@router.delete("/chat/session/{session_id}")
async def delete_chat_session(session_id: str, current_user=Depends(get_current_user)):
    clear_session(current_user.user_id, session_id)
    return {"message": "Session cleared"}


@router.get("/health")
async def ai_health(current_user=Depends(get_current_user)):
    from src.ai.gemini_client import _circuit_open, _circuit_failures, generate_text, get_openai_client
    model_loaded = get_openai_client() is not None
    try:
        response = await generate_text("Reply with the single word: ok", max_tokens=10)
        is_fallback = response.startswith("[Local fallback")
        return {
            "model_loaded": model_loaded, "circuit_open": _circuit_open,
            "circuit_failures": _circuit_failures, "openai_live": not is_fallback,
            "response_preview": response[:60],
        }
    except Exception as exc:
        return {
            "model_loaded": model_loaded, "circuit_open": _circuit_open,
            "circuit_failures": _circuit_failures, "openai_live": False, "error": str(exc),
        }
