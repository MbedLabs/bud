"""
* @file     ${tests/pg/BUD_audit_request_indexes_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The audit request indexes migrate up and down on PostgreSQL keeping every event; refusals flag once.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module migrates a scratch database of its own and records thirty refusals at once.
"""

import asyncio
import os
import secrets
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit, urlunsplit

import asyncpg
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.observability import client_ip_var
from app.db import database
from app.models import AuditEvent
from app.services import audit
from tests.pg.audit_request_indexes_pg import AuditRequestIndexesPgBase

ROOT = Path(__file__).resolve().parents[2]
REVISION = "020_audit_request_indexes"
PREVIOUS = "019_cli_auth_sessions"
INDEXES = {"ix_audit_events_outcome", "ix_audit_events_ip"}


def plain_url():
    """The PostgreSQL address of the test database without a driver."""
    return os.environ.get("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")


async def indexes(connection):
    """The names of the indexes on audit_events."""
    rows = await connection.fetch("SELECT indexname FROM pg_indexes WHERE tablename='audit_events'")
    return {row["indexname"] for row in rows}


class AuditRequestIndexesPgTest(AuditRequestIndexesPgBase):

    def setUpClass(self):
        super().setUpClass()
        script = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
        heads = script.get_heads()
        lineage = [revision.revision for revision in script.walk_revisions("base", heads[0])] if heads else []
        self.tc_checks = {
            "head": {
                "one head exists": (len(heads), 1),
                "the index migration is in the lineage": (REVISION in lineage, True),
                "the index migration follows the CLI sessions": (script.get_revision(REVISION).down_revision, PREVIOUS),
            },
            "migration": self.bud.bud_await(self.migration()),
            "flag": self.bud.bud_await(self.flag()),
        }

    def migrate(self, *arguments, url):
        """Run one migration command and return its exit code."""
        return self.bud.bud_alembic(list(arguments), url).returncode

    async def migration(self):
        admin = await asyncpg.connect(plain_url())
        name = "audit_indexes_" + secrets.token_hex(6)
        await admin.execute(f'CREATE DATABASE "{name}"')
        url = urlunsplit(urlsplit(plain_url())._replace(path=f"/{name}"))
        connection = await asyncpg.connect(url)
        checks = {}
        try:
            checks["the database reaches the CLI sessions"] = (self.migrate("upgrade", PREVIOUS, url=url), 0)
            await connection.execute(
                "INSERT INTO audit_events (occurred_at, actor_type, action, ip, outcome) "
                "VALUES (now(), 'anonymous', 'auth.login', '192.0.2.1', 'failure')"
            )
            checks["no index exists before the migration"] = (INDEXES & await indexes(connection), set())
            checks["the database upgrades to the index migration"] = (self.migrate("upgrade", REVISION, url=url), 0)
            checks["the indexes exist after the upgrade"] = (INDEXES <= await indexes(connection), True)
            checks["the event survives the upgrade"] = (await connection.fetchval("SELECT count(*) FROM audit_events"), 1)
            checks["the database downgrades to the CLI sessions"] = (self.migrate("downgrade", PREVIOUS, url=url), 0)
            checks["the downgrade returns to the CLI sessions"] = (await connection.fetchval("SELECT version_num FROM alembic_version"), PREVIOUS)
            checks["the indexes are gone after the downgrade"] = (INDEXES & await indexes(connection), set())
            checks["the event survives the downgrade"] = (await connection.fetchval("SELECT count(*) FROM audit_events"), 1)
            checks["the database upgrades again"] = (self.migrate("upgrade", REVISION, url=url), 0)
            checks["the index migration is reached again"] = (await connection.fetchval("SELECT version_num FROM alembic_version"), REVISION)
        finally:
            await connection.close()
            await admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
            await admin.close()
        return checks

    async def flag(self):
        engine = create_async_engine(plain_url().replace("postgresql://", "postgresql+asyncpg://"), pool_size=10, max_overflow=20)
        address = f"198.51.100.{secrets.randbelow(250) + 1}-{secrets.token_hex(4)}"
        token = client_ip_var.set(address)
        try:
            with mock.patch.object(database, "async_session_maker", async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)):
                await asyncio.gather(
                    *(
                        audit.record_api_request(
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
                        select(func.count(AuditEvent.id)).where(AuditEvent.ip == address, AuditEvent.action == "api.request")
                    )
                    flags = await session.scalar(
                        select(func.count(AuditEvent.id)).where(AuditEvent.ip == address, AuditEvent.action == "security.repeated_refusals")
                    )
        finally:
            client_ip_var.reset(token)
            await engine.dispose()
        return {
            "every refusal is recorded": (denied, 30),
            "one flag is left": (flags, 1),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    AuditRequestIndexesPgTest().run()
