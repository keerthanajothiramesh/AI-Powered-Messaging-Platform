from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from src.agents.base_agent import BaseAgent
from src.common.logger import get_logger

logger = get_logger(__name__)

# Messages retried within this window are skipped (exponential backoff simulation)
_BACKOFF_MINUTES = 5
# Messages undelivered beyond this threshold get escalated
_ESCALATION_HOURS = 24

_URGENT_KEYWORDS = [
    "urgent", "asap", "deadline", "critical", "emergency",
    "緊急", "至急", "重要",
]


def _is_urgent(content: str) -> bool:
    content_lower = content.lower()
    return any(kw in content_lower for kw in _URGENT_KEYWORDS)


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class DeliveryAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="DeliveryAgent",
            system_prompt="""You are a message delivery monitoring agent.
Analyse delivery failures and determine:
1. Root cause of delivery failure
2. Retry strategy
3. Whether to escalate or queue
Ensure at-least-once message delivery.""",
        )

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        from src.common.database import get_mongo_db
        db = get_mongo_db()
        now = datetime.now(timezone.utc)
        backoff_cutoff = now - timedelta(minutes=_BACKOFF_MINUTES)

        # Fetch failed messages not retried recently (backoff filter)
        failed_cursor = db.messages.find({
            "delivery_status": "failed",
            "$or": [
                {"last_retry_at": {"$lt": backoff_cutoff}},
                {"last_retry_at": {"$exists": False}},
            ],
        }).sort("timestamp", 1).limit(100)
        failed_messages = await failed_cursor.to_list(length=100)

        logger.info("delivery_agent_run", failed_count=len(failed_messages))

        if not failed_messages:
            return {
                "agent": self.name,
                "failed_found": 0,
                "recovered": 0,
                "escalated": 0,
                "pending": 0,
            }

        # Priority sort: urgent content first, then oldest first
        failed_messages.sort(
            key=lambda m: (0 if _is_urgent(m.get("content", "")) else 1, m.get("timestamp", now)),
        )

        from src.messaging.websocket_manager import get_connection_manager
        manager = get_connection_manager()

        recovered: List[str] = []
        escalated: List[str] = []
        pending: List[str] = []

        for msg in failed_messages:
            msg_id = msg["message_id"]
            receiver = msg.get("receiver_id")
            msg_time = msg.get("timestamp")

            # Escalate if undelivered beyond threshold
            if msg_time and (now - _to_utc(msg_time)) > timedelta(hours=_ESCALATION_HOURS):
                await db.messages.update_one(
                    {"message_id": msg_id},
                    {"$set": {
                        "delivery_escalated": True,
                        "last_retry_at": now,
                    }},
                )
                escalated.append(msg_id)
                logger.warning("delivery_escalated", message_id=msg_id)
                continue

            # Attempt re-delivery if receiver is online
            if receiver and manager.is_online(str(receiver)):
                msg_copy = {k: v for k, v in msg.items() if k != "_id"}
                ts = msg_copy.get("timestamp")
                if hasattr(ts, "isoformat"):
                    msg_copy["timestamp"] = ts.isoformat()

                await manager.send_to_user(str(receiver), {"type": "message", "data": msg_copy})
                await db.messages.update_one(
                    {"message_id": msg_id},
                    {"$set": {
                        "delivery_status": "delivered",
                        "last_retry_at": now,
                    }},
                )
                recovered.append(msg_id)
            else:
                # Receiver offline — update backoff metadata and move on
                await db.messages.update_one(
                    {"message_id": msg_id},
                    {
                        "$set": {"last_retry_at": now},
                        "$inc": {"retry_count": 1},
                    },
                )
                pending.append(msg_id)

        logger.info(
            "delivery_agent_done",
            recovered=len(recovered),
            escalated=len(escalated),
            pending=len(pending),
        )

        return {
            "agent": self.name,
            "failed_found": len(failed_messages),
            "recovered": len(recovered),
            "escalated": len(escalated),
            "pending": len(pending),
            "recovered_ids": recovered,
            "escalated_ids": escalated,
        }
