"""DeepEval evaluation suite for summarisation and search quality."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()


async def evaluate_summarisation():
    """Evaluate RAG summarisation quality."""
    from src.ai.gemini_client import init_gemini
    from src.config import settings

    if settings.GEMINI_API_KEY:
        init_gemini(settings.GEMINI_API_KEY)

    test_cases = [
        {
            "input": "Summarise the Project Launch Team conversation",
            "expected_keywords": ["project", "launch", "team"],
        },
        {
            "input": "What was discussed about the deadline?",
            "expected_keywords": ["deadline", "march", "deliverable"],
        },
    ]

    results = []
    for case in test_cases:
        from src.ai.gemini_client import generate_text
        output = await generate_text(case["input"], max_tokens=256)
        found = sum(1 for kw in case["expected_keywords"] if kw.lower() in output.lower())
        score = found / len(case["expected_keywords"])
        results.append({
            "input": case["input"],
            "output": output[:100] + "...",
            "keyword_coverage": score,
            "passed": score >= 0.5,
        })

    return results


async def evaluate_search():
    """Evaluate hybrid search relevance."""
    from src.search.search_service import hybrid_search

    queries = [
        ("project deadline", "deadline"),
        ("renovation images", "renovation"),
        ("office meeting", "meeting"),
    ]

    results = []
    for query, expected_kw in queries:
        try:
            hits = await hybrid_search(query, n_results=5)
            relevant = sum(1 for h in hits if expected_kw.lower() in h.get("content", "").lower())
            precision = relevant / len(hits) if hits else 0
            results.append({
                "query": query,
                "hits": len(hits),
                "relevant": relevant,
                "precision": precision,
                "passed": precision >= 0.3,
            })
        except Exception as e:
            results.append({"query": query, "error": str(e), "passed": False})

    return results


def print_report(summarisation_results, search_results):
    print("\n" + "=" * 60)
    print("EVALUATION REPORT")
    print("=" * 60)

    print("\n[Summarisation Quality]")
    for r in summarisation_results:
        status = "✓ PASS" if r.get("passed") else "✗ FAIL"
        print(f"  {status} | Coverage: {r.get('keyword_coverage', 0):.0%} | {r['input'][:40]}")

    print("\n[Search Relevance]")
    for r in search_results:
        if "error" in r:
            print(f"  ✗ ERROR | {r['query']}: {r['error'][:40]}")
        else:
            status = "✓ PASS" if r["passed"] else "✗ FAIL"
            print(f"  {status} | Precision: {r['precision']:.0%} | {r['query']}")

    print("\n" + "=" * 60)


async def main():
    print("Running evaluation suite...")
    summarisation_results = await evaluate_summarisation()
    search_results = await evaluate_search()
    print_report(summarisation_results, search_results)


if __name__ == "__main__":
    asyncio.run(main())
