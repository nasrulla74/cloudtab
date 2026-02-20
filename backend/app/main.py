import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import async_session
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.security import hash_password
from app.models.user import User

# Initialize structured logging before anything else
setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


async def seed_admin_user():
    """Create admin user if it doesn't exist."""
    async with async_session() as db:
        result = await db.execute(
            select(User).where(User.email == settings.ADMIN_EMAIL)
        )
        if result.scalar_one_or_none() is None:
            admin = User(
                email=settings.ADMIN_EMAIL,
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
            )
            db.add(admin)
            await db.commit()
            logger.info("Admin user seeded: %s", settings.ADMIN_EMAIL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("CloudTab starting up")
    await seed_admin_user()
    yield
    logger.info("CloudTab shutting down")


app = FastAPI(
    title="CloudTab",
    description="Odoo Server Management Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Register global exception handlers (validation, DB, generic)
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log every request with method, path, status, duration, and request ID."""
    # Generate a unique request ID for correlation
    request_id = uuid.uuid4().hex[:12]
    request.state.request_id = request_id

    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.error(
            "[%s] %s %s -> 500 (%.1fms) %s",
            request_id,
            request.method,
            request.url.path,
            duration_ms,
            str(exc),
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
            headers={"X-Request-ID": request_id},
        )

    duration_ms = (time.perf_counter() - start) * 1000

    # Skip logging health checks to reduce noise
    if request.url.path == "/health":
        response.headers["X-Request-ID"] = request_id
        return response

    log_fn = logger.warning if response.status_code >= 400 else logger.info
    log_fn(
        "[%s] %s %s -> %d (%.1fms)",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
