"""
* @file     ${tests/api/BUD_run_report_assertions.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The run report's assertion rows leave out skipped and information entries.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module tests one result with a passed, a skipped, an information and a failed entry.
"""

from app.models import TestResult
from app.services import run_reports
from tests.api.run_report_assertions import RunReportAssertionsBase


class RunReportAssertionsTest(RunReportAssertionsBase):

    def setUpClass(self):
        super().setUpClass()
        result = TestResult(
            test_class=self.parameters.REPORT_RESULT_CLASS,
            test_method=self.parameters.REPORT_RESULT_METHOD,
            passed=True,
            assertions=self.parameters.REPORT_RESULT_ENTRIES,
        )
        self.tc_details = run_reports._assertion_details([result])
        self.tc_outcome = run_reports._outcome_for_assertions(self.tc_details)

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    RunReportAssertionsTest().run()
