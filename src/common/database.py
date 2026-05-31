import asyncpg
import motor.motor_asyncio
from typing import Optional
from src.common.logger import get_logger

logger = get_logger(__name__)

_pg_pool: Optional[asyncpg.Pool] = None
_mongo_client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
_mongo_db = None


async def _init_conn(conn) -> None:
    try:
        from pgvector.asyncpg import register_vector
        await register_vector(conn)
    except Exception:
        pass  # pgvector not installed or extension not enabled yet


async def init_postgres(database_url: str) -> None:
    global _pg_pool
    try:
        clean_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        _pg_pool = await asyncpg.create_pool(
            clean_url,
            min_size=5,
            max_size=20,
            command_timeout=60,
            init=_init_conn,
        )
        logger.info("postgres_connected", pool_min=5, pool_max=20)
    except Exception as e:
        logger.error("postgres_connection_failed", error=str(e))
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


def _encode_mongo_url(url: str) -> str:
    from urllib.parse import urlparse, quote_plus, urlunparse
    parsed = urlparse(url)
    if parsed.username or parsed.password:
        host = parsed.hostname + (f":{parsed.port}" if parsed.port else "")
        encoded = parsed._replace(
            netloc=f"{quote_plus(parsed.username or '')}:{quote_plus(parsed.password or '')}@{host}"
        )
        return urlunparse(encoded)
    return url


async def init_mongodb(mongodb_url: str, db_name: str = "messaging") -> None:
    global _mongo_client, _mongo_db
    try:
        _mongo_client = motor.motor_asyncio.AsyncIOMotorClient(
            _encode_mongo_url(mongodb_url),
            maxPoolSize=50,
            minPoolSize=5,
            serverSelectionTimeoutMS=5000,
        )
        _mongo_db = _mongo_client[db_name]
        await _mongo_client.admin.command("ping")
        logger.info("mongodb_connected", db=db_name)
    except Exception as e:
        logger.error("mongodb_connection_failed", error=str(e))
        raise


async def close_mongodb() -> None:
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()
        logger.info("mongodb_client_closed")


def get_mongo_db():
    if _mongo_db is None:
        raise RuntimeError("MongoDB not initialized")
    return _mongo_db


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
                description TEXT,
                avatar_url TEXT,
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
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_members_group ON group_members(group_id);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_members_user ON group_members(user_id);
        """)
        # pgvector extension + embeddings table
        try:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS message_embeddings (
                    message_id TEXT PRIMARY KEY,
                    embedding vector(384),
                    content TEXT NOT NULL,
                    sender_id TEXT DEFAULT '',
                    group_id TEXT DEFAULT '',
                    receiver_id TEXT DEFAULT '',
                    media_type TEXT DEFAULT 'text',
                    language TEXT DEFAULT 'en',
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
                    id SERIAL PRIMARY KEY,
                    media_id TEXT NOT NULL,
                    chunk_index INT NOT NULL,
                    content TEXT NOT NULL,
                    embedding vector(384),
                    filename TEXT DEFAULT '',
                    media_type TEXT DEFAULT 'document',
                    uploader_id TEXT DEFAULT '',
                    group_id TEXT DEFAULT '',
                    receiver_id TEXT DEFAULT '',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(media_id, chunk_index)
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS doc_chunks_hnsw_idx
                ON document_chunks USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS doc_chunks_media_idx ON document_chunks(media_id)
            """)
        except Exception as e:
            logger.warning("pgvector_table_setup_failed", error=str(e))
        # Migrations: add profile columns idempotently
        for col, col_def in [
            ("job_title", "VARCHAR(200)"),
            ("company", "VARCHAR(200)"),
            ("department", "VARCHAR(200)"),
            ("work_location", "VARCHAR(200)"),
        ]:
            try:
                await conn.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {col_def}")
            except Exception:
                pass
        logger.info("postgres_tables_created")


async def create_mongo_indexes(db) -> None:
    await db.messages.create_index([("sender_id", 1), ("timestamp", -1)])
    await db.messages.create_index([("receiver_id", 1), ("timestamp", -1)])
    await db.messages.create_index([("group_id", 1), ("timestamp", -1)])
    await db.messages.create_index([("timestamp", -1)])
    # Drop legacy TTL index that targeted a non-existent field
    try:
        await db.messages.drop_index("offline_queue_ttl")
    except Exception:
        pass
    # Compound index for efficient offline-queue lookups (sparse — only docs with queued_at)
    await db.messages.create_index(
        [("receiver_id", 1), ("delivery_status", 1), ("queued_at", 1)],
        sparse=True,
        name="offline_queue_idx",
    )
    await db.notifications.create_index([("user_id", 1), ("is_read", 1)])
    await db.notifications.create_index([("created_at", -1)])
    await db.media.create_index([("uploader_id", 1)])
    await db.media.create_index([("group_id", 1)])
    logger.info("mongo_indexes_created")
