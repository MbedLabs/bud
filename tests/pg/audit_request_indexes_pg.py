"""
* @file     ${tests/pg/audit_request_indexes_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests that the audit request indexes migrate both ways and concurrent refusals flag once on PostgreSQL.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the checks against the live app and its database.
"""

from tests.bud_test_base import BudAppTestCase


class AuditRequestIndexesPgBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_PG_CHECK}")

    def bud_the_audit_index_migration_is_in_the_one_lineage(self):
        self.check("head")

    def bud_the_audit_indexes_migrate_both_ways_keeping_every_event(self):
        self.check("migration")

    def bud_concurrent_refusals_from_one_address_leave_one_flag(self):
        self.check("flag")
