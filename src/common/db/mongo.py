"""MongoDB connection management and index creation."""
import motor.motor_asyncio
from typing import Optional

from src.common.logger import get_logger

logger = get_logger(__name__)

_mongo_client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
_mongo_db = None


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
            maxPoolSize=50, minPoolSize=5, serverSelectionTimeoutMS=5000,
        )
        _mongo_db = _mongo_client[db_name]
        await _mongo_client.admin.command("ping")
        logger.info("mongodb_connected", db=db_name)
    except Exception as exc:
        logger.error("mongodb_connection_failed", error=str(exc))
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


async def create_mongo_indexes(db) -> None:
    await db.messages.create_index([("sender_id", 1), ("timestamp", -1)])
    await db.messages.create_index([("receiver_id", 1), ("timestamp", -1)])
    await db.messages.create_index([("group_id", 1), ("timestamp", -1)])
    await db.messages.create_index([("timestamp", -1)])
    try:
        await db.messages.drop_index("offline_queue_ttl")
    except Exception:
        pass
    await db.messages.create_index(
        [("receiver_id", 1), ("delivery_status", 1), ("queued_at", 1)],
        sparse=True, name="offline_queue_idx",
    )
    await db.notifications.create_index([("user_id", 1), ("is_read", 1)])
    await db.notifications.create_index([("created_at", -1)])
    await db.media.create_index([("uploader_id", 1)])
    await db.media.create_index([("group_id", 1)])
    await db.summary_feedback.create_index([("group_id", 1), ("average_score", -1)])
    await db.summary_feedback.create_index([("created_at", -1)])
    await db.summary_feedback.create_index([("feedback_id", 1)], unique=True)
    logger.info("mongo_indexes_created")
