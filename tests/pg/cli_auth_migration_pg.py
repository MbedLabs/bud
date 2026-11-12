"""
* @file     ${tests/pg/cli_auth_migration_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests that the CLI authorization migrations keep rows and its claims are atomic on PostgreSQL.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the checks against the live app and its database.
"""

from tests.bud_test_base import BudAppTestCase


class CliAuthMigrationPgBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_PG_CHECK}")

    def bud_the_cli_migration_has_one_append_only_head(self):
        self.check("head")

    def bud_the_cli_migration_keeps_rows_both_ways(self):
        self.check("migration")

    def bud_the_cli_migration_installs_on_an_empty_database(self):
        self.check("fresh")

    def bud_approval_exchange_and_refresh_each_have_one_winner(self):
        self.check("winners")

    def bud_approve_and_deny_of_one_request_have_one_winner(self):
        self.check("approve or deny")

    def bud_the_cli_user_lock_leaves_browser_refresh_working(self):
        self.check("lock")
