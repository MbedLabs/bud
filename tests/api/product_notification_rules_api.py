"""
* @file     ${tests/api/product_notification_rules_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the notification rules per product and the all-products switch of a channel.
* @author   Amine El Omari
* @date     2026-11-14
* @version  1.0.0
* @note     Base class containing the bud methods of the notification rules per product.
"""

from tests.bud_test_base import BudAppTestCase


class ProductNotificationRulesApiBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=name)

    def bud_a_channel_takes_every_product_unless_switched_off(self):
        self.check("all products")

    def bud_an_administrator_adds_and_lists_a_products_rules(self):
        self.check("administrator")

    def bud_the_channels_offered_carry_no_url_or_secret(self):
        self.check("options")

    def bud_products_manage_on_the_product_edits_its_rules(self):
        self.check("manager")

    def bud_without_products_manage_on_the_product_no_rule_is_shown(self):
        self.check("refused")

    def bud_every_rule_change_is_audited_with_the_product(self):
        self.check("audit")

    def bud_deleting_a_channel_or_a_product_removes_its_rules(self):
        self.check("removal")
