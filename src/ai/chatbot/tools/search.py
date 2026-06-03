"""Search & retrieval tool handlers: time search, documents, group catch-up."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from src.common.logger import get_logger

logger = get_logger(__name__)


async def search_messages_by_time(args: Dict, session) -> Any:
    from src.common.database import get_mongo_db, get_pg_pool
    db = get_mongo_db()
    pool = get_pg_pool()
    uid = str(session.user_id)
    hours = int(args.get("hours_ago", 24))
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT g.group_id FROM groups g JOIN group_members gm "
            "ON g.group_id = gm.group_id WHERE gm.user_id = $1", uid
        )
    gids = [str(r["group_id"]) for r in rows]

    match: Dict = {
        "timestamp": {"$gte": since}, "deleted": {"$ne": True},
        "$or": [{"sender_id": uid}, {"receiver_id": uid}, {"group_id": {"$in": gids}}],
    }
    if args.get("keyword"):
        match["content"] = {"$regex": args["keyword"], "$options": "i"}

    cursor = db.messages.find(
        match, {"content": 1, "sender_id": 1, "group_id": 1, "timestamp": 1, "media_type": 1}
    ).sort("timestamp", -1).limit(20)
    msgs = await cursor.to_list(length=20)
    return [
        {
            "content": m.get("content", ""),
            "sender_id": str(m.get("sender_id", "")),
            "group_id": str(m.get("group_id") or ""),
            "media_type": m.get("media_type", "text"),
            "timestamp": m["timestamp"].isoformat() if hasattr(m.get("timestamp"), "isoformat") else "",
        }
        for m in msgs
    ]


async def list_shared_documents(args: Dict) -> Any:
    from src.ai.vector_store import get_vector_store

    query = args.get("query") or "document"
    try:
        vs = get_vector_store()
        doc_results = await vs.search_document_chunks(query, n_results=30) if vs else []
    except Exception as exc:
        logger.warning("doc_search_failed", error=str(exc))
        doc_results = []

    # Group chunks by filename, track the best (max) relevance score per document
    filename_best: Dict[str, Dict] = {}
    for r in doc_results:
        meta = r.get("metadata", {})
        fname = meta.get("filename", "unknown")
        score = float(r.get("score", 0))
        if fname not in filename_best or score > filename_best[fname]["score"]:
            filename_best[fname] = {
                "score": score,
                "uploaded_by": meta.get("uploader_id", ""),
                "group_id": meta.get("group_id", ""),
                "preview": r.get("content", "")[:120],
            }

    # Keep only documents whose best-chunk score is above the relevance threshold,
    # then return the top 5 sorted by score descending
    MIN_SCORE = 0.35
    relevant = sorted(
        [(fname, data) for fname, data in filename_best.items() if data["score"] >= MIN_SCORE],
        key=lambda x: x[1]["score"],
        reverse=True,
    )[:5]

    docs = [
        {
            "filename": fname,
            "uploaded_by": data["uploaded_by"],
            "group_id": data["group_id"],
            "preview": data["preview"],
        }
        for fname, data in relevant
    ]
    return {"documents": docs, "count": len(docs)}


async def summarize_document(args: Dict) -> Any:
    from src.common.database import get_pg_pool
    from src.ai.gemini_client import generate_text

    filename_query = args.get("filename", "")
    question = args.get("question", "")

    pool = get_pg_pool()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT content, filename, chunk_index FROM document_chunks "
                "WHERE filename ILIKE $1 ORDER BY chunk_index",
                f"%{filename_query}%",
            )
        if not rows:
            return {
                "error": f"No content found for '{filename_query}'. "
                         "Use list_shared_documents to find the exact filename."
            }
        actual_filename = rows[0]["filename"]
        full_text = "\n\n".join(r["content"] for r in rows)
        if question:
            prompt = (
                f"Document: {actual_filename}\n\nContent:\n{full_text[:8000]}\n\n"
                f"Question: {question}\n\nAnswer based on the document content:"
            )
        else:
            prompt = (
                f"Document: {actual_filename}\n\nContent:\n{full_text[:8000]}\n\n"
                "Provide a comprehensive summary of this document."
            )
        summary = await generate_text(prompt, max_tokens=800)
        return {"filename": actual_filename, "summary": summary, "chunks_used": len(rows)}
    except Exception as exc:
        logger.error("summarize_document_failed", error=str(exc))
        return {"error": str(exc)}


async def catchup_for_group(args: Dict, session) -> Any:
    from src.common.database import get_mongo_db, get_pg_pool
    from src.ai.gemini_client import generate_text
    from src.ai.rag.formatting import build_user_map, format_messages
    from src.ai.rag.chunking import chunk_by_tokens
    from src.ai.rag.prompts import CATCHUP_PROMPT
    from src.ai.rag.parallel import hierarchical_merge, summarise_chunks_parallel

    pool = get_pg_pool()
    db = get_mongo_db()
    uid = str(session.user_id)
    hours = int(args.get("hours_ago", 48))
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    async with pool.acquire() as conn:
        group = await conn.fetchrow(
            "SELECT group_id, group_name FROM groups WHERE group_name ILIKE $1",
            f"%{args['group_name']}%"
        )
    if not group:
        return {"error": f"Group '{args['group_name']}' not found"}

    cursor = db.messages.find(
        {"group_id": str(group["group_id"]), "timestamp": {"$gte": since},
         "sender_id": {"$ne": uid}, "deleted": {"$ne": True}},
    ).sort("timestamp", 1)
    msgs = await cursor.to_list(length=300)

    if not msgs:
        return {"group": group["group_name"], "hours_ago": hours, "count": 0,
                "summary": "No new messages in this group during that period."}

    umap = await build_user_map(msgs)
    chunks = chunk_by_tokens(msgs)
    if len(chunks) == 1:
        text = format_messages(msgs, umap)
        summary = await generate_text(
            f"Summarise missed messages in '{group['group_name']}':\n\n{text}",
            system_prompt=CATCHUP_PROMPT, max_tokens=400,
        )
    else:
        chunk_sums = await summarise_chunks_parallel(
            chunks,
            prompt_fn=lambda t: f"Summarise missed messages in '{group['group_name']}':\n\n{t}",
            system_prompt=CATCHUP_PROMPT, max_tokens=256, user_map=umap,
        )
        summary = await hierarchical_merge(chunk_sums, CATCHUP_PROMPT, label=group["group_name"])

    return {"group": group["group_name"], "hours_ago": hours, "count": len(msgs), "summary": summary}
