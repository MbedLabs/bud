"""
* @file     ${tests/sec/BUD_application_policies_sec.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Holding several application policies never widens access: management stays guarded and only an Admin sets application policies.
* @author   Amine El Omari
* @date     2026-11-18
* @version  1.0.0
* @note     This module signs every person in with a real token; each step starts its own app.
"""

from tests.sec.application_policies_sec import ApplicationPoliciesSecBase


class ApplicationPoliciesSecTest(ApplicationPoliciesSecBase):

    def setUpClass(self):
        super().setUpClass()

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ApplicationPoliciesSecTest().run()
