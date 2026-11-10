"""
* @file     ${tests/api/run_report_assertions.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the assertion rows of the run report.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of the report's assertion rows and outcome.
"""

from tests.bud_test_base import BudAppTestCase


class RunReportAssertionsBase(BudAppTestCase):

    def bud_rows_leave_out_skipped_and_information_entries(self):
        rows = [(detail.assertion_type, detail.passed) for detail in self.tc_details]
        self.print_variables({"entries": self.parameters.REPORT_RESULT_ENTRIES, "rows": rows})
        self.assertEqual(
            rows,
            self.parameters.REPORT_ASSERTION_ROWS,
            msg=self.parameters.MSG_REPORT_ROWS,
            abort_on_fail=False,
        )

    def bud_outcome_counts_the_rows(self):
        found = (self.tc_outcome.passed, self.tc_outcome.failed, self.tc_outcome.skipped)
        self.print_variables({"passed, failed, skipped": found})
        self.assertEqual(
            found,
            self.parameters.REPORT_ASSERTION_OUTCOME,
            msg=self.parameters.MSG_REPORT_OUTCOME,
            abort_on_fail=False,
        )
