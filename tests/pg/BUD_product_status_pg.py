"""
* @file     ${tests/pg/BUD_product_status_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The product status migrates up and down on PostgreSQL keeping every product; existing products become Active.
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
from tests.pg.product_status_pg import ProductStatusPgBase

ROOT = Path(__file__).resolve().parents[2]
REVISION = "021_product_status"
PREVIOUS = "020_audit_request_indexes"
PRODUCT = "Demo"
ACTIVE = "Active"


def plain_url():
    """The PostgreSQL address of the test database without a driver."""
    return os.environ.get("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")


async def has_status(connection):
    """Whether products has a status column."""
    return await connection.fetchval(
        "SELECT count(*) FROM information_schema.columns "
        "WHERE table_name='products' AND column_name='status'"
    )


class ProductStatusPgTest(ProductStatusPgBase):

    def setUpClass(self):
        super().setUpClass()
        script = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
        heads = script.get_heads()
        lineage = [revision.revision for revision in script.walk_revisions("base", heads[0])] if heads else []
        self.tc_checks = {
            "head": {
                "one head exists": (len(heads), 1),
                "the product status is in the lineage": (REVISION in lineage, True),
                "the product status follows the audit indexes": (script.get_revision(REVISION).down_revision, PREVIOUS),
            },
            "migration": self.bud.bud_await(self.migration()),
        }

    def migrate(self, *arguments, url):
        """Run one migration command and return its exit code."""
        return self.bud.bud_alembic(list(arguments), url).returncode

    async def migration(self):
        admin = await asyncpg.connect(plain_url())
        name = "product_status_" + secrets.token_hex(6)
        await admin.execute(f'CREATE DATABASE "{name}"')
        url = urlunsplit(urlsplit(plain_url())._replace(path=f"/{name}"))
        connection = await asyncpg.connect(url)
        checks = {}
        try:
            checks["the database reaches the audit indexes"] = (self.migrate("upgrade", PREVIOUS, url=url), 0)
            await connection.execute(
                "INSERT INTO products (name, created_at, updated_at) VALUES ($1, now(), now())", PRODUCT
            )
            checks["no status exists before the migration"] = (await has_status(connection), 0)
            checks["the database upgrades to the product status"] = (self.migrate("upgrade", REVISION, url=url), 0)
            checks["the existing product is active"] = (
                await connection.fetchval("SELECT status FROM products WHERE name=$1", PRODUCT),
                ACTIVE,
            )
            checks["the database downgrades to the audit indexes"] = (self.migrate("downgrade", PREVIOUS, url=url), 0)
            checks["the status is gone after the downgrade"] = (await has_status(connection), 0)
            checks["the product survives the downgrade"] = (await connection.fetchval("SELECT count(*) FROM products"), 1)
            checks["the database upgrades again"] = (self.migrate("upgrade", REVISION, url=url), 0)
            checks["the product status is reached again"] = (
                await connection.fetchval("SELECT version_num FROM alembic_version"),
                REVISION,
            )
        finally:
            await connection.close()
            await admin.execute(f'DROP DATABASE IF EXISTS "{name}"')
            await admin.close()
        return checks

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ProductStatusPgTest().run()
