"""
FastAPI application for the Bud test automation platform

Main entry point for the backend API.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select, text

from app.api import auth as auth_api
from app.api import (health, products, results, runners, settings, test_runs,
                     teststations, uploads)
from app.api import users as users_api
from app.core.config import settings as app_settings
from app.core.deps import limiter
from app.core.security import get_password_hash
from app.db import database as db
from app.models.user import User, UserRole


async def seed_admin_user():
    # Always use the module's current session factory so tests can swap the engine
    # (``from db import async_session_maker`` would keep the import-time binding).
    async with db.async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == app_settings.ADMIN_EMAIL))
        admin = result.scalar_one_or_none()
        if admin is None:
            admin = User(
                email=app_settings.ADMIN_EMAIL,
                full_name=app_settings.ADMIN_FULL_NAME,
                hashed_password=get_password_hash(app_settings.ADMIN_PASSWORD),
                role=UserRole.admin,
                is_active=True,
            )
            session.add(admin)
        else:
            admin.role = UserRole.admin
            admin.is_active = True

        await session.commit()


async def migrate_user_columns() -> None:
    async with db.engine.begin() as conn:
        if conn.dialect.name != "postgresql":
            return

        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS invited_at TIMESTAMP NULL")
        )
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS invited_by_user_id INTEGER NULL")
        )
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_invite_sent_at TIMESTAMP NULL")
        )
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS invite_accepted_at TIMESTAMP NULL")
        )
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_set_at TIMESTAMP NULL")
        )
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMP NULL")
        )


async def migrate_user_roles_to_viewer() -> None:
    async with db.engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            await conn.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
                            BEGIN
                                ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'viewer';
                            EXCEPTION
                                WHEN duplicate_object THEN NULL;
                            END;
                        END IF;
                    END
                    $$;
                    """
                )
            )

    async with db.engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            await conn.execute(text("UPDATE users SET role = 'viewer' WHERE role::text = 'user'"))
        else:
            await conn.execute(text("UPDATE users SET role = 'viewer' WHERE role = 'user'"))


async def migrate_execution_columns() -> None:
    async with db.engine.begin() as conn:
        if conn.dialect.name != "postgresql":
            return

        await conn.execute(
            text("ALTER TABLE test_results ADD COLUMN IF NOT EXISTS assertions JSON NULL")
        )
        await conn.execute(
            text("ALTER TABLE test_results ADD COLUMN IF NOT EXISTS test_metadata JSON NULL")
        )
        await conn.execute(
            text("ALTER TABLE test_results ADD COLUMN IF NOT EXISTS product_id INTEGER NULL")
        )
        await conn.execute(text("ALTER TABLE test_results ALTER COLUMN test_run_id DROP NOT NULL"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    await db.create_tables()
    await migrate_user_columns()
    await migrate_user_roles_to_viewer()
    await migrate_execution_columns()
    await seed_admin_user()
    yield


# L1: Hide docs endpoints in production; set ENABLE_DOCS=true for local dev
app = FastAPI(
    title=f"{app_settings.BUD_APP_NAME} API",
    description="Backend API for the Bud test automation platform",
    version=app_settings.BUD_APP_VERSION,
    docs_url="/api/docs" if app_settings.ENABLE_DOCS else None,
    redoc_url="/api/redoc" if app_settings.ENABLE_DOCS else None,
    openapi_url="/api/openapi.json" if app_settings.ENABLE_DOCS else None,
    lifespan=lifespan,
)

# H2: Attach rate-limiter state and error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# M1: Restrict CORS — only listed origins, explicit methods, no wildcard headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-API-Key"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(auth_api.router, prefix="/api/auth", tags=["Auth"])
app.include_router(users_api.router, prefix="/api/users", tags=["Users"])
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(test_runs.router, prefix="/api/test-runs", tags=["Test Runs"])
app.include_router(results.router, prefix="/api/results", tags=["Results"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["Uploads"])
app.include_router(runners.router, prefix="/api/runners", tags=["Runners"])
app.include_router(teststations.router, prefix="/api/teststations", tags=["TestStations"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Bud TMP API",
        "version": app_settings.BUD_APP_VERSION,
    }
