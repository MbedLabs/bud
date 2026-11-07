"""
* @file     ${tests/bud_test_base.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Base of Bud's test cases: the interface, the parameters and the printed seed.
* @author   Amine El Omari
* @date     2026-11-07
* @version  1.0.0
* @note     Every Bud test case derives from BudAppTestCase.
"""

from budtestlibrary import BudTestCase

import tests.parameters as params
from tests.bud_interface import BudInterface


class BudAppTestCase(BudTestCase):

    def setUpClass(self):
        self.bud = BudInterface()
        self.bud.setUp()
        self.parameters = params
        self.log_info(f"BUDTEST_SEED={self.parameters.SEED}")

    def tearDownClass(self):
        self.bud.tearDown()
