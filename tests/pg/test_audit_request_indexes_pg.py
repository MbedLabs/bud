"""Audit request indexes migrate both ways on PostgreSQL, and concurrent refusals flag once."""

import asyncio
import os
import secrets
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[2]
REVISION = "020_audit_request_indexes"
INDEXES = {"ix_audit_events_outcome", "ix_audit_events_ip"}


def _postgres_url() -> str:
    """The PostgreSQL URL of the test database, or a skip when the suite runs on SQLite."""
    database_url = os.environ.get("DATABASE_URL", "")
    if "postgres" not in database_url:
        pytest.skip("tests/pg requires a PostgreSQL DATABASE_URL")
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


def _alembic(*arguments, database_url):
    """Run the repository's migration commands against one database."""
    environment = os.environ | {
        "DATABASE_URL": database_url,
        "BUD_DATABASE_URL": database_url,
        "BUD_DOTENV_DISABLED": "1",
    }
    result = subprocess.run(
        ["alembic", *arguments], cwd=ROOT, env=environment, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr


async def _indexes(connection):
    """Names of the indexes on audit_events."""
    rows = await connection.fetch("SELECT indexname FROM pg_indexes WHERE tablename='audit_events'")
    return {row["indexname"] for row in rows}


def test_the_audit_index_migration_is_the_single_head():
    script = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
    assert script.get_heads() == [REVISION]
    assert script.get_revision(REVISION).down_revision == "019_cli_auth_sessions"


async def test_the_audit_indexes_upgrade_and_downgrade_keeping_every_event():
    import asyncpg

    database_url = _postgres_url()
    admin_connection = await asyncpg.connect(database_url)
    database_name = "audit_indexes_" + secrets.token_hex(6)
    await admin_connection.execute(f'CREATE DATABASE "{database_name}"')
    scoped_url = urlunsplit(urlsplit(database_url)._replace(path=f"/{database_name}"))
    connection = await asyncpg.connect(scoped_url)
    try:
        _alembic("upgrade", "019_cli_auth_sessions", database_url=scoped_url)
        await connection.execute(
            "INSERT INTO audit_events (occurred_at, actor_type, action, ip, outcome) "
            "VALUES (now(), 'anonymous', 'auth.login', '192.0.2.1', 'failure')"
        )
        assert not INDEXES & await _indexes(connection)

        _alembic("upgrade", "head", database_url=scoped_url)
        assert INDEXES <= await _indexes(connection)
        assert await connection.fetchval("SELECT count(*) FROM audit_events") == 1

        _alembic("downgrade", "-1", database_url=scoped_url)
        assert await connection.fetchval("SELECT version_num FROM alembic_version") == (
            "019_cli_auth_sessions"
        )
        assert not INDEXES & await _indexes(connection)
        assert await connection.fetchval("SELECT count(*) FROM audit_events") == 1

        _alembic("upgrade", "head", database_url=scoped_url)
        assert await connection.fetchval("SELECT version_num FROM alembic_version") == REVISION
    finally:
        await connection.close()
        await admin_connection.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
        await admin_connection.close()


async def test_concurrent_refusals_from_one_address_leave_one_flag(monkeypatch):
    from app.core.observability import client_ip_var
    from app.db import database
    from app.models import AuditEvent
    from app.services.audit import record_api_request

    engine = create_async_engine(
        _postgres_url().replace("postgresql://", "postgresql+asyncpg://"),
        pool_size=10,
        max_overflow=20,
    )
    monkeypatch.setattr(
        database,
        "async_session_maker",
        async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False),
    )
    address = f"198.51.100.{secrets.randbelow(250) + 1}-{secrets.token_hex(4)}"
    token = client_ip_var.set(address)
    try:
        await asyncio.gather(
            *(
                record_api_request(
                    method="GET",
                    route="/api/auth/me",
                    path="/api/auth/me",
                    status=401,
                    duration_ms=1.0,
                    query_params=[],
                    auth="bearer",
                    path_params={},
                )
                for _ in range(30)
            )
        )
        async with database.async_session_maker() as session:
            denied = await session.scalar(
                select(func.count(AuditEvent.id)).where(
                    AuditEvent.ip == address, AuditEvent.action == "api.request"
                )
            )
            flags = await session.scalar(
                select(func.count(AuditEvent.id)).where(
                    AuditEvent.ip == address,
                    AuditEvent.action == "security.repeated_refusals",
                )
            )
    finally:
        client_ip_var.reset(token)
        await engine.dispose()

    assert denied == 30
    assert flags == 1
