"""CLI authorization migrations preserve existing rows and claims are atomic on PostgreSQL."""

import asyncio
import base64
import hashlib
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from urllib.parse import urlsplit, urlunsplit

import pytest

from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = "v" * 43
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip("=")
)


def _alembic(*arguments, database_url):
    """Run the repository's migration commands on an isolated schema."""
    environment = os.environ | {
        "DATABASE_URL": database_url,
        "BUD_DATABASE_URL": database_url,
        "BUD_DOTENV_DISABLED": "1",
    }
    result = subprocess.run(
        ["alembic", *arguments], cwd=ROOT, env=environment, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def test_cli_migration_has_one_append_only_head():
    script = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
    [head] = script.get_heads()
    lineage = [revision.revision for revision in script.walk_revisions("base", head)]
    assert "019_cli_auth_sessions" in lineage
    assert script.get_revision("019_cli_auth_sessions").down_revision == "018_report_requests"


RETAINED_TABLES = ("users", "user_tokens", "report_requests", "audit_events")
SESSION_COLUMNS = {
    "id",
    "client_name",
    "mode",
    "redirect_uri",
    "code_challenge",
    "state",
    "exchange_code_hash",
    "user_id",
    "approved_session_version",
    "expires_at",
    "consumed_at",
    "created_at",
}


async def _seed_previous_head(connection):
    """Insert one account, its refresh token, a report request and an audit event."""
    user_id = await connection.fetchval(
        "INSERT INTO users (email, full_name, hashed_password, role, is_active, session_version, "
        "created_at, updated_at) VALUES ('retained@example.com', 'Retained', 'hash', 'viewer', "
        "true, 1, now(), now()) RETURNING id"
    )
    await connection.execute(
        "INSERT INTO user_tokens (user_id, purpose, token_hash, expires_at, created_at) "
        "VALUES ($1, 'refresh', $2, now() + interval '1 day', now())",
        user_id,
        "a" * 64,
    )
    await connection.execute(
        "INSERT INTO report_requests (bloom_url, remote_id, run_id, project_prefix, "
        "requester_name, requester_email, status, notified_user_ids, created_at) VALUES "
        "('https://bloom.example.test', 1, 1, 'PRJ', 'Requester', 'requester@example.com', "
        "'pending', '[]', now())"
    )
    await connection.execute(
        "INSERT INTO audit_events (occurred_at, actor_user_id, actor_type, action, outcome) "
        "VALUES (now(), $1, 'user', 'auth.login', 'success')",
        user_id,
    )
    return user_id


async def _snapshot(connection):
    """Return the row count of every table the seed fills."""
    return {
        table: await connection.fetchval(f"SELECT count(*) FROM {table}")
        for table in RETAINED_TABLES
    }


async def _session_table_exists(connection):
    """Report whether the cli_auth_sessions table is present."""
    return await connection.fetchval("SELECT to_regclass('public.cli_auth_sessions') IS NOT NULL")


async def test_cli_migration_upgrades_previous_head_and_downgrades_with_sessions_present():
    import secrets

    import asyncpg

    database_url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    admin_connection = await asyncpg.connect(database_url)
    database_name = "cli_auth_migration_" + secrets.token_hex(6)
    await admin_connection.execute(f'CREATE DATABASE "{database_name}"')
    parsed = urlsplit(database_url)
    scoped_url = urlunsplit(parsed._replace(path=f"/{database_name}"))
    connection = await asyncpg.connect(scoped_url)
    try:
        _alembic("upgrade", "018_report_requests", database_url=scoped_url)
        user_id = await _seed_previous_head(connection)
        before = await _snapshot(connection)
        assert before == {table: 1 for table in RETAINED_TABLES}

        _alembic("upgrade", "019_cli_auth_sessions", database_url=scoped_url)
        assert await _snapshot(connection) == before
        columns = await connection.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='cli_auth_sessions'"
        )
        assert {row["column_name"] for row in columns} == SESSION_COLUMNS
        indexes = await connection.fetch(
            "SELECT indexname FROM pg_indexes WHERE tablename='cli_auth_sessions'"
        )
        assert "ix_cli_auth_sessions_expires_at" in {row["indexname"] for row in indexes}
        await connection.execute(
            "INSERT INTO cli_auth_sessions (id, client_name, mode, code_challenge, state, "
            "expires_at, created_at) VALUES (gen_random_uuid(), 'Pending', 'code', $1, 'state', "
            "now() + interval '10 minutes', now())",
            CHALLENGE,
        )
        await connection.execute(
            "INSERT INTO cli_auth_sessions (id, client_name, mode, redirect_uri, code_challenge, "
            "state, exchange_code_hash, user_id, approved_session_version, expires_at, "
            "consumed_at, created_at) VALUES (gen_random_uuid(), 'Approved', 'callback', "
            "'http://127.0.0.1:4567/callback', $1, 'state', $2, $3, 1, "
            "now() + interval '10 minutes', now(), now())",
            CHALLENGE,
            "b" * 64,
            user_id,
        )

        _alembic("downgrade", "018_report_requests", database_url=scoped_url)
        assert await connection.fetchval("SELECT version_num FROM alembic_version") == (
            "018_report_requests"
        )
        assert not await _session_table_exists(connection)
        assert await _snapshot(connection) == before

        _alembic("upgrade", "019_cli_auth_sessions", database_url=scoped_url)
        assert await connection.fetchval("SELECT version_num FROM alembic_version") == (
            "019_cli_auth_sessions"
        )
        assert await connection.fetchval("SELECT count(*) FROM cli_auth_sessions") == 0
        assert await _snapshot(connection) == before
    finally:
        await connection.close()
        await admin_connection.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
        await admin_connection.close()


async def test_cli_migration_installs_on_an_empty_database():
    import secrets

    import asyncpg

    database_url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    admin_connection = await asyncpg.connect(database_url)
    database_name = "cli_auth_fresh_" + secrets.token_hex(6)
    await admin_connection.execute(f'CREATE DATABASE "{database_name}"')
    parsed = urlsplit(database_url)
    scoped_url = urlunsplit(parsed._replace(path=f"/{database_name}"))
    connection = await asyncpg.connect(scoped_url)
    try:
        _alembic("upgrade", "head", database_url=scoped_url)
        assert await _session_table_exists(connection)
        script = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
        assert await connection.fetchval("SELECT version_num FROM alembic_version") == (
            script.get_current_head()
        )
    finally:
        await connection.close()
        await admin_connection.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
        await admin_connection.close()


def _race(call, other=None):
    """Begin two independent HTTP requests at the same barrier, the same one twice by default."""
    barrier = Barrier(2)

    def run(operation):
        """Call the operation after both worker threads are ready."""
        barrier.wait()
        return operation()

    with ThreadPoolExecutor(max_workers=2) as executor:
        return list(executor.map(run, (call, other or call)))


def _admin_headers(client):
    """Sign in as the seeded administrator and return its bearer header."""
    email = os.environ.get("ADMIN_EMAIL", "ci-admin@example.com")
    password = os.environ.get("ADMIN_PASSWORD", "ci-admin-password-123")
    login = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_cli_approval_exchange_and_refresh_each_have_one_winner(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.CLI_CODE_MODE_ENABLED", True)
    headers = _admin_headers(client)
    start = client.post(
        "/api/auth/cli/start",
        json={
            "client_name": "Concurrent client",
            "mode": "code",
            "code_challenge": CHALLENGE,
            "state": "state",
        },
    )
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    approvals = _race(
        lambda: client.post(
            "/api/auth/cli/approve", json={"session_id": session_id}, headers=headers
        )
    )
    assert sorted(response.status_code for response in approvals) == [200, 400]
    code = next(
        response.json()["exchange_code"] for response in approvals if response.status_code == 200
    )
    exchanges = _race(
        lambda: client.post(
            "/api/auth/cli/exchange",
            json={"session_id": session_id, "code": code, "code_verifier": VERIFIER},
        )
    )
    assert sorted(response.status_code for response in exchanges) == [200, 400]
    tokens = next(response.json() for response in exchanges if response.status_code == 200)
    refreshes = _race(
        lambda: client.post(
            "/api/auth/cli/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
    )
    assert sorted(response.status_code for response in refreshes) == [200, 401]


def _start_callback(client):
    """Start a callback-mode request and return its session id."""
    start = client.post(
        "/api/auth/cli/start",
        json={
            "client_name": "Concurrent client",
            "mode": "callback",
            "redirect_uri": "http://127.0.0.1:1234/callback",
            "code_challenge": CHALLENGE,
            "state": "state",
        },
    )
    assert start.status_code == 200, start.text
    return start.json()["session_id"]


def test_cli_approve_and_deny_of_one_request_have_one_winner(client):
    headers = _admin_headers(client)
    session_id = _start_callback(client)
    body = {"session_id": session_id}
    outcomes = _race(
        lambda: client.post("/api/auth/cli/approve", json=body, headers=headers),
        lambda: client.post("/api/auth/cli/deny", json=body, headers=headers),
    )
    assert sorted(response.status_code for response in outcomes) == [200, 400]
    assert client.get(f"/api/auth/cli/sessions/{session_id}", headers=headers).status_code == 400
    session_id = _start_callback(client)
    denials = _race(
        lambda: client.post("/api/auth/cli/deny", json={"session_id": session_id}, headers=headers)
    )
    assert sorted(response.status_code for response in denials) == [200, 400]


@pytest.fixture
async def cli_pg_sessions():
    """Open independent test-loop sessions without the application's pooled connections."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(
        os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


async def test_cli_user_lock_allows_browser_refresh_foreign_key_checks(
    cli_pg_sessions, monkeypatch
):
    import secrets

    monkeypatch.setattr("app.core.config.settings.CLI_CODE_MODE_ENABLED", True)

    from app.models import User, UserRole, UserTokenPurpose
    from app.schemas.cli_auth import CliStartRequest
    from app.services.cli_auth import (
        approve_session,
        refresh_credentials,
        start_session,
    )
    from app.services.token_service import (
        TokenValidationError,
        claim_token,
        create_user_token,
    )

    async with cli_pg_sessions() as setup:
        user = User(
            email=f"lock-{secrets.token_hex(6)}@example.com",
            full_name="Lock test",
            hashed_password="unused",
            role=UserRole.viewer,
            is_active=True,
            session_version=1,
        )
        setup.add(user)
        await setup.flush()
        user_id = user.id
        token = await create_user_token(
            setup,
            user_id=user_id,
            purpose=UserTokenPurpose.refresh,
            ttl_hours=1,
            invalidate_existing=False,
        )
        pending = await start_session(
            setup,
            CliStartRequest(
                client_name="Lock test", mode="code", code_challenge=CHALLENGE, state="state"
            ),
        )
        session_id = pending.id
        await setup.commit()

    async with cli_pg_sessions() as browser, cli_pg_sessions() as cli:
        await claim_token(browser, token=token, purpose=UserTokenPurpose.refresh)
        user = await cli.get(User, user_id)
        await approve_session(cli, session_id, user)

        async def browser_refresh():
            """Finish ordinary browser rotation while the CLI holds its user lock."""
            replacement = await create_user_token(
                browser,
                user_id=user_id,
                purpose=UserTokenPurpose.refresh,
                ttl_hours=1,
                invalidate_existing=False,
            )
            await browser.commit()
            return replacement

        async def cli_refresh():
            """Compete for the token the browser claimed, through the CLI service."""
            try:
                await refresh_credentials(cli, token)
                return "unexpected_success"
            except TokenValidationError:
                return "rejected"

        browser_result, cli_result = await asyncio.wait_for(
            asyncio.gather(browser_refresh(), cli_refresh(), return_exceptions=True), timeout=15
        )
        assert isinstance(browser_result, str), repr(browser_result)
        assert cli_result == "rejected", repr(cli_result)
