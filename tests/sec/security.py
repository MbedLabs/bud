"""
* @file     ${tests/sec/security.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the access and Test Station tokens.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of the token claims.
"""

from tests.bud_test_base import BudAppTestCase


class SecurityBase(BudAppTestCase):

    def bud_access_token_decodes(self):
        self.print_variables({"access token claims": self.tc_access})
        self.assertNotEqual(
            type(self.tc_access).__name__,
            self.parameters.NO_CLAIMS,
            msg=self.parameters.MSG_ACCESS_TOKEN_DECODES,
            abort_on_fail=True,
        )

    def bud_access_token_keeps_its_subject(self):
        self.assertEqual(
            self.tc_access["sub"],
            self.parameters.TOKEN_SUBJECT,
            msg=self.parameters.MSG_ACCESS_TOKEN_SUBJECT,
            abort_on_fail=False,
        )

    def bud_access_token_expires(self):
        self.assertIn(
            self.parameters.TOKEN_EXPIRY_CLAIM,
            self.tc_access,
            msg=self.parameters.MSG_ACCESS_TOKEN_EXPIRES,
            abort_on_fail=False,
        )

    def bud_station_token_decodes(self):
        self.print_variables({"station token claims": self.tc_station})
        self.assertNotEqual(
            type(self.tc_station).__name__,
            self.parameters.NO_CLAIMS,
            msg=self.parameters.MSG_STATION_TOKEN_DECODES,
            abort_on_fail=True,
        )

    def bud_station_token_names_its_account(self):
        self.assertEqual(
            self.tc_station["sub"],
            self.parameters.STATION_TOKEN_ACCOUNT,
            msg=self.parameters.MSG_STATION_TOKEN_SUBJECT,
            abort_on_fail=False,
        )

    def bud_station_token_is_a_runner_token(self):
        self.assertEqual(
            self.tc_station["type"],
            self.parameters.STATION_TOKEN_TYPE,
            msg=self.parameters.MSG_STATION_TOKEN_TYPE,
            abort_on_fail=False,
        )
