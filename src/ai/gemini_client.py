import asyncio
from typing import Optional, List, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.common.logger import get_logger

logger = get_logger(__name__)

_client = None
_model = None


def init_gemini(api_key: str) -> None:
    global _client, _model
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        _model = genai.GenerativeModel("gemini-2.5-flash")
        _client = genai
        logger.info("gemini_initialized", model="gemini-1.5-flash")
    except Exception as e:
        logger.error("gemini_init_failed", error=str(e))


def get_gemini_client():
    return _client


_circuit_failures = 0
_circuit_open = False


def _record_failure():
    global _circuit_failures, _circuit_open
    _circuit_failures += 1
    if _circuit_failures >= 3:
        _circuit_open = True
        logger.warning("gemini_circuit_open")


def _record_success():
    global _circuit_failures, _circuit_open
    _circuit_failures = 0
    _circuit_open = False


async def generate_text(
    prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> str:
    if _circuit_open:
        logger.warning("gemini_circuit_open_fallback")
        return await _local_fallback(prompt)

    if not _model:
        return await _local_fallback(prompt)

    try:
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _model.generate_content(
                full_prompt,
                generation_config={"max_output_tokens": max_tokens, "temperature": temperature},
            ),
        )
        _record_success()
        return response.text
    except Exception as e:
        logger.error("gemini_generate_failed", error=str(e))
        _record_failure()
        return await _local_fallback(prompt)


async def generate_with_tools(
    prompt: str,
    tools: List[Dict],
    conversation_history: Optional[List[Dict]] = None,
    system_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    if not _model or _circuit_open:
        return {"text": await _local_fallback(prompt), "tool_calls": []}

    try:
        import google.generativeai as genai

        tool_defs = []
        for tool in tools:
            tool_defs.append(
                genai.protos.Tool(
                    function_declarations=[
                        genai.protos.FunctionDeclaration(
                            name=tool["name"],
                            description=tool["description"],
                            parameters=genai.protos.Schema(
                                type=genai.protos.Type.OBJECT,
                                properties={
                                    k: genai.protos.Schema(
                                        type=genai.protos.Type.STRING,
                                        description=v.get("description", ""),
                                    )
                                    for k, v in tool.get("parameters", {}).get("properties", {}).items()
                                },
                                required=tool.get("parameters", {}).get("required", []),
                            ),
                        )
                    ]
                )
            )

        model_with_tools = genai.GenerativeModel(
            "gemini-2.5-flash",
            tools=tool_defs,
            system_instruction=system_prompt if system_prompt else None,
        )
        history = []
        if conversation_history:
            for msg in conversation_history:
                history.append({"role": msg["role"], "parts": [msg["content"]]})

        chat = model_with_tools.start_chat(history=history)
        response = await asyncio.get_event_loop().run_in_executor(
            None, lambda: chat.send_message(prompt)
        )
        _record_success()

        tool_calls = []
        text_parts = []
        for part in response.parts:
            if hasattr(part, "function_call") and part.function_call:
                tool_calls.append({
                    "name": part.function_call.name,
                    "args": dict(part.function_call.args),
                })
            if hasattr(part, "text") and part.text:
                text_parts.append(part.text)

        return {"text": " ".join(text_parts), "tool_calls": tool_calls}
    except Exception as e:
        logger.error("gemini_tool_call_failed", error=str(e))
        _record_failure()
        return {"text": await _local_fallback(prompt), "tool_calls": []}


async def _local_fallback(prompt: str) -> str:
    logger.info("using_local_fallback")
    from src.ai.local_fallback import generate_local
    return await generate_local(prompt)
