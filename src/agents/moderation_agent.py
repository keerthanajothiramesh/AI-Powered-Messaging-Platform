"""Content moderation agent — OpenAI Moderation API primary with regex fallback, mapping scores to block/warn/allow."""
import re
from typing import Dict, Any, List, Tuple

from src.agents.base_agent import BaseAgent
from src.common.logger import get_logger

logger = get_logger(__name__)

# ── Regex fallback (used only when OpenAI client is unavailable) ──────────────
_FALLBACK_PATTERNS = [
    r'\b(spam|scam|hack|phish)\b',
    r'(http[s]?://\S+){3,}',
]
_FALLBACK_RE = re.compile("|".join(_FALLBACK_PATTERNS), re.IGNORECASE)

# Severity threshold mapping (OpenAI score 0–1 → action)
_BLOCK_THRESHOLD = 0.80
_WARN_THRESHOLD  = 0.50


class ModerationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="ModerationAgent",
            system_prompt="You are a content moderation specialist.",
        )

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        content    = input_data.get("content", "")
        message_id = input_data.get("message_id", "")

        logger.info("moderation_agent_run", message_id=message_id)

        # ── Primary: OpenAI Moderation API ───────────────────────────────────
        result = await _openai_moderation(content)
        if result is not None:
            return {**result, "agent": self.name, "message_id": message_id}

        # ── Fallback: regex ───────────────────────────────────────────────────
        logger.warning("moderation_openai_unavailable", fallback="regex")
        return _regex_fallback(content, message_id, self.name)


async def _openai_moderation(content: str) -> Dict[str, Any] | None:
    """
    Call OpenAI Moderation API. Returns a result dict or None if unavailable.
    """
    try:
        from src.ai.gemini_client import get_openai_client
        client = get_openai_client()
        if not client:
            return None

        response = await client.moderations.create(input=content)
        result   = response.results[0]

        if not result.flagged:
            return {
                "is_flagged": False,
                "flags":      [],
                "severity":   0,
                "assessment": "OpenAI Moderation: no violations detected.",
                "action":     "allow",
            }

        # Find the highest-scoring category
        scores       = result.category_scores.model_dump()
        top_category = max(scores, key=scores.get)
        top_score    = scores[top_category]

        # Map score → severity 0–10 and action
        severity = round(top_score * 10)
        if top_score >= _BLOCK_THRESHOLD:
            action = "block"
        elif top_score >= _WARN_THRESHOLD:
            action = "warn"
        else:
            action = "allow"

        flagged_cats = [k for k, v in scores.items() if v >= _WARN_THRESHOLD]

        logger.info(
            "moderation_openai_result",
            top_category=top_category,
            top_score=round(top_score, 3),
            action=action,
        )

        return {
            "is_flagged": True,
            "flags":      flagged_cats,
            "severity":   severity,
            "assessment": (
                f"OpenAI Moderation: {top_category.replace('/', ' → ')} "
                f"(score {top_score:.2f})"
            ),
            "action": action,
        }

    except Exception as exc:
        logger.error("moderation_openai_failed", error=str(exc))
        return None


def _regex_fallback(content: str, message_id: str, agent_name: str) -> Dict[str, Any]:
    """Regex-based fallback when OpenAI is unavailable."""
    flags = []
    for pattern in _FALLBACK_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            flags.append(f"regex:{pattern[:30]}")

    if not flags:
        return {
            "agent":      agent_name,
            "message_id": message_id,
            "is_flagged": False,
            "flags":      [],
            "severity":   0,
            "assessment": "Regex fallback: no violations detected.",
            "action":     "allow",
        }

    return {
        "agent":      agent_name,
        "message_id": message_id,
        "is_flagged": True,
        "flags":      flags,
        "severity":   6,
        "assessment": "Regex fallback: suspicious pattern detected.",
        "action":     "warn",
    }
