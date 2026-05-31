import re
from typing import List, Dict, Any, Optional
from src.common.logger import get_logger
from src.ai.gemini_client import generate_with_tools, generate_text
from src.ai.pii_guard import scan_and_anonymize

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
    if len(text) > _MAX_INPUT_LEN:
        return "Input too long."
    if _BLOCKED_RE.search(text):
        logger.warning("moderation_blocked", snippet=text[:80])
        return _BLOCKED_RESPONSE
    return None


def _build_system_prompt(is_group: bool, conv_name: str) -> str:
    if conv_name:
        ctx = (
            f"\n\nYou are currently the AI assistant for the **{'group' if is_group else 'direct message'}** "
            f"conversation: '{conv_name}'."
        )
    else:
        ctx = ""
    return f"""You are an intelligent messaging assistant for an AI-powered chat platform.{ctx}

You help users:
1. Find specific messages using semantic search
2. Summarise conversations and group discussions
3. Answer questions about chat history
4. Answer questions from uploaded documents, PDFs, reports, and shared files
5. Look up media files and attachments

IMPORTANT RULES:
- When the user asks to 'summarize', 'summarise', 'give a summary', 'what was discussed', or similar, ALWAYS call the 'summarise_current_conversation' tool immediately. Do NOT ask which conversation or group — you already know the context.
- For questions about specific messages OR documents/files, always use 'search_messages' first.
- When a result has source='document', mention the filename so the user knows which file you're quoting.
- Multilingual: always output summaries in English even if source messages are in another language.
- Use friendly emojis occasionally to make responses more engaging. ✨

Language: Detect the user's language and respond in the SAME language.
Be concise, helpful, and friendly."""


CHATBOT_TOOLS = [
    {
        "name": "summarise_current_conversation",
        "description": (
            "Summarise the current conversation. Automatically uses the correct group or DM context — "
            "do NOT ask the user which conversation. Use this whenever the user asks to summarize, "
            "give a summary, or asks what was discussed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back (default 14)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "search_messages",
        "description": (
            "Search chat history AND uploaded documents/files for relevant content using semantic search. "
            "Use this for any question about past messages, shared files, PDFs, reports, or documents. "
            "Results include both chat messages and document chunks with their source noted."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "sender_name": {"type": "string", "description": "Filter by sender name (optional)"},
                "group_name": {"type": "string", "description": "Filter by group name (optional)"},
                "media_type": {
                    "type": "string",
                    "description": "Filter by media type: text/image/voice/video (optional)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_conversation_summary",
        "description": "Get a summary of a specific group conversation by name (use when user names a different group)",
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
    {
        "name": "fetch_unread_images",
        "description": (
            "Fetch unread image messages across all groups and DMs the user belongs to. "
            "Use this when the user asks to 'show unread images', 'find images I haven't seen', "
            "or 'show me pictures from my chats'."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


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
        rejection = _moderate_input(message)
        if rejection:
            return {"text": rejection, "tool_calls": [], "history_length": len(self.history)}

        safe_message, detected_pii = scan_and_anonymize(message)
        if detected_pii:
            logger.info("pii_anonymized", types=detected_pii, user_id=self.user_id)

        self.history.append({"role": "user", "content": safe_message})
        system_prompt = _build_system_prompt(self.is_group, self.conv_name)

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

            result = await self._execute_tool(tool_name, tool_args)
            tool_results.append({"tool": tool_name, "result": result})

            if result:
                context = f"\n\nTool result from {tool_name}: {str(result)[:500]}"
                final_text = await generate_text(
                    f"User asked: {message}{context}\n\nProvide a helpful, emoji-friendly response based on the tool result.",
                    system_prompt=system_prompt,
                    max_tokens=512,
                )

        self.history.append({"role": "model", "content": final_text})

        return {
            "text": final_text or "I couldn't find relevant information. Please try rephrasing your query. 🔍",
            "tool_calls": tool_results,
            "history_length": len(self.history),
        }

    async def _execute_tool(self, tool_name: str, args: Dict) -> Any:
        try:
            if tool_name == "summarise_current_conversation":
                days = int(args.get("days", 14))
                if self.is_group and self.conv_id:
                    from src.ai.rag_service import summarise_conversation
                    summary = await summarise_conversation(
                        self.conv_id, days=days, group_name=self.conv_name
                    )
                    return {"type": "group", "name": self.conv_name, "summary": summary, "days": days}
                elif not self.is_group and self.other_user_id:
                    from src.ai.rag_service import summarise_dm
                    summary = await summarise_dm(
                        self.user_id,
                        self.other_user_id,
                        days=days,
                        other_user_name=self.conv_name,
                    )
                    return {"type": "dm", "name": self.conv_name, "summary": summary, "days": days}
                else:
                    return {"error": "No conversation context available. Please open a specific chat first."}

            elif tool_name == "search_messages":
                from src.search.search_service import hybrid_search
                filters = {}
                if args.get("media_type"):
                    filters["media_type"] = args["media_type"]
                results = await hybrid_search(args["query"], n_results=8, filters=filters)
                return [
                    {
                        "content": r["content"],
                        "source": r.get("source_type", "message"),
                        "filename": r.get("metadata", {}).get("filename", ""),
                        "metadata": r.get("metadata", {}),
                    }
                    for r in results
                ]

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
                        "SELECT user_id, display_name, user_presence, last_seen "
                        "FROM users WHERE display_name ILIKE $1",
                        f"%{args['user_name']}%",
                    )
                if not user:
                    return {"error": f"User '{args['user_name']}' not found"}
                return {
                    "user": user["display_name"],
                    "presence": user["user_presence"],
                    "last_seen": user["last_seen"].isoformat() if user["last_seen"] else None,
                }

            elif tool_name == "fetch_unread_images":
                from src.common.database import get_mongo_db, get_pg_pool
                db = get_mongo_db()
                pool = get_pg_pool()
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT g.group_id, g.group_name FROM groups g "
                        "JOIN group_members gm ON g.group_id = gm.group_id "
                        "WHERE gm.user_id = $1", self.user_id
                    )
                group_map = {str(r["group_id"]): r["group_name"] for r in rows}
                group_ids = list(group_map.keys())
                cursor = db.messages.find(
                    {
                        "media_type": "image",
                        "$or": [
                            {"receiver_id": self.user_id, "read_status": "unread"},
                            {
                                "group_id": {"$in": group_ids},
                                "sender_id": {"$ne": self.user_id},
                                "read_by": {"$not": {"$elemMatch": {"$eq": self.user_id}}},
                            },
                        ],
                    },
                    {"message_id": 1, "media_url": 1, "content": 1, "sender_id": 1,
                     "group_id": 1, "receiver_id": 1, "timestamp": 1},
                ).limit(20).sort("timestamp", -1)
                results = []
                async for msg in cursor:
                    gid = str(msg.get("group_id") or "")
                    ts = msg.get("timestamp")
                    results.append({
                        "message_id": str(msg.get("message_id") or str(msg["_id"])),
                        "media_url": msg.get("media_url") or "",
                        "content": msg.get("content") or "",
                        "sender_id": str(msg.get("sender_id") or ""),
                        "group_id": gid,
                        "receiver_id": str(msg.get("receiver_id") or ""),
                        "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts or ""),
                        "group_name": group_map.get(gid, ""),
                    })
                return results

        except Exception as e:
            logger.error("tool_execution_failed", tool=tool_name, error=str(e))
            return {"error": str(e)}


# ─── Session management ───────────────────────────────────────────────────────

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
            user_id=user_id,
            conv_id=conv_id,
            is_group=is_group,
            conv_name=conv_name,
            other_user_id=other_user_id,
        )
    return _sessions[k]


def clear_session(user_id: str, session_id: Optional[str] = None) -> None:
    if session_id:
        _sessions.pop(_key(user_id, session_id), None)
    else:
        for k in list(_sessions):
            if k.startswith(f"{user_id}::"):
                del _sessions[k]
