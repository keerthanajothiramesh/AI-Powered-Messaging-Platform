"""Tool schemas for multilingual (Japanese/English) AI capabilities."""

MULTILINGUAL_TOOLS = [
    {
        "name": "suggest_replies_in_language",
        "description": (
            "Suggest 3 reply options to a message from someone, written in their language "
            "(e.g. Japanese), each with an English translation and tone label. "
            "Use when the user asks 'what should I reply to X' or 'help me reply to [name]'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sender_name": {"type": "string", "description": "Name of the person who sent the message"},
                "reply_language": {"type": "string", "description": "Language to compose replies in (default: Japanese)"},
                "num_options": {"type": "integer", "description": "Number of reply options (default: 3)"},
            },
            "required": ["sender_name"],
        },
    },
    {
        "name": "decode_voice_message",
        "description": (
            "Find the most recent message from a sender, detect its language, translate it, "
            "and extract key points. Especially useful for Japanese messages the user can't read."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sender_name": {"type": "string", "description": "Name of the sender"},
                "translate_to": {"type": "string", "description": "Language to translate to (default: English)"},
            },
            "required": ["sender_name"],
        },
    },
    {
        "name": "compose_message_in_language",
        "description": (
            "Compose a message in a foreign language (e.g. Japanese) at multiple formality levels "
            "(casual, polite, formal keigo). Use when user says 'help me tell [name] that...' "
            "or 'write a message in Japanese saying...'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "intent": {"type": "string", "description": "What the user wants to say, in their own language"},
                "language": {"type": "string", "description": "Target language (default: Japanese)"},
                "recipient_name": {"type": "string", "description": "Recipient name for context (optional)"},
                "formality": {"type": "string", "description": "Preferred level: casual, polite, or formal_keigo"},
            },
            "required": ["intent"],
        },
    },
    {
        "name": "explain_message_context",
        "description": (
            "Explain the cultural and linguistic context of a sender's last message, "
            "especially Japanese business culture nuances like indirect 'no' responses."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sender_name": {"type": "string", "description": "Name of the sender whose message to explain"},
                "include_cultural_notes": {"type": "boolean", "description": "Include cultural context (default: true)"},
            },
            "required": ["sender_name"],
        },
    },
    {
        "name": "cross_language_catchup",
        "description": (
            "Catch up on a group conversation that may be in another language (e.g. Japanese). "
            "Translates and summarizes everything in the user's preferred language."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "group_name": {"type": "string", "description": "Name of the group"},
                "hours_ago": {"type": "integer", "description": "How many hours back to look (default: 8)"},
                "output_language": {"type": "string", "description": "Language for the summary (default: English)"},
            },
            "required": ["group_name"],
        },
    },
    {
        "name": "multilingual_group_summary",
        "description": (
            "Summarize a group chat broken down by speaker, with per-person language detection "
            "and translation. Use when asking who said what in a mixed-language group."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "group_name": {"type": "string", "description": "Name of the group"},
                "output_language": {"type": "string", "description": "Output language (default: English)"},
                "days": {"type": "integer", "description": "Days to look back (default: 7)"},
            },
            "required": ["group_name"],
        },
    },
]
