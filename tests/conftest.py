"""Shared pytest fixtures for the bud-app-backend test suite."""

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


if os.environ.get("BUD_TESTS_USE_DOTENV") == "1":
    _load_workspace_dotenv_into_environ()
if "SECRET_KEY" not in os.environ and os.environ.get("BUD_SECRET_KEY"):
    os.environ["SECRET_KEY"] = os.environ["BUD_SECRET_KEY"]

os.environ.setdefault("SECRET_KEY", secrets.token_hex(32))
os.environ["RUNNER_API_KEY"] = "test-runner-api-key"
os.environ["BUD_RUNNER_API_KEY"] = os.environ["RUNNER_API_KEY"]
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["BUD_DATABASE_URL"] = os.environ["DATABASE_URL"]
os.environ.setdefault("BUD_SECRET_KEY", os.environ["SECRET_KEY"])

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.api.auth import get_current_active_entity, get_current_user  # noqa: E402
from app.api.results import get_uploader_entity  # noqa: E402
from app.db import database as db_module  # noqa: E402
from app.db.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402


@pytest_asyncio.fixture(scope="function")
async def _engine(tmp_path_factory):
    """Fresh file-backed SQLite engine per test — isolated and thread-safe."""
    database_path = tmp_path_factory.mktemp("database") / "test.db"
    test_db_url = f"sqlite+aiosqlite:///{database_path}"
    engine = create_async_engine(
        test_db_url,
        future=True,
        connect_args={"check_same_thread": False},
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
        session_version=1,
    )


@pytest_asyncio.fixture(scope="function")
async def client(_engine, test_user):
    """TestClient with DB + auth dependencies overridden."""
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


@pytest_asyncio.fixture(scope="function")
async def unauthenticated_client(_engine):
    """TestClient with the test database but no authentication overrides."""
    session_maker = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as tc:
            yield tc
    finally:
        app.dependency_overrides.clear()
