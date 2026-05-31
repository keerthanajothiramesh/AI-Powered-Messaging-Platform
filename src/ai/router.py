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


@router.get("/health")
async def gemini_health(current_user=Depends(get_current_user)):
    """Test Gemini connectivity. Returns status and circuit breaker state."""
    from src.ai.gemini_client import generate_text, _circuit_open, _circuit_failures, get_gemini_client
    model_loaded = get_gemini_client() is not None
    try:
        response = await generate_text("Reply with the single word: ok", max_tokens=10)
        is_fallback = response.startswith("[Local fallback")
        return {
            "model_loaded": model_loaded,
            "circuit_open": _circuit_open,
            "circuit_failures": _circuit_failures,
            "gemini_live": not is_fallback,
            "response_preview": response[:60],
        }
    except Exception as e:
        return {
            "model_loaded": model_loaded,
            "circuit_open": _circuit_open,
            "circuit_failures": _circuit_failures,
            "gemini_live": False,
            "error": str(e),
        }


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


# ── Conversation topic tags ───────────────────────────────────────────────────

class TopicsRequest(BaseModel):
    messages: List[str] = Field(..., max_length=20)


@router.post("/topics")
async def detect_topics(data: TopicsRequest, current_user=Depends(get_current_user)):
    import json, re
    from src.ai.gemini_client import generate_text
    if not data.messages:
        return {"topics": []}
    snippet = "\n".join(f"- {m[:120]}" for m in data.messages[-12:])
    prompt = (
        "Analyse these recent chat messages and identify 2–4 main topics being discussed.\n"
        "Return ONLY a raw JSON array of short topic strings (2-3 words max each, lowercase, no #).\n"
        'Example: ["project deadline", "api design", "team standup"]\n\n'
        f"Messages:\n{snippet}"
    )
    try:
        raw = await generate_text(prompt, temperature=0.3, max_tokens=80)
        raw = re.sub(r"```[a-z]*\n?", "", raw).strip()
        match = re.search(r'\[.*?\]', raw, re.DOTALL)
        topics = json.loads(match.group()) if match else []
        topics = [str(t).strip().lower() for t in topics if str(t).strip()][:4]
    except Exception:
        topics = []
    return {"topics": topics}


# ── Smart message highlights ──────────────────────────────────────────────────

class HighlightMsg(BaseModel):
    message_id: str
    sender_name: str
    content: str


class HighlightsRequest(BaseModel):
    messages: List[HighlightMsg] = Field(..., max_length=60)


@router.post("/highlights")
async def smart_highlights(data: HighlightsRequest, current_user=Depends(get_current_user)):
    import json, re
    from src.ai.gemini_client import generate_text
    if not data.messages:
        return {"highlights": []}
    lines = "\n".join(
        f"[{i}] {m.sender_name}: {m.content[:150]}"
        for i, m in enumerate(data.messages)
    )
    prompt = (
        "You are analysing a team chat. Identify the 3 most important messages — "
        "ones containing decisions, deadlines, action items, urgent issues, or key announcements.\n"
        "Return ONLY a raw JSON array of objects with keys: index (integer), reason (≤8 words).\n"
        'Example: [{"index":2,"reason":"Deployment deadline set for Friday"},{"index":7,"reason":"Critical bug reported in prod"}]\n\n'
        f"Messages:\n{lines}"
    )
    try:
        raw = await generate_text(prompt, temperature=0.2, max_tokens=200)
        raw = re.sub(r"```[a-z]*\n?", "", raw).strip()
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        items = json.loads(match.group()) if match else []
        result = []
        for item in items[:3]:
            idx = int(item.get("index", -1))
            if 0 <= idx < len(data.messages):
                msg = data.messages[idx]
                result.append({
                    "message_id": msg.message_id,
                    "sender_name": msg.sender_name,
                    "content": msg.content,
                    "reason": str(item.get("reason", "Important message")),
                })
    except Exception:
        result = []
    return {"highlights": result}


# ── Message autocomplete ──────────────────────────────────────────────────────

class CompleteRequest(BaseModel):
    partial: str = Field(..., min_length=5, max_length=500)
    context: List[str] = []


@router.post("/complete")
async def autocomplete_message(data: CompleteRequest, current_user=Depends(get_current_user)):
    from src.ai.gemini_client import generate_text
    ctx = ""
    if data.context:
        ctx = "Recent messages:\n" + "\n".join(f"- {m[:100]}" for m in data.context[-3:]) + "\n\n"
    prompt = (
        f"{ctx}"
        f"The user is typing: \"{data.partial}\"\n\n"
        "Continue this message naturally in 5–12 words. "
        "Return ONLY the continuation text — no quotes, no repetition of what was typed."
    )
    try:
        completion = await generate_text(prompt, temperature=0.5, max_tokens=60)
        completion = completion.strip().strip('"').strip("'")
        return {"completion": completion}
    except Exception:
        return {"completion": ""}
