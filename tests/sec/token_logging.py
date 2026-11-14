"""
* @file     ${tests/sec/token_logging.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests that one-time tokens stay out of the logs.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of the application's own log records.
"""

from tests.bud_test_base import BudAppTestCase


class TokenLoggingBase(BudAppTestCase):

    def bud_request_is_logged(self):
        self.print_variables({"application logs": self.tc_app_logs})
        self.assertIn(
            self.parameters.INVITE_INFO_PATH,
            self.tc_app_logs,
            msg=self.parameters.MSG_TOKEN_REQUEST_LOGGED,
            abort_on_fail=False,
        )

    def bud_token_is_not_logged(self):
        self.assertNotIn(
            self.parameters.ONE_TIME_TOKEN,
            self.tc_app_logs,
            msg=self.parameters.MSG_TOKEN_NOT_LOGGED,
            abort_on_fail=False,
        )
