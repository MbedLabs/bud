"""
* @file     ${tests/logic/dockerfile.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the ui-build stage of the Dockerfile.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of the ui-build stage.
"""

from tests.bud_test_base import BudAppTestCase


class DockerfileBase(BudAppTestCase):

    def bud_one_ui_build_stage(self):
        self.print_variables({"ui-build stages": self.tc_ui_build_from})
        self.assertEqual(
            len(self.tc_ui_build_from),
            self.parameters.DOCKERFILE_UI_BUILD_STAGES,
            msg=self.parameters.MSG_DOCKERFILE_ONE_UI_BUILD,
            abort_on_fail=True,
        )

    def bud_ui_build_runs_on_build_platform(self):
        self.assertIn(
            self.parameters.DOCKERFILE_BUILD_PLATFORM,
            self.tc_ui_build_from[0].split(),
            msg=self.parameters.MSG_DOCKERFILE_BUILD_PLATFORM,
            abort_on_fail=False,
        )
