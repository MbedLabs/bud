"""
* @file     ${tests/pg/product_status_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests that the product status migrates both ways on PostgreSQL.
* @author   Amine El Omari
* @date     2026-11-13
* @version  1.0.0
* @note     Base class containing the bud methods of the checks against a scratch database.
"""

from tests.bud_test_base import BudAppTestCase


class ProductStatusPgBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_PG_CHECK}")

    def bud_the_product_status_migration_is_in_the_one_lineage(self):
        self.check("head")

    def bud_the_product_status_migrates_both_ways_keeping_every_product(self):
        self.check("migration")
