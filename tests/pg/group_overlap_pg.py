"""
* @file     ${tests/pg/group_overlap_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests holding any number of groups on PostgreSQL: the schema, duplicates and cascades.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the checks against the live app and its database.
"""

from tests.bud_test_base import BudAppTestCase


class GroupOverlapPgBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_PG_CHECK}")

    def bud_the_membership_key_is_the_pair(self):
        self.check("schema")

    def bud_two_groups_make_two_rows_and_a_repeat_is_refused(self):
        self.check("duplicates")

    def bud_simultaneous_identical_assignments_leave_one_row(self):
        self.check("race")

    def bud_deleting_a_group_or_a_person_removes_only_their_rows(self):
        self.check("cascades")
