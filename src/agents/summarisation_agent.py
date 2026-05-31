from typing import Dict, Any

from src.agents.base_agent import BaseAgent
from src.common.logger import get_logger

logger = get_logger(__name__)


class SummarisationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="SummarisationAgent",
            system_prompt="""You are an expert at summarising conversations.
Create clear, structured summaries that:
- Highlight key decisions and outcomes
- List action items
- Note important dates/deadlines
- Are concise (under 300 words)
- Use bullet points for clarity""",
        )

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        group_id  = input_data.get("group_id")
        days      = input_data.get("days", 14)
        group_name = input_data.get("group_name", "the group")

        logger.info("summarisation_agent_run", group_id=group_id, days=days)

        from src.ai.rag_service import summarise_conversation, _count_tokens, _chunk_by_tokens
        from src.common.database import get_mongo_db
        from datetime import datetime, timedelta, timezone

        # Collect token stats before summarising so we can return them
        db = get_mongo_db()
        since = datetime.now(timezone.utc) - timedelta(days=days)
        cursor = db.messages.find(
            {"group_id": group_id, "timestamp": {"$gte": since}, "deleted": {"$ne": True}}
        ).sort("timestamp", 1)

        from src.ai.rag_service import _MAX_MESSAGES, _format_messages
        messages = await cursor.to_list(length=_MAX_MESSAGES)
        message_count = len(messages)

        formatted = _format_messages(messages) if messages else ""
        approx_tokens = _count_tokens(formatted) if formatted else 0
        chunks = _chunk_by_tokens(messages) if messages else []

        summary = await summarise_conversation(
            group_id, days=days, group_name=group_name
        )

        # LLM-as-Judge quality gate
        from src.agents.judge_agent import JudgeAgent
        judgment = await JudgeAgent().evaluate(summary, input_data)

        if judgment.get("average_score", 10) < 7:
            logger.warning("summary_quality_low", score=judgment["average_score"])
            refined_prompt = (
                f"The previous summary scored {judgment['average_score']:.1f}/10.\n"
                f"Issues: {judgment.get('feedback', '')}\n"
                f"Please generate an improved summary for {group_name} addressing these issues."
            )
            summary = await self._generate(refined_prompt, max_tokens=1024)

        return {
            "agent": self.name,
            "group_id": group_id,
            "group_name": group_name,
            "days": days,
            "summary": summary,
            "quality_score": judgment.get("average_score", 0),
            # Token optimisation metadata — surfaced for observability
            "token_stats": {
                "message_count": message_count,
                "approx_tokens": approx_tokens,
                "chunks_used": len(chunks),
                "strategy": "hierarchical" if len(chunks) > 1 else "single-pass",
            },
        }
