"""Prometheus counters, histograms, and gauges for HTTP requests, messages, AI calls, and WebSocket connections."""
import time
from prometheus_client import (
    Counter, Histogram, Gauge,
    generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry,
    REGISTRY,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ── Counters ──────────────────────────────────────────────────────────────────

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

messages_sent_total = Counter(
    "messages_sent_total",
    "Total messages sent (DM + group)",
    ["type"],   # dm | group
)

messages_failed_total = Counter(
    "messages_failed_total",
    "Total messages that entered failed/queued delivery status",
)

ai_calls_total = Counter(
    "ai_calls_total",
    "Total Gemini API calls",
    ["operation"],   # summarise | search | chat | judge
)

ai_errors_total = Counter(
    "ai_errors_total",
    "Total Gemini API errors (circuit breaker trips included)",
    ["operation"],
)

summary_feedback_total = Counter(
    "summary_feedback_total",
    "Summary feedback ratings recorded",
    ["rating"],   # thumbs_up | thumbs_down | auto_judge
)

# ── Histograms ────────────────────────────────────────────────────────────────

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

ai_response_duration_seconds = Histogram(
    "ai_response_duration_seconds",
    "Gemini API call latency",
    ["operation"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

message_delivery_latency_seconds = Histogram(
    "message_delivery_latency_seconds",
    "Time from message send to delivery confirmation",
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 30.0, 300.0],
)

# ── Gauges ────────────────────────────────────────────────────────────────────

active_websocket_connections = Gauge(
    "active_websocket_connections",
    "Current number of open WebSocket connections",
)

online_users = Gauge(
    "online_users_total",
    "Current number of users with presence=online",
)

# ── Starlette middleware ──────────────────────────────────────────────────────

_SKIP_PATHS = {"/metrics", "/health", "/favicon.ico"}


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _SKIP_PATHS:
            return await call_next(request)

        # Normalise path: replace UUIDs and numeric IDs to avoid cardinality explosion
        import re
        normalised = re.sub(
            r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "/{id}", path
        )
        normalised = re.sub(r"/\d+", "/{id}", normalised)

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        http_requests_total.labels(
            method=request.method,
            endpoint=normalised,
            status_code=str(response.status_code),
        ).inc()
        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=normalised,
        ).observe(duration)

        return response


def get_metrics_response() -> Response:
    """Return a Prometheus-format /metrics response."""
    data = generate_latest(REGISTRY)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


async def get_metrics_summary() -> dict:
    """
    JSON summary of key metrics for the React observability dashboard.
    Reads live Prometheus collector values — no DB queries needed.
    """
    from src.common.database import get_mongo_db, get_pg_pool

    db = get_mongo_db()
    pool = get_pg_pool()

    # Delivery stats from MongoDB
    total_msgs = await db.messages.count_documents({})
    failed_msgs = await db.messages.count_documents({"delivery_status": {"$in": ["failed", "queued"]}})
    delivered_msgs = await db.messages.count_documents({"delivery_status": "delivered"})
    delivery_rate = round(delivered_msgs / total_msgs * 100, 1) if total_msgs else 0.0

    # AI quality stats from feedback store
    from src.agents.feedback_store import get_feedback_stats
    feedback = await get_feedback_stats()

    # Online users from PostgreSQL
    try:
        async with pool.acquire() as conn:
            online_count = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE user_presence='online'"
            )
    except Exception:
        online_count = 0

    # Latest scheduled-agent run summaries
    from src.agents.feedback_store import get_latest_agent_run
    delivery_run    = await get_latest_agent_run("DeliveryAgent")
    moderation_run  = await get_latest_agent_run("CrossGroupModerationAgent")
    rca_run         = await get_latest_agent_run("RCAAgent")

    def _iso(doc):
        ran_at = doc.get("ran_at")
        if ran_at and hasattr(ran_at, "isoformat"):
            return ran_at.isoformat()
        return ran_at

    dr = delivery_run.get("result", {})
    mr = moderation_run.get("result", {})
    rr = rca_run.get("result", {})

    return {
        "messages": {
            "total": total_msgs,
            "delivered": delivered_msgs,
            "failed_or_queued": failed_msgs,
            "delivery_rate_pct": delivery_rate,
        },
        "ai_quality": {
            "total_evaluations": feedback.get("total", 0),
            "avg_judge_score": round(feedback.get("avg_score", 0) or 0, 2),
            "high_quality_pct": round(
                feedback.get("high_quality", 0) / max(feedback.get("total", 1), 1) * 100, 1
            ),
            "thumbs_up": feedback.get("thumbs_up", 0),
            "thumbs_down": feedback.get("thumbs_down", 0),
        },
        "users": {
            "online": int(online_count or 0),
        },
        "agents": {
            "delivery": {
                "ran_at":      _iso(delivery_run),
                "failed_found": dr.get("failed_found", 0),
                "recovered":   dr.get("recovered", 0),
                "escalated":   dr.get("escalated", 0),
                "pending":     dr.get("pending", 0),
            },
            "moderation": {
                "ran_at":        _iso(moderation_run),
                "scanned_users": mr.get("total_scanned_users", 0),
                "flagged_users": len(mr.get("flagged_users", [])),
                "analysis":      (mr.get("analysis", "") or "")[:220],
            },
            "rca": {
                "ran_at":          _iso(rca_run),
                "failure_rate_pct": rr.get("failure_rate_pct", 0),
                "total_failed":    rr.get("total_failed", 0),
                "analysis":        (rr.get("analysis", "") or "")[:220],
            },
        },
    }
