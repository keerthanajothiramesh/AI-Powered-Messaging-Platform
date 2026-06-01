"""AI text utility endpoints: translate, improve-draft, topics, highlights, autocomplete."""
import json
import re
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.auth.dependencies import get_current_user
from src.common.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/ai", tags=["ai"])

_LANG_NAMES: Dict[str, str] = {
    "en": "English", "ja": "Japanese", "es": "Spanish", "fr": "French",
    "de": "German", "hi": "Hindi", "zh": "Simplified Chinese",
    "ar": "Arabic", "pt": "Portuguese", "ko": "Korean", "ru": "Russian",
}
_TONE_INSTRUCTIONS: Dict[str, str] = {
    "professional": "Rewrite to be professional, clear, and business-appropriate. Remove slang.",
    "friendly":     "Rewrite to be warm, friendly, and approachable. Keep it conversational.",
    "concise":      "Rewrite to be as short and direct as possible. Cut filler words.",
    "formal":       "Rewrite to be formal and polished, suitable for senior stakeholders.",
}


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    target_language: str = Field(default="en", max_length=10)


class ImproveRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    tone: str = Field(default="professional")


class TopicsRequest(BaseModel):
    messages: List[str] = Field(..., max_length=20)


class HighlightMsg(BaseModel):
    message_id: str
    sender_name: str
    content: str


class HighlightsRequest(BaseModel):
    messages: List[HighlightMsg] = Field(..., max_length=60)


class CompleteRequest(BaseModel):
    partial: str = Field(..., min_length=5, max_length=500)
    context: List[str] = []


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


@router.post("/improve-draft")
async def improve_draft(data: ImproveRequest, current_user=Depends(get_current_user)):
    from src.ai.gemini_client import generate_text
    instruction = _TONE_INSTRUCTIONS.get(data.tone, _TONE_INSTRUCTIONS["professional"])
    prompt = f"{instruction} Return ONLY the rewritten message.\n\nOriginal: {data.text}"
    try:
        improved = await generate_text(prompt, temperature=0.4, max_tokens=500)
        return {"improved": improved.strip(), "tone": data.tone}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to improve draft")


@router.post("/topics")
async def detect_topics(data: TopicsRequest, current_user=Depends(get_current_user)):
    from src.ai.gemini_client import generate_text
    if not data.messages:
        return {"topics": []}
    snippet = "\n".join(f"- {m[:120]}" for m in data.messages[-12:])
    prompt = (
        "Identify 2–4 main topics from these chat messages. "
        "Return ONLY a raw JSON array of short topic strings (2-3 words, lowercase).\n"
        'Example: ["project deadline", "api design"]\n\nMessages:\n' + snippet
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


@router.post("/highlights")
async def smart_highlights(data: HighlightsRequest, current_user=Depends(get_current_user)):
    from src.ai.gemini_client import generate_text
    if not data.messages:
        return {"highlights": []}
    lines = "\n".join(f"[{i}] {m.sender_name}: {m.content[:150]}" for i, m in enumerate(data.messages))
    prompt = (
        "Identify the 3 most important messages — decisions, deadlines, action items, urgent issues.\n"
        "Return ONLY a raw JSON array: [{\"index\": int, \"reason\": \"≤8 words\"}]\n\n"
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
                    "message_id": msg.message_id, "sender_name": msg.sender_name,
                    "content": msg.content, "reason": str(item.get("reason", "Important message")),
                })
    except Exception:
        result = []
    return {"highlights": result}


@router.post("/complete")
async def autocomplete_message(data: CompleteRequest, current_user=Depends(get_current_user)):
    from src.ai.gemini_client import generate_text
    ctx = ""
    if data.context:
        ctx = "Recent messages:\n" + "\n".join(f"- {m[:100]}" for m in data.context[-3:]) + "\n\n"
    prompt = (
        f"{ctx}The user is typing: \"{data.partial}\"\n\n"
        "Continue this message naturally in 5–12 words. "
        "Return ONLY the continuation — no quotes, no repetition."
    )
    try:
        completion = await generate_text(prompt, temperature=0.5, max_tokens=60)
        return {"completion": completion.strip().strip('"').strip("'")}
    except Exception:
        return {"completion": ""}
