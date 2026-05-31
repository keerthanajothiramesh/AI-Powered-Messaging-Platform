"""Admin endpoints for demo dataset seeding and cleanup."""
import asyncio
import json
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends

from src.auth.dependencies import get_current_user
from src.common.database import get_mongo_db, get_pg_pool
from src.common.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

# Dataset files live at <project_root>/dataset/
DATA_DIR = Path("dataset")

# ─── In-memory progress state ─────────────────────────────────────────────────

_progress: Dict[str, Any] = {
    "status": "idle",       # idle | running | removing | done | error
    "step": "",
    "users_loaded": 0,   "users_total": 0,
    "groups_loaded": 0,  "groups_total": 0,
    "messages_loaded": 0, "messages_total": 0,
    "embeddings_loaded": 0, "embeddings_total": 0,
    "error": None,
}


# ─── Status endpoint ──────────────────────────────────────────────────────────

@router.get("/seed-status")
async def seed_status(_=Depends(get_current_user)):
    result = dict(_progress)
    # If idle in memory, check the DB to handle server restarts
    if _progress["status"] == "idle":
        try:
            pool = get_pg_pool()
            async with pool.acquire() as conn:
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM users WHERE is_demo = TRUE"
                )
            if count and count > 0:
                result["status"] = "done"
        except Exception:
            pass  # Column doesn't exist yet → still idle
    return result


# ─── Seed endpoint ────────────────────────────────────────────────────────────

@router.post("/seed-demo")
async def seed_demo(
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
):
    if _progress["status"] == "running":
        return {"message": "Seeding already in progress"}
    background_tasks.add_task(_run_seed, str(current_user["user_id"]))
    return {"message": "Seeding started"}


# ─── Real-message count (for removal warning) ─────────────────────────────────

@router.get("/seed-demo/real-count")
async def real_message_count(_=Depends(get_current_user)):
    """Count non-demo messages inside demo groups so the UI can warn before deleting."""
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


# ─── Remove endpoint ──────────────────────────────────────────────────────────

@router.delete("/seed-demo")
async def remove_demo(
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
):
    if _progress["status"] == "removing":
        return {"message": "Removal already in progress"}
    background_tasks.add_task(_run_remove, str(current_user["user_id"]))
    return {"message": "Removal started"}


# ─── Seed background task ─────────────────────────────────────────────────────

async def _run_seed(requester_user_id: str):
    global _progress
    _progress = {
        "status": "running", "step": "Preparing",
        "users_loaded": 0,   "users_total": 0,
        "groups_loaded": 0,  "groups_total": 0,
        "messages_loaded": 0, "messages_total": 0,
        "embeddings_loaded": 0, "embeddings_total": 0,
        "error": None,
    }
    try:
        pool = get_pg_pool()
        db = get_mongo_db()

        # ── Ensure is_demo columns exist ──
        _progress["step"] = "Preparing schema"
        async with pool.acquire() as conn:
            await conn.execute(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_demo BOOLEAN DEFAULT FALSE"
            )
            await conn.execute(
                "ALTER TABLE groups ADD COLUMN IF NOT EXISTS is_demo BOOLEAN DEFAULT FALSE"
            )
            await conn.execute(
                "ALTER TABLE message_embeddings ADD COLUMN IF NOT EXISTS is_demo BOOLEAN DEFAULT FALSE"
            )

        # ── Users ──
        _progress["step"] = "Loading users"
        users = json.loads((DATA_DIR / "users.json").read_text(encoding="utf-8"))
        _progress["users_total"] = len(users)
        async with pool.acquire() as conn:
            for u in users:
                try:
                    await conn.execute(
                        """INSERT INTO users
                           (user_id, email, display_name, password_hash,
                            user_presence, last_seen, status, registration_date,
                            timezone, language_preference, is_demo)
                           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                           ON CONFLICT (email) DO NOTHING""",
                        u["user_id"], u["email"], u["display_name"], u["password_hash"],
                        u.get("user_presence", "offline"),
                        _parse_dt(u.get("last_seen")),
                        u.get("status", "active"),
                        _parse_date(u.get("registration_date")),
                        u.get("timezone", "Asia/Kolkata"),
                        u.get("language_preference", "en"),
                        True,
                    )
                except Exception:
                    pass
                _progress["users_loaded"] += 1

        # ── Groups ──
        _progress["step"] = "Loading groups"
        groups = json.loads((DATA_DIR / "groups.json").read_text(encoding="utf-8"))
        _progress["groups_total"] = len(groups)
        group_ids = []
        async with pool.acquire() as conn:
            for g in groups:
                try:
                    await conn.execute(
                        """INSERT INTO groups
                           (group_id, group_name, description, created_by, max_participants, is_demo)
                           VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT (group_id) DO NOTHING""",
                        g["group_id"], g["group_name"], g.get("description"),
                        g["created_by"], g.get("max_participants", 100), True,
                    )
                    group_ids.append(g["group_id"])
                except Exception:
                    pass
                _progress["groups_loaded"] += 1

        # ── Synthetic group members ──
        _progress["step"] = "Loading group members"
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

        # ── Add the logged-in user to every demo group ──
        _progress["step"] = "Adding you to demo groups"
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

        # ── Messages ──
        _progress["step"] = "Loading messages"
        msg_files = sorted(DATA_DIR.glob("messages_*.json"))
        # Pre-count totals so the progress bar is accurate
        total_msgs = 0
        all_batches = []
        for f in msg_files:
            msgs = json.loads(f.read_text(encoding="utf-8"))
            all_batches.append(msgs)
            total_msgs += len(msgs)
        _progress["messages_total"] = total_msgs

        for msgs in all_batches:
            for m in msgs:
                if "timestamp" in m and isinstance(m["timestamp"], str):
                    try:
                        m["timestamp"] = datetime.fromisoformat(
                            m["timestamp"].replace("Z", "+00:00")
                        )
                    except Exception:
                        pass
                m["is_demo"] = True
            try:
                result = await db.messages.insert_many(msgs, ordered=False)
                _progress["messages_loaded"] += len(result.inserted_ids)
            except Exception as exc:
                # BulkWriteError fires on duplicates but partial inserts still happen
                inserted = getattr(getattr(exc, "details", None), "get", lambda k, d: d)(
                    "nInserted", len(msgs)
                )
                _progress["messages_loaded"] += inserted

        # ── Embeddings ──
        _progress["step"] = "Generating embeddings (this takes a few minutes)"
        await _generate_demo_embeddings(pool, db)

        _progress["status"] = "done"
        _progress["step"] = "Complete"
        logger.info("demo_seed_complete", user_id=requester_user_id)

    except Exception as exc:
        _progress["status"] = "error"
        _progress["error"] = str(exc)
        logger.error("demo_seed_failed", error=str(exc))


async def _generate_demo_embeddings(pool, db):
    from src.ai.embedding_service import get_embedding_service
    from pgvector.asyncpg import register_vector

    svc = get_embedding_service()
    if not svc:
        logger.warning("demo_embeddings_skipped", reason="embedding service unavailable")
        return

    total = await db.messages.count_documents(
        {"is_demo": True, "media_type": "text", "content": {"$exists": True, "$ne": ""}}
    )
    _progress["embeddings_total"] = total

    BATCH_SIZE = 256
    batch = []

    cursor = db.messages.find(
        {"is_demo": True, "media_type": "text", "content": {"$exists": True, "$ne": ""}},
        {"message_id": 1, "content": 1, "sender_id": 1,
         "group_id": 1, "receiver_id": 1, "media_type": 1, "language": 1},
    )

    async with pool.acquire() as conn:
        await register_vector(conn)

        async for msg in cursor:
            mid = str(msg.get("message_id") or msg.get("_id", ""))
            batch.append({
                "message_id": mid,
                "content": msg["content"],
                "sender_id": str(msg.get("sender_id") or ""),
                "group_id": str(msg.get("group_id") or ""),
                "receiver_id": str(msg.get("receiver_id") or ""),
                "media_type": msg.get("media_type", "text"),
                "language": msg.get("language", "en"),
            })
            if len(batch) >= BATCH_SIZE:
                await _flush_embeddings(conn, svc, batch)
                _progress["embeddings_loaded"] += len(batch)
                batch = []

        if batch:
            await _flush_embeddings(conn, svc, batch)
            _progress["embeddings_loaded"] += len(batch)


async def _flush_embeddings(conn, svc, batch):
    texts = [m["content"] for m in batch]
    loop = asyncio.get_event_loop()
    vecs = await loop.run_in_executor(None, lambda: svc.batch_embed(texts))
    records = [
        (
            m["message_id"], v, m["content"],
            m["sender_id"], m["group_id"], m["receiver_id"],
            m["media_type"], m["language"], True,
        )
        for m, v in zip(batch, vecs)
    ]
    await conn.executemany(
        """INSERT INTO message_embeddings
           (message_id, embedding, content, sender_id, group_id, receiver_id,
            media_type, language, is_demo)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
           ON CONFLICT (message_id) DO NOTHING""",
        records,
    )


# ─── Remove background task ───────────────────────────────────────────────────

async def _run_remove(requester_user_id: str):
    global _progress
    _progress = {
        "status": "removing", "step": "Removing embeddings",
        "users_loaded": 0,   "users_total": 0,
        "groups_loaded": 0,  "groups_total": 0,
        "messages_loaded": 0, "messages_total": 0,
        "embeddings_loaded": 0, "embeddings_total": 0,
        "error": None,
    }
    try:
        pool = get_pg_pool()
        db = get_mongo_db()

        # Check is_demo column exists — if not, nothing to remove
        async with pool.acquire() as conn:
            has_col = await conn.fetchval(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='users' AND column_name='is_demo'"
            )
        if not has_col:
            _progress["status"] = "idle"
            return

        _progress["step"] = "Removing embeddings"
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM message_embeddings WHERE is_demo = TRUE")

        _progress["step"] = "Removing messages"
        await db.messages.delete_many({"is_demo": True})

        _progress["step"] = "Removing group memberships"
        async with pool.acquire() as conn:
            demo_groups = await conn.fetch(
                "SELECT group_id FROM groups WHERE is_demo = TRUE"
            )
            for row in demo_groups:
                await conn.execute(
                    "DELETE FROM group_members WHERE group_id = $1", row["group_id"]
                )

        _progress["step"] = "Removing groups and users"
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM groups WHERE is_demo = TRUE")
            await conn.execute("DELETE FROM users WHERE is_demo = TRUE")

        _progress["status"] = "idle"
        _progress["step"] = ""
        logger.info("demo_remove_complete", user_id=requester_user_id)

    except Exception as exc:
        _progress["status"] = "error"
        _progress["error"] = str(exc)
        logger.error("demo_remove_failed", error=str(exc))


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_dt(val):
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(str(val).replace("Z", "+00:00"))


def _parse_date(val):
    if not val:
        return None
    if isinstance(val, date):
        return val
    return datetime.fromisoformat(str(val)[:10]).date()
