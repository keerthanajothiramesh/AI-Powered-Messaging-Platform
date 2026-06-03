import json
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from datetime import datetime, timezone

from src.messaging.websocket_manager import get_connection_manager
from src.messaging.message_service import (
    save_message, get_queued_messages, update_delivery_status, mark_message_read
)
from src.auth.service import decode_token
from src.common.database import get_pg_pool
from src.common.logger import get_logger
from src.common.metrics import (
    messages_sent_total, messages_failed_total,
    message_delivery_latency_seconds, online_users,
)

logger = get_logger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, token: str = Query(...)):
    token_data = decode_token(token)
    if not token_data or token_data.user_id != user_id:
        await websocket.close(code=4001)
        logger.warning("ws_auth_failed", user_id=user_id)
        return

    manager = get_connection_manager()
    await manager.connect(user_id, websocket)
    online_users.inc()

    # Notify all connected users that this user came online
    await manager.broadcast_to_all(
        {"type": "user_online", "data": {"user_id": user_id}},
        exclude_user=user_id,
    )

    pool = get_pg_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET user_presence='online', last_seen=NOW() WHERE user_id=$1", user_id
        )
        groups = await conn.fetch(
            "SELECT group_id FROM group_members WHERE user_id=$1", user_id
        )
    for g in groups:
        manager.join_group(user_id, str(g["group_id"]))

    queued = await get_queued_messages(user_id)
    for msg in queued:
        await manager.send_to_user(user_id, {"type": "message", "data": _serialize_message(msg)})
        await update_delivery_status(msg["message_id"], "delivered")

    await manager.send_to_user(user_id, {
        "type": "connected",
        "data": {"user_id": user_id, "queued_count": len(queued)},
    })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type")

            if event_type == "send_message":
                await _handle_send_message(user_id, event.get("data", {}), manager)

            elif event_type == "mark_read":
                data = event.get("data", {})
                await mark_message_read(data.get("message_id"), user_id)
                sender_id = data.get("sender_id")
                if sender_id:
                    await manager.send_to_user(sender_id, {
                        "type": "message_read",
                        "data": {"message_id": data.get("message_id"), "reader_id": user_id},
                    })

            elif event_type == "typing":
                data = event.get("data", {})
                target = data.get("receiver_id") or data.get("group_id")
                if data.get("group_id"):
                    await manager.broadcast_to_group(
                        data["group_id"],
                        {"type": "typing", "data": {"user_id": user_id, "group_id": data["group_id"]}},
                        exclude_user=user_id,
                    )
                elif data.get("receiver_id"):
                    await manager.send_to_user(data["receiver_id"], {
                        "type": "typing",
                        "data": {"user_id": user_id},
                    })

            elif event_type == "ping":
                await manager.send_to_user(user_id, {"type": "pong"})

    except WebSocketDisconnect:
        online_users.dec()
        last_seen_ts = datetime.now(timezone.utc).isoformat()
        # Broadcast offline event before removing from active connections
        await manager.broadcast_to_all(
            {"type": "user_offline", "data": {"user_id": user_id, "last_seen": last_seen_ts}},
            exclude_user=user_id,
        )
        manager.disconnect(user_id)
        pool2 = get_pg_pool()
        async with pool2.acquire() as conn:
            await conn.execute(
                "UPDATE users SET user_presence='offline', last_seen=NOW() WHERE user_id=$1", user_id
            )
        logger.info("ws_disconnected_clean", user_id=user_id)


async def _handle_send_message(sender_id: str, data: dict, manager) -> None:
    receiver_id = data.get("receiver_id")
    group_id = data.get("group_id")
    content = data.get("content", "").strip()
    media_type = data.get("media_type", "text")
    media_url = data.get("media_url")

    if not content:
        return

    t0 = time.perf_counter()
    msg = await save_message(
        sender_id=sender_id,
        content=content,
        media_type=media_type,
        media_url=media_url,
        receiver_id=receiver_id,
        group_id=group_id,
        delivery_status="sent",
    )

    msg_type = "group" if group_id else "dm"
    messages_sent_total.labels(type=msg_type).inc()

    # Attach display_name so group chat can render sender names without extra lookups
    sender_name = ""
    if group_id:
        try:
            pool = get_pg_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT display_name FROM users WHERE user_id=$1", sender_id
                )
            sender_name = row["display_name"] if row else ""
        except Exception:
            pass

    serialized = _serialize_message(msg)
    if sender_name:
        serialized["sender_name"] = sender_name
    event = {"type": "message", "data": serialized}

    if group_id:
        delivered_to = await manager.broadcast_to_group(group_id, event, exclude_user=sender_id)
        if delivered_to:
            await update_delivery_status(msg["message_id"], "delivered")
            message_delivery_latency_seconds.observe(time.perf_counter() - t0)
        await manager.send_to_user(sender_id, event)
    elif receiver_id:
        delivered = await manager.send_to_user(receiver_id, event)
        await manager.send_to_user(sender_id, event)
        if delivered:
            await update_delivery_status(msg["message_id"], "delivered")
            message_delivery_latency_seconds.observe(time.perf_counter() - t0)
        else:
            await update_delivery_status(msg["message_id"], "queued")
            messages_failed_total.inc()

    try:
        from src.ai.embedding_service import get_embedding_service
        emb_svc = get_embedding_service()
        if emb_svc:
            from src.ai.vector_store import get_vector_store
            vs = get_vector_store()
            if vs:
                metadata = {
                    "sender_id": sender_id,
                    "group_id": group_id or "",
                    "receiver_id": receiver_id or "",
                    "media_type": media_type,
                    "timestamp": msg["timestamp"].isoformat(),
                    "language": msg.get("language", "en"),
                }
                await vs.add_message_async(msg["message_id"], content, metadata)
    except Exception as e:
        logger.warning("embedding_index_failed", error=str(e))


def _serialize_message(msg: dict) -> dict:
    m = dict(msg)
    if "timestamp" in m and hasattr(m["timestamp"], "isoformat"):
        m["timestamp"] = m["timestamp"].isoformat()
    return m
