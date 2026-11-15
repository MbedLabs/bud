"""
* @file     ${tests/api/group_overlap_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests holding several groups over HTTP.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of giving, removing, deleting and requesting groups.
"""

from tests.bud_test_base import BudAppTestCase


class GroupOverlapApiBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_OVERLAP_CHECK}")

    def bud_two_groups_give_their_union(self):
        self.check("union")

    def bud_removing_one_group_keeps_what_the_other_gives(self):
        self.check("removal")

    def bud_giving_a_held_group_again_changes_nothing(self):
        self.check("duplicate")

    def bud_permission_follows_each_group_that_gives_it(self):
        self.check("routes")

    def bud_deleting_a_group_keeps_the_other_memberships(self):
        self.check("deletion")

    def bud_granting_a_request_adds_a_group_beside_the_others(self):
        self.check("request")
