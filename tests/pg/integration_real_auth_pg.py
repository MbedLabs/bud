"""
* @file     ${tests/pg/integration_real_auth_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the end-to-end flow with real authentication on PostgreSQL.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the checks against the live app.
"""

from tests.bud_test_base import BudAppTestCase


class IntegrationRealAuthPgBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_PG_CHECK}")

    def bud_the_ready_probe_reaches_the_database(self):
        self.check("ready")

    def bud_a_wrong_password_is_refused(self):
        self.check("wrong password")

    def bud_a_signed_out_write_is_refused(self):
        self.check("signed out")

    def bud_a_signed_in_write_is_stored_and_read(self):
        self.check("write")

    def bud_a_case_with_only_skipped_results_counts_as_skipped(self):
        self.check("skipped")

    def bud_a_person_cannot_report_station_execution(self):
        self.check("producer")
