"""Supplementary message endpoints: unread images, reply suggestions, reactions."""
import json
import re
from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.auth.dependencies import get_current_user
from src.common.database import get_mongo_db, get_pg_pool
from src.common.logger import get_logger
from src.messaging.message_service import add_reaction, get_dm_conversation_list
from src.messaging.websocket_manager import get_connection_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/dm/conversations")
async def list_dm_conversations(current_user=Depends(get_current_user)):
    convs = await get_dm_conversation_list(current_user.user_id)
    if not convs:
        return []
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id, display_name, user_presence, avatar_url, last_seen "
            "FROM users WHERE user_id = ANY($1::uuid[])",
            [c["user_id"] for c in convs],
        )
    user_map = {str(r["user_id"]): r for r in rows}
    result = []
    for c in convs:
        u = user_map.get(c["user_id"])
        if u:
            result.append({
                "user_id": c["user_id"], "display_name": u["display_name"],
                "user_presence": u["user_presence"], "avatar_url": u["avatar_url"],
                "last_seen": u["last_seen"].isoformat() if u["last_seen"] else None,
                "last_message": c["last_message"], "last_timestamp": c["last_timestamp"],
            })
    return result


class SuggestRepliesRequest(BaseModel):
    message: str
    context: List[str] = []


@router.get("/unread-images")
async def get_unread_images(current_user=Depends(get_current_user)):
    """Return unread image messages across all conversations for the current user."""
    db = get_mongo_db()
    pool = get_pg_pool()
    user_id = str(current_user.user_id)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT g.group_id, g.group_name FROM groups g "
            "JOIN group_members gm ON g.group_id = gm.group_id WHERE gm.user_id = $1",
            user_id,
        )
    group_map = {str(r["group_id"]): r["group_name"] for r in rows}
    group_ids = list(group_map.keys())

    cursor = db.messages.find(
        {
            "media_type": "image",
            "$or": [
                {"receiver_id": user_id, "read_status": "unread"},
                {"group_id": {"$in": group_ids}, "sender_id": {"$ne": user_id},
                 "read_by": {"$not": {"$elemMatch": {"$eq": user_id}}}},
            ],
        },
        {"message_id": 1, "media_url": 1, "content": 1, "sender_id": 1,
         "group_id": 1, "receiver_id": 1, "timestamp": 1},
    ).limit(20).sort("timestamp", -1)

    results = []
    async for msg in cursor:
        gid = str(msg.get("group_id") or "")
        ts = msg.get("timestamp")
        results.append({
            "message_id": str(msg.get("message_id") or str(msg["_id"])),
            "media_url": msg.get("media_url") or "",
            "content": msg.get("content") or "",
            "sender_id": str(msg.get("sender_id") or ""),
            "group_id": gid,
            "receiver_id": str(msg.get("receiver_id") or ""),
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts or ""),
            "group_name": group_map.get(gid, ""),
        })
    return results


@router.post("/suggest-replies")
async def suggest_replies(
    data: SuggestRepliesRequest,
    current_user=Depends(get_current_user),
):
    from src.ai.gemini_client import generate_text

    context_block = ""
    if data.context:
        context_block = "Recent conversation:\n" + "\n".join(f"- {m}" for m in data.context[-4:]) + "\n\n"

    prompt = (
        f"{context_block}Latest message received: \"{data.message}\"\n\n"
        "Generate exactly 3 short, natural reply suggestions (each under 10 words). "
        "Return ONLY a raw JSON array of 3 strings — no markdown, no explanation. "
        'Example: ["Sure!", "Let me check.", "Sounds good!"]'
    )
    try:
        raw = await generate_text(prompt, temperature=0.6, max_tokens=150)
        raw = re.sub(r"```[a-z]*\n?", "", raw).strip()
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            suggestions = json.loads(match.group())
            suggestions = [str(s).strip() for s in suggestions if str(s).strip()][:3]
        else:
            suggestions = []
    except Exception as exc:
        logger.warning("suggest_replies_failed", error=str(exc))
        suggestions = []
    return {"suggestions": suggestions}


@router.post("/{message_id}/react")
async def react_to_message(
    message_id: str,
    emoji: str = Query(..., max_length=5),
    current_user=Depends(get_current_user),
):
    await add_reaction(message_id, current_user.user_id, emoji)

    db = get_mongo_db()
    msg = await db.messages.find_one(
        {"message_id": message_id},
        {"sender_id": 1, "receiver_id": 1, "group_id": 1, "_id": 0},
    )
    if msg:
        manager = get_connection_manager()
        event = {
            "type": "message_reaction",
            "data": {
                "message_id": message_id, "emoji": emoji,
                "user_id": current_user.user_id,
                "sender_id": str(msg.get("sender_id", "")),
                "receiver_id": str(msg["receiver_id"]) if msg.get("receiver_id") else None,
                "group_id": str(msg["group_id"]) if msg.get("group_id") else None,
            },
        }
        if msg.get("group_id"):
            await manager.broadcast_to_group(str(msg["group_id"]), event)
        else:
            await manager.send_to_user(str(msg.get("sender_id", "")), event)
            if msg.get("receiver_id") and str(msg["receiver_id"]) != current_user.user_id:
                await manager.send_to_user(str(msg["receiver_id"]), event)
    return {"status": "ok"}
