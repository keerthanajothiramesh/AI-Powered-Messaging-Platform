from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from src.common.logger import get_logger

logger = get_logger(__name__)


class BaseAgent(ABC):
    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt

    @abstractmethod
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        pass

    async def _generate(self, prompt: str, max_tokens: int = 1024) -> str:
        from src.ai.gemini_client import generate_text
        logger.info("agent_generate", agent=self.name)
        return await generate_text(prompt, system_prompt=self.system_prompt, max_tokens=max_tokens)
