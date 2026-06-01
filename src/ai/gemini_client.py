import asyncio
import json
from typing import Optional, List, Dict, Any
from src.common.logger import get_logger

logger = get_logger(__name__)

_client = None
_MODEL = "gpt-4o-mini"


def init_openai(api_key: str) -> None:
    global _client
    try:
        from openai import AsyncOpenAI
        _client = AsyncOpenAI(api_key=api_key)
        logger.info("openai_initialized", model=_MODEL)
    except Exception as e:
        logger.error("openai_init_failed", error=str(e))


def get_openai_client():
    return _client


_circuit_failures = 0
_circuit_open = False
_circuit_opened_at: Optional[float] = None
_CIRCUIT_RESET_SECONDS = 30


def _record_failure():
    global _circuit_failures, _circuit_open, _circuit_opened_at
    _circuit_failures += 1
    if _circuit_failures >= 3:
        if not _circuit_open:
            _circuit_open = True
            _circuit_opened_at = asyncio.get_event_loop().time()
            logger.warning("openai_circuit_open")


def _record_success():
    global _circuit_failures, _circuit_open, _circuit_opened_at
    _circuit_failures = 0
    _circuit_open = False
    _circuit_opened_at = None


def _is_circuit_open() -> bool:
    global _circuit_open, _circuit_opened_at, _circuit_failures
    if not _circuit_open:
        return False
    try:
        elapsed = asyncio.get_event_loop().time() - (_circuit_opened_at or 0)
    except Exception:
        elapsed = 0
    if elapsed >= _CIRCUIT_RESET_SECONDS:
        _circuit_open = False
        _circuit_failures = 0
        logger.info("openai_circuit_half_open", elapsed=round(elapsed))
        return False
    return True


async def generate_text(
    prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> str:
    if _is_circuit_open():
        logger.warning("openai_circuit_open_fallback")
        return await _local_fallback(prompt)

    if not _client:
        return await _local_fallback(prompt)

    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await _client.chat.completions.create(
            model=_MODEL,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        _record_success()
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.error("openai_generate_failed", error=str(e))
        _record_failure()
        return await _local_fallback(prompt)


async def generate_with_tools(
    prompt: str,
    tools: List[Dict],
    conversation_history: Optional[List[Dict]] = None,
    system_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    if not _client or _is_circuit_open():
        return {"text": await _local_fallback(prompt), "tool_calls": []}

    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if conversation_history:
            for msg in conversation_history:
                role = "assistant" if msg["role"] == "model" else msg["role"]
                messages.append({"role": role, "content": msg["content"]})
        messages.append({"role": "user", "content": prompt})

        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                },
            }
            for tool in tools
        ]

        response = await _client.chat.completions.create(
            model=_MODEL,
            messages=messages,
            tools=openai_tools if openai_tools else None,
        )
        _record_success()

        msg = response.choices[0].message
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}
                tool_calls.append({"name": tc.function.name, "args": args})

        return {"text": msg.content or "", "tool_calls": tool_calls}
    except Exception as e:
        logger.error("openai_tool_call_failed", error=str(e))
        _record_failure()
        return {"text": await _local_fallback(prompt), "tool_calls": []}


async def _local_fallback(prompt: str) -> str:
    logger.info("using_local_fallback")
    from src.ai.local_fallback import generate_local
    return await generate_local(prompt)
