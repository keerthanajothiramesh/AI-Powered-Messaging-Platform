"""Generate pgvector embeddings for all messages using fastembed (local ONNX, no rate limits)."""
import json
import asyncio
import time
from pathlib import Path
import sys
import os

sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(Path(__file__).parent.parent)

from dotenv import load_dotenv
load_dotenv()

DATA_DIR = Path(__file__).parent
NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL", "")

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
BATCH_SIZE = 256


async def run():
    if not NEON_DATABASE_URL:
        print("ERROR: NEON_DATABASE_URL not set in .env")
        sys.exit(1)

    print(f"Loading embedding model: {MODEL_NAME} ({EMBEDDING_DIM}-dim, ONNX)")
    from fastembed import TextEmbedding
    model = TextEmbedding(MODEL_NAME)
    print("Model ready.")

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
    print("pgvector table ready.")

    msg_files = sorted(DATA_DIR.glob("messages_*.json"))
    if not msg_files:
        print("No messages_*.json files found. Run generate_dataset.py first.")
        await conn.close()
        sys.exit(1)

    total_indexed = 0
    t0 = time.time()

    for f in msg_files:
        messages = json.loads(f.read_text(encoding="utf-8"))
        text_msgs = [m for m in messages if m.get("media_type") == "text" and m.get("content")]

        for i in range(0, len(text_msgs), BATCH_SIZE):
            batch = text_msgs[i:i + BATCH_SIZE]
            texts = [m["content"] for m in batch]
            vecs = list(model.embed(texts))

            records = [
                (
                    m["message_id"],
                    v.tolist(),
                    m["content"],
                    str(m.get("sender_id", "")),
                    str(m.get("group_id", "") or ""),
                    str(m.get("receiver_id", "") or ""),
                    m.get("media_type", "text"),
                    m.get("language", "en"),
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
            total_indexed += len(records)

            if total_indexed % 5000 == 0:
                elapsed = time.time() - t0
                print(f"  Indexed {total_indexed:,} ({total_indexed / elapsed:.0f} msgs/sec)...")

    # Create HNSW index after data is loaded for optimal performance
    print("Building HNSW index...")
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS msg_emb_hnsw_idx
        ON message_embeddings USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    count = await conn.fetchval("SELECT COUNT(*) FROM message_embeddings")
    await conn.close()

    elapsed = time.time() - t0
    print(f"\nEmbeddings complete!")
    print(f"  Total indexed : {total_indexed:,}")
    print(f"  DB row count  : {count:,}")
    print(f"  Time          : {elapsed:.1f}s")
    print(f"  Rate          : {total_indexed / max(elapsed, 1):.0f} msgs/sec")


if __name__ == "__main__":
    asyncio.run(run())
