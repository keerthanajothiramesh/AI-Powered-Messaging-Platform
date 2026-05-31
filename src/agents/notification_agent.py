"""Smart notification agent — analyses user activity patterns to reduce fatigue."""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from src.agents.base_agent import BaseAgent
from src.common.logger import get_logger

logger = get_logger(__name__)

_URGENT_KEYWORDS = [
    "urgent", "asap", "deadline", "critical", "emergency",
    "緊急", "至急", "重要",
]

# Hours of day (UTC) bucketed into quiet vs active windows
_QUIET_HOUR_DEFAULT_START = 22   # 10 PM
_QUIET_HOUR_DEFAULT_END   = 7    # 7 AM


def _is_urgent(content: str) -> bool:
    return any(kw in content.lower() for kw in _URGENT_KEYWORDS)


async def _get_user_active_hours(user_id: str) -> Dict[str, Any]:
    """
    Query the last 7 days of last_seen timestamps to find the user's active window.
    Returns {"active_hours": [h, ...], "quiet_start": int, "quiet_end": int}.
    """
    try:
        from src.common.database import get_mongo_db
        db = get_mongo_db()
        since = datetime.now(timezone.utc) - timedelta(days=7)
        # We log presence changes as notification events — use those timestamps
        cursor = db.notifications.find(
            {"user_id": user_id, "created_at": {"$gte": since}},
            {"created_at": 1},
        ).limit(200)
        docs = await cursor.to_list(length=200)
        if len(docs) < 5:
            return {"active_hours": list(range(8, 22)), "quiet_start": _QUIET_HOUR_DEFAULT_START, "quiet_end": _QUIET_HOUR_DEFAULT_END}

        hour_counts = [0] * 24
        for d in docs:
            ts = d.get("created_at")
            if ts:
                h = ts.hour if hasattr(ts, "hour") else datetime.fromisoformat(str(ts)).hour
                hour_counts[h] += 1

        max_count = max(hour_counts) or 1
        active_hours = [h for h, c in enumerate(hour_counts) if c >= max_count * 0.2]

        # Derive quiet window as the longest contiguous gap in active hours
        quiet_start = _QUIET_HOUR_DEFAULT_START
        quiet_end   = _QUIET_HOUR_DEFAULT_END
        if active_hours:
            quiet_start = max(active_hours)
            quiet_end   = min(active_hours)

        return {"active_hours": active_hours, "quiet_start": quiet_start, "quiet_end": quiet_end}
    except Exception:
        return {"active_hours": list(range(8, 22)), "quiet_start": _QUIET_HOUR_DEFAULT_START, "quiet_end": _QUIET_HOUR_DEFAULT_END}


def _is_quiet_hours(hour: int, quiet_start: int, quiet_end: int) -> bool:
    if quiet_start > quiet_end:   # spans midnight, e.g. 22–7
        return hour >= quiet_start or hour < quiet_end
    return quiet_start <= hour < quiet_end


async def _get_recent_notification_count(user_id: str, window_minutes: int = 60) -> int:
    """Count notifications sent to this user in the last N minutes (fatigue detection)."""
    try:
        from src.common.database import get_mongo_db
        db = get_mongo_db()
        since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        return await db.notifications.count_documents({"user_id": user_id, "created_at": {"$gte": since}})
    except Exception:
        return 0


class NotificationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="NotificationAgent",
            system_prompt="""You are a smart notification agent.
Analyse user behaviour patterns and message context to determine:
1. Should this notification be sent immediately or batched?
2. What priority level is this notification?
3. Is the user likely in do-not-disturb mode?
Minimise notification fatigue while ensuring important messages get through.""",
        )

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        user_id         = input_data.get("user_id", "")
        message_content = input_data.get("content", "")
        sender_id       = input_data.get("sender_id", "")

        logger.info("notification_agent_run", user_id=user_id)

        urgency   = self._assess_urgency(message_content)
        now_hour  = datetime.now(timezone.utc).hour

        # Activity-pattern analysis
        activity     = await _get_user_active_hours(user_id)
        in_quiet     = _is_quiet_hours(now_hour, activity["quiet_start"], activity["quiet_end"])
        recent_count = await _get_recent_notification_count(user_id, window_minutes=60)
        fatigue_risk = recent_count >= 5   # more than 5 notifications in last hour

        # Decision logic
        if urgency == "high":
            # Urgent always goes through — even quiet hours
            should_notify  = True
            delivery_time  = "immediate"
            suppressed     = False
        elif in_quiet and not fatigue_risk:
            # Non-urgent during quiet hours — batch until active window
            should_notify  = True
            delivery_time  = f"batch_at_{activity['quiet_end']:02d}:00_UTC"
            suppressed     = False
        elif fatigue_risk and urgency == "low":
            # Too many notifications already — suppress low-urgency
            should_notify  = False
            delivery_time  = "suppressed"
            suppressed     = True
        else:
            should_notify  = urgency in ("high", "medium")
            delivery_time  = "immediate" if urgency == "high" else "batched"
            suppressed     = False

        logger.info(
            "notification_decision",
            user_id=user_id,
            urgency=urgency,
            in_quiet=in_quiet,
            fatigue_risk=fatigue_risk,
            should_notify=should_notify,
        )

        return {
            "agent":                self.name,
            "user_id":             user_id,
            "should_notify":       should_notify,
            "urgency":             urgency,
            "delivery_time":       delivery_time,
            "suppressed":          suppressed,
            "in_quiet_hours":      in_quiet,
            "fatigue_risk":        fatigue_risk,
            "recent_notif_count":  recent_count,
            "active_hours_sample": activity["active_hours"][:6],
        }

    def _assess_urgency(self, content: str) -> str:
        if _is_urgent(content):
            return "high"
        if "?" in content or len(content) < 50:
            return "medium"
        return "low"
