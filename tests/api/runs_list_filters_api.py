"""
* @file     ${tests/api/runs_list_filters_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests searching and locating test runs across every page of them.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the search, the location and the latest run per suite.
"""

from tests.bud_test_base import BudAppTestCase


class RunsListFiltersApiBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(
                found, expected, msg=f"{name}: {self.parameters.MSG_RUNS_FILTER_CHECK}"
            )

    def bud_search_reaches_every_page(self):
        self.check("search")

    def bud_location_covers_every_station_there(self):
        self.check("location")

    def bud_location_reaches_every_page(self):
        self.check("location pages")

    def bud_latest_per_suite_keeps_one_run_per_suite(self):
        self.check("latest")

    def bud_latest_per_suite_keeps_the_newest_run(self):
        self.check("newest")

    def bud_latest_per_suite_counts_the_deduplicated_runs(self):
        self.check("paging")

    def bud_latest_per_suite_narrows_before_deduplicating(self):
        self.check("narrowed")
