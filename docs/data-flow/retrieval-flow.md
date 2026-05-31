# Data Flow: Retrieval & AI Query

Covers three retrieval paths: **hybrid search**, **RAG summarisation**, and **multi-agent orchestration**.

---

## Hybrid Search Flow

```mermaid
sequenceDiagram
    participant Client as React Client
    participant API as FastAPI
    participant SearchSvc as Search Service
    participant BM25 as BM25 Index (in-memory)
    participant EmbSvc as Embedding Service
    participant Chroma as ChromaDB
    participant RRF as RRF Merger

    Client->>API: POST /api/search {query, filters, n_results}
    API->>API: Pydantic validation + JWT auth

    par BM25 retrieval
        API->>BM25: tokenize + score query against corpus
        BM25-->>API: ranked_bm25_results[]
    and Semantic retrieval
        API->>EmbSvc: embed(query) → 384-dim vector
        EmbSvc-->>API: query_vector
        API->>Chroma: similarity_search(query_vector, n=50)
        Chroma-->>API: semantic_results[]
    end

    API->>RRF: merge(bm25_results, semantic_results)
    Note over RRF: score = Σ 1/(k + rank_i), k=60
    RRF-->>API: fused_results[]

    API-->>Client: {results: [...], total: N, strategy: "hybrid"}
```

---

## RAG Summarisation Flow

```mermaid
sequenceDiagram
    participant Client as React Client
    participant API as FastAPI
    participant SummSvc as Summarisation Service (rag_service.py)
    participant PG as PostgreSQL
    participant Mongo as MongoDB
    participant Tiktoken as tiktoken (cl100k_base)
    participant Gemini as Gemini 2.5 Flash
    participant Judge as LLM-as-Judge

    Client->>API: POST /api/ai/summarise {group_id, days}

    API->>Mongo: fetch messages (last N days, limit 5000)
    API->>PG: resolve sender UUIDs → display names (single query)

    loop Chunk messages
        Tiktoken->>Tiktoken: count tokens per message
        Note over Tiktoken: chunk_limit = 3000 tokens<br/>overlap = 3 messages
    end

    par Parallel chunk summarisation (batch=5)
        API->>Gemini: summarise chunk 1
        API->>Gemini: summarise chunk 2
        API->>Gemini: summarise chunk N
    end

    alt combined summaries ≤ 6000 tokens
        API->>Gemini: merge all chunk summaries
    else combined summaries > 6000 tokens
        Note over API,Gemini: Hierarchical merge — recursive sub-batching
        API->>Gemini: merge batch 1 of chunk summaries
        API->>Gemini: merge batch 2 of chunk summaries
        API->>Gemini: final merge of merged summaries
    end

    API->>Judge: score(summary) → relevance · accuracy · completeness
    Judge-->>API: {average_score: 8.5, feedback: "..."}

    alt average_score < 7
        API->>Gemini: regenerate with improvement prompt
    end

    API-->>Client: {summary, quality_score, token_stats}
```

---

## Multi-Agent Orchestration Flow (LangGraph)

```mermaid
stateDiagram-v2
    [*] --> moderate: every request

    moderate --> finalise: action = block
    moderate --> router: action = allow / warn

    router --> search: intent = search
    router --> summarise: intent = summarise
    router --> delivery: intent = delivery
    router --> notify: intent = notify

    search --> judge
    summarise --> judge

    judge --> search: score < 7 AND retry_count < 2\n(rephrased query)
    judge --> summarise: score < 7 AND retry_count < 2
    judge --> finalise: score ≥ 7 OR retries exhausted

    delivery --> finalise
    notify --> finalise
    finalise --> [*]
```

### State passed through the graph

| Field | Set by | Used by |
|---|---|---|
| `query` | Caller | moderate, router, search, judge |
| `intent` | router | conditional edge `_by_intent` |
| `moderation_result` | moderate | finalise (block reason, severity) |
| `retry_query` | judge | search (rephrased query on retry) |
| `search_result` | search | judge, finalise |
| `summarisation_result` | summarise | judge (reuses internal quality_score), finalise |
| `judge_result` | judge | conditional edge `_after_judge`, finalise |
| `retry_count` | judge (increments) | `_after_judge` (caps at 2) |
| `final_response` | finalise | returned to caller |

---

## Graceful Degradation Layers

```
Request
  │
  ├─► Semantic search available?
  │     YES → BM25 + Semantic + RRF (hybrid, best quality)
  │     NO  → BM25 only (keyword, still useful)
  │
  ├─► Gemini available?
  │     YES → Gemini 2.5 Flash (full LLM quality)
  │     NO (circuit open) → Flan-T5 Small on CPU (local inference)
  │     NO (Flan-T5 unavailable) → Extractive stub (first 20 words)
  │
  └─► ChromaDB available?
        YES → Vector similarity search
        NO  → MongoDB full-text search fallback
```
