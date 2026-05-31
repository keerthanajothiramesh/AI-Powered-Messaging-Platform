from typing import Dict, Any, List
from src.agents.base_agent import BaseAgent
from src.common.logger import get_logger

logger = get_logger(__name__)


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

        failed_cursor = db.messages.find(
            {"delivery_status": "failed"}
        ).sort("timestamp", 1).limit(100)
        failed_messages = await failed_cursor.to_list(length=100)

        logger.info("delivery_agent_run", failed_count=len(failed_messages))

        recovered = 0
        for msg in failed_messages:
            from src.messaging.websocket_manager import get_connection_manager
            manager = get_connection_manager()
            receiver = msg.get("receiver_id")
            if receiver and manager.is_online(receiver):
                msg_copy = dict(msg)
                msg_copy.pop("_id", None)
                ts = msg_copy.get("timestamp")
                if hasattr(ts, "isoformat"):
                    msg_copy["timestamp"] = ts.isoformat()
                await manager.send_to_user(receiver, {"type": "message", "data": msg_copy})
                await db.messages.update_one(
                    {"message_id": msg["message_id"]},
                    {"$set": {"delivery_status": "delivered"}},
                )
                recovered += 1

        return {
            "agent": self.name,
            "failed_found": len(failed_messages),
            "recovered": recovered,
            "still_pending": len(failed_messages) - recovered,
        }
