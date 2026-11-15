"""
* @file     ${tests/api/auth_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the authentication endpoints with real credentials.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the login, the refresh, the profile and the one-time links.
"""

from tests.bud_test_base import BudAppTestCase


class AuthApiBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one, or
        among the expected ones when the check says so."""
        for name, (found, expected, *among) in self.tc_checks[scenario].items():
            message = f"{name}: {self.parameters.MSG_AUTH_CHECK}"
            if among:
                self.assertIn(found, list(expected), msg=message)
            else:
                self.assertEqual(found, expected, msg=message)

    def bud_login_returns_a_token_the_person_and_a_refresh_cookie(self):
        self.check("login")

    def bud_login_refuses_wrong_unknown_and_deactivated_accounts_alike(self):
        self.check("login refusals")

    def bud_the_refresh_cookie_rotates_once(self):
        self.check("refresh")

    def bud_logout_revokes_the_refresh_token(self):
        self.check("logout")

    def bud_the_profile_needs_a_token_and_takes_a_new_name(self):
        self.check("profile")

    def bud_an_administrator_moves_their_email_through_both_mailboxes(self):
        self.check("admin email change")

    def bud_another_person_waits_for_approval(self):
        self.check("email change request")

    def bud_a_password_change_needs_the_current_one_and_signs_out(self):
        self.check("password change")

    def bud_a_password_reset_reveals_no_account(self):
        self.check("password reset")

    def bud_bogus_one_time_tokens_are_refused(self):
        self.check("bogus tokens")
