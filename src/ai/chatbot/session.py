"""ChatbotSession — multi-turn conversation with tool calling."""
import asyncio
from typing import Any, Dict, List, Optional

from src.ai.gemini_client import generate_with_tools, generate_text
from src.ai.pii_guard import scan_and_anonymize
from src.ai.chatbot.moderation import moderate_input, moderate_content
from src.ai.chatbot.tools import CHATBOT_TOOLS, build_system_prompt
from src.ai.chatbot.tools.executor import execute_tool
from src.common.logger import get_logger

logger = get_logger(__name__)


class ChatbotSession:
    def __init__(
        self,
        user_id: str,
        conv_id: Optional[str] = None,
        is_group: bool = False,
        conv_name: Optional[str] = None,
        other_user_id: Optional[str] = None,
    ):
        self.user_id = user_id
        self.conv_id = conv_id
        self.is_group = is_group
        self.conv_name = conv_name or ""
        self.other_user_id = other_user_id
        self.history: List[Dict] = []

    async def chat(self, message: str) -> Dict[str, Any]:
        rejection = moderate_input(message)
        if rejection:
            return {"text": rejection, "tool_calls": [], "history_length": len(self.history)}

        content_rejection = await moderate_content(message)
        if content_rejection:
            return {"text": content_rejection, "tool_calls": [], "history_length": len(self.history)}

        safe_message, detected_pii = scan_and_anonymize(message)
        if detected_pii:
            logger.info("pii_anonymized", types=detected_pii, user_id=self.user_id)

        self.history.append({"role": "user", "content": safe_message})
        system_prompt = build_system_prompt(self.is_group, self.conv_name)

        response = await generate_with_tools(
            prompt=safe_message,
            tools=CHATBOT_TOOLS,
            conversation_history=self.history[:-1],
            system_prompt=system_prompt,
        )

        tool_results = []
        final_text = response.get("text", "")

        for tool_call in response.get("tool_calls", []):
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            logger.info("chatbot_tool_call", tool=tool_name, user_id=self.user_id)
            result = await execute_tool(tool_name, tool_args, self)
            tool_results.append({"tool": tool_name, "result": result})
            if result:
                context = f"\n\nTool result from {tool_name}: {str(result)[:500]}"
                final_text = await generate_text(
                    f"User asked: {message}{context}\n\nProvide a helpful, emoji-friendly response.",
                    system_prompt=system_prompt, max_tokens=512,
                )

        self.history.append({"role": "assistant", "content": final_text})

        if tool_results and final_text:
            asyncio.create_task(self._judge_and_persist(message, final_text))

        return {
            "text": final_text or "I couldn't find relevant information. Please try rephrasing. 🔍",
            "tool_calls": tool_results,
            "history_length": len(self.history),
        }

    async def _judge_and_persist(self, user_message: str, ai_response: str) -> None:
        try:
            from src.agents.judge_agent import JudgeAgent
            from src.agents.feedback_store import save_response_feedback
            judgment = await JudgeAgent().evaluate(
                ai_response, {"group_name": self.conv_name or "chat", "days": 0},
            )
            await save_response_feedback(
                user_id=self.user_id,
                conv_id=self.conv_id or "default",
                user_message=user_message,
                ai_response=ai_response,
                judgment=judgment,
            )
        except Exception as exc:
            logger.warning("chatbot_judge_failed", error=str(exc))


# ── Session registry ──────────────────────────────────────────────────────────

_sessions: Dict[str, ChatbotSession] = {}


def _key(user_id: str, session_id: str) -> str:
    return f"{user_id}::{session_id}"


def get_or_create_session(
    user_id: str,
    session_id: str = "default",
    conv_id: Optional[str] = None,
    is_group: bool = False,
    conv_name: Optional[str] = None,
    other_user_id: Optional[str] = None,
) -> ChatbotSession:
    k = _key(user_id, session_id)
    if k not in _sessions:
        _sessions[k] = ChatbotSession(
            user_id=user_id, conv_id=conv_id,
            is_group=is_group, conv_name=conv_name, other_user_id=other_user_id,
        )
    return _sessions[k]


def clear_session(user_id: str, session_id: Optional[str] = None) -> None:
    if session_id:
        _sessions.pop(_key(user_id, session_id), None)
    else:
        for k in list(_sessions):
            if k.startswith(f"{user_id}::"):
                del _sessions[k]
