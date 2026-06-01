# Architecture Decision Records (ADRs)

## ADR-001: MongoDB for Messages (vs PostgreSQL)

**Status:** Accepted  
**Context:** Need to store 60,000+ messages with flexible schemas including reactions, read-by lists, and media metadata.  
**Decision:** Use MongoDB Atlas for message storage.  
**Rationale:** Document model fits message schema naturally; horizontal scaling; TTL indexes for 30-day offline queue; flexible reactions/read-by as embedded arrays.  
**Trade-offs:** Eventual consistency vs. strong guarantees of PostgreSQL; no joins (compensated by denormalization).

---

## ADR-002: pgvector on Neon PostgreSQL for Vector Storage (vs ChromaDB)

**Status:** Accepted  
**Context:** Need semantic search across 60,000 messages; already running Neon PostgreSQL for users and groups.  
**Decision:** Use pgvector extension on the existing Neon PostgreSQL instance (`message_embeddings` table, cosine distance via `<=>` operator).  
**Rationale:** No additional database to manage; vectors co-located with relational data enabling filtered queries (by group_id, sender_id) in a single SQL statement; Neon handles managed scaling; asyncpg connection pool reused.  
**Trade-offs:** Single-node Neon free tier has storage limits; Pinecone/Weaviate would scale horizontally for 100M+ vectors. For this POC scale (60k messages), pgvector is sufficient.

---

## ADR-003: OpenAI API (GPT-4o-mini)

**Status:** Accepted  
**Context:** Need LLM for summarisation, chatbot, and agent orchestration.  
**Decision:** Use OpenAI GPT-4o-mini via the openai SDK.  
**Rationale:** Broad ecosystem and community tooling; strong multilingual support; native function/tool calling; reliable availability and quota management.  
**Trade-offs:** Paid tier required for sustained usage; no free local fallback model from OpenAI (Flan-T5 stub used as degraded fallback).

---

## ADR-004: LangGraph for Agents (vs Custom Orchestration)

**Status:** Accepted  
**Context:** Need multi-agent orchestration with moderation, search, summarisation, delivery agents.  
**Decision:** Use LangGraph + LangChain for agent framework.  
**Rationale:** Built-in state management; graph-based routing; agent-to-agent communication; observability; active development.  
**Trade-offs:** Learning curve; dependency weight; custom orchestrator would be lighter.

---

## ADR-005: Hybrid Search BM25 + Semantic (vs Pure Semantic)

**Status:** Accepted  
**Context:** Need accurate search across chat messages.  
**Decision:** Reciprocal Rank Fusion of BM25 (rank-bm25) + pgvector semantic search.  
**Rationale:** BM25 excels at exact keyword matches (names, codes); semantic search handles paraphrasing and intent; RRF combines both without tuning weights.  
**Trade-offs:** Slightly higher latency than pure semantic; requires maintaining both BM25 corpus and pgvector index.

---

## ADR-006: Polyglot Persistence Pattern

**Status:** Accepted  
**Context:** Different data types have different optimal storage engines.  
**Decision:** Neon PostgreSQL (users, groups, embeddings via pgvector) + MongoDB Atlas (messages, events).  
**Rationale:** Each database optimised for its workload; PostgreSQL for relational integrity and vector similarity (pgvector extension); MongoDB for flexible document storage and TTL indexes. Consolidating embeddings into PostgreSQL avoided a fourth managed service.  
**Trade-offs:** Operational complexity of 2 databases; pgvector on Neon free tier has row limits at very large scale (production would move vectors to Pinecone/Weaviate).

---

## ADR-007: WebSocket for Real-time (vs Polling)

**Status:** Accepted  
**Context:** Need <500ms message delivery when both users are online.  
**Decision:** FastAPI WebSocket with ConnectionManager for presence and message delivery.  
**Rationale:** Bidirectional; persistent connection; no polling overhead; native support in FastAPI; enables typing indicators and read receipts.  
**Trade-offs:** Connection state management complexity; horizontal scaling requires Redis pub/sub (noted as production limitation).

---

## ADR-008: OpenAI Moderation API for Content Guardrails (vs Regex-only)

**Status:** Accepted  
**Context:** Initial implementation used regex patterns for content moderation. Regex is brittle — it misses paraphrasing, multilingual harmful content, and context-dependent abuse.  
**Decision:** Replace regex content moderation with OpenAI Moderation API as the primary layer. Retain regex as fallback when OpenAI is unavailable.  
**Two-layer architecture:**
- Layer 1 (sync, regex): Prompt injection + jailbreak patterns — `chatbot_service.py`. OpenAI Moderation API does not catch these attack patterns.
- Layer 2 (async, API): Harmful content — hate, harassment, self-harm, sexual, violence — scored 0–1 per category. Score ≥ 0.8 → block. Score ≥ 0.5 → warn.  

**Rationale:** OpenAI Moderation API is free, < 100ms, context-aware, and multilingual. Reuses the existing OpenAI API key. Returns category-level scores (not just binary flagged) enabling granular severity mapping. No additional dependency or cost.  
**Trade-offs:** Adds one async API call per message in the agent pipeline. Mitigated by: (1) free endpoint with high rate limits, (2) regex fallback keeps the system functional when OpenAI is down.
