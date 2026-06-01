"""Chatbot tool schemas exposed to the LLM via function calling."""
from typing import Optional

from src.ai.chatbot.tools_extra import EXTRA_TOOLS
from src.ai.chatbot.tools_multilingual import MULTILINGUAL_TOOLS

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
    *EXTRA_TOOLS,
    *MULTILINGUAL_TOOLS,
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
1. Find specific messages using semantic or time-based search
2. Summarise conversations — current, specific group, or targeted time window
3. Answer questions from chat history and uploaded documents/files
4. Look up media, action items, meetings, and team activity stats
5. Send messages, draft replies, translate messages, set status
6. Schedule and retrieve reminders
7. Check who is online in a group or get unread counts
8. Multilingual support — reply in Japanese, compose messages, translate, cross-language summaries

IMPORTANT RULES:
- For 'summarize this conversation': call 'summarise_current_conversation'.
- For 'what happened in [group] since [time]': call 'catchup_for_group'.
- For 'what did I miss while offline': call 'summarise_current_conversation' (overall) or 'catchup_for_group' (specific group).
- For specific message lookup: use 'search_messages'. For time-filtered: use 'search_messages_by_time'.
- For 'send a reminder to X' or 'message X': use 'send_message'.
- For 'set me as busy/away': use 'set_my_status'.
- When a result has source='document', always mention the filename.
- For 'help me reply to [name]': use 'suggest_replies_in_language'. For 'what does [name] mean': use 'explain_message_context'.
- For 'compose in Japanese'/'tell [name] that...': use 'compose_message_in_language'. For voice/message decode: use 'decode_voice_message'.
- For 'catch me up on [foreign-language group]': use 'cross_language_catchup'. For 'summarize [group] by person': use 'multilingual_group_summary'.
- Multilingual: summaries always in English; chat responses match the user's language.

Language: Detect the user's language and respond in the SAME language.
Be concise, helpful, and friendly."""
