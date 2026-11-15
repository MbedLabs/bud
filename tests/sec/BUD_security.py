"""
* @file     ${tests/sec/BUD_security.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Access and Test Station tokens decode with their claims.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module tests one access token and one Test Station token.
"""

from app.core import security
from tests.sec.security import SecurityBase


class SecurityTest(SecurityBase):

    def setUpClass(self):
        super().setUpClass()
        access = security.create_access_token(
            {"sub": self.parameters.TOKEN_SUBJECT}, expires_delta=self.parameters.TOKEN_LIFETIME
        )
        self.tc_access = security.decode_access_token(access)
        station = security.generate_runner_token(self.parameters.STATION_TOKEN_ACCOUNT)
        self.tc_station = security.decode_access_token(station)

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    SecurityTest().run()
