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
        group_id   = input_data.get("group_id")
        days       = input_data.get("days", 14)
        group_name = input_data.get("group_name", "the group")

        logger.info("summarisation_agent_run", group_id=group_id, days=days)

        # Single DB call — returns both summary text and token stats
        from src.ai.rag_service import summarise_with_stats
        result = await summarise_with_stats(group_id, days=days, group_name=group_name)

        summary     = result["summary"]
        token_stats = result["token_stats"]

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
            # Re-evaluate refined summary
            judgment = await JudgeAgent().evaluate(summary, input_data)

        # Persist judge scores to MongoDB for feedback loop
        from src.agents.feedback_store import save_summary_feedback
        feedback_id = await save_summary_feedback(
            group_id=group_id or "",
            group_name=group_name,
            days=days,
            summary=summary,
            judgment=judgment,
        )

        return {
            "agent":         self.name,
            "group_id":      group_id,
            "group_name":    group_name,
            "days":          days,
            "summary":       summary,
            "quality_score": judgment.get("average_score", 0),
            "feedback_id":   feedback_id,
            "token_stats":   token_stats,
        }
