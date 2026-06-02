"""Multilingual tool handlers: reply suggestions, voice decode, compose, explain, group summaries."""
import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
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


async def _get_group(group_name: str):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT group_id, group_name FROM groups WHERE group_name ILIKE $1",
            f"%{group_name}%",
        )


async def _resolve_names(sender_ids: list) -> dict:
    if not sender_ids:
        return {}
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id::text, display_name FROM users WHERE user_id::text = ANY($1)",
            sender_ids,
        )
    return {r["user_id"]: r["display_name"] for r in rows}


# ── Per-sender tools ───────────────────────────────────────────────────────────

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


# ── Group-level multilingual tools ────────────────────────────────────────────

async def cross_language_catchup(args: Dict, session) -> Any:
    group = await _get_group(args["group_name"])
    if not group:
        return {"error": f"Group '{args['group_name']}' not found"}
    hours = int(args.get("hours_ago", 8))
    out_lang = args.get("output_language", "English")
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    db = get_mongo_db()
    msgs = await db.messages.find(
        {"group_id": str(group["group_id"]), "created_at": {"$gte": since}},
    ).sort("created_at", 1).limit(100).to_list(length=100)
    if not msgs:
        return {"group": group["group_name"], "message": "No messages found in this time period."}
    sender_ids = list({m.get("sender_id", "") for m in msgs if m.get("sender_id")})
    name_map = await _resolve_names(sender_ids)
    lines = "\n".join(
        f"{name_map.get(m.get('sender_id', ''), 'Unknown')}: {m.get('content', '')}"
        for m in msgs
    )
    prompt = (
        f"Group: {group['group_name']} — last {hours} hours ({len(msgs)} messages).\n"
        f"Messages may be in multiple languages including Japanese.\n\n{lines[:3000]}\n\n"
        f"Summarize in {out_lang}: key topics, decisions, action items, deadlines. "
        f"Translate any non-{out_lang} content. Be concise and actionable."
    )
    summary = await generate_text(prompt)

    from src.agents.judge_agent import JudgeAgent
    judgment = await JudgeAgent().evaluate(
        summary, {"group_name": group["group_name"], "days": round(hours / 24, 1)}
    )
    if judgment.get("average_score", 10) < 7:
        logger.warning("cross_language_catchup_quality_low",
                       group=group["group_name"], score=judgment["average_score"])
        refined_prompt = (
            f"{prompt}\n\n"
            f"Previous attempt scored {judgment['average_score']:.1f}/10. "
            f"Issues: {judgment.get('feedback', '')}. "
            f"Improve the summary, ensure all non-{out_lang} content is translated."
        )
        summary = await generate_text(refined_prompt)

    return {
        "group": group["group_name"],
        "period_hours": hours,
        "message_count": len(msgs),
        "output_language": out_lang,
        "summary": summary,
        "quality_score": round(judgment.get("average_score", 0), 1),
    }


async def multilingual_group_summary(args: Dict, session) -> Any:
    group = await _get_group(args["group_name"])
    if not group:
        return {"error": f"Group '{args['group_name']}' not found"}
    days = int(args.get("days", 7))
    out_lang = args.get("output_language", "English")
    since = datetime.now(timezone.utc) - timedelta(days=days)
    db = get_mongo_db()
    msgs = await db.messages.find(
        {"group_id": str(group["group_id"]), "created_at": {"$gte": since}, "content_type": "text"},
    ).sort("created_at", -1).limit(150).to_list(length=150)
    if not msgs:
        return {"group": group["group_name"], "message": "No messages found."}
    by_sender: Dict[str, list] = {}
    for m in msgs:
        by_sender.setdefault(m.get("sender_id", ""), []).append(m.get("content", ""))
    name_map = await _resolve_names(list(by_sender.keys()))

    async def _summarize_one(sid: str, texts: list) -> dict:
        name = name_map.get(sid, "Unknown")
        snippet = "\n".join(texts[:15])
        p = (
            f"{name} sent these messages:\n{snippet}\n\n"
            f"In {out_lang}: detect language, summarize what {name} discussed (2 sentences), list action items.\n"
            f'Return JSON: {{"name":"{name}","language":"...","summary":"...","actions":[]}}'
        )
        raw = await generate_text(p)
        return _parse_json(raw) or {"name": name, "summary": "Unable to summarize."}

    results = await asyncio.gather(
        *[_summarize_one(sid, txts) for sid, txts in by_sender.items()],
        return_exceptions=True,
    )
    speakers = [r for r in results if not isinstance(r, Exception) and r]
    return {
        "group": group["group_name"],
        "days": days,
        "output_language": out_lang,
        "total_messages": len(msgs),
        "speakers": speakers,
    }
