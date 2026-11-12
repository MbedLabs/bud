"""
* @file     ${tests/logic/config_settings.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests how Bud's settings read the environment.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud method of the settings built from each environment.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class ConfigSettingsBase(BudAppTestCase):

    @parameterized(params.CONFIG_CASES)
    def bud_the_settings_follow_the_environment(self, case):
        self.print_variables({"case": case, "environment": self.parameters.CONFIG_CASES[case][0]})
        for name, (found, expected) in self.tc_checks[case].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_CONFIG_CHECK}")
