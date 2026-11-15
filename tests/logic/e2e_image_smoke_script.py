"""
* @file     ${tests/logic/e2e_image_smoke_script.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the published image smoke script.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of the script's docker and curl calls.
"""

from tests.bud_test_base import BudAppTestCase


class E2eImageSmokeScriptBase(BudAppTestCase):

    def bud_admin_name_is_one_docker_argument(self):
        self.print_variables({"app run": self.tc_app_run})
        self.assertIn(
            self.parameters.SMOKE_ADMIN_NAME,
            self.tc_app_run,
            msg=self.parameters.MSG_SMOKE_ADMIN_NAME,
        )

    def bud_smoke_script_passes(self):
        p = self.parameters
        result = self.tc_smoke
        self.print_variables({"exit code": result.returncode, "stderr": result.stderr})
        self.assertEqual(result.returncode, p.SMOKE_EXIT_OK, msg=p.MSG_SMOKE_EXIT)
        self.assertIn(p.SMOKE_VERIFIED, result.stdout, msg=p.MSG_SMOKE_VERIFIED)
        self.assertIn(p.SMOKE_PASS, result.stdout, msg=p.MSG_SMOKE_PASS)
