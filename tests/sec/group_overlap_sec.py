"""
* @file     ${tests/sec/group_overlap_sec.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests that holding several groups never widens access.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of guarded group management and giving.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class GroupOverlapSecBase(BudAppTestCase):

    def bud_everyone_signs_in(self):
        self.assertEqual(
            self.tc_logins,
            [self.parameters.STATUS_OK] * len(self.tc_logins),
            msg=self.parameters.MSG_SEC_SIGNED_IN,
        )

    def bud_groups_without_access_management_open_nothing(self):
        p, found = self.parameters, self.tc_closed
        self.print_variables(found)
        self.assertEqual(found["groups"], p.STATUS_FORBIDDEN, msg=p.MSG_SEC_GROUPS_CLOSED)
        self.assertEqual(found["users"], p.STATUS_FORBIDDEN, msg=p.MSG_SEC_USERS_CLOSED)
        self.assertEqual(found["give"], p.STATUS_FORBIDDEN, msg=p.MSG_SEC_GIVE_CLOSED)
        self.assertEqual(found["rows"], 0, msg=p.MSG_SEC_NO_ROW)

    def bud_every_policy_still_cannot_give_administrators(self):
        p, found = self.parameters, self.tc_admin_group
        self.print_variables(found)
        self.assertEqual(
            found["given"], (p.STATUS_FORBIDDEN, p.SEC_ADMIN_ONLY), msg=p.MSG_SEC_ADMIN_GIVE
        )
        self.assertEqual(
            found["removed"], (p.STATUS_FORBIDDEN, p.SEC_ADMIN_ONLY), msg=p.MSG_SEC_ADMIN_REMOVE
        )
        self.assertEqual(found["recipient rows"], 0, msg=p.MSG_SEC_NO_ROW)
        self.assertEqual(found["holder rows"], 1, msg=p.MSG_SEC_HOLDER_KEPT)

    @parameterized(params.SEC_STATION_GROUPS)
    def bud_viewer_is_refused_management(self, name):
        self.assertEqual(
            self.tc_viewer[name],
            self.parameters.STATUS_UNPROCESSABLE,
            msg=self.parameters.MSG_SEC_VIEWER_REFUSED,
        )

    def bud_refused_viewer_keeps_its_memberships(self):
        self.assertEqual(
            self.tc_viewer["rows"], self.tc_viewer["held"], msg=self.parameters.MSG_SEC_VIEWER_ROWS
        )

    def bud_spread_access_does_not_cover_a_third_policy(self):
        p, found = self.parameters, self.tc_spread
        self.print_variables(found)
        self.assertEqual(found["wider"], p.STATUS_FORBIDDEN, msg=p.MSG_SEC_WIDER_REFUSED)
        self.assertEqual(found["covered"], p.STATUS_CREATED, msg=p.MSG_SEC_COVERED_GIVEN)
        self.assertEqual(found["rows"], 1, msg=p.MSG_SEC_ONE_ROW)
