from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pathlib import Path

from src.config import settings
from src.common.logger import configure_logging, get_logger
from src.common.exceptions import (
    AppError, app_error_handler, http_exception_handler,
    validation_error_handler, generic_error_handler,
)

configure_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup_begin", env=settings.APP_ENV)

    if settings.NEON_DATABASE_URL:
        try:
            from src.common.database import init_postgres, create_pg_tables
            await init_postgres(settings.NEON_DATABASE_URL)
            pool = __import__("src.common.database", fromlist=["get_pg_pool"]).get_pg_pool()
            await create_pg_tables(pool)
        except Exception as e:
            logger.error("postgres_startup_failed", error=str(e))
    else:
        logger.warning("postgres_skipped", reason="NEON_DATABASE_URL not set")

    if settings.MONGODB_URL:
        try:
            from src.common.database import init_mongodb, create_mongo_indexes, get_mongo_db
            await init_mongodb(settings.MONGODB_URL)
            db = get_mongo_db()
            await create_mongo_indexes(db)
        except Exception as e:
            logger.error("mongodb_startup_failed", error=str(e))
    else:
        logger.warning("mongodb_skipped", reason="MONGODB_URL not set")

    try:
        from src.ai.embedding_service import init_embedding_service
        init_embedding_service()
    except Exception as e:
        logger.error("embedding_startup_failed", error=str(e))

    try:
        from src.ai.vector_store import init_vector_store
        from src.common.database import get_pg_pool
        init_vector_store(get_pg_pool())
    except Exception as e:
        logger.error("vector_store_startup_failed", error=str(e))

    if settings.GEMINI_API_KEY:
        try:
            from src.ai.gemini_client import init_gemini
            init_gemini(settings.GEMINI_API_KEY)
        except Exception as e:
            logger.error("gemini_startup_failed", error=str(e))
    else:
        logger.warning("gemini_skipped", reason="GEMINI_API_KEY not set")

    try:
        from src.ai.pii_guard import init_pii_guard
        init_pii_guard()
    except Exception as e:
        logger.warning("pii_guard_startup_failed", error=str(e))

    Path(settings.LOCAL_UPLOADS_PATH).mkdir(parents=True, exist_ok=True)
    logger.info("startup_complete")

    yield

    logger.info("shutdown_begin")
    try:
        from src.common.database import close_postgres, close_mongodb
        await close_postgres()
        await close_mongodb()
    except Exception:
        pass
    logger.info("shutdown_complete")


app = FastAPI(
    title="AI-Powered Messaging Platform",
    description="Real-time messaging with AI features: semantic search, RAG summarisation, multi-agent orchestration",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "https://ai-powered-messaging-platform.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from src.common.metrics import PrometheusMiddleware
app.add_middleware(PrometheusMiddleware)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, generic_error_handler)

from src.common.health import router as health_router
from src.auth.router import router as auth_router
from src.messaging.user_router import router as user_router
from src.messaging.group_router import router as group_router
from src.messaging.message_router import router as message_router
from src.messaging.websocket_router import router as ws_router
from src.ai.router import router as ai_router
from src.search.router import router as search_router
from src.media.router import router as media_router
from src.notifications.router import router as notif_router
from src.agents.router import router as agents_router
from src.admin.router import router as admin_router

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(group_router)
app.include_router(message_router)
app.include_router(ws_router)
app.include_router(ai_router)
app.include_router(search_router)
app.include_router(media_router)
app.include_router(notif_router)
app.include_router(agents_router)
app.include_router(admin_router)

uploads_path = Path(settings.LOCAL_UPLOADS_PATH)
uploads_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")


@app.get("/")
async def root():
    return {
        "name": "AI-Powered Messaging Platform",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus-format metrics endpoint for scraping."""
    from src.common.metrics import get_metrics_response
    return get_metrics_response()


@app.get("/metrics/summary")
async def metrics_summary(_=__import__("fastapi").Depends(
    __import__("src.auth.dependencies", fromlist=["get_current_user"]).get_current_user
)):
    """JSON metrics summary consumed by the React observability dashboard."""
    from src.common.metrics import get_metrics_summary
    return await get_metrics_summary()
