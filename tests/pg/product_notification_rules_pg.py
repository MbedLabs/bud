"""
* @file     ${tests/pg/product_notification_rules_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the notification rules migration on PostgreSQL.
* @author   Amine El Omari
* @date     2026-11-14
* @version  1.0.0
* @note     Base class containing the bud methods of the notification rules migration.
"""

from tests.bud_test_base import BudAppTestCase


class ProductNotificationRulesPgBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_PNR_PG}")

    def bud_the_notification_rules_migration_is_in_the_one_lineage(self):
        self.check("head")

    def bud_every_existing_channel_keeps_every_product(self):
        self.check("migration")
