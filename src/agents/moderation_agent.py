import re
from typing import Dict, Any, List
from src.agents.base_agent import BaseAgent
from src.common.logger import get_logger

logger = get_logger(__name__)

TOXIC_PATTERNS = [
    r'\b(spam|scam|hack|phish)\b',
    r'(http[s]?://\S+){3,}',
]


class ModerationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="ModerationAgent",
            system_prompt="""You are a content moderation specialist.
Evaluate messages for:
1. Toxicity and harmful content
2. Spam patterns
3. Personal information leakage
4. Policy violations
Return a moderation decision with confidence score.""",
        )

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        content = input_data.get("content", "")
        message_id = input_data.get("message_id", "")

        logger.info("moderation_agent_run", message_id=message_id)

        flags = self._rule_based_check(content)

        if flags:
            ai_prompt = f"""Evaluate this message for policy violations:
"{content}"

Flags detected: {', '.join(flags)}
Is this genuinely harmful? Rate severity 0-10. Recommend: allow/warn/block."""
            ai_assessment = await self._generate(ai_prompt, max_tokens=256)
        else:
            ai_assessment = "No violations detected."

        is_flagged = len(flags) > 0
        return {
            "agent": self.name,
            "message_id": message_id,
            "is_flagged": is_flagged,
            "flags": flags,
            "assessment": ai_assessment,
            "action": "block" if is_flagged else "allow",
        }

    def _rule_based_check(self, content: str) -> List[str]:
        flags = []
        content_lower = content.lower()
        for pattern in TOXIC_PATTERNS:
            if re.search(pattern, content_lower):
                flags.append(f"pattern_match:{pattern[:20]}")
        return flags
