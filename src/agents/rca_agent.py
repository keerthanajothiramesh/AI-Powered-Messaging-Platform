"""Root Cause Analysis agent — uses Gemini to explain delivery failure patterns."""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from src.agents.base_agent import BaseAgent
from src.common.logger import get_logger

logger = get_logger(__name__)

_RCA_SYSTEM_PROMPT = """You are a root cause analysis agent for a messaging platform.
Given statistics about failed and escalated message deliveries, identify:
1. The most likely root causes (e.g., users consistently offline, network errors, queue expiry)
2. Which users or groups are most affected
3. Concrete recommendations to improve delivery rates

Be concise and actionable. Use bullet points. Highlight the top 3 root causes."""


class RCAAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="RCAAgent", system_prompt=_RCA_SYSTEM_PROMPT)

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        from src.common.database import get_mongo_db
        db = get_mongo_db()
        now = datetime.now(timezone.utc)
        window_hours = int(input_data.get("hours", 72))
        since = now - timedelta(hours=window_hours)

        # ── Collect failure statistics ────────────────────────────────────────
        pipeline = [
            {"$match": {
                "delivery_status": {"$in": ["failed", "queued"]},
                "timestamp": {"$gte": since},
            }},
            {"$group": {
                "_id": "$delivery_status",
                "count": {"$sum": 1},
                "avg_retry_count": {"$avg": "$retry_count"},
                "escalated_count": {"$sum": {"$cond": ["$delivery_escalated", 1, 0]}},
            }},
        ]
        status_stats = await db.messages.aggregate(pipeline).to_list(length=10)

        # Top affected receivers
        receiver_pipeline = [
            {"$match": {
                "delivery_status": {"$in": ["failed", "queued"]},
                "timestamp": {"$gte": since},
            }},
            {"$group": {"_id": "$receiver_id", "failures": {"$sum": 1}}},
            {"$sort": {"failures": -1}},
            {"$limit": 5},
        ]
        top_receivers = await db.messages.aggregate(receiver_pipeline).to_list(length=5)

        # Top affected groups
        group_pipeline = [
            {"$match": {
                "delivery_status": {"$in": ["failed", "queued"]},
                "group_id": {"$exists": True, "$ne": None, "$ne": ""},
                "timestamp": {"$gte": since},
            }},
            {"$group": {"_id": "$group_id", "failures": {"$sum": 1}}},
            {"$sort": {"failures": -1}},
            {"$limit": 5},
        ]
        top_groups = await db.messages.aggregate(group_pipeline).to_list(length=5)

        # Total counts
        total_failed = sum(s["count"] for s in status_stats)
        total_escalated = sum(s.get("escalated_count", 0) for s in status_stats)
        total_msgs = await db.messages.count_documents({"timestamp": {"$gte": since}})
        failure_rate = (total_failed / total_msgs * 100) if total_msgs else 0

        logger.info("rca_agent_run", total_failed=total_failed, window_hours=window_hours)

        if total_failed == 0:
            return {
                "agent": self.name,
                "window_hours": window_hours,
                "total_failed": 0,
                "failure_rate_pct": 0.0,
                "analysis": "No delivery failures detected in the analysis window. System is healthy.",
                "status_breakdown": [],
                "top_affected_receivers": [],
                "top_affected_groups": [],
            }

        # ── Resolve receiver IDs → display names ─────────────────────────────
        receiver_ids = [r["_id"] for r in top_receivers if r.get("_id")]
        group_ids    = [g["_id"] for g in top_groups    if g.get("_id")]
        name_map: Dict[str, str] = {}
        group_name_map: Dict[str, str] = {}
        if receiver_ids or group_ids:
            from src.common.database import get_pg_pool
            pool = get_pg_pool()
            async with pool.acquire() as conn:
                if receiver_ids:
                    try:
                        rows = await conn.fetch(
                            "SELECT user_id, display_name FROM users WHERE user_id = ANY($1::uuid[])",
                            receiver_ids,
                        )
                        name_map = {str(r["user_id"]): r["display_name"] for r in rows}
                    except Exception:
                        pass
                if group_ids:
                    try:
                        rows = await conn.fetch(
                            "SELECT group_id, group_name FROM groups WHERE group_id = ANY($1::uuid[])",
                            group_ids,
                        )
                        group_name_map = {str(r["group_id"]): r["group_name"] for r in rows}
                    except Exception:
                        pass

        affected_receivers = [
            {"user_id": r["_id"], "name": name_map.get(str(r["_id"]), "unknown"), "failures": r["failures"]}
            for r in top_receivers
        ]
        affected_groups = [
            {"group_id": g["_id"], "name": group_name_map.get(str(g["_id"]), "unknown"), "failures": g["failures"]}
            for g in top_groups
        ]

        # ── Gemini RCA prompt ─────────────────────────────────────────────────
        stats_text = "\n".join(
            f"- Status '{s['_id']}': {s['count']} messages, avg {s.get('avg_retry_count', 0):.1f} retries, "
            f"{s.get('escalated_count', 0)} escalated"
            for s in status_stats
        )
        receiver_text = "\n".join(
            f"- {r['name']} ({r['user_id']}): {r['failures']} failures"
            for r in affected_receivers
        )
        group_text = "\n".join(
            f"- {g['name']} ({g['group_id']}): {g['failures']} failures"
            for g in affected_groups
        ) or "None"

        prompt = (
            f"Delivery failure analysis for the last {window_hours} hours:\n\n"
            f"Total messages: {total_msgs}\n"
            f"Total failed/queued: {total_failed} ({failure_rate:.1f}%)\n"
            f"Escalated (>24h undelivered): {total_escalated}\n\n"
            f"Status breakdown:\n{stats_text}\n\n"
            f"Top affected receivers:\n{receiver_text or 'None'}\n\n"
            f"Top affected groups:\n{group_text}\n\n"
            "Provide root cause analysis and recommendations."
        )

        analysis = await self._generate(prompt, max_tokens=512)

        return {
            "agent": self.name,
            "window_hours": window_hours,
            "total_messages": total_msgs,
            "total_failed": total_failed,
            "failure_rate_pct": round(failure_rate, 2),
            "total_escalated": total_escalated,
            "status_breakdown": [
                {
                    "status": s["_id"],
                    "count": s["count"],
                    "avg_retries": round(s.get("avg_retry_count", 0) or 0, 1),
                    "escalated": s.get("escalated_count", 0),
                }
                for s in status_stats
            ],
            "top_affected_receivers": affected_receivers,
            "top_affected_groups": affected_groups,
            "analysis": analysis,
        }
