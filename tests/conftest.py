"""Shared pytest configuration and SQLite app fixtures for the bud backend test suite."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio

POSTGRES_TESTS_DIR = Path(__file__).resolve().parent / "pg"


def _load_workspace_dotenv_into_environ() -> None:
    """Load `budProject/.env` into the environment without overriding variables already set."""
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
os.environ.setdefault("BUD_SECRET_KEY", os.environ["SECRET_KEY"])


def _only_postgres_tests(args: list[str]) -> bool:
    """Return True when every path pytest was invoked with lies under tests/pg."""
    paths = [Path(arg.split("::")[0]).resolve() for arg in args if not arg.startswith("-")]
    return bool(paths) and all(path == POSTGRES_TESTS_DIR or POSTGRES_TESTS_DIR in path.parents for path in paths)


def pytest_configure(config: pytest.Config) -> None:
    """Point the app at an in-memory SQLite database unless only tests/pg is being run."""
    if _only_postgres_tests(list(config.args)):
        return
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    os.environ["BUD_DATABASE_URL"] = os.environ["DATABASE_URL"]


@pytest_asyncio.fixture(scope="function")
async def _engine(tmp_path_factory):
    """Fresh file-backed SQLite engine per test, bound into app.db.database."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.db import database as db_module
    from app.db.database import Base

    database_path = tmp_path_factory.mktemp("database") / "test.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{database_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    db_module.engine = engine
    db_module.async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(_engine) -> AsyncGenerator:
    """An AsyncSession on the per-test SQLite engine."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    session_maker = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session


@pytest.fixture(scope="function")
def test_user():
    """A stand-in authenticated administrator for endpoints protected by get_current_user."""
    from app.models.user import User, UserRole

    return User(
        id=1,
        email="tester@example.com",
        full_name="Tester",
        hashed_password="not-used",
        role=UserRole.admin,
        is_active=True,
        session_version=1,
    )


def _override_get_db(engine):
    """Build a get_db override that opens sessions on the given engine."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator:
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return override_get_db


@pytest_asyncio.fixture(scope="function")
async def client(_engine, test_user):
    """TestClient with the database and authentication dependencies overridden."""
    from fastapi.testclient import TestClient

    from app.api.auth import get_current_active_entity, get_current_user
    from app.api.results import get_uploader_entity
    from app.db.database import get_db
    from app.main import app

    async def override_get_current_entity():
        return test_user

    app.dependency_overrides[get_db] = _override_get_db(_engine)
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
    from fastapi.testclient import TestClient

    from app.db.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = _override_get_db(_engine)
    try:
        with TestClient(app) as tc:
            yield tc
    finally:
        app.dependency_overrides.clear()
