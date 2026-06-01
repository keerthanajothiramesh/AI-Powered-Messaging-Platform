"""Multilingual tool handlers: reply suggestions, voice decode, compose, explain."""
import json
import re
from typing import Any, Dict

from src.ai.gemini_client import generate_text
from src.common.database import get_pg_pool, get_mongo_db
from src.common.logger import get_logger

logger = get_logger(__name__)

_JSON_RE = re.compile(r'(\{.*\}|\[.*\])', re.DOTALL)


def _parse_json(raw: str) -> Any:
    m = _JSON_RE.search(raw)
    try:
        return json.loads(m.group()) if m else {}
    except Exception:
        return {}


async def _last_message(sender_name: str):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT user_id, display_name FROM users WHERE display_name ILIKE $1",
            f"%{sender_name}%",
        )
    if not user:
        return None, None
    db = get_mongo_db()
    msg = await db.messages.find_one(
        {"sender_id": str(user["user_id"])},
        sort=[("created_at", -1)],
    )
    return user, msg


async def suggest_replies_in_language(args: Dict, session) -> Any:
    sender_name = args["sender_name"]
    reply_lang = args.get("reply_language", "Japanese")
    n = int(args.get("num_options", 3))
    user, msg = await _last_message(sender_name)
    if not user:
        return {"error": f"User '{sender_name}' not found"}
    if not msg:
        return {"error": f"No messages found from {user['display_name']}"}
    content = msg.get("content", "")
    prompt = (
        f'Message received: "{content}"\n\n'
        f"Generate {n} reply options in {reply_lang}, each with:\n"
        f'- "reply": text in {reply_lang}\n'
        f'- "english": English translation\n'
        f'- "tone": casual/polite/formal\n\n'
        f'Return ONLY a JSON array: [{{"reply":"...","english":"...","tone":"..."}}]'
    )
    raw = await generate_text(prompt)
    parsed = _parse_json(raw)
    return {
        "original_message": content,
        "sender": user["display_name"],
        "reply_language": reply_lang,
        "suggestions": parsed if isinstance(parsed, list) else [],
    }


async def decode_voice_message(args: Dict, session) -> Any:
    sender_name = args["sender_name"]
    translate_to = args.get("translate_to", "English")
    user, msg = await _last_message(sender_name)
    if not user:
        return {"error": f"User '{sender_name}' not found"}
    if not msg:
        return {"error": f"No messages found from {user['display_name']}"}
    content = msg.get("content", "")
    content_type = msg.get("content_type", "text")
    if content_type in ("voice", "audio"):
        return {
            "sender": user["display_name"],
            "type": content_type,
            "note": "Audio transcription not available. Message stored as media URL.",
            "url": content,
        }
    prompt = (
        f'Analyze this message: "{content}"\n\n'
        f"Detect language, translate to {translate_to}, extract key points.\n"
        f'Return JSON: {{"detected_language":"...","translation":"...","key_points":["..."],"requires_action":true}}'
    )
    raw = await generate_text(prompt)
    parsed = _parse_json(raw)
    return {
        "sender": user["display_name"],
        "original": content,
        "sent_at": msg.get("created_at").isoformat() if msg.get("created_at") else None,
        **(parsed if isinstance(parsed, dict) else {"translation": raw}),
    }


async def compose_message_in_language(args: Dict, session) -> Any:
    intent = args["intent"]
    lang = args.get("language", "Japanese")
    recipient = args.get("recipient_name", "")
    formality = args.get("formality", "polite")
    ctx = f" for {recipient}" if recipient else ""
    prompt = (
        f'Compose a message{ctx} in {lang} conveying: "{intent}"\n\n'
        f"Provide all 3 formality levels (casual, polite, formal keigo).\n"
        f"For each: message in {lang}, English translation, when to use.\n"
        f'Return JSON: {{"options":[{{"formality":"...","message":"...","english":"...","use_when":"..."}}]}}'
    )
    raw = await generate_text(prompt)
    parsed = _parse_json(raw)
    return {
        "intent": intent,
        "language": lang,
        "recipient": recipient,
        "recommended_formality": formality,
        **(parsed if isinstance(parsed, dict) else {}),
    }


async def explain_message_context(args: Dict, session) -> Any:
    sender_name = args["sender_name"]
    include_cultural = args.get("include_cultural_notes", True)
    user, msg = await _last_message(sender_name)
    if not user:
        return {"error": f"User '{sender_name}' not found"}
    if not msg:
        return {"error": f"No messages found from {user['display_name']}"}
    content = msg.get("content", "")
    cultural = (
        "\nInclude cultural nuances (Japanese business), true intent vs literal meaning, "
        "indirect 'no' patterns (e.g. 検討します), politeness level signals."
        if include_cultural else ""
    )
    prompt = (
        f'Explain this message: "{content}"{cultural}\n\n'
        f'Return JSON: {{"language":"...","literal_translation":"...","intended_meaning":"...",'
        f'"cultural_note":"...","suggested_response_tone":"...","urgency":"low/medium/high"}}'
    )
    raw = await generate_text(prompt)
    parsed = _parse_json(raw)
    return {
        "sender": user["display_name"],
        "original_message": content,
        "sent_at": msg.get("created_at").isoformat() if msg.get("created_at") else None,
        **(parsed if isinstance(parsed, dict) else {"intended_meaning": raw}),
    }
