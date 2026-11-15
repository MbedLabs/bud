"""
* @file     ${tests/pg/refresh_flow_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the refresh-token flow on PostgreSQL.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the checks against the live app.
"""

from tests.bud_test_base import BudAppTestCase


class RefreshFlowPgBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_PG_CHECK}")

    def bud_login_sets_an_http_only_refresh_cookie(self):
        self.check("cookie")

    def bud_refresh_issues_a_working_access_token(self):
        self.check("refresh")

    def bud_refresh_without_a_cookie_is_refused(self):
        self.check("no cookie")

    def bud_refresh_rotates_and_the_old_token_is_refused(self):
        self.check("rotation")

    def bud_logout_revokes_the_refresh_token(self):
        self.check("logout")
