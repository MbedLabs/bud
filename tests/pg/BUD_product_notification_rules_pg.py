"""
* @file     ${tests/pg/BUD_product_notification_rules_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The notification rules migrate up and down on PostgreSQL; every existing channel keeps every product.
* @author   Amine El Omari
* @date     2026-11-14
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
from tests.pg.product_notification_rules_pg import ProductNotificationRulesPgBase

ROOT = Path(__file__).resolve().parents[2]
REVISION = "023_product_notification_rules"
PREVIOUS = "022_product_access"
SEED = (
    "INSERT INTO notification_channels (name, format, url_encrypted, url_prefix, run_filter, enabled, "
    "created_at, updated_at) VALUES "
    "('team', 'slack', 'x', 'https://hooks.example.com/', 'all', true, now(), now()), "
    "('alerts', 'discord', 'x', 'https://hooks.example.com/', 'failures', true, now(), now()), "
    "('n8n', 'json', 'x', 'https://hooks.example.com/', 'first_failure', false, now(), now())"
)
CHANNELS = "SELECT name, run_filter, enabled, all_products FROM notification_channels ORDER BY name"
EXPECTED = [
    ("alerts", "failures", True, True),
    ("n8n", "first_failure", False, True),
    ("team", "all", True, True),
]


def plain_url():
    """The PostgreSQL address of the test database without a driver."""
    return os.environ.get("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")


class ProductNotificationRulesPgTest(ProductNotificationRulesPgBase):

    def setUpClass(self):
        super().setUpClass()
        script = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
        heads = script.get_heads()
        lineage = [revision.revision for revision in script.walk_revisions("base", heads[0])] if heads else []
        self.tc_checks = {
            "head": {
                "one head exists": (len(heads), 1),
                "the notification rules are in the lineage": (REVISION in lineage, True),
                "the notification rules follow the product access": (
                    script.get_revision(REVISION).down_revision,
                    PREVIOUS,
                ),
            },
            "migration": self.bud.bud_await(self.migration()),
        }

    def migrate(self, *arguments, url):
        """Run one migration command and return its exit code."""
        return self.bud.bud_alembic(list(arguments), url).returncode

    async def migration(self):
        admin = await asyncpg.connect(plain_url())
        name = "notification_rules_" + secrets.token_hex(6)
        await admin.execute(f'CREATE DATABASE "{name}"')
        url = urlunsplit(urlsplit(plain_url())._replace(path=f"/{name}"))
        connection = await asyncpg.connect(url)
        checks = {}
        try:
            checks["the database reaches the product access"] = (self.migrate("upgrade", PREVIOUS, url=url), 0)
            await connection.execute(SEED)
            checks["the database upgrades to the notification rules"] = (self.migrate("upgrade", REVISION, url=url), 0)
            checks["every channel keeps its filter and state and takes every product"] = (
                [tuple(row) for row in await connection.fetch(CHANNELS)],
                EXPECTED,
            )
            checks["no product rule exists after the migration"] = (
                await connection.fetchval("SELECT count(*) FROM product_notification_rules"),
                0,
            )
            checks["the database downgrades to the product access"] = (self.migrate("downgrade", PREVIOUS, url=url), 0)
            checks["the rule table is gone after the downgrade"] = (
                await connection.fetchval("SELECT to_regclass('product_notification_rules') IS NULL"),
                True,
            )
            checks["the channels keep their rows after the downgrade"] = (
                await connection.fetchval("SELECT count(*) FROM notification_channels"),
                3,
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
    ProductNotificationRulesPgTest().run()
