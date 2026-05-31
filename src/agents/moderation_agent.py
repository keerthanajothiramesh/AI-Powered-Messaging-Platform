import re
from typing import Dict, Any, List, Tuple

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

Respond in this EXACT format:
SEVERITY: [0-10]
RECOMMENDATION: [allow|warn|block]
REASON: [one sentence]""",
        )

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        content = input_data.get("content", "")
        message_id = input_data.get("message_id", "")

        logger.info("moderation_agent_run", message_id=message_id)

        flags = self._rule_based_check(content)

        if not flags:
            return {
                "agent": self.name,
                "message_id": message_id,
                "is_flagged": False,
                "flags": [],
                "severity": 0,
                "assessment": "No violations detected.",
                "action": "allow",
            }

        # Rule matched — ask the AI to score actual severity before deciding
        ai_prompt = (
            f'Evaluate this message for policy violations:\n"{content}"\n\n'
            f'Flags detected: {", ".join(flags)}\n'
            "Is this genuinely harmful? Use the exact response format specified."
        )
        ai_assessment = await self._generate(ai_prompt, max_tokens=128)
        severity, recommendation, reason = _parse_assessment(ai_assessment)

        logger.info(
            "moderation_ai_result",
            severity=severity,
            recommendation=recommendation,
        )

        return {
            "agent": self.name,
            "message_id": message_id,
            "is_flagged": True,
            "flags": flags,
            "severity": severity,
            "assessment": reason,
            "action": recommendation,   # allow | warn | block — AI-driven, not just rule-matched
        }

    def _rule_based_check(self, content: str) -> List[str]:
        flags = []
        content_lower = content.lower()
        for pattern in TOXIC_PATTERNS:
            if re.search(pattern, content_lower):
                flags.append(f"pattern_match:{pattern[:20]}")
        return flags


def _parse_assessment(response: str) -> Tuple[int, str, str]:
    """Extract severity (0-10), recommendation (allow/warn/block), and reason."""
    severity = 5
    recommendation = "warn"
    reason = response.strip()

    for line in response.splitlines():
        line = line.strip()
        if line.upper().startswith("SEVERITY:"):
            try:
                severity = int(re.search(r"\d+", line).group())
            except (AttributeError, ValueError):
                pass
        elif line.upper().startswith("RECOMMENDATION:"):
            val = line.split(":", 1)[1].strip().lower()
            if val in ("allow", "warn", "block"):
                recommendation = val
        elif line.upper().startswith("REASON:"):
            reason = line.split(":", 1)[1].strip()

    # Safety override: severity 8+ always blocks regardless of recommendation
    if severity >= 8:
        recommendation = "block"

    return severity, recommendation, reason
