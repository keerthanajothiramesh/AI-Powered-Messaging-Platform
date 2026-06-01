"""Additional chatbot tool schemas — informational, compositional, and search tools."""

EXTRA_TOOLS = [
    {
        "name": "get_my_action_items",
        "description": (
            "Find tasks and action items assigned to or mentioning the current user "
            "in recent messages. Use when asked about pending tasks or to-dos."
        ),
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Days to look back (default 7)"},
        }, "required": []},
    },
    {
        "name": "get_group_activity_stats",
        "description": (
            "Show who sent how many messages in a group over the last N days. "
            "Use for 'how active is the team' or 'who is most active' questions."
        ),
        "parameters": {"type": "object", "properties": {
            "group_name": {"type": "string", "description": "Name of the group"},
            "days": {"type": "integer", "description": "Days to look back (default 7)"},
        }, "required": ["group_name"]},
    },
    {
        "name": "set_my_status",
        "description": "Update the current user's presence status (online / offline / busy / away).",
        "parameters": {"type": "object", "properties": {
            "status": {"type": "string", "description": "One of: online, offline, busy, away"},
        }, "required": ["status"]},
    },
    {
        "name": "get_unread_count",
        "description": "Count unread messages across all DMs and groups for the current user.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "draft_reply",
        "description": (
            "Draft a reply to a specific message. Describe the message you want to reply to "
            "and optionally specify a tone. Returns a ready-to-send draft."
        ),
        "parameters": {"type": "object", "properties": {
            "message_about": {"type": "string", "description": "Describe the message to reply to"},
            "tone": {"type": "string", "description": "Tone: professional / casual / formal (default: professional)"},
        }, "required": ["message_about"]},
    },
    {
        "name": "search_messages_by_time",
        "description": (
            "Search messages within a specific time window. "
            "Use for 'what happened yesterday', 'messages from last 2 hours', etc."
        ),
        "parameters": {"type": "object", "properties": {
            "hours_ago": {"type": "integer", "description": "Look back this many hours (e.g. 24 for yesterday)"},
            "keyword": {"type": "string", "description": "Optional keyword to filter content"},
        }, "required": ["hours_ago"]},
    },
    {
        "name": "list_shared_documents",
        "description": "List files and documents shared in conversations, optionally filtered by group or topic.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Topic or file type to search for"},
            "group_name": {"type": "string", "description": "Optional: limit to a specific group"},
        }, "required": []},
    },
    {
        "name": "translate_message",
        "description": "Find a specific message and translate it to another language.",
        "parameters": {"type": "object", "properties": {
            "message_about": {"type": "string", "description": "Describe the message to translate"},
            "language": {"type": "string", "description": "Target language (e.g. English, Japanese, French)"},
        }, "required": ["message_about", "language"]},
    },
    {
        "name": "schedule_reminder",
        "description": "Save a reminder for yourself to review later.",
        "parameters": {"type": "object", "properties": {
            "message": {"type": "string", "description": "What to remind about"},
            "remind_at": {"type": "string", "description": "When (ISO datetime or natural language like 'tomorrow 3pm')"},
        }, "required": ["message"]},
    },
    {
        "name": "get_reminders",
        "description": "List all pending reminders for the current user.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "extract_meetings",
        "description": (
            "Extract meeting invites, calls, and scheduled events mentioned in recent messages. "
            "Use for 'what meetings do I have' or 'are there any upcoming calls'."
        ),
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Days to look back (default 7)"},
        }, "required": []},
    },
    {
        "name": "catchup_for_group",
        "description": (
            "Generate a targeted catch-up summary for one specific group covering a time window. "
            "Use when the user asks 'what happened in [group] since [time]'."
        ),
        "parameters": {"type": "object", "properties": {
            "group_name": {"type": "string", "description": "Name of the group"},
            "hours_ago": {"type": "integer", "description": "How many hours back to cover (default 48)"},
        }, "required": ["group_name"]},
    },
]
