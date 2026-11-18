"""
* @file     ${tests/api/BUD_application_policies_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    An administrator sets a user's application policies; each policy adds and takes away only its own app-level access.
* @author   Amine El Omari
* @date     2026-11-18
* @version  1.0.0
* @note     This module tests an administrator, a developer and a viewer; each step starts its own app.
"""

from tests.api.application_policies_api import ApplicationPoliciesApiBase


class ApplicationPoliciesApiTest(ApplicationPoliciesApiBase):

    def setUpClass(self):
        super().setUpClass()

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ApplicationPoliciesApiTest().run()
