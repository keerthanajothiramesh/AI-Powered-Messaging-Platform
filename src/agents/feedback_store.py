"""Persistence layer for LLM-as-Judge scores and user feedback ratings."""
from datetime import datetime, timezone
from typing import Dict, Any, List
from src.common.logger import get_logger
from src.common.metrics import summary_feedback_total

logger = get_logger(__name__)


async def save_summary_feedback(
    *,
    group_id: str,
    group_name: str,
    days: int,
    summary: str,
    judgment: Dict[str, Any],
) -> str:
    """Persist a judge evaluation to MongoDB. Returns the inserted document id."""
    from src.common.database import get_mongo_db
    import uuid
    db = get_mongo_db()
    doc = {
        "feedback_id": str(uuid.uuid4()),
        "group_id": group_id,
        "group_name": group_name,
        "days": days,
        "summary": summary,
        "relevance": judgment.get("relevance", 0),
        "accuracy": judgment.get("accuracy", 0),
        "completeness": judgment.get("completeness", 0),
        "average_score": judgment.get("average_score", 0),
        "judge_feedback": judgment.get("feedback", ""),
        "user_rating": None,   # set later via /agents/feedback/{id}/rate
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.summary_feedback.insert_one(doc)
    summary_feedback_total.labels(rating="auto_judge").inc()
    logger.info("summary_feedback_saved", feedback_id=doc["feedback_id"], score=doc["average_score"])
    return doc["feedback_id"]


async def save_response_feedback(
    *,
    user_id: str,
    conv_id: str,
    user_message: str,
    ai_response: str,
    judgment: Dict[str, Any],
) -> str:
    """Persist a judge evaluation for a chatbot response."""
    from src.common.database import get_mongo_db
    import uuid
    db = get_mongo_db()
    doc = {
        "feedback_id": str(uuid.uuid4()),
        "type": "chatbot_response",
        "user_id": user_id,
        "conv_id": conv_id,
        "user_message": user_message[:500],
        "ai_response": ai_response[:1000],
        "relevance": judgment.get("relevance", 0),
        "accuracy": judgment.get("accuracy", 0),
        "completeness": judgment.get("completeness", 0),
        "average_score": judgment.get("average_score", 0),
        "judge_feedback": judgment.get("feedback", ""),
        "user_rating": None,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.summary_feedback.insert_one(doc)
    summary_feedback_total.labels(rating="auto_judge").inc()
    logger.info("response_feedback_saved", feedback_id=doc["feedback_id"], score=doc["average_score"])
    return doc["feedback_id"]


async def set_user_rating(feedback_id: str, rating: int) -> bool:
    """Record a user thumbs-up (1) or thumbs-down (-1) against a feedback entry."""
    from src.common.database import get_mongo_db
    db = get_mongo_db()
    result = await db.summary_feedback.update_one(
        {"feedback_id": feedback_id},
        {"$set": {"user_rating": rating, "rated_at": datetime.now(timezone.utc)}},
    )
    if result.modified_count > 0:
        label = "thumbs_up" if rating == 1 else "thumbs_down"
        summary_feedback_total.labels(rating=label).inc()
    return result.modified_count > 0


async def get_top_summaries(group_id: str = None, limit: int = 3) -> List[Dict[str, Any]]:
    """Return the highest-rated summaries for use as few-shot examples."""
    from src.common.database import get_mongo_db
    db = get_mongo_db()
    query: Dict[str, Any] = {"average_score": {"$gte": 8}, "summary": {"$exists": True}}
    if group_id:
        query["group_id"] = group_id
    cursor = db.summary_feedback.find(
        query,
        {"summary": 1, "group_name": 1, "average_score": 1, "user_rating": 1, "_id": 0},
    ).sort([("user_rating", -1), ("average_score", -1)]).limit(limit)
    return await cursor.to_list(length=limit)


async def save_agent_run(agent_name: str, result: Dict[str, Any]) -> None:
    """Upsert the latest run result for a scheduled agent (one doc per agent)."""
    from src.common.database import get_mongo_db
    db = get_mongo_db()
    await db.agent_runs.replace_one(
        {"agent_name": agent_name},
        {"agent_name": agent_name, "result": result, "ran_at": datetime.now(timezone.utc)},
        upsert=True,
    )
    logger.info("agent_run_saved", agent=agent_name)


async def get_latest_agent_run(agent_name: str) -> Dict[str, Any]:
    """Return the most recent run document for the given agent, or {}."""
    from src.common.database import get_mongo_db
    db = get_mongo_db()
    doc = await db.agent_runs.find_one({"agent_name": agent_name}, {"_id": 0})
    return doc or {}


async def get_feedback_stats() -> Dict[str, Any]:
    """Aggregate stats used by the observability dashboard."""
    from src.common.database import get_mongo_db
    db = get_mongo_db()
    pipeline = [
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "avg_score": {"$avg": "$average_score"},
            "high_quality": {"$sum": {"$cond": [{"$gte": ["$average_score", 7]}, 1, 0]}},
            "low_quality": {"$sum": {"$cond": [{"$lt": ["$average_score", 7]}, 1, 0]}},
            "thumbs_up": {"$sum": {"$cond": [{"$eq": ["$user_rating", 1]}, 1, 0]}},
            "thumbs_down": {"$sum": {"$cond": [{"$eq": ["$user_rating", -1]}, 1, 0]}},
        }},
    ]
    rows = await db.summary_feedback.aggregate(pipeline).to_list(length=1)
    if rows:
        r = rows[0]
        r.pop("_id", None)
        return r
    return {"total": 0, "avg_score": 0, "high_quality": 0, "low_quality": 0, "thumbs_up": 0, "thumbs_down": 0}
