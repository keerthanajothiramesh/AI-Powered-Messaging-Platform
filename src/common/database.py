"""
Backward-compatible re-export stub.
Implementation lives in src/common/db/ package.
"""
from src.common.db import (  # noqa: F401
    init_postgres, close_postgres, get_pg_pool, create_pg_tables,
    init_mongodb, close_mongodb, get_mongo_db, create_mongo_indexes,
)
