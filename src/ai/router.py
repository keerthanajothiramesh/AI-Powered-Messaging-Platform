from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime, timezone, timedelta

from src.auth.dependencies import get_current_user
from src.ai.rag_service import summarise_conversation, catch_up_summary, search_with_ai, extract_action_items
from src.ai.chatbot_service import get_or_create_session, clear_session
from src.common.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/ai", tags=["ai"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    filters: Optional[Dict] = None


class SummariseRequest(BaseModel):
    group_id: str
    days: int = Field(default=14, ge=1, le=90)


class CatchupRequest(BaseModel):
    hours_offline: int = Field(default=72, ge=1, le=720)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    reset_session: bool = False
    # Thread / session context
    session_id: Optional[str] = None
    conv_id: Optional[str] = None
    is_group: bool = False
    conv_name: Optional[str] = None
    other_user_id: Optional[str] = None


@router.post("/search")
async def ai_search(data: SearchRequest, current_user=Depends(get_current_user)):
    result = await search_with_ai(data.query, current_user.user_id, data.filters)
    return result


@router.post("/summarise")
async def summarise(data: SummariseRequest, current_user=Depends(get_current_user)):
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

    # Use SummarisationAgent — runs LLM-as-Judge and regenerates if quality < 7/10
    from src.agents.summarisation_agent import SummarisationAgent
    agent = SummarisationAgent()
    result = await agent.run({
        "group_id": data.group_id,
        "group_name": group_name,
        "days": data.days,
    })

    action_items = await extract_action_items(result["summary"])
    return {
        "group_id": data.group_id,
        "group_name": group_name,
        "days": data.days,
        "summary": result["summary"],
        "quality_score": round(result.get("quality_score", 0), 1),
        "feedback_id": result.get("feedback_id"),
        "action_items": action_items,
    }


@router.post("/catchup")
async def catchup_summary(data: CatchupRequest, current_user=Depends(get_current_user)):
    offline_since = datetime.now(timezone.utc) - timedelta(hours=data.hours_offline)
    result = await catch_up_summary(current_user.user_id, offline_since)
    return result


@router.post("/chat")
async def chat(data: ChatRequest, current_user=Depends(get_current_user)):
    sid = data.session_id or data.conv_id or "default"

    if data.reset_session:
        clear_session(current_user.user_id, sid)

    session = get_or_create_session(
        user_id=current_user.user_id,
        session_id=sid,
        conv_id=data.conv_id,
        is_group=data.is_group,
        conv_name=data.conv_name,
        other_user_id=data.other_user_id,
    )
    result = await session.chat(data.message)
    return result


@router.delete("/chat/session")
async def reset_chat_session(current_user=Depends(get_current_user)):
    clear_session(current_user.user_id)
    return {"message": "All sessions cleared"}


@router.delete("/chat/session/{session_id}")
async def delete_chat_session(session_id: str, current_user=Depends(get_current_user)):
    clear_session(current_user.user_id, session_id)
    return {"message": "Session cleared"}


# ── Inline translation ────────────────────────────────────────────────────────

class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    target_language: str = Field(default="en", max_length=10)


_LANG_NAMES: Dict[str, str] = {
    "en": "English", "ja": "Japanese", "es": "Spanish",
    "fr": "French", "de": "German", "hi": "Hindi",
    "zh": "Simplified Chinese", "ar": "Arabic", "pt": "Portuguese",
    "ko": "Korean", "ru": "Russian",
}


@router.post("/translate")
async def translate_message(data: TranslateRequest, current_user=Depends(get_current_user)):
    from src.ai.gemini_client import generate_text
    target_name = _LANG_NAMES.get(data.target_language, data.target_language)
    prompt = (
        f"Translate the following message to {target_name}. "
        "Return ONLY the translated text — no explanation, no quotes, no prefix.\n\n"
        f"{data.text}"
    )
    try:
        translated = await generate_text(prompt, temperature=0.2, max_tokens=500)
        return {"translated": translated.strip(), "target_language": data.target_language}
    except Exception:
        raise HTTPException(status_code=500, detail="Translation failed")


# ── AI draft tone improver ────────────────────────────────────────────────────

class ImproveRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    tone: str = Field(default="professional")


_TONE_INSTRUCTIONS: Dict[str, str] = {
    "professional": "Rewrite to be professional, clear, and business-appropriate. Remove slang.",
    "friendly":     "Rewrite to be warm, friendly, and approachable. Keep it conversational.",
    "concise":      "Rewrite to be as short and direct as possible. Cut filler words.",
    "formal":       "Rewrite to be formal and polished, suitable for senior stakeholders.",
}


@router.post("/improve-draft")
async def improve_draft(data: ImproveRequest, current_user=Depends(get_current_user)):
    from src.ai.gemini_client import generate_text
    instruction = _TONE_INSTRUCTIONS.get(data.tone, _TONE_INSTRUCTIONS["professional"])
    prompt = (
        f"{instruction} "
        "Return ONLY the rewritten message — no explanation, no quotes.\n\n"
        f"Original: {data.text}"
    )
    try:
        improved = await generate_text(prompt, temperature=0.4, max_tokens=500)
        return {"improved": improved.strip(), "tone": data.tone}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to improve draft")
