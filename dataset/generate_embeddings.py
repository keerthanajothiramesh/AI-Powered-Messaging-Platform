"""Generate ChromaDB embeddings for all messages."""
import asyncio
import json
from pathlib import Path
import sys
import os

sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(Path(__file__).parent.parent)

from dotenv import load_dotenv
load_dotenv()

DATA_DIR = Path(__file__).parent
CHROMA_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")


def run():
    print("Loading embedding model (this may take a minute)...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print("Model loaded")

    import chromadb
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(
        "messages", metadata={"hnsw:space": "cosine"}
    )
    print(f"ChromaDB collection ready, existing: {collection.count()}")

    msg_files = sorted(DATA_DIR.glob("messages_*.json"))
    total_indexed = 0
    batch_size = 500

    for f in msg_files:
        messages = json.loads(f.read_text(encoding="utf-8"))
        text_msgs = [m for m in messages if m.get("media_type") == "text" and m.get("content")]

        for i in range(0, len(text_msgs), batch_size):
            batch = text_msgs[i:i + batch_size]
            texts = [m["content"] for m in batch]
            ids = [m["message_id"] for m in batch]
            metadatas = [
                {
                    "sender_id": str(m.get("sender_id", "")),
                    "group_id": str(m.get("group_id", "") or ""),
                    "receiver_id": str(m.get("receiver_id", "") or ""),
                    "media_type": m.get("media_type", "text"),
                    "timestamp": str(m.get("timestamp", "")),
                    "language": m.get("language", "en"),
                }
                for m in batch
            ]

            try:
                embeddings = model.encode(texts, normalize_embeddings=True).tolist()
                existing = set(collection.get(ids=ids)["ids"])
                new_idx = [j for j, id_ in enumerate(ids) if id_ not in existing]
                if new_idx:
                    collection.add(
                        ids=[ids[j] for j in new_idx],
                        embeddings=[embeddings[j] for j in new_idx],
                        documents=[texts[j] for j in new_idx],
                        metadatas=[metadatas[j] for j in new_idx],
                    )
                    total_indexed += len(new_idx)
            except Exception as e:
                print(f"  Batch error: {e}")

            if total_indexed % 5000 == 0 and total_indexed > 0:
                print(f"  Indexed {total_indexed:,} messages so far...")

    print(f"Embeddings complete! Total indexed: {total_indexed:,}")
    print(f"Collection count: {collection.count():,}")


if __name__ == "__main__":
    run()
