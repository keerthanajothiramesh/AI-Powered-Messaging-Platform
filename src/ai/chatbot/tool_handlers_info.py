"""Informational tool handlers: action items, activity stats, unread count, meetings."""
import json
import re
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from src.common.logger import get_logger

logger = get_logger(__name__)


async def get_my_action_items(args: Dict, session) -> Any:
    from src.common.database import get_mongo_db, get_pg_pool
    pool = get_pg_pool()
    db = get_mongo_db()
    uid = str(session.user_id)
    days = int(args.get("days", 7))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT display_name FROM users WHERE user_id = $1", uid)
        grows = await conn.fetch(
            "SELECT g.group_id FROM groups g JOIN group_members gm "
            "ON g.group_id = gm.group_id WHERE gm.user_id = $1", uid
        )
    first = (user["display_name"].split()[0] if user else "")
    group_ids = [str(r["group_id"]) for r in grows]

    kw = r"please|can you|could you|action:|todo|deadline|follow.?up|assigned|by when"
    or_clauses = [{"receiver_id": uid}, {"group_id": {"$in": group_ids}}]
    if first:
        or_clauses.append({"content": {"$regex": first, "$options": "i"}})

    cursor = db.messages.find(
        {"timestamp": {"$gte": since}, "sender_id": {"$ne": uid}, "deleted": {"$ne": True},
         "content": {"$regex": kw, "$options": "i"}, "$or": or_clauses},
        {"content": 1, "sender_id": 1, "group_id": 1, "timestamp": 1},
    ).sort("timestamp", -1).limit(10)
    msgs = await cursor.to_list(length=10)

    sids = [_uuid.UUID(str(m["sender_id"])) for m in msgs if m.get("sender_id")]
    async with pool.acquire() as conn:
        nrows = await conn.fetch(
            "SELECT user_id, display_name FROM users WHERE user_id = ANY($1::uuid[])", sids
        )
    nmap = {str(r["user_id"]): r["display_name"] for r in nrows}

    return {"action_items": [
        {"task": m.get("content", ""), "from": nmap.get(str(m.get("sender_id", "")), "Unknown"),
         "group_id": str(m.get("group_id") or ""),
         "timestamp": m["timestamp"].isoformat() if hasattr(m.get("timestamp"), "isoformat") else ""}
        for m in msgs
    ], "count": len(msgs), "days": days}


async def get_group_activity_stats(args: Dict) -> Any:
    from src.common.database import get_mongo_db, get_pg_pool
    pool = get_pg_pool()
    db = get_mongo_db()
    days = int(args.get("days", 7))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    async with pool.acquire() as conn:
        group = await conn.fetchrow(
            "SELECT group_id, group_name FROM groups WHERE group_name ILIKE $1",
            f"%{args['group_name']}%"
        )
    if not group:
        return {"error": f"Group '{args['group_name']}' not found"}

    pipeline = [
        {"$match": {"group_id": str(group["group_id"]), "timestamp": {"$gte": since}, "deleted": {"$ne": True}}},
        {"$group": {"_id": "$sender_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}, {"$limit": 10},
    ]
    stats = await db.messages.aggregate(pipeline).to_list(length=10)
    sids = [_uuid.UUID(s["_id"]) for s in stats if s.get("_id")]
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id, display_name FROM users WHERE user_id = ANY($1::uuid[])", sids
        )
    nmap = {str(r["user_id"]): r["display_name"] for r in rows}
    total = sum(s["count"] for s in stats)
    return {"group": group["group_name"], "days": days, "total_messages": total,
            "top_contributors": [
                {"name": nmap.get(s["_id"], (s["_id"] or "")[:8]), "messages": s["count"]}
                for s in stats]}


async def get_unread_count(session) -> Any:
    from src.common.database import get_mongo_db, get_pg_pool
    db = get_mongo_db()
    pool = get_pg_pool()
    uid = str(session.user_id)
    dm_count = await db.messages.count_documents(
        {"receiver_id": uid, "read_status": "unread", "deleted": {"$ne": True}}
    )
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT g.group_id FROM groups g JOIN group_members gm "
            "ON g.group_id = gm.group_id WHERE gm.user_id = $1", uid
        )
    gids = [str(r["group_id"]) for r in rows]
    grp_count = await db.messages.count_documents(
        {"group_id": {"$in": gids}, "sender_id": {"$ne": uid},
         "read_by": {"$not": {"$elemMatch": {"$eq": uid}}}, "deleted": {"$ne": True}}
    ) if gids else 0
    return {"total_unread": dm_count + grp_count, "dm_unread": dm_count, "group_unread": grp_count}


async def extract_meetings(args: Dict) -> Any:
    from src.ai.gemini_client import generate_text
    from src.search.search_service import hybrid_search
    results = await hybrid_search("meeting call standup sync schedule", n_results=15)
    if not results:
        return {"meetings": [], "count": 0}
    text = "\n".join(f"- {r['content']}" for r in results[:12])
    prompt = (
        f"Extract all meetings, calls, or scheduled events from these messages:\n\n{text}\n\n"
        "Return a JSON array of objects with: title, date_time, participants (array), location. "
        "Use null for unknown fields. Return ONLY the JSON array, no explanation."
    )
    raw = await generate_text(prompt, max_tokens=500)
    try:
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        meetings = json.loads(match.group()) if match else []
    except Exception:
        meetings = []
    return {"meetings": meetings, "count": len(meetings)}
