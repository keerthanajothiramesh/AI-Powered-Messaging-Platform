"""Health check endpoints — overall status, database connectivity, AI client, and vector store checks."""
from fastapi import APIRouter
from src.common.logger import get_logger
from src.common.database import get_pg_pool, get_mongo_db

logger = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check():
    return {"status": "ok", "service": "AI Messaging Platform"}


@router.get("/db")
async def db_health():
    result = {"postgresql": "unknown", "mongodb": "unknown"}
    try:
        pool = get_pg_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        result["postgresql"] = "healthy"
    except Exception as e:
        result["postgresql"] = f"unhealthy: {str(e)}"

    try:
        db = get_mongo_db()
        await db.client.admin.command("ping")
        result["mongodb"] = "healthy"
    except Exception as e:
        result["mongodb"] = f"unhealthy: {str(e)}"

    overall = "healthy" if all(v == "healthy" for v in result.values()) else "degraded"
    return {"status": overall, "databases": result}


@router.get("/ai")
async def ai_health():
    try:
        from src.ai.gemini_client import get_openai_client
        client = get_openai_client()
        status = "healthy" if client else "unavailable"
    except Exception as e:
        status = f"unhealthy: {str(e)}"
    return {"status": "healthy" if status == "healthy" else "degraded", "openai": status}


@router.get("/vector")
async def vector_health():
    try:
        pool = get_pg_pool()
        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM message_embeddings")
        return {"status": "healthy", "pgvector": "healthy", "message_count": count}
    except Exception as e:
        return {"status": "degraded", "pgvector": f"unhealthy: {str(e)}"}
