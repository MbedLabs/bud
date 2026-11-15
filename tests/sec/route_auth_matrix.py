"""
* @file     ${tests/sec/route_auth_matrix.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests that no Bud API route is published by accident.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of the route authentication guard.
"""

from tests.bud_test_base import BudAppTestCase


class RouteAuthMatrixBase(BudAppTestCase):

    def bud_every_private_route_has_an_authentication_boundary(self):
        self.print_variables({"routes checked": self.tc_route_count})
        self.assertEqual(
            self.tc_unprotected, [], msg=self.parameters.MSG_ROUTES_GUARDED, abort_on_fail=False
        )

    def bud_guard_finds_no_authentication_in_an_empty_tree(self):
        self.print_variables({"dependencies of an empty tree": self.tc_empty_tree})
        self.assertTrue(
            self.tc_empty_tree.isdisjoint(self.parameters.AUTH_DEPENDENCIES),
            msg=self.parameters.MSG_GUARD_EMPTY_TREE,
            actual=self.tc_empty_tree,
            abort_on_fail=False,
        )
