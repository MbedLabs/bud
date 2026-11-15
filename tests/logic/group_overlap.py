"""
* @file     ${tests/logic/group_overlap.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests access over overlapping groups.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of permission evaluation and giving rules.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class GroupOverlapBase(BudAppTestCase):

    def bud_two_groups_give_their_union(self):
        p, found = self.parameters, self.tc_union
        self.print_variables({"both": sorted(found["both"])})
        self.assertEqual(found["both"], found["base and groups"], msg=p.MSG_GROUP_UNION)
        self.assertEqual(found["both"], found["each holder"], msg=p.MSG_GROUP_UNION_OF_EACH)
        self.assertEqual(p.GROUP_MANAGED <= found["both"], True, msg=p.MSG_GROUP_MANAGED)
        self.assertEqual(found["managed in base"], set(), msg=p.MSG_GROUP_NOT_BASE)

    def bud_a_shared_permission_stays_until_both_groups_go(self):
        p, found = self.parameters, self.tc_release
        self.print_variables(
            {
                key: sorted(value) if isinstance(value, frozenset) else value
                for key, value in found.items()
            }
        )
        self.assertEqual(p.GROUP_MANAGED <= found["one left"], True, msg=p.MSG_GROUP_KEPT)
        self.assertEqual(found["none left"], found["developer base"], msg=p.MSG_GROUP_DROPPED)
        self.assertIn(p.GROUP_AUDIT_VIEW, found["audit both"], msg=p.MSG_GROUP_KEPT)
        self.assertIn(p.GROUP_AUDIT_VIEW, found["audit one"], msg=p.MSG_GROUP_KEPT)
        self.assertEqual(found["audit none"], found["viewer base"], msg=p.MSG_GROUP_DROPPED)

    @parameterized(params.GROUP_ADMIN_MEMBERSHIPS)
    def bud_admin_holds_every_permission(self, memberships):
        p = self.parameters
        count, permissions = self.tc_admin[memberships]
        self.assertEqual(count, memberships, msg=p.MSG_GROUP_ADMIN_COUNT)
        self.assertEqual(permissions, self.tc_all_permissions, msg=p.MSG_GROUP_ADMIN_ALL)

    def bud_user_groups_lists_one_users_groups_by_name(self):
        p, found = self.parameters, self.tc_listed
        self.print_variables(found)
        self.assertEqual(found["owner"], sorted(p.GROUP_OWNER_GROUPS), msg=p.MSG_GROUP_LISTED)
        self.assertEqual(found["other"], [p.GROUP_STATIONS], msg=p.MSG_GROUP_LISTED)
        self.assertEqual(found["bystander"], [], msg=p.MSG_GROUP_LISTED)

    def bud_station_management_is_checked_per_given_group(self):
        p, found = self.parameters, self.tc_station_check
        self.print_variables(found)
        self.assertEqual(
            type(found["viewer"]).__name__, p.HTTP_EXCEPTION, msg=p.MSG_GROUP_VIEWER_REFUSED
        )
        self.assertEqual(
            getattr(found["viewer"], "status_code", None),
            p.STATUS_UNPROCESSABLE,
            msg=p.MSG_GROUP_VIEWER_CODE,
        )
        self.assertEqual(
            type(found["developer"]).__name__, p.NONE_TYPE, msg=p.MSG_GROUP_DEVELOPER_ACCEPTED
        )

    def bud_giver_is_judged_on_all_their_groups(self):
        p, found = self.parameters, self.tc_giver
        self.print_variables(found)
        self.assertEqual(
            type(found["covered"]).__name__, p.NONE_TYPE, msg=p.MSG_GROUP_GIVER_COVERED
        )
        self.assertEqual(
            type(found["wider"]).__name__, p.HTTP_EXCEPTION, msg=p.MSG_GROUP_GIVER_REFUSED
        )
        self.assertEqual(
            getattr(found["wider"], "status_code", None),
            p.STATUS_FORBIDDEN,
            msg=p.MSG_GROUP_GIVER_CODE,
        )

    def bud_giving_a_group_twice_leaves_one_membership(self):
        p, found = self.parameters, self.tc_twice
        self.print_variables(found)
        self.assertEqual(found["first"], True, msg=p.MSG_GROUP_FIRST_GIVE)
        self.assertEqual(found["second"], False, msg=p.MSG_GROUP_SECOND_GIVE)
        self.assertEqual(found["memberships"], 1, msg=p.MSG_GROUP_ONE_MEMBERSHIP)
