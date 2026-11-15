"""
* @file     ${tests/pg/integrity_conflict_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests a real constraint violation is answered as a conflict without its constraint.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the checks against the live app.
"""

from tests.bud_test_base import BudAppTestCase


class IntegrityConflictPgBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_PG_CHECK}")

    def bud_a_constraint_violation_is_a_conflict(self):
        self.check("conflict")

    def bud_the_conflict_leaks_no_constraint(self):
        self.check("leak")
