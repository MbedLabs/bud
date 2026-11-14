"""
* @file     ${tests/sec/BUD_token_logging.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    One-time tokens never appear in the application's own log records.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module tests a token sent in the body and one sent in the query string.
"""

import logging

from tests.sec.token_logging import TokenLoggingBase


class TokenLoggingTest(TokenLoggingBase):

    def setUpClass(self):
        super().setUpClass()
        self.bud.bud_start_app(signed_in=False)
        token = {"token": self.parameters.ONE_TIME_TOKEN}
        self.bud.bud_start_log_capture(logging.INFO)
        self.bud.bud_request(self.parameters.POST, self.parameters.INVITE_INFO_PATH, json=token)
        self.bud.bud_request(
            self.parameters.POST,
            self.parameters.INVITE_INFO_QUERY_PATH.format(self.parameters.ONE_TIME_TOKEN),
            json=token,
        )
        records = self.bud.bud_stop_log_capture()
        self.tc_app_logs = "\n".join(
            record.getMessage()
            for record in records
            if record.name.startswith(self.parameters.APP_LOGGERS)
        )

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    TokenLoggingTest().run()
