"""
* @file     ${tests/api/run_stats_distinct.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the distinct test counters of the run statistics.
* @author   Amine El Omari
* @date     2026-11-07
* @version  1.0.0
* @note     Base class containing the bud methods of the distinct test and execution counters.
"""

from tests.bud_test_base import BudAppTestCase


class RunStatsDistinctBase(BudAppTestCase):

    def bud_statistics_answer(self):
        self.print_variables({"status": self.tc_suite_stats.status_code})
        self.assertEqual(
            self.tc_suite_stats.status_code,
            self.parameters.STATUS_OK,
            msg=self.parameters.MSG_STATS_ANSWER,
            abort_on_fail=True,
        )

    def bud_each_test_is_counted_once(self):
        stats = self.tc_suite_stats.json()
        self.print_variables(
            {"runs": self.parameters.RUN_COUNT, "distinct": stats["distinct_tests"]}
        )
        self.assertEqual(
            stats["distinct_tests"],
            self.parameters.DISTINCT_TESTS,
            msg=self.parameters.MSG_DISTINCT_ONCE,
            abort_on_fail=False,
        )

    def bud_latest_run_decides_each_test(self):
        stats = self.tc_suite_stats.json()
        found = (
            stats["distinct_passed_tests"],
            stats["distinct_failed_tests"],
            stats["distinct_skipped_tests"],
        )
        expected = (
            self.parameters.LATEST_PASSED,
            self.parameters.LATEST_FAILED,
            self.parameters.LATEST_SKIPPED,
        )
        self.print_variables({"latest outcomes": self.parameters.LATEST_OUTCOMES, "found": found})
        self.assertEqual(
            found, expected, msg=self.parameters.MSG_DISTINCT_LATEST, abort_on_fail=False
        )

    def bud_distinct_pass_rate_counts_passed_distinct_tests(self):
        rate = self.tc_suite_stats.json()["distinct_test_pass_rate"]
        self.print_variables({"distinct pass rate": rate})
        self.assertEqual(
            rate,
            self.parameters.DISTINCT_PASS_RATE,
            msg=self.parameters.MSG_DISTINCT_RATE,
            abort_on_fail=False,
        )

    def bud_executions_count_every_run(self):
        total = self.tc_suite_stats.json()["total_tests"]
        self.print_variables({"test executions": total})
        self.assertEqual(
            total,
            self.parameters.TEST_EXECUTIONS,
            msg=self.parameters.MSG_EXECUTIONS,
            abort_on_fail=False,
        )

    def bud_other_suite_counts_without_the_filter(self):
        distinct = self.tc_all_stats.json()["distinct_tests"]
        self.print_variables({"distinct without filter": distinct})
        self.assertEqual(
            distinct,
            self.parameters.DISTINCT_TESTS + len(self.parameters.OTHER_SUITE_CLASSES),
            msg=self.parameters.MSG_SUITE_FILTER,
            abort_on_fail=False,
        )
