"""
* @file     ${tests/pg/session_invalidation_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests that a password change or reset ends every session on PostgreSQL.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the checks against the live app.
"""

from tests.bud_test_base import BudAppTestCase


class SessionInvalidationPgBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_PG_CHECK}")

    def bud_a_password_change_ends_every_session(self):
        self.check("change")

    def bud_a_password_reset_ends_every_session(self):
        self.check("reset")
