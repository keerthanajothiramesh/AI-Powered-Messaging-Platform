"""Chatbot tool schemas exposed to the LLM via function calling."""
from typing import Optional

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
                "days": {"type": "integer", "description": "Number of days to look back (default 14)"},
            },
            "required": [],
        },
    },
    {
        "name": "search_messages",
        "description": (
            "Search chat history AND uploaded documents/files for relevant content. "
            "Results include both chat messages and document chunks with their source noted."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "sender_name": {"type": "string", "description": "Filter by sender name (optional)"},
                "group_name": {"type": "string", "description": "Filter by group name (optional)"},
                "media_type": {"type": "string", "description": "Filter: text/image/voice/video (optional)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_conversation_summary",
        "description": "Get a summary of a specific group conversation by name",
        "parameters": {
            "type": "object",
            "properties": {
                "group_name": {"type": "string", "description": "Name of the group to summarise"},
                "days": {"type": "string", "description": "Days to look back (default: 14)"},
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
                "media_type": {"type": "string", "description": "Type: image/video/voice"},
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
            "Fetch unread image messages across all groups and DMs the user belongs to."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "send_message",
        "description": (
            "Send a direct message to another user by name. Use when the user asks to "
            "send, forward, or remind someone of something."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "recipient_name": {"type": "string", "description": "Display name of the recipient"},
                "message": {"type": "string", "description": "Message text to send"},
            },
            "required": ["recipient_name", "message"],
        },
    },
    {
        "name": "get_group_members_status",
        "description": (
            "List members of a group with their online/offline status. "
            "Use when the user asks who is online in a group."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "group_name": {"type": "string", "description": "Name of the group"},
            },
            "required": ["group_name"],
        },
    },
]


def build_system_prompt(is_group: bool, conv_name: str) -> str:
    ctx = ""
    if conv_name:
        kind = "group" if is_group else "direct message"
        ctx = f"\n\nYou are currently the AI assistant for the **{kind}** conversation: '{conv_name}'."
    return f"""You are an intelligent messaging assistant for an AI-powered chat platform.{ctx}

You help users:
1. Find specific messages using semantic search
2. Summarise conversations and group discussions
3. Answer questions about chat history
4. Answer questions from uploaded documents, PDFs, reports, and shared files
5. Look up media files and attachments

IMPORTANT RULES:
- When the user asks to 'summarize', always call 'summarise_current_conversation' immediately.
- For questions about specific messages OR documents, always use 'search_messages' first.
- When a result has source='document', mention the filename.
- Multilingual: always output summaries in English even if source messages are in another language.

Language: Detect the user's language and respond in the SAME language.
Be concise, helpful, and friendly."""
