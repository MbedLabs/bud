"""Shared pytest configuration and SQLite app fixtures for the bud backend test suite."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio

POSTGRES_TESTS_DIR = Path(__file__).resolve().parent / "pg"
TEST_POSTGRES_PORT = 15432
TEST_SMTP_PORT = 11025
DEV_POSTGRES_PORTS = frozenset({5432, 5433, 5434})
DEV_SMTP_PORTS = frozenset({25, 465, 587, 1025, 2525, 8025})
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _test_smtp_port() -> int:
    """Return the dedicated Mailpit SMTP port, refusing privileged and local development ports."""
    raw = os.environ.get("TEST_SMTP_PORT", str(TEST_SMTP_PORT))
    if not raw.isdigit() or not 1024 < int(raw) < 65536 or int(raw) in DEV_SMTP_PORTS:
        raise RuntimeError("Tests require a dedicated test Mailpit port, not a local development port")
    return int(raw)


def _postgres_port_allowed(port: int | None) -> bool:
    """Return True for an explicit non-development PostgreSQL port."""
    return port is not None and 1024 < port < 65536 and port not in DEV_POSTGRES_PORTS


SMTP_PORT = _test_smtp_port()


def _isolate_test_environment() -> None:
    """Configure test-only application credentials and the unauthenticated test Mailpit."""
    from urllib.parse import urlparse

    from cryptography.fernet import Fernet

    database_url = os.environ.get("DATABASE_URL", "")
    if database_url:
        parsed = urlparse(database_url)
        if parsed.scheme.startswith("postgres") and (
            parsed.scheme not in {"postgres", "postgresql", "postgresql+asyncpg"}
            or parsed.hostname not in LOOPBACK_HOSTS
            or parsed.username != "test_user"
            or parsed.password != "test_password"
            or parsed.path != "/test_bud"
            or not _postgres_port_allowed(parsed.port)
            or parsed.query
            or parsed.fragment
        ):
            raise RuntimeError("Tests require the isolated test database and test credentials")
        if parsed.scheme.startswith("sqlite") and database_url not in {
            "sqlite:///:memory:",
            "sqlite+aiosqlite:///:memory:",
        }:
            raise RuntimeError("Tests require an in-memory SQLite database")
        if not parsed.scheme.startswith(("postgres", "sqlite")):
            raise RuntimeError("Tests require an isolated PostgreSQL or SQLite database")
    else:
        database_url = (
            f"postgresql+asyncpg://test_user:test_password@localhost:{TEST_POSTGRES_PORT}/test_bud"
        )

    values = {
        "DOTENV_DISABLED": "1",
        "SECRET_KEY": "test-secret-key-for-ci-at-least-32-characters-long",
        "SERVICE_TOKEN_PEPPER": "test-service-token-pepper-for-ci-at-least-32-characters-long",
        "INTEGRATION_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "RUNNER_API_KEY": "test-runner-api-key",
        "ADMIN_EMAIL": "admin@example.com",
        "ADMIN_PASSWORD": "ci-admin-password-123",
        "ADMIN_FULL_NAME": "CI Admin",
        "DATABASE_URL": database_url,
        "SMTP_ENABLED": "true",
        "SMTP_HOST": "127.0.0.1",
        "SMTP_PORT": str(SMTP_PORT),
        "SMTP_USERNAME": "",
        "SMTP_PASSWORD": "",
        "SMTP_FROM_EMAIL": "noreply@example.com",
        "SMTP_STARTTLS": "false",
        "SMTP_SSL": "false",
        "STORAGE_BACKEND": "local",
        "S3_BUCKET": "",
        "S3_ENDPOINT_URL": "",
        "S3_ACCESS_KEY_ID": "",
        "S3_SECRET_ACCESS_KEY": "",
        "APP_BASE_URL": "http://localhost:8001",
        "FRONTEND_BASE_URL": "http://localhost:8001",
        "AUTO_SEED_ADMIN": "true",
        "RUN_STARTUP_DATA_REPAIR": "false",
    }
    for key, value in values.items():
        for prefix in ("", "BUD_"):
            os.environ[prefix + key] = value
    for key in ("SMTP_REPLY_TO", "BUD_SMTP_REPLY_TO", "BUD_TESTS_USE_DOTENV"):
        os.environ.pop(key, None)
    for key in ("DB_USER", "DB_PASSWORD", "DB_NAME", "DB_HOST", "DB_PORT"):
        for prefix in ("", "BUD_"):
            os.environ.pop(prefix + key, None)
    for key in tuple(os.environ):
        if key.startswith("AWS_"):
            os.environ.pop(key, None)
    os.environ.update(
        {
            "AWS_ACCESS_KEY_ID": "test-access-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret-key",
            "AWS_SHARED_CREDENTIALS_FILE": "/dev/null",
            "AWS_CONFIG_FILE": "/dev/null",
            "AWS_EC2_METADATA_DISABLED": "true",
            "AWS_DEFAULT_REGION": "us-east-1",
        }
    )
    os.environ["APP_ENV"] = "development"
    os.environ["BUD_ENV"] = "development"


def _guard_test_smtp(event: str, args: tuple) -> None:
    """Reject operator dotenv reads, external SMTP and authentication payloads."""
    if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0]))
        if path.name == ".env" and path.absolute().parent.resolve() in Path(__file__).resolve().parents:
            raise PermissionError("Operator dotenv files are forbidden in tests")
    if event == "smtplib.connect":
        _, host, port = args
        if host not in LOOPBACK_HOSTS or port != SMTP_PORT:
            raise PermissionError(f"Tests may connect only to the test Mailpit on port {SMTP_PORT}")
    elif event == "smtplib.send":
        _, data = args
        command = data.lstrip().split(None, 1)
        if command and command[0].upper() == b"AUTH":
            raise PermissionError("SMTP authentication is forbidden in tests")


_isolate_test_environment()
sys.addaudithook(_guard_test_smtp)


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
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

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
    from app.core.access import seed_default_access

    async with db_module.async_session_maker() as session:
        await seed_default_access(session)
        await session.commit()
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


@pytest.fixture
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


@pytest_asyncio.fixture(scope="function")
async def test_station(db_session):
    """A persisted station that produces test runs."""
    from app.models import Runner

    station = Runner(
        account="station-01", password_hash="x", token="station-token", socket_port=53035
    )
    db_session.add(station)
    await db_session.commit()
    return station


@pytest_asyncio.fixture(scope="function")
async def station_run(db_session, test_station):
    """A test run the fixture station owns, for evidence uploads."""
    from app.models import TestRun

    run = TestRun(
        name="station-run", test_case_list="[]", status="Running", runner_id=test_station.id
    )
    db_session.add(run)
    await db_session.commit()
    return run


@pytest.fixture
def station_upload(station_request, station_run):
    """Upload one file as the fixture station to its own run."""

    def upload(name="trace.txt", content=b"evidence", content_type="text/plain", **data):
        """Send ``POST /api/uploads`` as the station."""
        form = {"run_id": str(station_run.id), **data}
        return station_request(
            "POST", "/api/uploads", files={"file": (name, content, content_type)}, data=form
        )

    return upload


@pytest.fixture
def station_request(client, test_station):
    """Send an HTTP request as a station and restore the human client afterward."""
    from app.api.auth import get_current_active_entity
    from app.api.results import get_uploader_entity
    from app.main import app

    async def current_station():
        return test_station

    def request(method, url, **kwargs):
        """Send one station-authenticated request."""
        dependencies = (get_current_active_entity, get_uploader_entity)
        previous = {dependency: app.dependency_overrides[dependency] for dependency in dependencies}
        for dependency in dependencies:
            app.dependency_overrides[dependency] = current_station
        try:
            return client.request(method, url, **kwargs)
        finally:
            app.dependency_overrides.update(previous)

    return request


@pytest.fixture
def fresh_auth_rate_limits():
    """Isolate the rate-limit counters around one real-auth HTTP scenario."""
    from app.core.deps import limiter

    limiter.reset()
    try:
        yield
    finally:
        limiter.reset()
