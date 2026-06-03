"""Parallel chunk summarisation and recursive hierarchical merge for large conversation RAG pipelines."""
import asyncio
from typing import Callable, Dict, List, Optional

from src.ai.gemini_client import generate_text
from src.ai.rag.chunking import count_tokens, _PARALLEL_BATCH, _MERGE_TOKEN_LIMIT
from src.ai.rag.formatting import format_messages
from src.common.logger import get_logger

logger = get_logger(__name__)


async def summarise_chunks_parallel(
    chunks: List[List[Dict]],
    prompt_fn: Callable[[str], str],
    system_prompt: str,
    max_tokens: int = 512,
    user_map: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Summarise all chunks, running up to _PARALLEL_BATCH at a time."""
    _user_map = user_map or {}

    async def _one(chunk: List[Dict]) -> str:
        text = format_messages(chunk, _user_map)
        return await generate_text(
            prompt_fn(text), system_prompt=system_prompt, max_tokens=max_tokens
        )

    results: List[str] = []
    total_batches = (len(chunks) + _PARALLEL_BATCH - 1) // _PARALLEL_BATCH

    for i in range(0, len(chunks), _PARALLEL_BATCH):
        batch = chunks[i: i + _PARALLEL_BATCH]
        batch_results = await asyncio.gather(*[_one(c) for c in batch])
        results.extend(batch_results)
        logger.info(
            "summarise_batch_done",
            batch=i // _PARALLEL_BATCH + 1,
            total_batches=total_batches,
        )
    return results


async def hierarchical_merge(
    summaries: List[str], system_prompt: str, label: str = "conversation"
) -> str:
    """Recursively merge summaries until a single string remains."""
    if len(summaries) == 1:
        return summaries[0]

    combined = "\n\n---\n\n".join(summaries)
    if count_tokens(combined) <= _MERGE_TOKEN_LIMIT:
        prompt = (
            f"Merge these {len(summaries)} partial summaries of '{label}' "
            f"into one coherent final summary:\n\n{combined}"
        )
        return await generate_text(prompt, system_prompt=system_prompt, max_tokens=1024)

    groups: List[List[str]] = []
    current_group: List[str] = []
    current_tokens = 0
    for s in summaries:
        tokens = count_tokens(s)
        if current_group and current_tokens + tokens > _MERGE_TOKEN_LIMIT:
            groups.append(current_group)
            current_group, current_tokens = [s], tokens
        else:
            current_group.append(s)
            current_tokens += tokens
    if current_group:
        groups.append(current_group)

    logger.info("hierarchical_merge", label=label, groups=len(groups))

    async def _merge_group(group: List[str]) -> str:
        text = "\n\n---\n\n".join(group)
        prompt = f"Merge these partial summaries of '{label}' into one coherent summary:\n\n{text}"
        return await generate_text(prompt, system_prompt=system_prompt, max_tokens=1024)

    merged = await asyncio.gather(*[_merge_group(g) for g in groups])
    return await hierarchical_merge(list(merged), system_prompt, label)
