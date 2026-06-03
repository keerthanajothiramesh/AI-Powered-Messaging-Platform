"""DeepEval-based quality tests that verify good summaries pass LLM-graded metrics (relevancy, coherence, conciseness, faithfulness) and that bad or hallucinated summaries are correctly rejected."""
import pytest
from deepeval import evaluate
from deepeval.metrics import (
    GEval,
    SummarizationMetric,
)
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

# ── Sample test fixtures (representative of real demo data) ───────────────────

SAMPLE_CONVERSATION = """
Alice: Hey team, we need to finalise the Q2 report by Friday March 31st.
Bob: I'll have the finance section ready by Wednesday.
Alice: Great. Carol, can you handle the marketing metrics?
Carol: Sure. I'll also add the customer satisfaction scores from last quarter.
Bob: Reminder that the board presentation is on April 3rd — we need the deck too.
Alice: Right. Let's split it — Bob does slides 1-10, Carol does 11-20.
Carol: Done. Should we share with David for review?
Alice: Yes, send it to David by Thursday EOD so he has time to review before the board meeting.
"""

GOOD_SUMMARY = """
The team discussed finalising the Q2 report due Friday, March 31st.
- Bob will complete the finance section by Wednesday.
- Carol will handle marketing metrics and customer satisfaction scores.
- The board presentation is on April 3rd; the deck is split (Bob: slides 1–10, Carol: 11–20).
- Final deck to be shared with David by Thursday EOD for review.
"""

BAD_SUMMARY = """
The team had a meeting. They talked about various things including reports.
Alice mentioned something about a deadline. Bob and Carol are involved.
"""

HALLUCINATED_SUMMARY = """
The team agreed to submit the Q2 report by March 31st. Alice will personally
present to the board on April 5th. The team also decided to hire two new analysts
and increase the marketing budget by 20%.
"""


# ── DeepEval metric definitions ───────────────────────────────────────────────

relevancy_metric = GEval(
    name="Relevancy",
    criteria=(
        "Does the summary cover the main topics discussed in the conversation? "
        "Score higher if key decisions, deadlines, and assignments are present."
    ),
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.7,
)

coherence_metric = GEval(
    name="Coherence",
    criteria=(
        "Is the summary well-structured, readable, and logically ordered? "
        "Score higher if it uses bullet points and clear language."
    ),
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.7,
)

conciseness_metric = GEval(
    name="Conciseness",
    criteria=(
        "Is the summary concise (under 300 words) while retaining all essential information? "
        "Penalise padding, repetition, and unnecessary filler."
    ),
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.6,
)

faithfulness_metric = GEval(
    name="Faithfulness",
    criteria=(
        "Does the summary contain ONLY information that is present in the source conversation? "
        "Score 0 if it introduces facts not mentioned in the input (hallucinations)."
    ),
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.8,
)

# ── Custom delivery latency metric (no LLM needed — pure statistics) ──────────

class DeliveryLatencyMetric:
    """
    Custom metric: what fraction of messages were delivered within the SLA window.
    Reads delivery data from MongoDB; no LLM involved.
    SLA: DM messages should be delivered within 5 seconds when receiver is online.
    """
    name = "DeliveryLatencyCompliance"
    threshold = 0.90   # 90% of messages must meet SLA

    def measure(self, latency_samples_ms: list) -> dict:
        if not latency_samples_ms:
            return {"score": 1.0, "reason": "No samples"}
        sla_ms = 5_000
        compliant = sum(1 for l in latency_samples_ms if l <= sla_ms)
        score = compliant / len(latency_samples_ms)
        p50 = sorted(latency_samples_ms)[len(latency_samples_ms) // 2]
        p95 = sorted(latency_samples_ms)[int(len(latency_samples_ms) * 0.95)]
        return {
            "score": score,
            "p50_ms": p50,
            "p95_ms": p95,
            "compliant": compliant,
            "total": len(latency_samples_ms),
            "passed": score >= self.threshold,
        }


# ── Custom retrieval relevance metric ─────────────────────────────────────────

class RetrievalRelevanceMetric:
    """
    Measures what fraction of top-K retrieved results are actually relevant
    to the query (precision@K).  Uses keyword overlap as a proxy — replace
    with embedding cosine similarity for production use.
    """
    name = "RetrievalPrecision"
    threshold = 0.6

    def measure(self, query: str, retrieved_contents: list) -> dict:
        if not retrieved_contents:
            return {"score": 0.0, "reason": "No results"}
        query_words = set(query.lower().split())
        relevant = [
            c for c in retrieved_contents
            if len(query_words & set(c.lower().split())) >= 1
        ]
        score = len(relevant) / len(retrieved_contents)
        return {
            "score": score,
            "relevant": len(relevant),
            "total": len(retrieved_contents),
            "passed": score >= self.threshold,
        }


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_good_summary_passes_all_metrics():
    """A high-quality summary should pass relevancy, coherence, conciseness, faithfulness."""
    test_case = LLMTestCase(
        input=SAMPLE_CONVERSATION,
        actual_output=GOOD_SUMMARY,
    )
    results = evaluate(
        test_cases=[test_case],
        metrics=[relevancy_metric, coherence_metric, conciseness_metric, faithfulness_metric],
        run_async=False,
        print_results=False,
    )
    for r in results.test_results:
        for m in r.metrics_data:
            assert m.success, f"Metric '{m.name}' failed on good summary: score={m.score:.2f}"


@pytest.mark.asyncio
async def test_bad_summary_fails_relevancy():
    """A vague summary should score below the relevancy threshold."""
    test_case = LLMTestCase(
        input=SAMPLE_CONVERSATION,
        actual_output=BAD_SUMMARY,
    )
    results = evaluate(
        test_cases=[test_case],
        metrics=[relevancy_metric],
        run_async=False,
        print_results=False,
    )
    score = results.test_results[0].metrics_data[0].score
    assert score < 0.7, f"Expected bad summary to score below 0.7 but got {score:.2f}"


@pytest.mark.asyncio
async def test_hallucinated_summary_fails_faithfulness():
    """A summary with invented facts should fail the faithfulness metric."""
    test_case = LLMTestCase(
        input=SAMPLE_CONVERSATION,
        actual_output=HALLUCINATED_SUMMARY,
    )
    results = evaluate(
        test_cases=[test_case],
        metrics=[faithfulness_metric],
        run_async=False,
        print_results=False,
    )
    score = results.test_results[0].metrics_data[0].score
    assert score < 0.8, f"Expected hallucinated summary to score below 0.8 but got {score:.2f}"


def test_delivery_latency_sla():
    """90% of simulated delivery latencies must be within 5 s."""
    metric = DeliveryLatencyMetric()
    # Simulate: mostly fast deliveries with a few slow outliers
    latencies_ms = [120, 200, 350, 80, 4800, 150, 200, 310, 250, 6200]
    result = metric.measure(latencies_ms)
    assert result["passed"], (
        f"SLA compliance {result['score']:.0%} below threshold "
        f"(p50={result['p50_ms']}ms, p95={result['p95_ms']}ms)"
    )


def test_retrieval_relevance():
    """At least 60% of retrieved results must be relevant to the query."""
    metric = RetrievalRelevanceMetric()
    query = "project deadline report"
    retrieved = [
        "The Q2 report deadline is March 31st",
        "Finance section for the project is due Wednesday",
        "Let's have lunch tomorrow",
        "Board meeting on April 3rd for the project",
        "Weather is nice today",
    ]
    result = metric.measure(query, retrieved)
    assert result["passed"], (
        f"Retrieval precision {result['score']:.0%} below threshold "
        f"({result['relevant']}/{result['total']} relevant)"
    )


def test_retrieval_relevance_empty():
    """Empty result set should return score 0."""
    metric = RetrievalRelevanceMetric()
    result = metric.measure("any query", [])
    assert result["score"] == 0.0


def test_delivery_latency_all_fast():
    """All sub-second deliveries should give score 1.0."""
    metric = DeliveryLatencyMetric()
    latencies = [50, 100, 200, 80, 150] * 20
    result = metric.measure(latencies)
    assert result["score"] == 1.0
