"""FastAPI application for the Bud test automation platform

The API documentation is served only when ENABLE_DOCS is true. CORS allows the configured
origins with credentials, explicit methods and explicit headers. The custom runs router,
whose paths (/test-runs/custom, /runners/claim-run) sit under both prefixes, is registered
before the test-runs and runners routers.
"""

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.api import access_requests as access_requests_api
from app.api import audit as audit_api
from app.api import auth as auth_api
from app.api import (
    cli_auth,
    company_logo,
    custom_runs,
    groups,
    health,
    policies,
    products,
    report_requests,
    reports,
    results,
    runners,
    settings,
    setup,
    test_runs,
    uploads,
)
from app.api import users as users_api
from app.core.access import seed_default_access
from app.core.config import settings as app_settings
from app.core.deps import limiter
from app.core.identity import BUD_PRODUCT_IDENTITY, BUD_PRODUCT_NAME
from app.core.observability import (
    RequestObservabilityMiddleware,
    metrics_router,
    request_id_var,
    setup_logging,
)
from app.core.security import get_password_hash
from app.db import database as db
from app.models.user import User, UserRole
from app.services.artifact_cleanup import reconcile_artifacts
from app.services.report_requests import sync_report_requests

setup_logging(level=app_settings.LOG_LEVEL, json_logs=bool(app_settings.LOG_JSON))
logger = logging.getLogger(__name__)


async def seed_admin_user():
    """Create the configured administrator, or give the existing account the admin role,
    through the session factory current in app.db.
    """
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


async def seed_access_defaults() -> None:
    """Create the shipped policies and groups that are missing."""
    async with db.async_session_maker() as session:
        await seed_default_access(session)
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
            await conn.execute(text("""
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
                    """))

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
    if app_settings.RUN_STARTUP_DATA_REPAIR:
        await db.create_tables()
        await migrate_user_columns()
        await migrate_user_roles_to_viewer()
        await migrate_execution_columns()
        await seed_access_defaults()
    if app_settings.AUTO_SEED_ADMIN:
        await seed_admin_user()

    async def cleanup_loop() -> None:
        while True:
            try:
                async with db.async_session_maker() as session:
                    report = await reconcile_artifacts(session)
                    if report.leader_acquired:
                        logger.info(
                            "Artifact cleanup: expired=%s orphan=%s missing=%s",
                            report.expired_artifacts,
                            report.orphan_files,
                            report.missing_files,
                        )
            except Exception:
                logger.exception("Artifact cleanup pass failed")
            await asyncio.sleep(24 * 60 * 60)

    async def report_request_loop() -> None:
        """Collect Bloom requests once a minute while this app is running."""
        while True:
            await asyncio.sleep(60)
            try:
                async with db.async_session_maker() as session:
                    await sync_report_requests(session)
            except Exception:
                logger.exception("Report-request collection failed; will retry")

    request_task = asyncio.create_task(report_request_loop())
    cleanup_task = asyncio.create_task(cleanup_loop())
    try:
        yield
    finally:
        request_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await request_task
        cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cleanup_task


app = FastAPI(
    title=BUD_PRODUCT_IDENTITY,
    description=f"Backend API for {BUD_PRODUCT_NAME}",
    version=app_settings.BUD_APP_VERSION,
    docs_url="/api/docs" if app_settings.ENABLE_DOCS else None,
    redoc_url="/api/redoc" if app_settings.ENABLE_DOCS else None,
    openapi_url="/api/openapi.json" if app_settings.ENABLE_DOCS else None,
    lifespan=lifespan,
)

app.state.limiter = limiter


INTEGRITY_ANSWERS: dict[str, tuple[int, str]] = {
    "23505": (409, "That already exists."),
    "23P01": (409, "That already exists."),
    "23503": (409, "Something this refers to is missing or still in use."),
    "23502": (422, "A required value was missing."),
    "23514": (422, "A value was outside what this field accepts."),
}


def _sqlstate(exc: Exception) -> str:
    cause = getattr(exc, "orig", None)
    for candidate in (cause, getattr(cause, "__cause__", None)):
        for attribute in ("sqlstate", "pgcode"):
            code = getattr(candidate, attribute, None)
            if code:
                return str(code)
    return ""


async def _integrity_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Answer a constraint violation with the status its SQLSTATE names.

    The constraint text is logged, never returned.
    """

    request_id = request_id_var.get()
    status_code, detail = INTEGRITY_ANSWERS.get(
        _sqlstate(exc), (409, "That conflicts with something already stored.")
    )
    logger.warning(
        "Integrity error on %s %s: %s",
        request.method,
        request.url.path,
        getattr(exc, "orig", None) or exc,
    )
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": f"{detail} Quote reference {request_id} when reporting this.",
            "request_id": request_id,
        },
        headers={"x-request-id": request_id},
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = request_id_var.get()
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": (
                "Something went wrong on the server. "
                f"Quote reference {request_id} when reporting this."
            ),
            "request_id": request_id,
        },
        headers={"x-request-id": request_id},
    )


app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_exception_handler(IntegrityError, _integrity_error_handler)
app.add_exception_handler(Exception, _unhandled_exception_handler)

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(RequestObservabilityMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-API-Key"],
)

app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(metrics_router, prefix="/api", tags=["Observability"])
app.include_router(auth_api.router, prefix="/api/auth", tags=["Auth"])
app.include_router(cli_auth.router, prefix="/api/auth/cli", tags=["CLI authentication"])
app.include_router(users_api.router, prefix="/api/users", tags=["Users"])
app.include_router(audit_api.router, prefix="/api/audit", tags=["Audit"])
app.include_router(
    access_requests_api.router, prefix="/api/access-requests", tags=["Access requests"]
)
app.include_router(groups.router, prefix="/api/groups", tags=["Groups"])
app.include_router(groups.access_router, prefix="/api/access", tags=["Access"])
app.include_router(policies.router, prefix="/api/policies", tags=["Policies"])
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(custom_runs.router, prefix="/api", tags=["Custom Runs"])
app.include_router(test_runs.router, prefix="/api/test-runs", tags=["Test Runs"])
app.include_router(report_requests.router, prefix="/api/report-requests", tags=["Report requests"])
app.include_router(results.router, prefix="/api/results", tags=["Results"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["Uploads"])
app.include_router(runners.router, prefix="/api/runners", tags=["Runners"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(setup.router, prefix="/api", tags=["Setup"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(company_logo.router, prefix="/api/company-logo", tags=["Company logo"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": BUD_PRODUCT_IDENTITY,
        "version": app_settings.BUD_APP_VERSION,
    }
