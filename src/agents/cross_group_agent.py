"""Cross-group moderation agent — detects coordinated toxic patterns from users active across multiple groups."""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from src.agents.base_agent import BaseAgent
from src.common.logger import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You are a cross-group moderation intelligence agent for a messaging platform.
Given evidence of potentially coordinated harmful behaviour across multiple groups, determine:
1. Whether the pattern is genuinely coordinated (vs coincidental)
2. Severity: low / medium / high
3. Recommended action: monitor / warn_user / mute_user / escalate_to_admin
4. Which groups and users are most affected

Be precise. Only flag content that is clearly harmful (hate speech, spam, harassment).
Do not flag off-topic or informal messages. Return your analysis in structured form."""


class CrossGroupModerationAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="CrossGroupModerationAgent", system_prompt=_SYSTEM_PROMPT)

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        from src.common.database import get_mongo_db, get_pg_pool
        db = get_mongo_db()
        pool = get_pg_pool()

        window_hours = int(input_data.get("hours", 24))
        since = datetime.now(timezone.utc) - timedelta(hours=window_hours)

        logger.info("cross_group_agent_run", window_hours=window_hours)

        # ── Find users who posted in 3+ groups in the window ─────────────────
        pipeline = [
            {"$match": {
                "group_id": {"$exists": True, "$ne": None, "$ne": ""},
                "timestamp": {"$gte": since},
                "deleted": {"$ne": True},
            }},
            {"$group": {
                "_id": "$sender_id",
                "groups": {"$addToSet": "$group_id"},
                "message_count": {"$sum": 1},
            }},
            {"$match": {"$expr": {"$gte": [{"$size": "$groups"}, 3]}}},
            {"$sort": {"message_count": -1}},
            {"$limit": 20},
        ]
        prolific_users = await db.messages.aggregate(pipeline).to_list(length=20)

        if not prolific_users:
            return {
                "agent": self.name,
                "window_hours": window_hours,
                "flagged_users": [],
                "suspicious_patterns": [],
                "analysis": "No cross-group activity patterns detected. All groups appear normal.",
                "total_scanned_users": 0,
            }

        # ── For each prolific user, sample their recent messages ─────────────
        user_ids = [u["_id"] for u in prolific_users if u.get("_id")]
        user_samples: Dict[str, List[str]] = {}
        for uid in user_ids:
            cursor = db.messages.find(
                {
                    "sender_id": uid,
                    "timestamp": {"$gte": since},
                    "media_type": "text",
                    "content": {"$exists": True, "$ne": ""},
                },
                {"content": 1, "group_id": 1},
            ).sort("timestamp", -1).limit(10)
            msgs = await cursor.to_list(length=10)
            user_samples[uid] = [m["content"][:200] for m in msgs if m.get("content")]

        # ── Resolve user IDs to display names ─────────────────────────────────
        name_map: Dict[str, str] = {}
        group_name_map: Dict[str, str] = {}
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT user_id, display_name FROM users WHERE user_id = ANY($1::uuid[])",
                    user_ids,
                )
                name_map = {str(r["user_id"]): r["display_name"] for r in rows}
                all_group_ids = list({g for u in prolific_users for g in u.get("groups", [])})
                if all_group_ids:
                    grows = await conn.fetch(
                        "SELECT group_id, group_name FROM groups WHERE group_id = ANY($1::uuid[])",
                        all_group_ids,
                    )
                    group_name_map = {str(r["group_id"]): r["group_name"] for r in grows}
        except Exception:
            pass

        # ── Use ModerationAgent to flag suspicious messages ───────────────────
        from src.agents.moderation_agent import ModerationAgent
        mod_agent = ModerationAgent()

        flagged: List[Dict[str, Any]] = []
        for user_info in prolific_users:
            uid     = user_info["_id"]
            name    = name_map.get(str(uid), str(uid))
            groups  = [group_name_map.get(str(g), str(g)) for g in user_info.get("groups", [])]
            samples = user_samples.get(uid, [])

            # Check each sample message for toxicity
            toxic_msgs = []
            for msg in samples:
                mod_result = await mod_agent.run({"content": msg, "user_id": uid})
                if mod_result.get("action") in ("warn", "block"):
                    toxic_msgs.append({"content": msg[:100], "severity": mod_result.get("severity", 0)})

            if toxic_msgs:
                flagged.append({
                    "user_id": uid,
                    "display_name": name,
                    "groups_active_in": groups,
                    "group_count": len(user_info.get("groups", [])),
                    "message_count": user_info["message_count"],
                    "toxic_messages": toxic_msgs,
                    "max_severity": max(m["severity"] for m in toxic_msgs),
                })

        # ── Gemini analysis of flagged patterns ───────────────────────────────
        if not flagged:
            analysis = (
                f"Scanned {len(prolific_users)} users active across 3+ groups in the last {window_hours}h. "
                "No coordinated toxic patterns detected."
            )
        else:
            flag_text = "\n".join(
                f"- {f['display_name']} active in {f['group_count']} groups "
                f"({', '.join(f['groups_active_in'][:3])}), "
                f"{len(f['toxic_messages'])} toxic message(s), max severity {f['max_severity']}"
                for f in flagged
            )
            prompt = (
                f"Cross-group moderation scan — last {window_hours} hours.\n\n"
                f"Flagged users:\n{flag_text}\n\n"
                "Analyse whether this represents coordinated harmful behaviour "
                "and provide recommended actions."
            )
            analysis = await self._generate(prompt, max_tokens=512)

        return {
            "agent": self.name,
            "window_hours": window_hours,
            "total_scanned_users": len(prolific_users),
            "flagged_users": flagged,
            "suspicious_patterns": [
                {
                    "user_id": f["user_id"],
                    "display_name": f["display_name"],
                    "severity": f["max_severity"],
                    "groups": f["groups_active_in"],
                }
                for f in flagged
            ],
            "analysis": analysis,
        }
