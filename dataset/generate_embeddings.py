"""Generate ChromaDB embeddings for all messages using Gemini text-embedding-004."""
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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

EMBEDDING_DIM = 768


def embed_batch(genai, texts: list[str]) -> list[list[float]]:
    results = []
    for text in texts:
        try:
            r = genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type="retrieval_document",
            )
            results.append(r["embedding"])
        except Exception as e:
            print(f"  Embedding error: {e}")
            results.append([0.0] * EMBEDDING_DIM)
        time.sleep(0.05)  # ~20 req/s to stay within free-tier quota
    return results


def run():
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY not set in .env")
        sys.exit(1)

    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    print("Gemini embedding API ready (text-embedding-004, 768-dim)")

    import chromadb
    # Delete stale collection if it exists with wrong dimension
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    try:
        client.delete_collection("messages")
        print("Deleted old 'messages' collection (dimension reset)")
    except Exception:
        pass

    collection = client.get_or_create_collection(
        "messages", metadata={"hnsw:space": "cosine"}
    )
    print(f"ChromaDB collection ready")

    msg_files = sorted(DATA_DIR.glob("messages_*.json"))
    total_indexed = 0
    batch_size = 50  # smaller batches for API rate limits

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
                existing = set(collection.get(ids=ids)["ids"])
                new_idx = [j for j, id_ in enumerate(ids) if id_ not in existing]
                if new_idx:
                    new_texts = [texts[j] for j in new_idx]
                    embeddings = embed_batch(genai, new_texts)
                    collection.add(
                        ids=[ids[j] for j in new_idx],
                        embeddings=embeddings,
                        documents=new_texts,
                        metadatas=[metadatas[j] for j in new_idx],
                    )
                    total_indexed += len(new_idx)
            except Exception as e:
                print(f"  Batch error: {e}")

            if total_indexed % 1000 == 0 and total_indexed > 0:
                print(f"  Indexed {total_indexed:,} messages so far...")

    print(f"Embeddings complete! Total indexed: {total_indexed:,}")
    print(f"Collection count: {collection.count():,}")


if __name__ == "__main__":
    run()
