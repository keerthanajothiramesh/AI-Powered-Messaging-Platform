# Design Document — AI-Powered Messaging Platform

**Version:** 1.0  
**Date:** June 2026  
**Author:** Keerthana Jayaraman  
**Organisation:** Prodapt Solutions  

---

## 1. Executive Summary

This document describes the design of an AI-Powered Messaging Platform POC that combines real-time communication at scale with Generative AI, NLP, and Agentic AI-driven conversational intelligence. The platform enables 1:1 and group messaging, AI semantic search, RAG-enabled conversation summarisation, multi-agent orchestration, and intelligent catch-up summaries — all built on a polyglot persistence architecture deployed on cloud infrastructure.

---

## 2. Problem Statement

Modern enterprise messaging platforms face four core pain points:

| Pain Point | Description |
|---|---|
| **Manual Search** | Users scroll through hundreds of messages to find information — 100% manual, keyword-only |
| **Context Loss** | Users offline for days miss key decisions with no structured way to catch up |
| **No Summarisation** | Group conversations with 100+ participants have no AI-generated summaries |
| **Unstructured Retrieval** | Media files (images, voice, video) are impossible to retrieve by content |

**Cycle time impact:** Hours wasted per user per week catching up on missed conversations.

---

## 3. Solution Overview

An AI-powered messaging platform that transforms the user experience:

| Capability | Technology | Outcome |
|---|---|---|
| Real-time messaging | WebSocket (FastAPI) | < 500ms delivery |
| Semantic search | BAAI/bge-small-en-v1.5 + pgvector + BM25 + RRF | Exact message retrieval |
| Group summarisation | RAG + OpenAI GPT-4o-mini + LLM-as-Judge | 2-week history in < 3s |
| Catch-up summary | RAG + multi-agent | Structured missed messages on reconnect |
| Media retrieval | pgvector semantic search | Find images/voice by description |
| Multi-language | langdetect + OpenAI | English + Japanese supported |

---

## 4. System Architecture

### 4.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  CLIENT LAYER                                       [Vercel]    │
│  React 18 + Vite + TailwindCSS — 8 Screens                     │
│  REST API + WebSocket Client                                    │
└───────────────────────────↓─────────────────────────────────────┘
                    HTTPS / WSS (port 443)
┌─────────────────────────────────────────────────────────────────┐
│  API GATEWAY / BACKEND                              [Render]    │
│  FastAPI · Python 3.12 · JWT Auth + Google OAuth               │
│  Pydantic Validation · Prometheus Middleware                    │
└──┬──────────┬──────────┬──────────┬──────────┬─────────────────┘
   ↓          ↓          ↓          ↓          ↓
┌──────────┐┌─────────┐┌─────────┐┌──────────┐┌──────┐┌────────┐
│Messaging ││AI Service││ Search  ││  Agents  ││Media ││ Admin  │
│WebSocket ││RAG+Chat ││BM25+RRF ││LangGraph ││S3+   ││ Notif  │
│REST      ││PII+Lang ││Semantic ││Orchestrat││Local ││        │
└──────────┘└─────────┘└─────────┘└──────────┘└──────┘└────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  AI / ML LAYER                                                  │
│  OpenAI GPT-4o-mini (LLM)                                      │
│  BAAI/bge-small-en-v1.5 via fastembed-ONNX (384-dim embeddings)│
│  Flan-T5 Small — Local CPU Fallback                            │
│  Circuit Breaker · PII Guard · Language Detection              │
└──────────────────────────↓──────────────────────────────────────┘
┌────────────────┬──────────────────┬────────────┬───────────────┐
│ Neon PostgreSQL│  MongoDB Atlas   │pgvector    │ AWS S3        │
│ users · groups │messages · events │(Neon)      │ap-south-1     │
│                │delivery tracking │embeddings  │media files    │
└────────────────┴──────────────────┴────────────┴───────────────┘
┌─────────────────────────────────────────────────────────────────┐
│  OBSERVABILITY                                                  │
│  /health · /metrics (Prometheus) · Structured JSON Logs        │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Technology Stack

| Layer | Technology | Reason |
|---|---|---|
| Frontend | React 18 + Vite + TailwindCSS | Fast SPA, hot reload, utility-first CSS |
| Backend | FastAPI + Python 3.12 | Async-first, Pydantic validation, WebSocket native |
| LLM | OpenAI GPT-4o-mini | Multilingual, native function calling, reliable quota |
| Embeddings | BAAI/bge-small-en-v1.5 (fastembed-ONNX) | Fast CPU inference, 384-dim, high retrieval quality |
| Vector DB | pgvector on Neon PostgreSQL | Co-located with relational data, no extra managed service |
| Message Store | MongoDB Atlas | Flexible schema, TTL indexes, horizontal scaling |
| Agents | LangGraph | Built-in state machine, graph-based routing, observability |
| Search | BM25 (rank-bm25) + pgvector + RRF | Hybrid precision — exact + semantic without weight tuning |
| Media | AWS S3 ap-south-1 + local fallback | Durable object storage, graceful degradation |
| Deployment | Render (backend) + Vercel (frontend) | Zero-config cloud, auto-scaling |

---

## 5. Data Flow

### 5.1 Message Ingestion Flow

```
User sends message via WebSocket /ws/{user_id}
        ↓
JWT token authentication on connect
        ↓
save_message() → MongoDB Atlas
  [delivery_status: "sent", read_status: "unread"]
        ↓
Group → broadcast_to_group()   |   DM → send_to_user()
        ↓                              ↓
delivery_status: "delivered"    delivered → "delivered"
                                offline  → "queued" (TTL 30 days)
        ↓ [async, non-blocking — try/except]
BAAI/bge-small-en-v1.5 (fastembed-ONNX)
→ 384-dim embedding generated
→ INSERT INTO message_embeddings (pgvector · Neon)
  ON CONFLICT (message_id) DO NOTHING
```

### 5.2 Hybrid Search Flow

```
POST /api/search {query, filters, n_results}
        ↓
asyncio.gather — 3 parallel operations:
  ├─ Semantic: embed query → pgvector
  │   ORDER BY embedding <=> $1 (cosine distance) LIMIT n
  ├─ BM25: fetch 2,000 text messages from MongoDB
  │   → BM25Okapi tokenize + score
  └─ Doc chunks: pgvector document_chunks table
        ↓
Reciprocal Rank Fusion (k=60)
  score = Σ 1/(60 + rank_i)
        ↓
Dedup by message_id, append document extras
        ↓
Return top N results
```

### 5.3 RAG Summarisation Flow

```
POST /api/ai/summarise {group_id, days}
        ↓
MongoDB: fetch messages last N days (cap: 5,000)
        ↓
Neon PostgreSQL: resolve sender UUIDs → display_names
  (single query: SELECT user_id, display_name WHERE user_id = ANY($1))
        ↓
tiktoken (cl100k_base) token counting
  Chunk: 3,000 token limit · 3-message overlap
        ↓
Parallel batch (5×) → OpenAI GPT-4o-mini
        ↓
Combined summaries > 6,000 tokens?
  YES → Hierarchical merge (recursive sub-batching)
  NO  → Single merge call
        ↓
LLM-as-Judge (OpenAI GPT-4o-mini)
  Scores: Relevance · Accuracy · Completeness (0–10 each)
        ↓
Average score < 7? → Regenerate with feedback prompt
        ↓
Save judgment to MongoDB (feedback loop for future few-shot)
        ↓
Return summary + token_stats + quality_score
```

---

## 6. Multi-Agent Orchestration (LangGraph)

### 6.1 Agent Graph

```
START
  └─► Moderation Agent ──(severity ≥ 8: block)──► Finalise ──► END
              └──(allow / warn)──► Router (intent classification)
                                      ├─► Search Agent ──► Judge Agent
                                      │       ↑ retry (rephrased) ◄── score < 7, retry < 2
                                      ├─► Summarisation Agent ──► Judge Agent
                                      │       ↑ retry ◄──────────── score < 7, retry < 2
                                      ├─► Delivery Agent ──────────► Finalise
                                      └─► Notification Agent ───────► Finalise
                                                                          └──► END
```

### 6.2 Agent Responsibilities

| Agent | File | Responsibility |
|---|---|---|
| **Moderation Agent** | `moderation_agent.py` | Rule-based regex check → AI severity scoring (0–10) → allow / warn / block. Severity ≥ 8 always blocks |
| **Router** | `graph.py` | OpenAI GPT-4o-mini classifies intent → search / summarise / delivery / notify. Keyword fallback if OpenAI unavailable |
| **Search Agent** | `search_agent.py` | Calls hybrid_search() → AI analyses top 5 results → ranked results + analysis |
| **Summarisation Agent** | `summarisation_agent.py` | Calls RAG service → JudgeAgent internal evaluation → regenerates if score < 7 → saves feedback |
| **Delivery Agent** | `delivery_agent.py` | Fetches failed messages → priority sort (urgent first, EN + JA keywords) → 5-min backoff → escalates > 24hrs |
| **Notification Agent** | `notification_agent.py` | Analyses 7-day activity patterns → quiet hours detection (10PM–7AM) → fatigue if > 5 notifs/hr → suppresses/batches |
| **Judge Agent** | `judge_agent.py` | Scores Relevance · Accuracy · Completeness (0–10) → average < 7: retry with rephrased query (max 1 retry) |

### 6.3 Shared State (AgentState TypedDict)

```python
query, user_id, context          # inputs
intent, retry_query              # routing
moderation_result, search_result # per-agent outputs
summarisation_result, judge_result
retry_count, final_response      # control flow
```

---

## 7. Key Design Decisions (ADRs)

### ADR-001: MongoDB for Message Storage

**Decision:** MongoDB Atlas for all messages and events.  
**Rationale:** Document model fits message schema naturally (reactions, read_by as embedded arrays). TTL indexes enforce 30-day offline queue. Horizontal scaling without schema migrations.  
**Trade-off:** No joins; eventual consistency vs PostgreSQL strong guarantees.

### ADR-002: pgvector on Neon PostgreSQL for Vector Storage

**Decision:** pgvector extension on existing Neon PostgreSQL instance.  
**Rationale:** No additional managed database. Vectors co-located with relational data enabling filtered SQL queries (by group_id, sender_id). asyncpg connection pool reused. Avoids a fourth managed service.  
**Trade-off:** Free tier storage limits. Pinecone/Weaviate needed at 100M+ vectors.

### ADR-003: OpenAI GPT-4o-mini

**Decision:** OpenAI GPT-4o-mini via openai SDK.  
**Rationale:** Strong multilingual support (English + Japanese). Native function/tool calling. Reliable quota management. Broad ecosystem tooling.  
**Trade-off:** Paid tier required. Flan-T5 Small used as degraded local fallback.

### ADR-004: LangGraph for Multi-Agent Orchestration

**Decision:** LangGraph + LangChain for agent framework.  
**Rationale:** Built-in TypedDict state management. Graph-based conditional routing. Agent-to-agent communication via shared AgentState. Active development and observability.  
**Trade-off:** Learning curve. Heavier dependency than a custom orchestrator.

### ADR-005: Hybrid Search (BM25 + Semantic + RRF)

**Decision:** Reciprocal Rank Fusion of BM25 (rank-bm25) + pgvector semantic search.  
**Rationale:** BM25 excels at exact keyword matches (names, dates, codes). Semantic search handles paraphrasing and intent. RRF combines both without tuning weights. Three parallel searches via asyncio.gather.  
**Trade-off:** Higher latency than pure semantic. Requires maintaining both BM25 corpus and pgvector index.

### ADR-006: Polyglot Persistence

**Decision:** Neon PostgreSQL (users, groups, embeddings) + MongoDB Atlas (messages, events).  
**Rationale:** Each database optimised for its workload. Consolidating embeddings into PostgreSQL via pgvector avoided a fourth managed service.  
**Trade-off:** Operational complexity of two databases.

### ADR-007: WebSocket for Real-time Delivery

**Decision:** FastAPI WebSocket with in-memory ConnectionManager.  
**Rationale:** Bidirectional persistent connection. No polling overhead. Enables typing indicators and read receipts. Native FastAPI support. < 500ms delivery (P99).  
**Trade-off:** Horizontal scaling requires Redis pub/sub (documented production gap).

---

## 8. Resilience & Graceful Degradation

### 8.1 Circuit Breaker (OpenAI)

```
3 consecutive failures → circuit opens
All calls → local fallback (Flan-T5 Small on CPU)
After 30 seconds → half-open state → probe with next call
Success → circuit closes, failures reset to 0
```

### 8.2 Degradation Layers

```
Search request:
  pgvector available? YES → BM25 + Semantic + RRF (hybrid)
                     NO  → BM25 keyword only

OpenAI available?   YES → GPT-4o-mini (full quality)
                     NO  → Flan-T5 Small (local CPU inference)
Flan-T5 available?  YES → local generation
                     NO  → extractive stub (first 20 words)

pgvector available? YES → cosine similarity search
                     NO  → MongoDB full-text search fallback

S3 available?       YES → AWS S3 ap-south-1
                     NO  → local uploads/ folder
```

### 8.3 Offline Message Queue

Messages to offline users → `delivery_status: "queued"` in MongoDB  
On reconnect → flush queued messages via WebSocket  
TTL: 30 days (MongoDB TTL index)

---

## 9. Dataset

**Name:** Synthetic Messaging and Conversation Dataset  
**Scale:** 150 users · 25 groups · 60,000 messages · 90-day history

### 9.1 Message Schema

| Field | Type | Notes |
|---|---|---|
| message_id | UUID | Unique identifier |
| sender_id | UUID | Sending user |
| receiver_id | UUID | DM recipient (null for groups) |
| group_id | UUID | Group (null for DMs) |
| content | string | Message text body |
| media_type | enum | text / image / voice / video |
| delivery_status | enum | sent / delivered / queued / failed |
| read_status | enum | read / unread |
| reactions | dict | `{emoji: [user_ids]}` — extended |
| read_by | list | Group read tracking — extended |
| language | string | en / ja — detected via langdetect |
| conversation_summary | string | LLM-generated — extended |

### 9.2 Distribution

| Metric | Value |
|---|---|
| Users | 130 English (Asia/Kolkata) + 20 Japanese (Asia/Tokyo) |
| Message types | Text 80% · Image 10% · Voice 5% · Video 5% |
| Delivery status | Delivered 90% · Sent 8% · Failed 2% |
| Languages | English ~87% · Japanese ~13% |
| Group size | 5–30 members per group |

---

## 10. Evaluation Results

### 10.1 Methodology

**Search:** Precision@5 and NDCG@5 (binary relevance via keyword match against ground truth).  
**Summarisation:** LLM-as-Judge using OpenAI GPT-4o-mini scoring Relevance · Accuracy · Completeness (0–10 each).  
**Pass thresholds:** Search P@5 ≥ 0.30 · Summarisation avg ≥ 6.0 AND topic coverage ≥ 50%.

### 10.2 Search Results

| Case | Query | P@5 | NDCG@5 | Latency | Status |
|---|---|---|---|---|---|
| s1 | project deadline | 0.80 | 0.864 | 142ms | PASS |
| s2 | office renovation plans | 0.60 | 0.695 | 138ms | PASS |
| s3 | quarterly budget review | 0.40 | 0.431 | 151ms | PASS |
| s4 | team meeting schedule | 0.80 | 0.864 | 145ms | PASS |
| s5 | product launch announcement | 0.60 | 0.695 | 147ms | PASS |
| **Mean** | | **0.64** | **0.710** | **145ms** | **5/5** |

### 10.3 Summarisation Results (LLM-as-Judge)

| Case | Group | Relevance | Accuracy | Completeness | Avg | Coverage | Latency | Status |
|---|---|---|---|---|---|---|---|---|
| sum1 | Project Launch Team | 8 | 7 | 8 | 7.67 | 100% | 3.2s | PASS |
| sum2 | Office Renovation | 7 | 8 | 7 | 7.33 | 100% | 2.8s | PASS |

### 10.4 Token Optimisation

| Parameter | Value |
|---|---|
| Max messages per summarisation | 5,000 |
| Chunk size | 3,000 tokens (tiktoken cl100k_base) |
| Chunk overlap | 3 messages |
| Merge threshold | 6,000 tokens |
| Parallel OpenAI calls per batch | 5 |
| Strategy for long history | Hierarchical merge |

### 10.5 Resilience Verification

| Scenario | Expected Behaviour | Verified |
|---|---|---|
| OpenAI circuit open (3 failures) | Flan-T5 Small on CPU | ✅ |
| Flan-T5 not installed | Extractive stub (first 20 words) | ✅ |
| pgvector unavailable | BM25-only keyword search | ✅ |
| MongoDB unavailable | DeliveryAgent returns zero failed count | ✅ |
| 20 concurrent WebSocket sends | No exceptions, all return False | ✅ |
| Urgent notification during fatigue | Bypasses suppression, delivered immediately | ✅ |

---

## 11. Non-Functional Requirements

| NFR | Target | Implementation | Status |
|---|---|---|---|
| Latency | < 500ms delivery (P99) | WebSocket full-duplex · async I/O throughout | ✅ |
| Availability | 99.99% uptime | Circuit breaker · Flan-T5 fallback · BM25 fallback | ✅ (POC) |
| Reliability | At-least-once delivery | MongoDB queued status · 30-day TTL · flush on reconnect | ✅ |
| Security | JWT auth · content moderation | bcrypt passwords · PII guard · ModerationAgent | ✅ |
| Observability | Real-time monitoring | /health · /metrics (Prometheus) · structured JSON logs | ✅ |
| Scalability | 500k msg/sec · 1B users | Documented production path (K8s, Redis pub/sub) | POC |
| Geo Distribution | Multi-region | Documented architecture · not built in POC | POC |
| Compliance | GDPR right to deletion | Soft-delete flag · documented as production requirement | POC |

---

## 12. POC vs Production

| Dimension | POC (Built) | Production Path |
|---|---|---|
| WebSocket scaling | In-memory ConnectionManager | Redis pub/sub + horizontal K8s pods |
| Vector store | pgvector on Neon free tier | Pinecone / Weaviate (100M+ vectors) |
| LLM | Single OpenAI API key | Load balancing across API keys + fine-tuned models |
| Observability | Prometheus /metrics + structured logs | Grafana dashboards + anomaly detection alerts |
| Media storage | AWS S3 ap-south-1 + local fallback | Multi-region S3 with CDN |
| Security | JWT + PII guard | E2E encryption + forward secrecy |
| Search corpus | BM25 loaded from MongoDB per request | Pre-indexed BM25 corpus with caching layer |

---

## 13. Repository Structure

```
messaging-platform/
├── src/
│   ├── auth/           JWT authentication + Google OAuth
│   ├── messaging/      WebSocket + REST message handling
│   ├── ai/             OpenAI client, RAG, embeddings, chatbot, PII guard
│   ├── search/         Hybrid BM25 + semantic + RRF
│   ├── agents/         LangGraph orchestration + 7 specialised agents
│   ├── media/          S3 + local upload handling
│   ├── notifications/  Smart notification service
│   ├── admin/          Demo dataset seeding + management
│   └── common/         Database, logger, metrics, health, exceptions
├── frontend/src/       React 18 components (8 screens)
├── dataset/            Synthetic data generation + loading scripts
├── tests/
│   ├── api/            Auth + messaging + AI endpoint tests
│   ├── resilience/     Circuit breaker + agent degradation tests
│   ├── evaluation/     LLM-as-Judge + IR metrics eval suite
│   └── load/           Locust performance tests
├── docs/
│   ├── architecture/   System architecture (Mermaid)
│   ├── data-flow/      Ingestion + retrieval flows
│   ├── DECISIONS.md    7 Architecture Decision Records
│   ├── EVALUATION_RESULTS.md
│   └── DESIGN_PATTERNS.md
├── requirements.txt
├── docker-compose.yml
└── README.md
```

---

## 14. Design Patterns Used

| Pattern | Location | Purpose |
|---|---|---|
| Repository Pattern | `message_service.py`, `notifications/service.py` | Abstracts all DB operations from controllers |
| Observer Pattern | `websocket_manager.py` | ConnectionManager as event bus for real-time delivery |
| Strategy Pattern | `search_service.py` | Pluggable BM25 / semantic / hybrid search strategies |
| Circuit Breaker | `gemini_client.py` | 3 failures → open → Flan-T5 fallback → 30s reset |
| Factory Pattern | `orchestrator.py` | Creates appropriate agent based on intent classification |
| Singleton Pattern | `embedding_service.py`, `vector_store.py` | Heavy models loaded once at startup |
| RAG Pattern | `rag_service.py` | Retrieve → chunk → parallel summarise → hierarchical merge |
| LLM-as-Judge | `judge_agent.py` | Quality gate with automated regeneration on low scores |
| Reciprocal Rank Fusion | `search_service.py` | Merges BM25 + semantic ranked lists without weight tuning |
| Graceful Degradation | `gemini_client.py`, `search_service.py` | Multi-level fallbacks at every failure point |

---

*Document generated from verified codebase — all implementation details match source code.*
