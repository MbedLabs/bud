"""
* @file     ${tests/api/run_stats_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the run statistics and their filter options.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of the statistics over every matching run.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class RunStatsApiBase(BudAppTestCase):

    @parameterized(params.STATS_CASES)
    def bud_statistics_count_every_matching_run(self, case):
        response = self.tc_stats[case]
        self.print_variables({"case": case, "status": response.status_code, "body": response.text})
        self.assertEqual(
            response.status_code,
            self.parameters.STATUS_OK,
            msg=self.parameters.MSG_STATS_ANSWERS_FILTERED,
            abort_on_fail=True,
        )
        for field, expected in self.parameters.STATS_CASES[case][1].items():
            self.assertEqual(
                response.json().get(field),
                expected,
                msg=f"{field}: {self.parameters.MSG_STATS_VALUE}",
            )

    def bud_filter_options_list_suites_and_stations(self):
        self.print_variables({"filter options": self.tc_options.text})
        for field, expected in self.parameters.STATS_FILTER_OPTIONS.items():
            self.assertEqual(
                self.tc_options.json().get(field), expected, msg=self.parameters.MSG_STATS_OPTIONS
            )

    @parameterized(params.STATS_LITERAL_PATHS)
    def bud_path_is_not_shadowed_by_the_run_id_route(self, path):
        self.assertEqual(
            self.tc_literal[path],
            self.parameters.STATUS_OK,
            msg=self.parameters.MSG_STATS_LITERAL_PATH,
        )
