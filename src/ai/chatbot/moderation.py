"""Two-layer chatbot guardrails — sync regex for prompt-injection and async OpenAI Moderation API for harmful content."""
import re
from src.common.logger import get_logger

logger = get_logger(__name__)

_BLOCKED_PATTERNS = [
    r"\b(ignore|forget|disregard)\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)\b",
    r"\bpretend\s+(you\s+are|to\s+be)\b",
    r"\bjailbreak\b",
    r"\bdan\s+mode\b",
    r"\bact\s+as\s+(an?\s+)?(evil|unfiltered|unrestricted)\b",
    r"<(script|iframe|object|embed)[^>]*>",
    r"\bdrop\s+table\b",
    r"\bexec\s*\(",
]
_BLOCKED_RE = re.compile("|".join(_BLOCKED_PATTERNS), re.IGNORECASE)
_MAX_INPUT_LEN = 2000

_BLOCKED_RESPONSE = (
    "I can only help with searching messages, summarising conversations, "
    "and looking up chat history. Please ask me something related to that."
)


def moderate_input(text: str) -> str | None:
    """Sync regex check: prompt injection + jailbreak patterns. Returns rejection message or None."""
    if len(text) > _MAX_INPUT_LEN:
        return "Input too long."
    if _BLOCKED_RE.search(text):
        logger.warning("chatbot_prompt_injection_blocked", snippet=text[:80])
        return _BLOCKED_RESPONSE
    return None


async def moderate_content(text: str) -> str | None:
    """Async OpenAI Moderation API check. Returns rejection message or None."""
    try:
        from src.ai.gemini_client import get_openai_client
        client = get_openai_client()
        if not client:
            return None
        response = await client.moderations.create(input=text)
        result = response.results[0]
        if result.flagged:
            scores = result.category_scores.model_dump()
            top_category = max(scores, key=scores.get)
            top_score = scores[top_category]
            if top_score >= 0.80:
                logger.warning(
                    "chatbot_content_moderation_blocked",
                    category=top_category, score=round(top_score, 3),
                )
                return (
                    f"I'm unable to respond to that message as it was flagged "
                    f"for {top_category.replace('/', ' ')}. "
                    "Please keep conversations respectful. 🛡️"
                )
    except Exception as exc:
        logger.warning("chatbot_moderation_api_failed", error=str(exc))
    return None
