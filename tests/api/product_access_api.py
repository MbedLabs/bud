"""
* @file     ${tests/api/product_access_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests access per product: who reads which runs and who sets a product's members.
* @author   Amine El Omari
* @date     2026-11-13
* @version  1.0.0
* @note     Base class containing the bud methods of access per product.
"""

from tests.bud_test_base import BudAppTestCase


class ProductAccessApiBase(BudAppTestCase):

    def bud_a_user_lists_only_the_runs_of_his_products(self):
        p = self.parameters
        self.print_variables({"listed": self.tc_listed})
        self.assertEqual(self.tc_listed, [p.PA_RUN_A], msg=p.MSG_PA_LIST)

    def bud_statistics_count_only_his_products(self):
        self.assertEqual(self.tc_stats_runs, 1, msg=self.parameters.MSG_PA_STATS)

    def bud_a_run_of_his_product_is_read(self):
        p = self.parameters
        self.assertEqual(self.tc_own_run, p.STATUS_OK, msg=p.MSG_PA_OWN_RUN)

    def bud_a_run_of_another_product_is_not_found(self):
        p = self.parameters
        self.assertEqual(self.tc_other_run, p.STATUS_NOT_FOUND, msg=p.MSG_PA_OTHER_RUN)

    def bud_a_run_without_a_product_is_read_by_administrators_only(self):
        p = self.parameters
        self.assertEqual(self.tc_no_product_run, p.STATUS_NOT_FOUND, msg=p.MSG_PA_NO_PRODUCT)
        self.assertEqual(self.tc_admin_no_product_run, p.STATUS_OK, msg=p.MSG_PA_ADMIN_NO_PRODUCT)

    def bud_his_permissions_list_what_he_holds_on_some_product(self):
        p = self.parameters
        self.print_variables({"permissions": self.tc_me_permissions})
        self.assertIn("evidence.view", self.tc_me_permissions, msg=p.MSG_PA_ME)

    def bud_an_administrator_sets_and_clears_a_products_members(self):
        p = self.parameters
        self.print_variables({"set": self.tc_set_status, "members": self.tc_set_members})
        self.assertEqual(self.tc_set_status, p.STATUS_OK, msg=p.MSG_PA_SET)
        self.assertEqual(self.tc_set_members, [p.PA_NEWCOMER["email"]], msg=p.MSG_PA_SET_MEMBERS)
        self.assertEqual(self.tc_added_events, 1, msg=p.MSG_PA_ADDED)
        self.assertEqual(self.tc_cleared_members, [], msg=p.MSG_PA_CLEARED)
        self.assertEqual(self.tc_removed_events, 1, msg=p.MSG_PA_REMOVED)

    def bud_a_user_without_access_management_cannot_set_members(self):
        p = self.parameters
        self.assertEqual(self.tc_viewer_set, p.STATUS_FORBIDDEN, msg=p.MSG_PA_NOT_MANAGER)

    def bud_products_manage_counts_on_its_product_only(self):
        p = self.parameters
        self.assertEqual(self.tc_manage_own, p.STATUS_OK, msg=p.MSG_PA_MANAGE_OWN)
        self.assertEqual(self.tc_manage_other, p.STATUS_FORBIDDEN, msg=p.MSG_PA_MANAGE_OTHER)
        self.assertEqual(self.tc_manage_create, p.STATUS_FORBIDDEN, msg=p.MSG_PA_CREATE)
