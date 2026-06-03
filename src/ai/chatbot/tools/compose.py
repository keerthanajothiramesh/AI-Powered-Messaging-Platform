"""Chatbot tool handlers for composition — draft replies, translate messages, set status, and manage reminders."""
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Dict

from src.common.logger import get_logger

logger = get_logger(__name__)


async def draft_reply(args: Dict) -> Any:
    from src.ai.gemini_client import generate_text
    from src.search.search_service import hybrid_search

    results = await hybrid_search(args["message_about"], n_results=3)
    if not results:
        return {"error": "Could not find the message you're referring to"}

    original = results[0]["content"]
    tone = args.get("tone", "professional")
    prompt = (
        f"Original message: \"{original}\"\n\n"
        f"Write a {tone} reply to this message. "
        "Be concise (1-3 sentences). Return only the reply text, no preamble."
    )
    reply = await generate_text(prompt, max_tokens=200)
    return {"draft": reply, "original_message": original, "tone": tone}


async def translate_message(args: Dict) -> Any:
    from src.ai.gemini_client import generate_text
    from src.search.search_service import hybrid_search

    results = await hybrid_search(args["message_about"], n_results=1)
    if not results:
        return {"error": "Could not find the message to translate"}

    original = results[0]["content"]
    lang = args.get("language", "English")
    prompt = f'Translate this message to {lang}: "{original}"\nReturn only the translation.'
    translation = await generate_text(prompt, max_tokens=300)
    return {"original": original, "translation": translation, "language": lang}


async def set_my_status(args: Dict, session) -> Any:
    from src.common.database import get_pg_pool
    valid = {"online", "offline", "busy", "away"}
    status = args.get("status", "").lower()
    if status not in valid:
        return {"error": f"Invalid status. Choose from: {', '.join(sorted(valid))}"}
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET user_presence = $1 WHERE user_id = $2",
            status, str(session.user_id)
        )
    logger.info("status_updated", user_id=str(session.user_id), status=status)
    return {"updated": True, "status": status}


async def schedule_reminder(args: Dict, session) -> Any:
    from src.common.database import get_mongo_db
    db = get_mongo_db()
    remind_at_str = args.get("remind_at", "")
    remind_at = None
    try:
        remind_at = datetime.fromisoformat(remind_at_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        pass

    rid = str(_uuid.uuid4())
    await db.reminders.insert_one({
        "_id": rid, "reminder_id": rid,
        "user_id": str(session.user_id),
        "message": args["message"],
        "remind_at": remind_at,
        "remind_at_label": remind_at_str,
        "created_at": datetime.now(timezone.utc),
        "is_sent": False,
    })
    logger.info("reminder_scheduled", user_id=str(session.user_id), message=args["message"])
    return {
        "scheduled": True,
        "message": args["message"],
        "remind_at": remind_at.isoformat() if remind_at else remind_at_str or "no time set",
    }


async def get_reminders(session) -> Any:
    from src.common.database import get_mongo_db
    db = get_mongo_db()
    cursor = db.reminders.find(
        {"user_id": str(session.user_id), "is_sent": False},
        {"reminder_id": 1, "message": 1, "remind_at": 1, "remind_at_label": 1, "created_at": 1, "_id": 0},
    ).sort("created_at", -1).limit(20)
    reminders = await cursor.to_list(length=20)
    for r in reminders:
        if hasattr(r.get("remind_at"), "isoformat"):
            r["remind_at"] = r["remind_at"].isoformat()
        if hasattr(r.get("created_at"), "isoformat"):
            r["created_at"] = r["created_at"].isoformat()
    return {"reminders": reminders, "count": len(reminders)}
