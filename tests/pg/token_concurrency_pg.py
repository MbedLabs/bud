"""
* @file     ${tests/pg/token_concurrency_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests that one-time tokens survive concurrent use exactly once on PostgreSQL.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the checks against the live app and its database.
"""

from tests.bud_test_base import BudAppTestCase


class TokenConcurrencyPgBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_PG_CHECK}")

    def bud_a_concurrent_refresh_succeeds_once(self):
        self.check("refresh")

    def bud_a_concurrent_password_reset_succeeds_once(self):
        self.check("reset")

    def bud_a_concurrent_invitation_acceptance_succeeds_once(self):
        self.check("invite")

    def bud_a_concurrent_email_verification_succeeds_once(self):
        self.check("verify")
