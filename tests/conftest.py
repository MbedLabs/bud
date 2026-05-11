"""
Shared pytest fixtures for the bud-app-backend test suite.

Uses an in-memory SQLite (aiosqlite) database so tests run without needing
a local Postgres. Overrides the real ``get_db`` and ``get_current_user``
dependencies so endpoints can be exercised via FastAPI's TestClient.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import AsyncGenerator

# Workspace `.env` at `budProject/.env` — load first so local dev matches production variable names.


def _load_workspace_dotenv_into_environ() -> None:
    path = Path(__file__).resolve().parents[2] / ".env"
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key and key not in os.environ:
            os.environ[key] = val


_load_workspace_dotenv_into_environ()
if "SECRET_KEY" not in os.environ and os.environ.get("BUD_SECRET_KEY"):
    os.environ["SECRET_KEY"] = os.environ["BUD_SECRET_KEY"]

# These MUST be set BEFORE ``app.core.config`` is imported — the Settings
# validator rejects an empty SECRET_KEY.
os.environ.setdefault("SECRET_KEY", secrets.token_hex(32))
# Contract tests send ``X-API-Key: test-runner-api-key``; never use production key from ``.env``.
os.environ["RUNNER_API_KEY"] = "test-runner-api-key"
os.environ["BUD_RUNNER_API_KEY"] = os.environ["RUNNER_API_KEY"]
# Always use isolated SQLite for ORM tests; real ``BUD_DATABASE_URL`` stays in ``.env`` for operators.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["BUD_DATABASE_URL"] = os.environ["DATABASE_URL"]
os.environ.setdefault("BUD_SECRET_KEY", os.environ["SECRET_KEY"])

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api.auth import get_current_active_entity, get_current_user  # noqa: E402
from app.api.results import get_uploader_entity  # noqa: E402
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
    app.dependency_overrides[get_uploader_entity] = override_get_current_entity
    try:
        with TestClient(app) as tc:
            yield tc
    finally:
        app.dependency_overrides.clear()
