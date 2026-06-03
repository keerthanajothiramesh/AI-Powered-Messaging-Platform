"""Batch embedding generator — embeds all demo text messages and upserts vectors into pgvector."""
import asyncio
from pathlib import Path

from src.admin.progress import set_step, set_total, increment
from src.common.logger import get_logger

logger = get_logger(__name__)

_BATCH_SIZE = 256


async def generate_demo_embeddings(pool, db) -> None:
    from src.ai.embedding_service import get_embedding_service
    from pgvector.asyncpg import register_vector

    svc = get_embedding_service()
    if not svc:
        logger.warning("demo_embeddings_skipped", reason="embedding service unavailable")
        return

    set_step("Generating embeddings (this takes a few minutes)")
    total = await db.messages.count_documents(
        {"is_demo": True, "media_type": "text", "content": {"$exists": True, "$ne": ""}}
    )
    set_total("embeddings_total", total)

    batch = []
    cursor = db.messages.find(
        {"is_demo": True, "media_type": "text", "content": {"$exists": True, "$ne": ""}},
        {"message_id": 1, "content": 1, "sender_id": 1, "group_id": 1,
         "receiver_id": 1, "media_type": 1, "language": 1},
    )

    async with pool.acquire() as conn:
        await register_vector(conn)
        async for msg in cursor:
            mid = str(msg.get("message_id") or msg.get("_id", ""))
            batch.append({
                "message_id": mid, "content": msg["content"],
                "sender_id": str(msg.get("sender_id") or ""),
                "group_id": str(msg.get("group_id") or ""),
                "receiver_id": str(msg.get("receiver_id") or ""),
                "media_type": msg.get("media_type", "text"),
                "language": msg.get("language", "en"),
            })
            if len(batch) >= _BATCH_SIZE:
                await _flush_embeddings(conn, svc, batch)
                increment("embeddings_loaded", len(batch))
                batch = []
        if batch:
            await _flush_embeddings(conn, svc, batch)
            increment("embeddings_loaded", len(batch))


async def _flush_embeddings(conn, svc, batch: list) -> None:
    texts = [m["content"] for m in batch]
    loop = asyncio.get_event_loop()
    vecs = await loop.run_in_executor(None, lambda: svc.batch_embed(texts))
    records = [
        (m["message_id"], v, m["content"], m["sender_id"], m["group_id"],
         m["receiver_id"], m["media_type"], m["language"], True)
        for m, v in zip(batch, vecs)
    ]
    await conn.executemany(
        """INSERT INTO message_embeddings
           (message_id, embedding, content, sender_id, group_id, receiver_id,
            media_type, language, is_demo)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
           ON CONFLICT (message_id) DO NOTHING""",
        records,
    )
