"""Demo dataset seeder — loads users, groups, members, and messages from JSON fixtures into Postgres and MongoDB."""
import json
from datetime import datetime
from pathlib import Path
from typing import List

from src.admin.dm_seeder import seed_demo_dms
from src.admin.remove_service import run_remove  # noqa: F401 — re-exported for callers
from src.admin.embed_service import generate_demo_embeddings
from src.admin.helpers import parse_date, parse_dt
from src.admin.progress import get_progress, increment, reset_progress, set_step, set_status, set_total
from src.common.database import get_mongo_db, get_pg_pool
from src.common.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = Path("dataset")


async def run_seed(requester_user_id: str) -> None:
    reset_progress("running")
    try:
        pool = get_pg_pool()
        db = get_mongo_db()
        await _ensure_schema(pool)
        await _load_users(pool)
        group_ids = await _load_groups(pool)
        await _load_members(pool, group_ids, requester_user_id)
        await _load_messages(db)
        await seed_demo_dms(db, json.loads((DATA_DIR / "users.json").read_text(encoding="utf-8")), requester_user_id)
        await generate_demo_embeddings(pool, db)
        set_status("done", "Complete")
        logger.info("demo_seed_complete", user_id=requester_user_id)
    except Exception as exc:
        set_status("error", error=str(exc))
        logger.error("demo_seed_failed", error=str(exc))


async def _ensure_schema(pool) -> None:
    set_step("Preparing schema")
    async with pool.acquire() as conn:
        for table, col in [("users", "is_demo BOOLEAN DEFAULT FALSE"),
                           ("groups", "is_demo BOOLEAN DEFAULT FALSE"),
                           ("message_embeddings", "is_demo BOOLEAN DEFAULT FALSE")]:
            await conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col}")


async def _load_users(pool) -> None:
    set_step("Loading users")
    users = json.loads((DATA_DIR / "users.json").read_text(encoding="utf-8"))
    set_total("users_total", len(users))
    async with pool.acquire() as conn:
        for u in users:
            try:
                await conn.execute(
                    """INSERT INTO users (user_id, email, display_name, password_hash,
                       user_presence, last_seen, status, registration_date, timezone,
                       language_preference, is_demo) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                       ON CONFLICT (email) DO NOTHING""",
                    u["user_id"], u["email"], u["display_name"], u["password_hash"],
                    u.get("user_presence", "offline"), parse_dt(u.get("last_seen")),
                    u.get("status", "active"), parse_date(u.get("registration_date")),
                    u.get("timezone", "Asia/Kolkata"), u.get("language_preference", "en"), True,
                )
            except Exception:
                pass
            increment("users_loaded")


async def _load_groups(pool) -> List[str]:
    set_step("Loading groups")
    groups = json.loads((DATA_DIR / "groups.json").read_text(encoding="utf-8"))
    set_total("groups_total", len(groups))
    group_ids = []
    async with pool.acquire() as conn:
        for g in groups:
            try:
                await conn.execute(
                    """INSERT INTO groups (group_id, group_name, description, created_by, max_participants, is_demo)
                       VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT (group_id) DO NOTHING""",
                    g["group_id"], g["group_name"], g.get("description"),
                    g["created_by"], g.get("max_participants", 100), True,
                )
                group_ids.append(g["group_id"])
            except Exception:
                pass
            increment("groups_loaded")
    return group_ids


async def _load_members(pool, group_ids: List[str], requester_user_id: str) -> None:
    set_step("Loading group members")
    members = json.loads((DATA_DIR / "group_members.json").read_text(encoding="utf-8"))
    async with pool.acquire() as conn:
        for m in members:
            try:
                await conn.execute(
                    """INSERT INTO group_members (group_id, user_id, role)
                       VALUES ($1,$2,$3) ON CONFLICT (group_id, user_id) DO NOTHING""",
                    m["group_id"], m["user_id"], m.get("role", "member"),
                )
            except Exception:
                pass
    set_step("Adding you to demo groups")
    async with pool.acquire() as conn:
        for gid in group_ids:
            try:
                await conn.execute(
                    """INSERT INTO group_members (group_id, user_id, role)
                       VALUES ($1,$2,'member') ON CONFLICT (group_id, user_id) DO NOTHING""",
                    gid, requester_user_id,
                )
            except Exception:
                pass


async def _load_messages(db) -> None:
    set_step("Loading messages")
    msg_files = sorted(DATA_DIR.glob("messages_*.json"))
    all_batches = []
    total_msgs = 0
    for f in msg_files:
        msgs = json.loads(f.read_text(encoding="utf-8"))
        all_batches.append(msgs)
        total_msgs += len(msgs)
    set_total("messages_total", total_msgs)

    for msgs in all_batches:
        for m in msgs:
            if "timestamp" in m and isinstance(m["timestamp"], str):
                try:
                    m["timestamp"] = datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00"))
                except Exception:
                    pass
            if "message_id" in m and "_id" not in m:
                m["_id"] = m["message_id"]
            m["is_demo"] = True
        try:
            result = await db.messages.insert_many(msgs, ordered=False)
            increment("messages_loaded", len(result.inserted_ids))
        except Exception as exc:
            inserted = getattr(getattr(exc, "details", None), "get", lambda k, d: d)("nInserted", 0)
            increment("messages_loaded", inserted)


