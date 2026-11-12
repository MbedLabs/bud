"""
* @file     ${tests/api/users_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests user administration.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of users, invitations and the email-change workflow.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class UsersApiBase(BudAppTestCase):

    def check(self, section):
        """Assert every named check of one section: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[section].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_USERS_CHECK}")

    def bud_lists_and_creates_users(self):
        self.check("list and create")

    def bud_invites_resends_and_revokes(self):
        self.check("invitations")

    def bud_email_change_waits_for_confirmation(self):
        self.check("email change")

    def bud_updates_and_deletes_users(self):
        self.check("update and delete")

    @parameterized(params.USERS_SIGNED_OUT_CALLS)
    def bud_signed_out_visitor_cannot_reach_user_routes(self, method, path):
        self.assertEqual(
            self.tc_signed_out[(method, path)],
            self.parameters.STATUS_UNAUTHORIZED,
            msg=self.parameters.MSG_USERS_SIGNED_OUT,
        )
