from typing import Dict, Any, Optional
from src.common.logger import get_logger
from src.ai.gemini_client import generate_text

logger = get_logger(__name__)

ROUTER_PROMPT = """You are an orchestrator agent. Classify the user's intent into ONE category:
- search: User wants to find specific messages
- summarise: User wants a conversation summary
- moderation: Content needs moderation review
- notification: Notification timing analysis
- delivery: Message delivery recovery

User query: "{query}"

Respond with just the category name."""


async def orchestrate(query: str, context: Optional[Dict] = None) -> Dict[str, Any]:
    context = context or {}
    logger.info("orchestrator_run", query=query[:50])

    intent_prompt = ROUTER_PROMPT.format(query=query)
    intent = await generate_text(intent_prompt, max_tokens=10)
    intent = intent.strip().lower()

    logger.info("orchestrator_intent", intent=intent)

    if "search" in intent:
        from src.agents.search_agent import SearchAgent
        agent = SearchAgent()
        return await agent.run({**context, "query": query})

    elif "summarise" in intent or "summar" in intent:
        from src.agents.summarisation_agent import SummarisationAgent
        agent = SummarisationAgent()
        return await agent.run({**context, "query": query})

    elif "moderat" in intent:
        from src.agents.moderation_agent import ModerationAgent
        agent = ModerationAgent()
        return await agent.run({**context, "content": query})

    elif "notif" in intent:
        from src.agents.notification_agent import NotificationAgent
        agent = NotificationAgent()
        return await agent.run({**context, "content": query})

    elif "delivery" in intent:
        from src.agents.delivery_agent import DeliveryAgent
        agent = DeliveryAgent()
        return await agent.run(context)

    else:
        from src.agents.search_agent import SearchAgent
        agent = SearchAgent()
        return await agent.run({**context, "query": query})
