"""
* @file     ${tests/api/cli_auth.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests interactive CLI sign-in with the approving person's own access.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the start, approval, exchange, refresh, deny, check and code mode.
"""

from tests.bud_test_base import BudAppTestCase


class CliAuthBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_CLI_CHECK}")

    def bud_the_authorization_link_uses_the_ui_path(self):
        self.check("link")

    def bud_approval_issues_the_approving_persons_access(self):
        self.check("issue callback")

    def bud_approval_issues_the_approving_persons_access_in_code_mode(self):
        self.check("issue code")

    def bud_refresh_rotates_and_retires_the_previous_token(self):
        self.check("refresh")

    def bud_revoking_every_refresh_token_ends_cli_access(self):
        self.check("revoke all")

    def bud_the_browser_cookie_refresh_is_kept(self):
        self.check("browser refresh")

    def bud_a_password_change_ends_cli_access(self):
        self.check("password change")

    def bud_a_session_version_change_ends_cli_access(self):
        self.check("session version")

    def bud_start_deletes_finished_requests_and_keeps_live_ones(self):
        self.check("purge")

    def bud_a_failed_refresh_is_audited_without_the_token(self):
        self.check("failed refresh")

    def bud_a_deactivated_persons_refresh_is_refused_and_kept(self):
        self.check("deactivated refresh")

    def bud_any_refresh_token_is_accepted_by_cli_refresh(self):
        self.check("any refresh")

    def bud_code_sign_in_is_off_by_default_and_read_from_both_names(self):
        self.check("setting")

    def bud_the_request_code_matches_the_rfc_vector(self):
        self.check("rfc vector")

    def bud_a_request_shows_its_time_without_its_code(self):
        self.check("request time")

    def bud_code_sign_in_off_refuses_start(self):
        self.check("off start")

    def bud_code_sign_in_off_refuses_lookup_and_approval(self):
        self.check("off lookup")

    def bud_code_sign_in_off_refuses_exchange(self):
        self.check("off exchange")

    def bud_a_missing_request_stays_invalid_with_code_sign_in_off(self):
        self.check("off missing")

    def bud_callback_sign_in_works_with_code_sign_in_off(self):
        self.check("off callback")

    def bud_deny_in_callback_mode_answers_the_loopback_and_deletes(self):
        self.check("deny callback")

    def bud_deny_in_code_mode_answers_empty_and_deletes(self):
        self.check("deny code")

    def bud_deny_ends_a_code_request_with_code_sign_in_off(self):
        self.check("deny off")

    def bud_deny_refuses_a_request_that_is_not_pending(self):
        self.check("deny refused")

    def bud_check_accepts_the_typed_code_in_any_case_and_spacing(self):
        self.check("check accepted")

    def bud_check_refuses_a_wrong_code_and_keeps_the_request(self):
        self.check("check refused")

    def bud_check_refuses_a_request_that_is_not_pending(self):
        self.check("check not pending")

    def bud_check_needs_sign_in_and_code_mode(self):
        self.check("check needs")

    def bud_approval_needs_the_matching_request_code(self):
        self.check("approve code")
