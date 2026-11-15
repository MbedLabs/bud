"""
* @file     ${tests/pg/email_change_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the verified email change and invitation as verification on PostgreSQL.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the checks against the live app and its database.
"""

from tests.bud_test_base import BudAppTestCase


class EmailChangePgBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_PG_CHECK}")

    def bud_an_email_change_needs_approval_and_confirmation_and_ends_sessions(self):
        self.check("flow")

    def bud_a_token_cannot_apply_another_pending_address(self):
        self.check("race")

    def bud_a_wrong_password_starts_no_change(self):
        self.check("wrong password")

    def bud_an_administrator_change_needs_confirmation(self):
        self.check("admin")

    def bud_accepting_an_invitation_verifies_the_account(self):
        self.check("invite")
