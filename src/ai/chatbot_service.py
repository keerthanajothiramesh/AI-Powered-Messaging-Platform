import re
from typing import List, Dict, Any, Optional
from src.common.logger import get_logger
from src.ai.gemini_client import generate_with_tools, generate_text

logger = get_logger(__name__)

# ─── Input guardrails ─────────────────────────────────────────────────────────

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


def _moderate_input(text: str) -> str | None:
    """Return a rejection reason string if input should be blocked, else None."""
    if len(text) > _MAX_INPUT_LEN:
        return "Input too long."
    if _BLOCKED_RE.search(text):
        logger.warning("moderation_blocked", snippet=text[:80])
        return _BLOCKED_RESPONSE
    return None


SYSTEM_PROMPT = """You are an intelligent messaging assistant for an AI-powered chat platform.

You help users:
1. Find specific messages using semantic search
2. Summarise conversations and group discussions
3. Answer questions about chat history
4. Look up media files and attachments

Language: Detect the user's language and respond in the SAME language.
If the user writes in Japanese (日本語), respond entirely in Japanese.
If the user writes in English, respond in English.

Be concise, helpful, and friendly. Always cite your sources when referencing specific messages."""

CHATBOT_TOOLS = [
    {
        "name": "search_messages",
        "description": "Search chat history for relevant messages using semantic search",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "sender_name": {"type": "string", "description": "Filter by sender name (optional)"},
                "group_name": {"type": "string", "description": "Filter by group name (optional)"},
                "media_type": {"type": "string", "description": "Filter by media type: text/image/voice/video (optional)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_conversation_summary",
        "description": "Get a summary of a group conversation over a time period",
        "parameters": {
            "type": "object",
            "properties": {
                "group_name": {"type": "string", "description": "Name of the group to summarise"},
                "days": {"type": "string", "description": "Number of days to look back (default: 14)"},
            },
            "required": ["group_name"],
        },
    },
    {
        "name": "find_media",
        "description": "Find media files (images, videos, voice notes) in chat history",
        "parameters": {
            "type": "object",
            "properties": {
                "media_type": {"type": "string", "description": "Type of media: image/video/voice"},
                "keywords": {"type": "string", "description": "Keywords to search in media descriptions"},
            },
            "required": ["media_type"],
        },
    },
    {
        "name": "get_user_activity",
        "description": "Get information about a user's recent activity",
        "parameters": {
            "type": "object",
            "properties": {
                "user_name": {"type": "string", "description": "Name of the user"},
            },
            "required": ["user_name"],
        },
    },
]


class ChatbotSession:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.history: List[Dict] = []

    async def chat(self, message: str) -> Dict[str, Any]:
        rejection = _moderate_input(message)
        if rejection:
            return {"text": rejection, "tool_calls": [], "history_length": len(self.history)}

        self.history.append({"role": "user", "content": message})

        response = await generate_with_tools(
            prompt=message,
            tools=CHATBOT_TOOLS,
            conversation_history=self.history[:-1],
        )

        tool_results = []
        final_text = response.get("text", "")

        for tool_call in response.get("tool_calls", []):
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            logger.info("chatbot_tool_call", tool=tool_name, user_id=self.user_id)

            result = await _execute_tool(tool_name, tool_args)
            tool_results.append({"tool": tool_name, "result": result})

            if result:
                context = f"\n\nTool result from {tool_name}: {str(result)[:500]}"
                follow_up = await generate_text(
                    f"{SYSTEM_PROMPT}\n\nUser asked: {message}{context}\n\nProvide a helpful response based on the tool result.",
                    max_tokens=512,
                )
                final_text = follow_up

        self.history.append({"role": "model", "content": final_text})

        return {
            "text": final_text or "I couldn't find relevant information. Please try rephrasing your query.",
            "tool_calls": tool_results,
            "history_length": len(self.history),
        }


async def _execute_tool(tool_name: str, args: Dict) -> Any:
    try:
        if tool_name == "search_messages":
            from src.search.search_service import hybrid_search
            filters = {}
            if args.get("media_type"):
                filters["media_type"] = args["media_type"]
            results = await hybrid_search(args["query"], n_results=5, filters=filters)
            return [{"content": r["content"], "metadata": r.get("metadata", {})} for r in results]

        elif tool_name == "get_conversation_summary":
            from src.common.database import get_pg_pool
            pool = get_pg_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT group_id, group_name FROM groups WHERE group_name ILIKE $1",
                    f"%{args['group_name']}%",
                )
            if not row:
                return {"error": f"Group '{args['group_name']}' not found"}
            from src.ai.rag_service import summarise_conversation
            days = int(args.get("days", "14"))
            summary = await summarise_conversation(
                str(row["group_id"]), days=days, group_name=row["group_name"]
            )
            return {"group": row["group_name"], "summary": summary, "days": days}

        elif tool_name == "find_media":
            from src.ai.vector_store import get_vector_store
            vs = get_vector_store()
            if not vs:
                return []
            keywords = args.get("keywords", args.get("media_type", ""))
            results = vs.search_media(keywords, n_results=10, media_type=args.get("media_type"))
            return results

        elif tool_name == "get_user_activity":
            from src.common.database import get_pg_pool
            pool = get_pg_pool()
            async with pool.acquire() as conn:
                user = await conn.fetchrow(
                    "SELECT user_id, display_name, user_presence, last_seen FROM users WHERE display_name ILIKE $1",
                    f"%{args['user_name']}%",
                )
            if not user:
                return {"error": f"User '{args['user_name']}' not found"}
            return {
                "user": user["display_name"],
                "presence": user["user_presence"],
                "last_seen": user["last_seen"].isoformat() if user["last_seen"] else None,
            }

    except Exception as e:
        logger.error("tool_execution_failed", tool=tool_name, error=str(e))
        return {"error": str(e)}


_sessions: Dict[str, ChatbotSession] = {}


def get_or_create_session(user_id: str) -> ChatbotSession:
    if user_id not in _sessions:
        _sessions[user_id] = ChatbotSession(user_id)
    return _sessions[user_id]


def clear_session(user_id: str) -> None:
    _sessions.pop(user_id, None)
