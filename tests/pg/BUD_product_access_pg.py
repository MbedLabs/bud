"""
* @file     ${tests/pg/BUD_product_access_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The access per product migrates up and down on PostgreSQL; every user keeps his access on every product.
* @author   Amine El Omari
* @date     2026-11-13
* @version  1.0.0
* @note     This module migrates a scratch database of its own.
"""

import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg

from alembic.config import Config
from alembic.script import ScriptDirectory
from tests.pg.product_access_pg import ProductAccessPgBase

ROOT = Path(__file__).resolve().parents[2]
REVISION = "022_product_access"
PREVIOUS = "021_product_status"
SEED = (
    "INSERT INTO products (name, status, created_at, updated_at) VALUES "
    "('Demo', 'Active', now(), now()), ('ABC', 'Active', now(), now())",
    "INSERT INTO users (email, full_name, hashed_password, role, is_active, session_version, "
    "created_at, updated_at) VALUES "
    "('viewer@example.com', 'V', 'x', 'viewer', true, 1, now(), now()), "
    "('developer@example.com', 'D', 'x', 'developer', true, 1, now(), now()), "
    "('admin@example.com', 'A', 'x', 'admin', true, 1, now(), now())",
    "INSERT INTO policies (name, permissions, is_default, created_at, updated_at) VALUES "
    "('Reports only', '{\"reports\": [\"export\"]}', false, now(), now()), "
    "('Stations only', '{\"stations\": [\"view\"]}', false, now(), now())",
    "INSERT INTO access_groups (name, is_default, created_at, updated_at) VALUES "
    "('Reporters', false, now(), now()), ('Station watchers', false, now(), now())",
    "INSERT INTO access_group_policies SELECT g.id, p.id FROM access_groups g, policies p "
    "WHERE (g.name = 'Reporters' AND p.name = 'Reports only') "
    "OR (g.name = 'Station watchers' AND p.name = 'Stations only')",
    "INSERT INTO access_group_members (group_id, user_id, created_at) SELECT g.id, u.id, now() "
    "FROM access_groups g, users u WHERE g.name IN ('Reporters', 'Station watchers') "
    "AND u.email = 'viewer@example.com'",
)
ROWS = (
    "SELECT u.email, p.name, g.name FROM product_access pa JOIN users u ON u.id = pa.user_id "
    "JOIN products p ON p.id = pa.product_id JOIN access_groups g ON g.id = pa.group_id ORDER BY 1, 2, 3"
)
EXPECTED = [
    ("developer@example.com", "ABC", "Test Operators"),
    ("developer@example.com", "Demo", "Test Operators"),
    ("viewer@example.com", "ABC", "Reporters"),
    ("viewer@example.com", "ABC", "Results Viewers"),
    ("viewer@example.com", "Demo", "Reporters"),
    ("viewer@example.com", "Demo", "Results Viewers"),
]


def plain_url():
    """The PostgreSQL address of the test database without a driver."""
    return os.environ.get("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")


class ProductAccessPgTest(ProductAccessPgBase):

    def setUpClass(self):
        super().setUpClass()
        script = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
        heads = script.get_heads()
        lineage = [revision.revision for revision in script.walk_revisions("base", heads[0])] if heads else []
        self.tc_checks = {
            "head": {
                "one head exists": (len(heads), 1),
                "the product access is in the lineage": (REVISION in lineage, True),
                "the product access follows the product status": (script.get_revision(REVISION).down_revision, PREVIOUS),
            },
            "migration": self.bud.bud_await(self.migration()),
        }

    def migrate(self, *arguments, url):
        """Run one migration command and return its exit code."""
        return self.bud.bud_alembic(list(arguments), url).returncode

    async def migration(self):
        admin = await asyncpg.connect(plain_url())
        name = "product_access_" + secrets.token_hex(6)
        await admin.execute(f'CREATE DATABASE "{name}"')
        url = urlunsplit(urlsplit(plain_url())._replace(path=f"/{name}"))
        connection = await asyncpg.connect(url)
        checks = {}
        try:
            checks["the database reaches the product status"] = (self.migrate("upgrade", PREVIOUS, url=url), 0)
            for statement in SEED:
                await connection.execute(statement)
            checks["the database upgrades to the product access"] = (self.migrate("upgrade", REVISION, url=url), 0)
            rows = [tuple(row) for row in await connection.fetch(ROWS)]
            checks["each user keeps his product groups and his base role's group on every product"] = (rows, EXPECTED)
            checks["the database downgrades to the product status"] = (self.migrate("downgrade", PREVIOUS, url=url), 0)
            checks["the access table is gone after the downgrade"] = (
                await connection.fetchval("SELECT to_regclass('product_access') IS NULL"),
                True,
            )
            checks["the database upgrades again"] = (self.migrate("upgrade", REVISION, url=url), 0)
        finally:
            await connection.close()
            await admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
            await admin.close()
        return checks

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ProductAccessPgTest().run()
