"""
* @file     ${tests/pg/BUD_application_policies_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Application policies are keyed by person and policy; repeats and simultaneous changes leave one row and deletions drop only their own rows.
* @author   Amine El Omari
* @date     2026-11-18
* @version  1.0.0
* @note     This module reads the application policies table directly next to the live app.
"""

from tests.pg.application_policies_pg import ApplicationPoliciesPgBase


class ApplicationPoliciesPgTest(ApplicationPoliciesPgBase):

    def setUpClass(self):
        super().setUpClass()
        self.client = self.bud.bud_start_live_app()
        self.login, self.headers = self.bud.bud_live_bearer()

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ApplicationPoliciesPgTest().run()
