"""
* @file     ${tests/pg/execution_request_claims_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests that concurrent station claims and completions commit once on PostgreSQL.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the checks against the live app.
"""

from tests.bud_test_base import BudAppTestCase


class ExecutionRequestClaimsPgBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_PG_CHECK}")

    def bud_concurrent_claims_with_one_key_commit_one_execution(self):
        self.check("claims same key")

    def bud_concurrent_claims_with_two_keys_commit_one_execution(self):
        self.check("claims two keys")

    def bud_concurrent_equal_completions_record_one_answer(self):
        self.check("completions same answer")

    def bud_concurrent_different_completions_record_one_answer(self):
        self.check("completions two answers")
