"""
* @file     ${tests/pg/BUD_cli_auth_migration_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The CLI sessions migration keeps every row up and down, and approvals, exchanges and refreshes win once.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module migrates scratch databases of its own and races requests on the live app.
"""

import asyncio
import base64
import hashlib
import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest import mock
from urllib.parse import urlsplit, urlunsplit

import asyncpg
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.config import settings
from app.models import User, UserRole, UserTokenPurpose
from app.schemas.cli_auth import CliStartRequest
from app.services import cli_auth, token_service
from tests.pg.cli_auth_migration_pg import CliAuthMigrationPgBase

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = "v" * 43
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip("=")
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


def code_for(challenge):
    """The XXXX-XXXX request code of a challenge, computed independently of the app."""
    letters = base64.b32encode(hashlib.sha256(challenge.encode()).digest()[:5]).decode()
    return f"{letters[:4]}-{letters[4:]}"


REQUEST_CODE = code_for(CHALLENGE)


def plain_url():
    """The PostgreSQL address of the test database without a driver."""
    return os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")


def body_of(response):
    """The JSON answer, or an empty one."""
    try:
        return response.json() or {}
    except ValueError:
        return {}


async def seed_previous_head(connection):
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


async def snapshot(connection):
    """The row count of every table the seed fills."""
    return {table: await connection.fetchval(f"SELECT count(*) FROM {table}") for table in RETAINED_TABLES}


async def session_table_exists(connection):
    return await connection.fetchval("SELECT to_regclass('public.cli_auth_sessions') IS NOT NULL")


class CliAuthMigrationPgTest(CliAuthMigrationPgBase):

    def setUpClass(self):
        super().setUpClass()
        script = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
        heads = script.get_heads()
        lineage = [revision.revision for revision in script.walk_revisions("base", heads[0])] if heads else []
        self.script = script
        self.tc_checks = {
            "head": {
                "one head exists": (len(heads), 1),
                "the CLI sessions are in the lineage": ("019_cli_auth_sessions" in lineage, True),
                "the CLI sessions follow the report requests": (script.get_revision("019_cli_auth_sessions").down_revision, "018_report_requests"),
            },
            "migration": self.bud.bud_await(self.migration()),
            "fresh": self.bud.bud_await(self.fresh()),
        }
        self.client = self.bud.bud_start_live_app()
        with mock.patch.object(settings, "CLI_CODE_MODE_ENABLED", True):
            self.tc_checks["winners"] = self.winners()
            self.tc_checks["approve or deny"] = self.approve_or_deny()
            self.tc_checks["lock"] = self.bud.bud_await(self.lock())

    def migrate(self, *arguments, url):
        return self.bud.bud_alembic(list(arguments), url).returncode

    async def scratch(self, stem):
        """A new scratch database: the admin connection, its name, its address and a connection."""
        admin = await asyncpg.connect(plain_url())
        name = stem + secrets.token_hex(6)
        await admin.execute(f'CREATE DATABASE "{name}"')
        url = urlunsplit(urlsplit(plain_url())._replace(path=f"/{name}"))
        return admin, name, url, await asyncpg.connect(url)

    async def migration(self):
        admin, name, url, connection = await self.scratch("cli_auth_migration_")
        checks = {}
        try:
            checks["the database reaches the report requests"] = (self.migrate("upgrade", "018_report_requests", url=url), 0)
            user_id = await seed_previous_head(connection)
            before = await snapshot(connection)
            checks["one row is seeded per table"] = (before, {table: 1 for table in RETAINED_TABLES})
            checks["the database upgrades to the CLI sessions"] = (self.migrate("upgrade", "019_cli_auth_sessions", url=url), 0)
            checks["the rows survive the upgrade"] = (await snapshot(connection), before)
            columns = await connection.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='cli_auth_sessions'"
            )
            checks["the session table has its columns"] = ({row["column_name"] for row in columns}, SESSION_COLUMNS)
            indexes = await connection.fetch("SELECT indexname FROM pg_indexes WHERE tablename='cli_auth_sessions'")
            checks["the expiry is indexed"] = ("ix_cli_auth_sessions_expires_at" in {row["indexname"] for row in indexes}, True)
            await connection.execute(
                "INSERT INTO cli_auth_sessions (id, client_name, mode, code_challenge, state, expires_at, created_at) "
                "VALUES (gen_random_uuid(), 'Pending', 'code', $1, 'state', now() + interval '10 minutes', now())",
                CHALLENGE,
            )
            await connection.execute(
                "INSERT INTO cli_auth_sessions (id, client_name, mode, redirect_uri, code_challenge, state, exchange_code_hash, "
                "user_id, approved_session_version, expires_at, consumed_at, created_at) VALUES (gen_random_uuid(), 'Approved', "
                "'callback', 'http://127.0.0.1:4567/callback', $1, 'state', $2, $3, 1, now() + interval '10 minutes', now(), now())",
                CHALLENGE,
                "b" * 64,
                user_id,
            )
            checks["the database downgrades with sessions present"] = (self.migrate("downgrade", "018_report_requests", url=url), 0)
            checks["the downgrade returns to the report requests"] = (await connection.fetchval("SELECT version_num FROM alembic_version"), "018_report_requests")
            checks["the session table is gone"] = (await session_table_exists(connection), False)
            checks["the rows survive the downgrade"] = (await snapshot(connection), before)
            checks["the database upgrades again"] = (self.migrate("upgrade", "019_cli_auth_sessions", url=url), 0)
            checks["the upgrade reaches the CLI sessions"] = (await connection.fetchval("SELECT version_num FROM alembic_version"), "019_cli_auth_sessions")
            checks["no session is left"] = (await connection.fetchval("SELECT count(*) FROM cli_auth_sessions"), 0)
            checks["the rows survive again"] = (await snapshot(connection), before)
        finally:
            await connection.close()
            await admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
            await admin.close()
        return checks

    async def fresh(self):
        admin, name, url, connection = await self.scratch("cli_auth_fresh_")
        try:
            upgraded = self.migrate("upgrade", "head", url=url)
            return {
                "an empty database upgrades": (upgraded, 0),
                "the session table exists": (await session_table_exists(connection), True),
                "the database is at the head": (await connection.fetchval("SELECT version_num FROM alembic_version"), self.script.get_current_head()),
            }
        finally:
            await connection.close()
            await admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
            await admin.close()

    @staticmethod
    def race(call, other=None):
        """Begin two requests at the same barrier, one call twice by default."""
        barrier = Barrier(2)

        def run(operation):
            barrier.wait()
            return operation()

        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(run, (call, other or call)))

    def admin(self):
        login, headers = self.bud.bud_live_bearer()
        return login, headers

    def start(self, mode="code"):
        body = {"client_name": "Concurrent client", "mode": mode, "code_challenge": CHALLENGE, "state": "state"}
        if mode == "callback":
            body["redirect_uri"] = "http://127.0.0.1:1234/callback"
        return self.client.post("/api/auth/cli/start", json=body)

    def winners(self):
        login, headers = self.admin()
        start = self.start()
        session_id = body_of(start).get("session_id")
        approvals = self.race(
            lambda: self.client.post("/api/auth/cli/approve", json={"session_id": session_id, "request_code": REQUEST_CODE}, headers=headers)
        )
        code = next((body_of(r).get("exchange_code") for r in approvals if r.status_code == 200), "")
        exchanges = self.race(
            lambda: self.client.post("/api/auth/cli/exchange", json={"session_id": session_id, "code": code, "code_verifier": VERIFIER})
        )
        tokens = next((body_of(r) for r in exchanges if r.status_code == 200), {})
        refreshes = self.race(lambda: self.client.post("/api/auth/cli/refresh", json={"refresh_token": tokens.get("refresh_token")}))
        return {
            "the administrator signs in": (login, 200),
            "the sign-in starts": (start.status_code, 200),
            "one approval wins": (sorted(r.status_code for r in approvals), [200, 400]),
            "one exchange wins": (sorted(r.status_code for r in exchanges), [200, 400]),
            "one refresh wins": (sorted(r.status_code for r in refreshes), [200, 401]),
        }

    def approve_or_deny(self):
        login, headers = self.admin()
        first = self.start("callback")
        session_id = body_of(first).get("session_id")
        outcomes = self.race(
            lambda: self.client.post("/api/auth/cli/approve", json={"session_id": session_id, "request_code": REQUEST_CODE}, headers=headers),
            lambda: self.client.post("/api/auth/cli/deny", json={"session_id": session_id}, headers=headers),
        )
        lookup = self.client.get(f"/api/auth/cli/sessions/{session_id}", headers=headers).status_code
        second = self.start("callback")
        other_id = body_of(second).get("session_id")
        denials = self.race(lambda: self.client.post("/api/auth/cli/deny", json={"session_id": other_id}, headers=headers))
        return {
            "the administrator signs in": (login, 200),
            "both sign-ins start": ((first.status_code, second.status_code), (200, 200)),
            "approve or deny wins once": (sorted(r.status_code for r in outcomes), [200, 400]),
            "the decided request is no longer readable": (lookup, 400),
            "one of two denials wins": (sorted(r.status_code for r in denials), [200, 400]),
        }

    async def lock(self):
        engine = create_async_engine(plain_url().replace("postgresql://", "postgresql+asyncpg://"), poolclass=NullPool)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with maker() as setup:
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
                token = await token_service.create_user_token(
                    setup, user_id=user_id, purpose=UserTokenPurpose.refresh, ttl_hours=1, invalidate_existing=False
                )
                pending = await cli_auth.start_session(
                    setup, CliStartRequest(client_name="Lock test", mode="code", code_challenge=CHALLENGE, state="state")
                )
                session_id = pending.id
                await setup.commit()
            async with maker() as browser, maker() as cli:
                await token_service.claim_token(browser, token=token, purpose=UserTokenPurpose.refresh)
                person = await cli.get(User, user_id)
                await cli_auth.approve_session(cli, session_id, person, REQUEST_CODE)

                async def browser_refresh():
                    replacement = await token_service.create_user_token(
                        browser, user_id=user_id, purpose=UserTokenPurpose.refresh, ttl_hours=1, invalidate_existing=False
                    )
                    await browser.commit()
                    return replacement

                async def cli_refresh():
                    try:
                        await cli_auth.refresh_credentials(cli, token)
                        return "unexpected_success"
                    except token_service.TokenValidationError:
                        return "rejected"

                browser_result, cli_result = await asyncio.wait_for(
                    asyncio.gather(browser_refresh(), cli_refresh(), return_exceptions=True), timeout=15
                )
        finally:
            await engine.dispose()
        return {
            "the browser refresh completes": (type(browser_result).__name__, "str"),
            "the CLI refresh of the claimed token is refused": (cli_result, "rejected"),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    CliAuthMigrationPgTest().run()
