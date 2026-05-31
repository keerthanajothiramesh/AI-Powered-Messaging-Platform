# Data Flow: Message Ingestion

Covers two ingestion paths: **real-time WebSocket send** and **bulk dataset load**.

---

## Real-Time Ingestion Flow

```mermaid
sequenceDiagram
    participant Client as React Client
    participant WS as WebSocket Manager
    participant MsgSvc as Messaging Service
    participant Mongo as MongoDB Atlas
    participant EmbSvc as Embedding Service
    participant PGVec as pgvector (Neon)

    Client->>WS: WS connect + JWT auth
    WS->>WS: Authenticate token, register connection
    Client->>WS: send {type: "message", content, group_id}

    WS->>MsgSvc: route to message handler
    MsgSvc->>MsgSvc: Validate content (PII guard + Pydantic)
    MsgSvc->>Mongo: insert message document<br/>{message_id, group_id, sender_id, content, timestamp}
    Mongo-->>MsgSvc: acknowledged

    MsgSvc->>WS: broadcast to online group members
    WS-->>Client: {type: "message", data: {...}}

    Note over MsgSvc,PGVec: Background embedding (non-blocking)
    MsgSvc->>EmbSvc: embed(content) → 384-dim vector
    EmbSvc->>PGVec: INSERT INTO message_embeddings (message_id, embedding, metadata)
    PGVec-->>EmbSvc: ok

    Note over MsgSvc,Mongo: Offline delivery queue
    MsgSvc->>Mongo: update delivery_status="failed"<br/>for offline receivers
```

---

## Bulk Dataset Ingestion Flow

Used during initial setup (`dataset/load_mongo.py`, `dataset/generate_embeddings.py`).

```mermaid
flowchart TD
    A[generate_dataset.py<br/>Faker — 150 users · 25 groups · 60k msgs] --> B[load_postgres.py<br/>Users + Groups → Neon PostgreSQL<br/>asyncpg connection pool]
    B --> C[load_mongo.py<br/>Messages + Events → MongoDB Atlas<br/>Motor async bulk insert<br/>batch size = 1000]
    C --> D[generate_embeddings.py<br/>Load messages from Mongo<br/>Batch embed via fastembed BAAI/bge-small-en-v1.5<br/>ONNX runtime — no GPU needed]
    D --> E[pgvector on Neon<br/>INSERT INTO message_embeddings<br/>group_id · sender_id · timestamp · language]

    style A fill:#f0f4ff
    style E fill:#e8f5e9
```

---

## Storage Schema

### PostgreSQL (Neon)
```
users(user_id UUID PK, display_name, email, language, created_at)
groups(group_id UUID PK, group_name, created_at)
group_members(group_id FK, user_id FK)
```

### MongoDB Atlas
```js
messages: {
  message_id: UUID,
  group_id: UUID,
  sender_id: UUID,
  content: String,
  timestamp: ISODate,
  delivery_status: "delivered" | "failed" | "pending",
  last_retry_at: ISODate,
  retry_count: Int,
  delivery_escalated: Bool,
  message_type: "text" | "image" | "file",
  language: "en" | "ja"
}
```

### pgvector on Neon PostgreSQL
```sql
message_embeddings (
  message_id  TEXT PRIMARY KEY,
  embedding   vector(384),        -- BAAI/bge-small-en-v1.5 via fastembed
  content     TEXT,
  sender_id   TEXT,
  group_id    TEXT,
  receiver_id TEXT,
  media_type  TEXT,
  language    TEXT
)
-- Cosine similarity index: embedding <=> query_vector
```

---

## Key Design Decisions

- **Async throughout**: asyncpg + Motor ensure zero blocking I/O during ingestion.
- **Batch insert to pgvector**: messages embedded and inserted in batches via `ON CONFLICT DO NOTHING` to avoid duplicates.
- **Embedding at ingest time**: vectors are pre-computed so search has zero embedding latency at query time.
- **MongoDB TTL index**: messages older than 30 days auto-expire from the failed-delivery queue.
