"""
FastAPI application for bud.embedlabs.de

Main entry point for the backend API.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select

from app.api import auth as auth_api
from app.api import health, results, runners, test_runs, uploads
from app.api import users as users_api
from app.core.config import settings
from app.core.deps import limiter
from app.core.security import get_password_hash
from app.db import database as db
from app.models.user import User, UserRole


async def seed_admin_user():
    # Always use the module's current session factory so tests can swap the engine
    # (``from db import async_session_maker`` would keep the import-time binding).
    async with db.async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == settings.ADMIN_EMAIL))
        if not result.scalar_one_or_none():
            admin = User(
                email=settings.ADMIN_EMAIL,
                full_name=settings.ADMIN_FULL_NAME,
                hashed_password=get_password_hash(settings.ADMIN_PASSWORD),
                role=UserRole.admin,
                is_active=True,
            )
            session.add(admin)
            await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    await db.create_tables()
    await seed_admin_user()
    yield


# L1: Hide docs endpoints in production; set ENABLE_DOCS=true for local dev
app = FastAPI(
    title="Bud Test Platform API",
    description="Backend API for bud.embedlabs.de - Test automation platform",
    version="0.1.0",
    docs_url="/api/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/api/redoc" if settings.ENABLE_DOCS else None,
    openapi_url="/api/openapi.json" if settings.ENABLE_DOCS else None,
    lifespan=lifespan,
)

# H2: Attach rate-limiter state and error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# M1: Restrict CORS — only listed origins, explicit methods, no wildcard headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-API-Key"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(auth_api.router, prefix="/api/auth", tags=["Auth"])
app.include_router(users_api.router, prefix="/api/users", tags=["Users"])
app.include_router(test_runs.router, prefix="/api/test-runs", tags=["Test Runs"])
app.include_router(results.router, prefix="/api/results", tags=["Results"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["Uploads"])
app.include_router(runners.router, prefix="/api/runners", tags=["Runners"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Bud Test Platform API",
        "version": "0.1.0",
    }
