"""
* @file     ${tests/logic/access_token_format.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests which access tokens decode.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of the token algorithm and expiry checks.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class AccessTokenFormatBase(BudAppTestCase):

    def bud_standard_hs256_token_decodes(self):
        self.print_variables({"claims": self.tc_standard})
        self.assertEqual(
            (self.tc_standard or {}).get("sub"),
            self.parameters.TOKEN_USER_ID,
            msg=self.parameters.MSG_TOKEN_HS256,
            abort_on_fail=False,
        )

    def bud_issued_token_decodes(self):
        self.print_variables({"claims": self.tc_issued})
        self.assertEqual(
            (self.tc_issued or {}).get("type"),
            self.parameters.TOKEN_USER_TYPE,
            msg=self.parameters.MSG_TOKEN_ISSUED,
            abort_on_fail=False,
        )

    @parameterized(params.TOKEN_REFUSED_CASES)
    def bud_token_is_refused(self, case):
        self.print_variables({"case": case, "claims": self.tc_refused[case]})
        self.assertEqual(
            type(self.tc_refused[case]).__name__,
            self.parameters.NO_CLAIMS,
            msg=self.parameters.MSG_TOKEN_REFUSED,
            abort_on_fail=False,
        )

    def bud_expired_station_token_is_refused(self):
        self.print_variables({"claims": self.tc_station_checked})
        self.assertEqual(
            type(self.tc_station_checked).__name__,
            self.parameters.NO_CLAIMS,
            msg=self.parameters.MSG_TOKEN_STATION_EXPIRED,
            abort_on_fail=False,
        )

    def bud_expired_station_token_decodes_without_the_check(self):
        self.print_variables({"claims": self.tc_station_unchecked})
        self.assertEqual(
            (self.tc_station_unchecked or {}).get("jti"),
            self.parameters.TOKEN_STATION_JTI,
            msg=self.parameters.MSG_TOKEN_STATION_NO_CHECK,
            abort_on_fail=False,
        )
