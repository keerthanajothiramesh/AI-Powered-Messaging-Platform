"""Generate pgvector embeddings for all messages using fastembed (local ONNX, no rate limits).
Reads messages directly from MongoDB Atlas — no local JSON files required.
"""
import asyncio
import time
from pathlib import Path
import sys
import os

sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(Path(__file__).parent.parent)

from dotenv import load_dotenv
load_dotenv()

NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL", "")
MONGODB_URL = os.getenv("MONGODB_URL", "")

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
BATCH_SIZE = 256


async def run():
    if not NEON_DATABASE_URL:
        print("ERROR: NEON_DATABASE_URL not set in .env")
        sys.exit(1)
    if not MONGODB_URL:
        print("ERROR: MONGODB_URL not set in .env")
        sys.exit(1)

    print(f"Loading embedding model: {MODEL_NAME} ({EMBEDDING_DIM}-dim, ONNX)")
    from fastembed import TextEmbedding
    model = TextEmbedding(MODEL_NAME)
    print("Model ready.\n")

    # Connect to MongoDB
    from motor.motor_asyncio import AsyncIOMotorClient
    mongo = AsyncIOMotorClient(MONGODB_URL)
    db = mongo["messaging_platform"]
    collection = db["messages"]

    total_in_mongo = await collection.count_documents({})
    print(f"MongoDB: {total_in_mongo:,} total messages")

    # Connect to Neon PostgreSQL
    import asyncpg
    from pgvector.asyncpg import register_vector

    clean_url = NEON_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(clean_url)
    await register_vector(conn)
    print("Connected to Neon PostgreSQL.")

    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS message_embeddings (
            message_id TEXT PRIMARY KEY,
            embedding vector(384),
            content TEXT NOT NULL,
            sender_id TEXT DEFAULT '',
            group_id TEXT DEFAULT '',
            receiver_id TEXT DEFAULT '',
            media_type TEXT DEFAULT 'text',
            language TEXT DEFAULT 'en',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    already = await conn.fetchval("SELECT COUNT(*) FROM message_embeddings")
    print(f"Already indexed: {already:,}\n")

    # Fetch already-indexed IDs to skip them
    existing_ids = set()
    if already > 0:
        rows = await conn.fetch("SELECT message_id FROM message_embeddings")
        existing_ids = {r["message_id"] for r in rows}
        print(f"Skipping {len(existing_ids):,} already-indexed messages.")

    total_indexed = 0
    batch = []
    t0 = time.time()

    cursor = collection.find(
        {"media_type": "text", "content": {"$exists": True, "$ne": ""}},
        {"message_id": 1, "content": 1, "sender_id": 1,
         "group_id": 1, "receiver_id": 1, "media_type": 1, "language": 1},
    )

    async for msg in cursor:
        mid = str(msg.get("message_id") or msg.get("_id", ""))
        if mid in existing_ids:
            continue
        batch.append({
            "message_id": mid,
            "content": msg["content"],
            "sender_id": str(msg.get("sender_id") or ""),
            "group_id": str(msg.get("group_id") or ""),
            "receiver_id": str(msg.get("receiver_id") or ""),
            "media_type": msg.get("media_type", "text"),
            "language": msg.get("language", "en"),
        })

        if len(batch) >= BATCH_SIZE:
            await _flush(conn, model, batch)
            total_indexed += len(batch)
            batch = []
            if total_indexed % 2000 == 0:
                elapsed = time.time() - t0
                print(f"  Indexed {total_indexed:,} ({total_indexed / max(elapsed, 1):.0f} msgs/sec)...")

    if batch:
        await _flush(conn, model, batch)
        total_indexed += len(batch)

    if total_indexed > 0:
        print("\nBuilding HNSW index...")
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS msg_emb_hnsw_idx
            ON message_embeddings USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """)

    count = await conn.fetchval("SELECT COUNT(*) FROM message_embeddings")
    await conn.close()
    mongo.close()

    elapsed = time.time() - t0
    print(f"\nEmbeddings complete!")
    print(f"  New this run  : {total_indexed:,}")
    print(f"  DB total      : {count:,}")
    print(f"  Time          : {elapsed:.1f}s")
    if total_indexed:
        print(f"  Rate          : {total_indexed / max(elapsed, 1):.0f} msgs/sec")


async def _flush(conn, model, batch):
    texts = [m["content"] for m in batch]
    vecs = list(model.embed(texts))
    records = [
        (
            m["message_id"], v.tolist(), m["content"],
            m["sender_id"], m["group_id"], m["receiver_id"],
            m["media_type"], m["language"],
        )
        for m, v in zip(batch, vecs)
    ]
    await conn.executemany(
        """INSERT INTO message_embeddings
           (message_id, embedding, content, sender_id, group_id, receiver_id, media_type, language)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
           ON CONFLICT (message_id) DO NOTHING""",
        records,
    )


if __name__ == "__main__":
    asyncio.run(run())
