"""
* @file     ${tests/sec/cli_auth_sec.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests that CLI authorization refuses invalid callbacks, proof keys, state and account changes.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the start, approval, exchange, refresh binding, deny and rate limits.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class CliAuthSecBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one, or
        among the expected ones when the check says so."""
        for name, (found, expected, *among) in self.tc_checks[scenario].items():
            message = f"{name}: {self.parameters.MSG_CLI_SEC_CHECK}"
            if among:
                self.assertIn(found, list(expected), msg=message)
            else:
                self.assertEqual(found, expected, msg=message)

    def bud_only_exact_loopback_callbacks_are_accepted(self):
        self.check("callbacks")

    def bud_invalid_start_fields_are_refused(self):
        self.check("fields")

    def bud_approval_needs_a_person_and_happens_once(self):
        self.check("confirmation")

    @parameterized(params.CLI_EXCHANGE_FAILURES)
    def bud_an_invalid_exchange_issues_no_token(self, failure):
        self.check(f"exchange {failure}")

    def bud_malformed_verifiers_are_refused(self):
        self.check("verifiers")

    def bud_a_cli_token_needs_a_live_refresh_row_of_its_person(self):
        self.check("refresh rows")

    @parameterized(params.CLI_BAD_BINDINGS)
    def bud_an_invalid_refresh_binding_is_refused(self, condition):
        self.check(f"binding {condition}")

    def bud_station_tokens_still_authenticate(self):
        self.check("station")

    @parameterized(params.CLI_LIMITED_ROUTES)
    def bud_public_cli_routes_are_rate_limited(self, path):
        self.check(f"limited {path}")

    def bud_deny_needs_a_signed_in_person_and_keeps_the_request(self):
        self.check("deny")

    def bud_deny_refuses_malformed_bodies_without_a_rate_limit(self):
        self.check("deny bodies")

    def bud_a_typed_code_mismatch_is_audited(self):
        self.check("mismatch")

    def bud_check_and_approve_are_rate_limited(self):
        self.check("check limits")

    def bud_approval_refuses_a_request_approved_after_its_check(self):
        self.check("approved elsewhere")
