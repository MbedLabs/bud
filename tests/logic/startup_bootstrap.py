"""
* @file     ${tests/logic/startup_bootstrap.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests what the app runs when it starts.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of the data repair and admin seed settings.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class StartupBootstrapBase(BudAppTestCase):

    @parameterized(params.STARTUP_CASES)
    def bud_start_runs_what_the_settings_ask_for(self, case):
        expected = self.parameters.STARTUP_CASES[case][2]
        self.print_variables({"case": case, "steps run": self.tc_steps[case]})
        self.assertEqual(self.tc_steps[case], expected, msg=self.parameters.MSG_STARTUP_STEPS)
