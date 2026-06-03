"""Chatbot tool schemas and system prompt — single source of truth for all tool definitions."""

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
        "description": "Fetch unread image messages across all groups and DMs the user belongs to.",
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
    # ── Informational / stats ──────────────────────────────────────────────────
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
    # ── Search & retrieval ─────────────────────────────────────────────────────
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
        "description": (
            "Find uploaded documents that are relevant to the user's topic. "
            "Always pass the user's actual topic or question as 'query' so only relevant files are returned."
        ),
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "The user's topic or question used to filter documents by relevance (e.g. 'leave policy', 'Q1 revenue')"},
            "group_name": {"type": "string", "description": "Optional: limit to a specific group"},
        }, "required": ["query"]},
    },
    {
        "name": "summarize_document",
        "description": (
            "Read the full content of a specific uploaded document and summarize it, or answer a question "
            "about its content. Use this whenever the user asks to summarize a document, asks what a document "
            "contains, or asks a specific question about a document (PDF, DOCX, report, etc.)."
        ),
        "parameters": {"type": "object", "properties": {
            "filename": {"type": "string", "description": "Filename or partial name of the document (e.g. 'Q1_Financial_Report')"},
            "question": {"type": "string", "description": "Optional specific question to answer from the document"},
        }, "required": ["filename"]},
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
    # ── Multilingual ───────────────────────────────────────────────────────────
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
    # ── Presence & membership ──────────────────────────────────────────────────
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
- For 'summarize [document]', 'what does [document] say', or any question about a document's content: use 'summarize_document' with the filename (partial name is fine). Pass the user's question in the 'question' field when they ask something specific.
- When a result has source='document', always mention the filename.
- For 'help me reply to [name]': use 'suggest_replies_in_language'. For 'what does [name] mean': use 'explain_message_context'.
- For 'compose in Japanese'/'tell [name] that...': use 'compose_message_in_language'. For voice/message decode: use 'decode_voice_message'.
- For 'catch me up on [foreign-language group]': use 'cross_language_catchup'. For 'summarize [group] by person': use 'multilingual_group_summary'.
- Multilingual: summaries always in English; chat responses match the user's language.

Language: Detect the user's language and respond in the SAME language.
Be concise, helpful, and friendly."""
