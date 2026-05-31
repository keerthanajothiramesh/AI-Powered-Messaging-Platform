from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel

from src.auth.dependencies import get_current_user
from src.messaging.schemas import (
    SendDirectMessageRequest, SendGroupMessageRequest, MessageResponse, EditMessageRequest
)
from src.messaging.message_service import (
    save_message, get_direct_messages, get_group_messages,
    mark_message_read, soft_delete_message, add_reaction,
    get_dm_conversation_list, edit_message as edit_message_service,
)
from src.messaging.websocket_manager import get_connection_manager
from src.common.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/messages", tags=["messages"])


def _to_response(msg: dict) -> dict:
    m = dict(msg)
    if "timestamp" in m and hasattr(m["timestamp"], "isoformat"):
        m["timestamp"] = m["timestamp"].isoformat()
    return m


@router.post("/direct", status_code=201)
async def send_direct_message(
    data: SendDirectMessageRequest,
    current_user=Depends(get_current_user),
):
    manager = get_connection_manager()
    is_online = manager.is_online(data.receiver_id)
    delivery_status = "sent" if not is_online else "delivered"

    msg = await save_message(
        sender_id=current_user.user_id,
        content=data.content,
        media_type=data.media_type.value,
        media_url=data.media_url,
        receiver_id=data.receiver_id,
        delivery_status=delivery_status,
    )

    event = {"type": "message", "data": _to_response(msg)}
    await manager.send_to_user(data.receiver_id, event)
    await manager.send_to_user(current_user.user_id, event)

    try:
        from src.ai.vector_store import get_vector_store
        vs = get_vector_store()
        if vs:
            await vs.add_message_async(msg["message_id"], data.content, {
                "sender_id": current_user.user_id,
                "receiver_id": data.receiver_id,
                "group_id": "",
                "media_type": data.media_type.value,
                "timestamp": msg["timestamp"].isoformat(),
                "language": "en",
            })
    except Exception as e:
        logger.warning("embedding_failed", error=str(e))

    return _to_response(msg)


@router.post("/group/{group_id}", status_code=201)
async def send_group_message(
    group_id: str,
    data: SendGroupMessageRequest,
    current_user=Depends(get_current_user),
):
    from src.common.database import get_pg_pool
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        member = await conn.fetchrow(
            "SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2",
            group_id, current_user.user_id,
        )
        if not member:
            raise HTTPException(status_code=403, detail="Not a group member")

    msg = await save_message(
        sender_id=current_user.user_id,
        content=data.content,
        media_type=data.media_type.value,
        media_url=data.media_url,
        group_id=group_id,
        delivery_status="delivered",
    )

    manager = get_connection_manager()
    event = {"type": "message", "data": _to_response(msg)}
    await manager.broadcast_to_group(group_id, event, exclude_user=current_user.user_id)
    await manager.send_to_user(current_user.user_id, event)

    try:
        from src.ai.vector_store import get_vector_store
        vs = get_vector_store()
        if vs:
            await vs.add_message_async(msg["message_id"], data.content, {
                "sender_id": current_user.user_id,
                "group_id": group_id,
                "receiver_id": "",
                "media_type": data.media_type.value,
                "timestamp": msg["timestamp"].isoformat(),
                "language": "en",
            })
    except Exception as e:
        logger.warning("embedding_failed", error=str(e))

    return _to_response(msg)


@router.get("/dm/conversations")
async def list_dm_conversations(current_user=Depends(get_current_user)):
    from src.common.database import get_pg_pool
    convs = await get_dm_conversation_list(current_user.user_id)
    if not convs:
        return []
    pool = get_pg_pool()
    user_ids = [c["user_id"] for c in convs]
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id, display_name, user_presence, avatar_url FROM users WHERE user_id = ANY($1::uuid[])",
            user_ids,
        )
    user_map = {str(r["user_id"]): r for r in rows}
    result = []
    for c in convs:
        u = user_map.get(c["user_id"])
        if u:
            result.append({
                "user_id": c["user_id"],
                "display_name": u["display_name"],
                "user_presence": u["user_presence"],
                "avatar_url": u["avatar_url"],
                "last_message": c["last_message"],
                "last_timestamp": c["last_timestamp"],
            })
    return result


@router.get("/conversation/{other_user_id}")
async def get_conversation(
    other_user_id: str,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current_user=Depends(get_current_user),
):
    messages = await get_direct_messages(current_user.user_id, other_user_id, limit, skip)
    return [_to_response(m) for m in messages]


@router.get("/group/{group_id}/history")
async def get_group_history(
    group_id: str,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current_user=Depends(get_current_user),
):
    from src.common.database import get_pg_pool
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        member = await conn.fetchrow(
            "SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2",
            group_id, current_user.user_id,
        )
        if not member:
            raise HTTPException(status_code=403, detail="Not a group member")

    messages = await get_group_messages(group_id, limit, skip)
    return [_to_response(m) for m in messages]


@router.put("/{message_id}/read")
async def read_message(message_id: str, current_user=Depends(get_current_user)):
    await mark_message_read(message_id, current_user.user_id)

    # Notify the original sender so their tick turns blue in real-time
    from src.common.database import get_mongo_db
    db = get_mongo_db()
    msg = await db.messages.find_one({"message_id": message_id}, {"sender_id": 1, "_id": 0})
    if msg and msg.get("sender_id") and msg["sender_id"] != current_user.user_id:
        manager = get_connection_manager()
        await manager.send_to_user(msg["sender_id"], {
            "type": "message_read",
            "data": {"message_id": message_id},
        })

    return {"status": "ok"}


@router.put("/{message_id}")
async def update_message(
    message_id: str, data: EditMessageRequest, current_user=Depends(get_current_user)
):
    updated = await edit_message_service(message_id, current_user.user_id, data.content)
    if not updated:
        raise HTTPException(status_code=404, detail="Message not found or not yours")

    manager = get_connection_manager()
    event = {
        "type": "message_edited",
        "data": {
            "message_id": message_id,
            "content": data.content,
            "sender_id": str(updated.get("sender_id", "")),
            "receiver_id": str(updated["receiver_id"]) if updated.get("receiver_id") else None,
            "group_id": str(updated["group_id"]) if updated.get("group_id") else None,
        },
    }
    if updated.get("group_id"):
        await manager.broadcast_to_group(str(updated["group_id"]), event, exclude_user=current_user.user_id)
    elif updated.get("receiver_id"):
        await manager.send_to_user(str(updated["receiver_id"]), event)
    await manager.send_to_user(current_user.user_id, event)

    return _to_response(updated)


@router.delete("/{message_id}")
async def delete_message(message_id: str, current_user=Depends(get_current_user)):
    from src.common.database import get_mongo_db
    db = get_mongo_db()
    msg = await db.messages.find_one({"message_id": message_id, "sender_id": current_user.user_id})
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found or not yours")

    deleted = await soft_delete_message(message_id, current_user.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Message not found or not yours")

    manager = get_connection_manager()
    event = {
        "type": "message_deleted",
        "data": {
            "message_id": message_id,
            "sender_id": str(msg.get("sender_id", "")),
            "receiver_id": str(msg["receiver_id"]) if msg.get("receiver_id") else None,
            "group_id": str(msg["group_id"]) if msg.get("group_id") else None,
        },
    }
    if msg.get("group_id"):
        await manager.broadcast_to_group(str(msg["group_id"]), event, exclude_user=current_user.user_id)
    elif msg.get("receiver_id"):
        await manager.send_to_user(str(msg["receiver_id"]), event)
    await manager.send_to_user(current_user.user_id, event)

    return {"status": "deleted"}


class SuggestRepliesRequest(BaseModel):
    message: str
    context: List[str] = []


@router.post("/suggest-replies")
async def suggest_replies(
    data: SuggestRepliesRequest,
    current_user=Depends(get_current_user),
):
    import json, re
    from src.ai.gemini_client import generate_text

    context_block = ""
    if data.context:
        context_block = "Recent conversation:\n" + "\n".join(f"- {m}" for m in data.context[-4:]) + "\n\n"

    prompt = (
        f"{context_block}"
        f"Latest message received: \"{data.message}\"\n\n"
        "Generate exactly 3 short, natural reply suggestions (each under 10 words). "
        "Return ONLY a JSON array of 3 strings, no explanation or markdown."
    )

    try:
        raw = await generate_text(prompt, temperature=0.6, max_tokens=120)
        match = re.search(r'\[.*?\]', raw, re.DOTALL)
        if match:
            suggestions = json.loads(match.group())
            suggestions = [str(s).strip() for s in suggestions if s][:3]
        else:
            suggestions = []
    except Exception as e:
        logger.warning("suggest_replies_failed", error=str(e))
        suggestions = []

    return {"suggestions": suggestions}


@router.post("/{message_id}/react")
async def react_to_message(
    message_id: str,
    emoji: str = Query(..., max_length=5),
    current_user=Depends(get_current_user),
):
    await add_reaction(message_id, current_user.user_id, emoji)
    return {"status": "ok"}
