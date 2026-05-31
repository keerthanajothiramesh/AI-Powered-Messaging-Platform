from typing import Dict, Any
from src.common.logger import get_logger
from src.ai.gemini_client import generate_text

logger = get_logger(__name__)

JUDGE_PROMPT = """You are an LLM-as-Judge evaluating the quality of an AI-generated conversation summary.

Score the summary on these criteria (0-10 each):
1. Relevance: Does it cover the main topics discussed?
2. Accuracy: Are the facts correct based on the conversation?
3. Completeness: Does it capture key decisions, action items, and important info?

Respond in this exact format:
RELEVANCE: [0-10]
ACCURACY: [0-10]
COMPLETENESS: [0-10]
FEEDBACK: [one sentence of constructive feedback]"""


class JudgeAgent:
    async def evaluate(self, summary: str, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("judge_agent_evaluate")
        prompt = f"""Summary to evaluate:
\"\"\"{summary}\"\"\"

Context: Group {context.get('group_name', 'unknown')}, covering {context.get('days', 14)} days."""

        try:
            response = await generate_text(prompt, system_prompt=JUDGE_PROMPT, max_tokens=256)
            return _parse_judgment(response)
        except Exception as e:
            logger.error("judge_agent_failed", error=str(e))
            return {"relevance": 7, "accuracy": 7, "completeness": 7, "average_score": 7, "feedback": ""}


def _parse_judgment(response: str) -> Dict[str, Any]:
    result = {"relevance": 7, "accuracy": 7, "completeness": 7, "feedback": "", "average_score": 7}
    try:
        for line in response.split("\n"):
            if line.startswith("RELEVANCE:"):
                result["relevance"] = int(line.split(":")[1].strip().split()[0])
            elif line.startswith("ACCURACY:"):
                result["accuracy"] = int(line.split(":")[1].strip().split()[0])
            elif line.startswith("COMPLETENESS:"):
                result["completeness"] = int(line.split(":")[1].strip().split()[0])
            elif line.startswith("FEEDBACK:"):
                result["feedback"] = line.split(":", 1)[1].strip()
        result["average_score"] = (result["relevance"] + result["accuracy"] + result["completeness"]) / 3
    except Exception as e:
        logger.warning("judgment_parse_failed", error=str(e))
    return result
