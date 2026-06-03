"""Admin REST API — check seed status, trigger demo data seeding, and remove demo data."""
from fastapi import APIRouter, BackgroundTasks, Depends

from src.admin.progress import get_progress
from src.admin.seed_service import run_seed
from src.admin.remove_service import run_remove
from src.auth.dependencies import get_current_user
from src.common.database import get_mongo_db, get_pg_pool
from src.common.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/seed-status")
async def seed_status(_=Depends(get_current_user)):
    result = get_progress()
    if result["status"] == "idle":
        try:
            pool = get_pg_pool()
            async with pool.acquire() as conn:
                count = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_demo = TRUE")
            if count and count > 0:
                result["status"] = "done"
        except Exception:
            pass
    return result


@router.post("/seed-demo")
async def seed_demo(
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
):
    if get_progress()["status"] == "running":
        return {"message": "Seeding already in progress"}
    background_tasks.add_task(run_seed, str(current_user.user_id))
    return {"message": "Seeding started"}


@router.get("/seed-demo/real-count")
async def real_message_count(_=Depends(get_current_user)):
    """Count non-demo messages in demo groups so the UI can warn before deleting."""
    try:
        pool = get_pg_pool()
        db = get_mongo_db()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT group_id FROM groups WHERE is_demo = TRUE")
        demo_ids = [str(r["group_id"]) for r in rows]
        if not demo_ids:
            return {"count": 0}
        count = await db.messages.count_documents(
            {"group_id": {"$in": demo_ids}, "is_demo": {"$ne": True}}
        )
        return {"count": int(count)}
    except Exception:
        return {"count": 0}


@router.delete("/seed-demo")
async def remove_demo(
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
):
    if get_progress()["status"] == "removing":
        return {"message": "Removal already in progress"}
    background_tasks.add_task(run_remove, str(current_user.user_id))
    return {"message": "Removal started"}
