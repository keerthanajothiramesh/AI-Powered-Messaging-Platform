from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional

from src.auth.dependencies import get_current_user
from src.messaging.schemas import (
    SendDirectMessageRequest, SendGroupMessageRequest, MessageResponse
)
from src.messaging.message_service import (
    save_message, get_direct_messages, get_group_messages,
    mark_message_read, soft_delete_message, add_reaction,
    get_dm_conversation_list,
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
    return {"status": "ok"}


@router.delete("/{message_id}")
async def delete_message(message_id: str, current_user=Depends(get_current_user)):
    deleted = await soft_delete_message(message_id, current_user.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Message not found or not yours")
    return {"status": "deleted"}


@router.post("/{message_id}/react")
async def react_to_message(
    message_id: str,
    emoji: str = Query(..., max_length=5),
    current_user=Depends(get_current_user),
):
    await add_reaction(message_id, current_user.user_id, emoji)
    return {"status": "ok"}
