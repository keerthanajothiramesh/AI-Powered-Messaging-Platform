"""Demo data removal service — deletes all is_demo-flagged users, groups, messages, and embeddings."""
from src.admin.progress import reset_progress, set_status, set_step
from src.common.database import get_mongo_db, get_pg_pool
from src.common.logger import get_logger

logger = get_logger(__name__)


async def run_remove(requester_user_id: str) -> None:
    reset_progress("removing")
    try:
        pool = get_pg_pool()
        db = get_mongo_db()
        async with pool.acquire() as conn:
            has_col = await conn.fetchval(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='users' AND column_name='is_demo'"
            )
        if not has_col:
            set_status("idle")
            return

        set_step("Removing embeddings")
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM message_embeddings WHERE is_demo = TRUE")

        set_step("Removing messages")
        await db.messages.delete_many({"is_demo": True})

        set_step("Removing group memberships")
        async with pool.acquire() as conn:
            demo_groups = await conn.fetch("SELECT group_id FROM groups WHERE is_demo = TRUE")
            for row in demo_groups:
                await conn.execute("DELETE FROM group_members WHERE group_id = $1", row["group_id"])

        set_step("Removing groups and users")
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM groups WHERE is_demo = TRUE")
            await conn.execute("DELETE FROM users WHERE is_demo = TRUE")

        set_status("idle", "")
        logger.info("demo_remove_complete", user_id=requester_user_id)
    except Exception as exc:
        set_status("error", error=str(exc))
        logger.error("demo_remove_failed", error=str(exc))
