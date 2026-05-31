"""Generate ChromaDB embeddings for all messages using sentence-transformers (local, no rate limits)."""
import json
import time
from pathlib import Path
import sys
import os

sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(Path(__file__).parent.parent)

from dotenv import load_dotenv
load_dotenv()

DATA_DIR = Path(__file__).parent
CHROMA_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
BATCH_SIZE = 256  # sentence-transformers handles large batches efficiently on CPU


def run():
    print(f"Loading local embedding model: {MODEL_NAME} ({EMBEDDING_DIM}-dim)")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME)
    print("Model loaded.")

    import chromadb
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    # Reset collection so dimension matches the new model
    try:
        client.delete_collection("messages")
        print("Deleted old 'messages' collection (dimension reset)")
    except Exception:
        pass

    collection = client.get_or_create_collection(
        "messages", metadata={"hnsw:space": "cosine"}
    )
    print("ChromaDB collection ready")

    msg_files = sorted(DATA_DIR.glob("messages_*.json"))
    if not msg_files:
        print("No messages_*.json files found in dataset/. Run generate_dataset.py first.")
        sys.exit(1)

    total_indexed = 0
    t0 = time.time()

    for f in msg_files:
        messages = json.loads(f.read_text(encoding="utf-8"))
        text_msgs = [m for m in messages if m.get("media_type") == "text" and m.get("content")]

        for i in range(0, len(text_msgs), BATCH_SIZE):
            batch = text_msgs[i:i + BATCH_SIZE]
            ids = [m["message_id"] for m in batch]
            texts = [m["content"] for m in batch]
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
                existing = set(collection.get(ids=ids)["ids"])
                new_idx = [j for j, id_ in enumerate(ids) if id_ not in existing]
                if not new_idx:
                    continue

                new_texts = [texts[j] for j in new_idx]
                embeddings = model.encode(
                    new_texts,
                    batch_size=64,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                ).tolist()

                collection.add(
                    ids=[ids[j] for j in new_idx],
                    embeddings=embeddings,
                    documents=new_texts,
                    metadatas=[metadatas[j] for j in new_idx],
                )
                total_indexed += len(new_idx)
            except Exception as e:
                print(f"  Batch error: {e}")

            if total_indexed > 0 and total_indexed % 2000 == 0:
                elapsed = time.time() - t0
                rate = total_indexed / elapsed
                print(f"  Indexed {total_indexed:,} messages ({rate:.0f}/s)...")

    elapsed = time.time() - t0
    print(f"\nEmbeddings complete!")
    print(f"  Total indexed : {total_indexed:,}")
    print(f"  Collection    : {collection.count():,}")
    print(f"  Time          : {elapsed:.1f}s")
    print(f"  Rate          : {total_indexed / max(elapsed, 1):.0f} msgs/sec")


if __name__ == "__main__":
    run()
