"""
Evaluation suite — LLM-as-Judge + IR metrics for search and summarisation.

Metrics:
  Search    : Precision@5, NDCG@5 (binary relevance)
  Summarise : LLM-as-Judge (relevance · accuracy · completeness, 0-10 each)
              + keyword topic coverage

Usage:
    python tests/evaluation/eval_suite.py
    python tests/evaluation/eval_suite.py --json          # machine-readable output
    python tests/evaluation/eval_suite.py --case s1       # single search case
"""

import asyncio
import json
import math
import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

GROUND_TRUTH_PATH = Path(__file__).parent / "ground_truth.json"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_ground_truth() -> dict:
    with open(GROUND_TRUTH_PATH) as f:
        return json.load(f)


def _precision_at_k(hits: list, relevant_keywords: list, k: int = 5) -> float:
    """Fraction of top-k results that contain at least one relevant keyword."""
    top_k = hits[:k]
    if not top_k:
        return 0.0
    relevant = sum(
        1 for h in top_k
        if any(kw.lower() in h.get("content", "").lower() for kw in relevant_keywords)
    )
    return relevant / len(top_k)


def _dcg_at_k(hits: list, relevant_keywords: list, k: int = 5) -> float:
    """Discounted Cumulative Gain at k (binary relevance: 1 if any keyword found)."""
    dcg = 0.0
    for i, h in enumerate(hits[:k], start=1):
        rel = 1 if any(kw.lower() in h.get("content", "").lower() for kw in relevant_keywords) else 0
        dcg += rel / math.log2(i + 1)
    return dcg


def _ndcg_at_k(hits: list, relevant_keywords: list, k: int = 5) -> float:
    """Normalized DCG — ideal DCG assumes first k results are all relevant."""
    ideal_dcg = sum(1 / math.log2(i + 1) for i in range(1, min(k, len(hits)) + 1))
    if ideal_dcg == 0:
        return 0.0
    return _dcg_at_k(hits, relevant_keywords, k) / ideal_dcg


def _topic_coverage(summary: str, expected_topics: list) -> float:
    """Fraction of expected topic keywords found anywhere in the summary."""
    found = sum(1 for t in expected_topics if t.lower() in summary.lower())
    return found / len(expected_topics) if expected_topics else 0.0


# ── Search evaluation ─────────────────────────────────────────────────────────

async def evaluate_search(cases: list, k: int = 5) -> list:
    from src.search.search_service import hybrid_search

    results = []
    for case in cases:
        t0 = time.perf_counter()
        try:
            hits = await hybrid_search(case["query"], n_results=k)
            latency_ms = (time.perf_counter() - t0) * 1000

            p_at_k = _precision_at_k(hits, case["relevant_keywords"], k)
            ndcg = _ndcg_at_k(hits, case["relevant_keywords"], k)
            passed = p_at_k >= case.get("min_precision_at_5", 0.3)

            results.append({
                "id": case["id"],
                "query": case["query"],
                "hits_returned": len(hits),
                f"precision_at_{k}": round(p_at_k, 3),
                f"ndcg_at_{k}": round(ndcg, 3),
                "latency_ms": round(latency_ms, 1),
                "passed": passed,
            })
        except Exception as exc:
            results.append({
                "id": case["id"],
                "query": case["query"],
                "error": str(exc),
                "passed": False,
            })
    return results


# ── Summarisation evaluation ──────────────────────────────────────────────────

async def evaluate_summarisation(cases: list) -> list:
    from src.ai.rag_service import summarise_with_stats
    from src.agents.judge_agent import JudgeAgent

    judge = JudgeAgent()
    results = []

    for case in cases:
        ctx = case["context"]
        t0 = time.perf_counter()
        try:
            output = await summarise_with_stats(
                group_id=None,   # None → evaluator uses group_name lookup
                days=ctx.get("days", 14),
                group_name=ctx.get("group_name", "evaluation group"),
            )
            latency_ms = (time.perf_counter() - t0) * 1000
            summary = output["summary"]
            token_stats = output.get("token_stats", {})

            # LLM-as-Judge scoring
            judgment = await judge.evaluate(summary, ctx)

            coverage = _topic_coverage(summary, case.get("expected_topics", []))
            judge_score = judgment.get("average_score", 0)
            passed = (
                judge_score >= case.get("judge_min_score", 6.0)
                and coverage >= case.get("min_topic_coverage", 0.5)
            )

            results.append({
                "id": case["id"],
                "group": ctx.get("group_name"),
                "days": ctx.get("days"),
                "judge_relevance": judgment.get("relevance"),
                "judge_accuracy": judgment.get("accuracy"),
                "judge_completeness": judgment.get("completeness"),
                "judge_average": round(judge_score, 2),
                "judge_feedback": judgment.get("feedback", ""),
                "topic_coverage": round(coverage, 3),
                "token_stats": token_stats,
                "latency_ms": round(latency_ms, 1),
                "passed": passed,
            })
        except Exception as exc:
            results.append({
                "id": case["id"],
                "group": ctx.get("group_name"),
                "error": str(exc),
                "passed": False,
            })
    return results


# ── Report ────────────────────────────────────────────────────────────────────

def print_report(search_results: list, summ_results: list) -> None:
    W = 65
    print("\n" + "=" * W)
    print("  EVALUATION REPORT — AI Messaging Platform")
    print("=" * W)

    print("\n── Search Quality (Hybrid BM25 + Semantic + RRF) ──")
    print(f"  {'ID':<6} {'P@5':>6} {'NDCG@5':>8} {'Latency':>9}  Status")
    print(f"  {'-'*6} {'-'*6} {'-'*8} {'-'*9}  ------")
    for r in search_results:
        if "error" in r:
            print(f"  {r['id']:<6}  ERROR: {r['error'][:35]}")
        else:
            status = "PASS" if r["passed"] else "FAIL"
            print(
                f"  {r['id']:<6} {r.get('precision_at_5', 0):>6.2f} "
                f"{r.get('ndcg_at_5', 0):>8.3f} "
                f"{r.get('latency_ms', 0):>7.0f}ms  {status}"
            )

    if search_results:
        avg_p = sum(r.get("precision_at_5", 0) for r in search_results if "error" not in r) / max(len([r for r in search_results if "error" not in r]), 1)
        avg_ndcg = sum(r.get("ndcg_at_5", 0) for r in search_results if "error" not in r) / max(len([r for r in search_results if "error" not in r]), 1)
        avg_lat = sum(r.get("latency_ms", 0) for r in search_results if "error" not in r) / max(len([r for r in search_results if "error" not in r]), 1)
        print(f"\n  Mean P@5: {avg_p:.2f} | Mean NDCG@5: {avg_ndcg:.3f} | Mean Latency: {avg_lat:.0f}ms")

    print("\n── Summarisation Quality (LLM-as-Judge) ──")
    print(f"  {'ID':<6} {'Rel':>5} {'Acc':>5} {'Cmp':>5} {'Avg':>6} {'Cover':>7} {'Latency':>9}  Status")
    print(f"  {'-'*6} {'-'*5} {'-'*5} {'-'*5} {'-'*6} {'-'*7} {'-'*9}  ------")
    for r in summ_results:
        if "error" in r:
            print(f"  {r['id']:<6}  ERROR: {r['error'][:40]}")
        else:
            status = "PASS" if r["passed"] else "FAIL"
            print(
                f"  {r['id']:<6} "
                f"{r.get('judge_relevance', 0):>5} "
                f"{r.get('judge_accuracy', 0):>5} "
                f"{r.get('judge_completeness', 0):>5} "
                f"{r.get('judge_average', 0):>6.1f} "
                f"{r.get('topic_coverage', 0):>7.0%} "
                f"{r.get('latency_ms', 0):>7.0f}ms  {status}"
            )
        if r.get("judge_feedback"):
            print(f"         Feedback: {r['judge_feedback'][:55]}")

    total = len(search_results) + len(summ_results)
    passed = sum(1 for r in search_results + summ_results if r.get("passed"))
    print(f"\n  Overall: {passed}/{total} cases passed")
    print("=" * W + "\n")


# ── Entry point ───────────────────────────────────────────────────────────────

async def main(args) -> dict:
    from src.config import settings
    from src.ai.gemini_client import init_openai
    from src.common.database import init_postgres, init_mongodb, get_pg_pool, create_pg_tables, create_mongo_indexes, get_mongo_db

    if settings.OPENAI_API_KEY:
        init_openai(settings.OPENAI_API_KEY)

    if settings.NEON_DATABASE_URL:
        await init_postgres(settings.NEON_DATABASE_URL)
        pool = get_pg_pool()
        await create_pg_tables(pool)
        from src.ai.vector_store import init_vector_store
        init_vector_store(pool)
        from src.ai.embedding_service import init_embedding_service
        init_embedding_service()
    else:
        print("WARNING: NEON_DATABASE_URL not set — semantic search will be skipped")

    if settings.MONGODB_URL:
        try:
            await init_mongodb(settings.MONGODB_URL)
            db = get_mongo_db()
            await create_mongo_indexes(db)
            print("MongoDB connected ✓")
        except Exception as e:
            print(f"WARNING: MongoDB connection failed — {e}")
            print("Fix: Add your local IP to MongoDB Atlas → Network Access → Add IP Address")
    else:
        print("WARNING: MONGODB_URL not set — BM25 search and summarisation will fail")

    gt = _load_ground_truth()
    search_cases = gt["search"]
    summ_cases = gt["summarisation"]

    # Filter to single case if --case passed
    if args.case:
        search_cases = [c for c in search_cases if c["id"] == args.case]
        summ_cases = [c for c in summ_cases if c["id"] == args.case]

    search_results = await evaluate_search(search_cases)
    summ_results = await evaluate_summarisation(summ_cases)

    report = {"search": search_results, "summarisation": summ_results}

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(search_results, summ_results)

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the AI evaluation suite")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--case", type=str, default=None, help="Run a single case by ID (e.g. s1, sum1)")
    parsed = parser.parse_args()
    asyncio.run(main(parsed))
