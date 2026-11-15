"""
* @file     ${tests/api/auth_token_lifecycles.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the one-time link flows end to end.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the invitation, the password reset and the email change.
"""

from tests.bud_test_base import BudAppTestCase


class AuthTokenLifecyclesBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one, or
        among the expected ones when the check says so."""
        for name, (found, expected, *among) in self.tc_checks[scenario].items():
            message = f"{name}: {self.parameters.MSG_LIFECYCLE_CHECK}"
            if among:
                self.assertIn(found, list(expected), msg=message)
            else:
                self.assertEqual(found, expected, msg=message)

    def bud_the_invite_link_carries_the_token_in_the_fragment(self):
        self.check("invite link")

    def bud_invite_info_describes_a_valid_invitation(self):
        self.check("invite info")

    def bud_accepting_an_invitation_sets_the_password(self):
        self.check("accept")

    def bud_an_invitation_is_accepted_once(self):
        self.check("accept twice")

    def bud_revoking_invalidates_the_outstanding_token(self):
        self.check("revoke")

    def bud_a_revoked_invitation_leaves_no_password_for_later(self):
        self.check("revoked password")

    def bud_resending_issues_a_fresh_token(self):
        self.check("resend")

    def bud_the_emailed_token_resets_the_password(self):
        self.check("reset")

    def bud_a_reset_signs_existing_sessions_out(self):
        self.check("sign out")

    def bud_a_reset_token_is_single_use(self):
        self.check("reset twice")

    def bud_the_new_password_meets_the_policy(self):
        self.check("weak password")

    def bud_no_token_is_issued_for_an_unknown_address(self):
        self.check("unknown address")

    def bud_the_login_moves_after_the_new_mailbox_confirms(self):
        self.check("email change")

    def bud_the_confirmation_goes_to_the_new_address(self):
        self.check("confirmation address")

    def bud_a_cancelled_change_is_not_confirmed(self):
        self.check("cancelled change")

    def bud_a_confirmation_token_is_single_use(self):
        self.check("confirm twice")
