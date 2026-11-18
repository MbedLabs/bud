"""
* @file     ${tests/logic/BUD_application_policies.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    A person holds any number of application policies; app-level access is the base allowance united with them all.
* @author   Amine El Omari
* @date     2026-11-18
* @version  1.0.0
* @note     This module tests the access services; each step opens its own app database.
"""

from tests.logic.application_policies import ApplicationPoliciesBase


class ApplicationPoliciesTest(ApplicationPoliciesBase):

    def setUpClass(self):
        super().setUpClass()

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ApplicationPoliciesTest().run()
