from typing import Dict, Any
from src.agents.base_agent import BaseAgent
from src.common.logger import get_logger

logger = get_logger(__name__)


class NotificationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="NotificationAgent",
            system_prompt="""You are a smart notification agent.
Analyse user behavior patterns and message context to determine:
1. Should this notification be sent immediately or batched?
2. What priority level is this notification?
3. Is the user likely in do-not-disturb mode?
Minimise notification fatigue while ensuring important messages get through.""",
        )

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        user_id = input_data.get("user_id")
        message_content = input_data.get("content", "")
        sender_id = input_data.get("sender_id")

        logger.info("notification_agent_run", user_id=user_id)

        urgency = self._assess_urgency(message_content)
        should_notify = urgency in ("high", "medium")

        return {
            "agent": self.name,
            "user_id": user_id,
            "should_notify": should_notify,
            "urgency": urgency,
            "delivery_time": "immediate" if urgency == "high" else "batched",
        }

    def _assess_urgency(self, content: str) -> str:
        urgent_keywords = ["urgent", "asap", "deadline", "important", "critical", "emergency",
                           "緊急", "至急", "重要"]
        content_lower = content.lower()
        if any(kw in content_lower for kw in urgent_keywords):
            return "high"
        if "?" in content or len(content) < 50:
            return "medium"
        return "low"
