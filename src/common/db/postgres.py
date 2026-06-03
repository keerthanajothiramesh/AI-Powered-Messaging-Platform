"""asyncpg connection pool setup, pgvector table creation, and schema migration for PostgreSQL."""
import asyncpg
from typing import Optional

from src.common.logger import get_logger

logger = get_logger(__name__)

_pg_pool: Optional[asyncpg.Pool] = None


async def _init_conn(conn) -> None:
    try:
        from pgvector.asyncpg import register_vector
        await register_vector(conn)
    except Exception:
        pass


async def init_postgres(database_url: str) -> None:
    global _pg_pool
    try:
        clean_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        _pg_pool = await asyncpg.create_pool(
            clean_url, min_size=5, max_size=20, command_timeout=60, init=_init_conn,
        )
        logger.info("postgres_connected", pool_min=5, pool_max=20)
    except Exception as exc:
        logger.error("postgres_connection_failed", error=str(exc))
        raise


async def close_postgres() -> None:
    global _pg_pool
    if _pg_pool:
        await _pg_pool.close()
        logger.info("postgres_pool_closed")


def get_pg_pool() -> asyncpg.Pool:
    if not _pg_pool:
        raise RuntimeError("PostgreSQL pool not initialized")
    return _pg_pool


async def create_pg_tables(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR(255) UNIQUE NOT NULL,
                display_name VARCHAR(255) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                user_presence VARCHAR(50) DEFAULT 'offline',
                last_seen TIMESTAMPTZ,
                status VARCHAR(50) DEFAULT 'active',
                registration_date DATE DEFAULT CURRENT_DATE,
                timezone VARCHAR(100) DEFAULT 'Asia/Kolkata',
                language_preference VARCHAR(10) DEFAULT 'en',
                avatar_url TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                group_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                group_name VARCHAR(255) NOT NULL,
                description TEXT, avatar_url TEXT,
                created_by UUID REFERENCES users(user_id),
                max_participants INTEGER DEFAULT 100,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS group_members (
                id SERIAL PRIMARY KEY,
                group_id UUID REFERENCES groups(group_id) ON DELETE CASCADE,
                user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
                role VARCHAR(50) DEFAULT 'member',
                joined_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(group_id, user_id)
            );
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_group_members_group ON group_members(group_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_group_members_user ON group_members(user_id);")
        await _setup_pgvector(conn)
        await _run_migrations(conn)
        logger.info("postgres_tables_created")


async def _setup_pgvector(conn) -> None:
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS message_embeddings (
                message_id TEXT PRIMARY KEY, embedding vector(384),
                content TEXT NOT NULL, sender_id TEXT DEFAULT '',
                group_id TEXT DEFAULT '', receiver_id TEXT DEFAULT '',
                media_type TEXT DEFAULT 'text', language TEXT DEFAULT 'en',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS msg_emb_hnsw_idx
            ON message_embeddings USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id SERIAL PRIMARY KEY, media_id TEXT NOT NULL, chunk_index INT NOT NULL,
                content TEXT NOT NULL, embedding vector(384),
                filename TEXT DEFAULT '', media_type TEXT DEFAULT 'document',
                uploader_id TEXT DEFAULT '', group_id TEXT DEFAULT '', receiver_id TEXT DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW(), UNIQUE(media_id, chunk_index)
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS doc_chunks_hnsw_idx
            ON document_chunks USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS doc_chunks_media_idx ON document_chunks(media_id)")
    except Exception as exc:
        logger.warning("pgvector_table_setup_failed", error=str(exc))


async def _run_migrations(conn) -> None:
    for col, col_def in [
        ("job_title", "VARCHAR(200)"), ("company", "VARCHAR(200)"),
        ("department", "VARCHAR(200)"), ("work_location", "VARCHAR(200)"),
    ]:
        try:
            await conn.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {col_def}")
        except Exception:
            pass
