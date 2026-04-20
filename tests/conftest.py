"""
Shared pytest fixtures for the bud-app-backend test suite.

Uses an in-memory SQLite (aiosqlite) database so tests run without needing
a local Postgres. Overrides the real ``get_db`` and ``get_current_user``
dependencies so endpoints can be exercised via FastAPI's TestClient.
"""

from __future__ import annotations

import os
import secrets
from typing import AsyncGenerator

# These MUST be set BEFORE ``app.core.config`` is imported — the Settings
# validator rejects an empty SECRET_KEY.
os.environ.setdefault("SECRET_KEY", secrets.token_hex(32))
os.environ.setdefault("RUNNER_API_KEY", "test-runner-api-key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("BUD_SECRET_KEY", os.environ["SECRET_KEY"])
os.environ.setdefault("BUD_RUNNER_API_KEY", os.environ["RUNNER_API_KEY"])
os.environ.setdefault("BUD_DATABASE_URL", os.environ["DATABASE_URL"])

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api.auth import get_current_active_entity, get_current_user  # noqa: E402
from app.db import database as db_module  # noqa: E402
from app.db.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def _engine():
    """Fresh in-memory SQLite engine per test — isolated, deterministic."""
    # StaticPool: ``:memory:`` must share one DB across connections (lifespan +
    # TestClient use separate connections from the fixture's create_all).
    engine = create_async_engine(
        TEST_DB_URL,
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Rebind module-level engine so any app code that grabs
    # ``async_session_maker`` indirectly stays consistent with this engine.
    db_module.engine = engine
    db_module.async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(_engine) -> AsyncGenerator[AsyncSession, None]:
    session_maker = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session


@pytest.fixture(scope="function")
def test_user() -> User:
    """A stand-in authenticated user for endpoints protected by get_current_user."""
    return User(
        id=1,
        email="tester@example.com",
        full_name="Tester",
        hashed_password="not-used",
        role=UserRole.admin,
        is_active=True,
    )


@pytest_asyncio.fixture(scope="function")
async def client(_engine, test_user):
    """
    TestClient with DB + auth dependencies overridden.

    Each request gets its own AsyncSession from the in-memory engine, and
    ``get_current_user`` returns the pre-built ``test_user`` so we don't
    have to issue a real JWT in tests that aren't specifically about auth.
    """
    session_maker = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def override_get_current_entity() -> User:
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_entity
    app.dependency_overrides[get_current_active_entity] = override_get_current_entity
    try:
        with TestClient(app) as tc:
            yield tc
    finally:
        app.dependency_overrides.clear()
