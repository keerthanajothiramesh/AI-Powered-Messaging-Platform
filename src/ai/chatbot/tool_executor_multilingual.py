"""Dispatcher for multilingual chatbot tools."""
from typing import Any, Dict, Optional

from src.ai.chatbot.tool_handlers_multilingual import (
    suggest_replies_in_language as _suggest_replies,
    decode_voice_message as _decode_voice,
    compose_message_in_language as _compose,
    explain_message_context as _explain,
)
from src.ai.chatbot.tool_handlers_multilingual_group import (
    cross_language_catchup as _cross_catchup,
    multilingual_group_summary as _ml_summary,
)

_ML_TOOLS = {
    "suggest_replies_in_language",
    "decode_voice_message",
    "compose_message_in_language",
    "explain_message_context",
    "cross_language_catchup",
    "multilingual_group_summary",
}


async def execute_multilingual_tool(tool_name: str, args: Dict, session) -> Optional[Any]:
    """Return result if tool_name is a multilingual tool, else None."""
    if tool_name not in _ML_TOOLS:
        return None
    if tool_name == "suggest_replies_in_language":
        return await _suggest_replies(args, session)
    if tool_name == "decode_voice_message":
        return await _decode_voice(args, session)
    if tool_name == "compose_message_in_language":
        return await _compose(args, session)
    if tool_name == "explain_message_context":
        return await _explain(args, session)
    if tool_name == "cross_language_catchup":
        return await _cross_catchup(args, session)
    if tool_name == "multilingual_group_summary":
        return await _ml_summary(args, session)
    return None
