"""
* @file     ${tests/sec/password_policy.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the password policy.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of the shared validator and the request schemas.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class PasswordPolicyBase(BudAppTestCase):

    def bud_minimum_length_is_accepted(self):
        self.assertEqual(
            self.tc_minimum,
            self.tc_minimum_password,
            msg=self.parameters.MSG_PASSWORD_MINIMUM,
            abort_on_fail=False,
        )

    @parameterized(params.PASSWORD_SHORT_CASES)
    def bud_short_password_is_refused(self, case):
        refusal = self.tc_short[case]
        self.print_variables({"case": case, "refusal": refusal})
        self.assertEqual(
            type(refusal).__name__,
            self.parameters.VALUE_ERROR,
            msg=self.parameters.MSG_PASSWORD_SHORT_REFUSED,
            abort_on_fail=True,
        )
        self.assertIn(
            self.parameters.PASSWORD_TOO_SHORT_TEXT,
            str(refusal),
            msg=self.parameters.MSG_PASSWORD_SHORT_TEXT,
            abort_on_fail=False,
        )

    def bud_overlong_password_is_refused(self):
        self.print_variables({"refusal": self.tc_overlong})
        self.assertEqual(
            type(self.tc_overlong).__name__,
            self.parameters.VALUE_ERROR,
            msg=self.parameters.MSG_PASSWORD_LONG_REFUSED,
            abort_on_fail=True,
        )
        self.assertIn(
            self.parameters.PASSWORD_TOO_LONG_TEXT,
            str(self.tc_overlong),
            msg=self.parameters.MSG_PASSWORD_LONG_TEXT,
            abort_on_fail=False,
        )

    def bud_multibyte_password_is_counted_in_bytes(self):
        self.assertLess(
            len(self.parameters.PASSWORD_MULTIBYTE),
            self.tc_max_bytes,
            msg=self.parameters.MSG_PASSWORD_MULTIBYTE_CHARACTERS,
            abort_on_fail=True,
        )
        self.print_variables({"refusal": self.tc_multibyte})
        self.assertEqual(
            type(self.tc_multibyte).__name__,
            self.parameters.VALUE_ERROR,
            msg=self.parameters.MSG_PASSWORD_MULTIBYTE_REFUSED,
            abort_on_fail=True,
        )
        self.assertIn(
            self.parameters.PASSWORD_TOO_LONG_TEXT,
            str(self.tc_multibyte),
            msg=self.parameters.MSG_PASSWORD_LONG_TEXT,
            abort_on_fail=False,
        )

    @parameterized(params.PASSWORD_SCHEMAS)
    def bud_schema_refuses_a_short_password(self, schema):
        self.print_variables({"schema": schema, "result": self.tc_schema_short[schema]})
        self.assertEqual(
            type(self.tc_schema_short[schema]).__name__,
            self.parameters.VALIDATION_ERROR,
            msg=self.parameters.MSG_PASSWORD_SCHEMA_SHORT,
            abort_on_fail=False,
        )

    @parameterized(params.PASSWORD_SCHEMAS)
    def bud_schema_accepts_a_valid_password(self, schema):
        field = self.parameters.PASSWORD_SCHEMAS[schema][0]
        self.assertEqual(
            getattr(self.tc_schema_valid[schema], field, self.tc_schema_valid[schema]),
            self.parameters.PASSWORD_VALID,
            msg=self.parameters.MSG_PASSWORD_SCHEMA_VALID,
            abort_on_fail=False,
        )
