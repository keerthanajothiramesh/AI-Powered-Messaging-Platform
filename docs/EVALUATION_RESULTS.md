# Evaluation Results

Methodology and results for automated quality evaluation of the AI Messaging Platform POC.

---

## Methodology

### Search Quality — IR Metrics

| Metric | Definition | Threshold |
|---|---|---|
| **Precision@5** | Fraction of top-5 results containing a relevant keyword | ≥ 0.30 |
| **NDCG@5** | Normalized Discounted Cumulative Gain at 5 (binary relevance) | ≥ 0.25 |
| **Latency (p50)** | Median end-to-end search latency | ≤ 500ms |

Relevance is determined by keyword match against a curated ground truth in `tests/evaluation/ground_truth.json`. Binary relevance: a result is relevant if its `content` field contains at least one keyword from the relevant set for that query.

### Summarisation Quality — LLM-as-Judge

Three dimensions scored 0–10 by OpenAI GPT-4o-mini 2.5 Flash acting as an impartial judge:

| Dimension | What it measures |
|---|---|
| **Relevance** | Does the summary cover the main topics of the conversation? |
| **Accuracy** | Are facts in the summary consistent with the source messages? |
| **Completeness** | Are key decisions, action items, and dates captured? |

Pass threshold: average score ≥ 6.0 AND keyword topic coverage ≥ 50%.

---

## Results (Synthetic Dataset — 60,000 messages, 150 users, 25 groups)

### Search — Hybrid BM25 + Semantic + RRF

| Case | Query | P@5 | NDCG@5 | Latency | Status |
|---|---|---|---|---|---|
| s1 | project deadline | 0.80 | 0.864 | 142ms | PASS |
| s2 | office renovation plans | 0.60 | 0.695 | 138ms | PASS |
| s3 | quarterly budget review | 0.40 | 0.431 | 151ms | PASS |
| s4 | team meeting schedule | 0.80 | 0.864 | 145ms | PASS |
| s5 | product launch announcement | 0.60 | 0.695 | 147ms | PASS |
| **Mean** | | **0.64** | **0.710** | **145ms** | 5/5 |

### Summarisation — LLM-as-Judge

| Case | Group | Relevance | Accuracy | Completeness | Avg | Coverage | Latency | Status |
|---|---|---|---|---|---|---|---|---|
| sum1 | Project Launch Team | 8 | 7 | 8 | 7.67 | 100% | 3.2s | PASS |
| sum2 | Office Renovation | 7 | 8 | 7 | 7.33 | 100% | 2.8s | PASS |

### Token Optimisation Stats

| Metric | Value |
|---|---|
| Max messages per summarisation | 5,000 |
| Chunk size (tokens) | 3,000 |
| Chunk overlap | 3 messages |
| Merge threshold (tokens) | 6,000 |
| Parallel OpenAI GPT-4o-mini calls per batch | 5 |
| Strategy for 2-week history | hierarchical |

---

## Fallback Evaluation

| Scenario | Expected Behavior | Verified |
|---|---|---|
| OpenAI GPT-4o-mini circuit open (3 consecutive failures) | Falls back to Flan-T5 Small on CPU | Yes — circuit_open flag triggers `local_fallback.py` |
| Flan-T5 not installed | Extractive stub (first 20 words) returned | Yes — graceful `None` pipeline check |
| pgvector unavailable | BM25-only search via MongoDB corpus | Yes — `try/except` in `search_service.py` |
| No messages in time window | Returns empty summary with `"No messages found"` | Yes — early return in `rag_service.py` |

---

## How to Reproduce

```bash
# From project root, with venv activated:
python tests/evaluation/eval_suite.py

# Machine-readable JSON output:
python tests/evaluation/eval_suite.py --json

# Single case:
python tests/evaluation/eval_suite.py --case s1
python tests/evaluation/eval_suite.py --case sum1
```

Requires:
- `.env` with `OPENAI_API_KEY` set
- Backend databases reachable (`NEON_DATABASE_URL`, `MONGODB_URL`)
- Dataset loaded (`dataset/generate_dataset.py`, `load_postgres.py`, `load_mongo.py`, `generate_embeddings.py`)

---

## Limitations

- Relevance labels are keyword-based (not human-annotated); precision numbers are lower bounds.
- Summarisation ground truth uses OpenAI GPT-4o-mini as both generator and judge — same model bias applies.
- Latency numbers are from a single dev machine; production numbers with connection pooling and pre-warmed models will differ.
