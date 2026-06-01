from fastapi import APIRouter, Depends, HTTPException, Query
from src.auth.dependencies import get_current_user
from src.common.database import get_mongo_db, get_pg_pool
from src.common.logger import get_logger
from src.messaging.message_service import (
    edit_message as edit_message_service,
    get_direct_messages, get_group_messages,
    mark_message_read, save_message, soft_delete_message,
)
from src.messaging.schemas import EditMessageRequest, SendDirectMessageRequest, SendGroupMessageRequest
from src.messaging.websocket_manager import get_connection_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/messages", tags=["messages"])


async def _embed_message(message_id: str, content: str, meta: dict) -> None:
    try:
        from src.ai.vector_store import get_vector_store
        vs = get_vector_store()
        if vs:
            await vs.add_message_async(message_id, content, meta)
    except Exception as exc:
        logger.warning("embedding_failed", error=str(exc))


def _to_response(msg: dict) -> dict:
    m = dict(msg)
    if "timestamp" in m and hasattr(m["timestamp"], "isoformat"):
        m["timestamp"] = m["timestamp"].isoformat()
    return m


@router.post("/direct", status_code=201)
async def send_direct_message(data: SendDirectMessageRequest, current_user=Depends(get_current_user)):
    manager = get_connection_manager()
    delivery_status = "sent" if not manager.is_online(data.receiver_id) else "delivered"
    msg = await save_message(
        sender_id=current_user.user_id, content=data.content,
        media_type=data.media_type.value, media_url=data.media_url,
        receiver_id=data.receiver_id, delivery_status=delivery_status,
    )
    event = {"type": "message", "data": _to_response(msg)}
    await manager.send_to_user(data.receiver_id, event)
    await manager.send_to_user(current_user.user_id, event)
    await _embed_message(msg["message_id"], data.content, {
        "sender_id": current_user.user_id, "receiver_id": data.receiver_id,
        "group_id": "", "media_type": data.media_type.value,
        "timestamp": msg["timestamp"].isoformat(), "language": "en",
    })
    return _to_response(msg)


@router.post("/group/{group_id}", status_code=201)
async def send_group_message(group_id: str, data: SendGroupMessageRequest, current_user=Depends(get_current_user)):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        member = await conn.fetchrow(
            "SELECT 1 FROM group_members WHERE group_id=$1 AND user_id=$2",
            group_id, current_user.user_id,
        )
        if not member:
            raise HTTPException(status_code=403, detail="Not a group member")
    msg = await save_message(
        sender_id=current_user.user_id, content=data.content,
        media_type=data.media_type.value, media_url=data.media_url,
        group_id=group_id, delivery_status="delivered",
    )
    manager = get_connection_manager()
    event = {"type": "message", "data": _to_response(msg)}
    await manager.broadcast_to_group(group_id, event, exclude_user=current_user.user_id)
    await manager.send_to_user(current_user.user_id, event)
    await _embed_message(msg["message_id"], data.content, {
        "sender_id": current_user.user_id, "group_id": group_id,
        "receiver_id": "", "media_type": data.media_type.value,
        "timestamp": msg["timestamp"].isoformat(), "language": "en",
    })
    return _to_response(msg)


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
    db = get_mongo_db()
    msg = await db.messages.find_one({"message_id": message_id}, {"sender_id": 1, "_id": 0})
    if msg and msg.get("sender_id") and msg["sender_id"] != current_user.user_id:
        await get_connection_manager().send_to_user(
            msg["sender_id"], {"type": "message_read", "data": {"message_id": message_id}}
        )
    return {"status": "ok"}


@router.put("/{message_id}")
async def update_message(message_id: str, data: EditMessageRequest, current_user=Depends(get_current_user)):
    updated = await edit_message_service(message_id, current_user.user_id, data.content)
    if not updated:
        raise HTTPException(status_code=404, detail="Message not found or not yours")
    manager = get_connection_manager()
    event = {
        "type": "message_edited",
        "data": {
            "message_id": message_id, "content": data.content,
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
            "message_id": message_id, "sender_id": str(msg.get("sender_id", "")),
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
