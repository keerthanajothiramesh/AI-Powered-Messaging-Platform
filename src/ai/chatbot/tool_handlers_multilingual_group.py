"""Multilingual group handlers: cross-language catchup and per-speaker group summary."""
import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from src.ai.gemini_client import generate_text
from src.common.database import get_pg_pool, get_mongo_db
from src.common.logger import get_logger

logger = get_logger(__name__)

_JSON_RE = re.compile(r'\{.*\}', re.DOTALL)


def _parse_json(raw: str) -> dict:
    m = _JSON_RE.search(raw)
    try:
        return json.loads(m.group()) if m else {}
    except Exception:
        return {}


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
    return {
        "group": group["group_name"],
        "period_hours": hours,
        "message_count": len(msgs),
        "output_language": out_lang,
        "summary": summary,
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
