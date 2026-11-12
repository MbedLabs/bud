"""
* @file     ${tests/api/bloom_sync.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests sending a run's results to Bloom.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the result rows and the sync events.
"""

from tests.bud_test_base import BudAppTestCase


class BloomSyncBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.print_variables({"check": name, "found": found, "expected": expected})
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_BLOOM_SYNC_CHECK}")

    def bud_methods_reduce_to_one_row_per_test_case(self):
        self.check("coalesce")

    def bud_sync_without_settings_is_skipped(self):
        self.check("missing settings")

    def bud_refused_sync_records_a_failed_event(self):
        self.check("refused")

    def bud_rows_count_the_results_left_out(self):
        self.check("tally")

    def bud_sync_events_name_the_results_left_out(self):
        self.check("left out")
