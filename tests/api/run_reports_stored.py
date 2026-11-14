"""
* @file     ${tests/api/run_reports_stored.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the reports a finished run stores as artifacts.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of stored run and suite reports.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class RunReportsStoredBase(BudAppTestCase):

    def bud_finished_run_stores_both_reports(self):
        self.assertEqual(
            self.tc_names, self.tc_expected_names, msg=self.parameters.MSG_STORED_REPORTS
        )

    def bud_stored_reports_are_pdfs(self):
        p = self.parameters
        self.print_variables({"reports": self.tc_pdfs})
        self.assertEqual(len(self.tc_pdfs), 2, msg=p.MSG_STORED_REPORTS)
        for magic, size, length, content_type in self.tc_pdfs:
            self.assertEqual(magic, p.PDF_MAGIC, msg=p.MSG_STORED_PDF)
            self.assertEqual(size, length, msg=p.MSG_STORED_PDF)
            self.assertEqual(content_type, p.STORED_PDF_TYPE, msg=p.MSG_STORED_PDF)

    def bud_storing_twice_does_not_duplicate(self):
        self.assertEqual(len(self.tc_twice), 2, msg=self.parameters.MSG_STORED_ONCE)

    @parameterized(params.STORED_REPORT_TEXTS)
    def bud_suite_report_details_its_run(self, text):
        self.assertIn(text, self.tc_suite_text, msg=self.parameters.MSG_STORED_SUITE_DETAIL)

    def bud_suite_report_names_its_run_only(self):
        p = self.parameters
        self.assertIn(
            p.STORED_RUN_ID_TEXT.format(self.tc_current_id),
            self.tc_suite_text,
            msg=p.MSG_STORED_SUITE_DETAIL,
        )
        self.assertNotIn(p.STORED_HISTORICAL_TEXT, self.tc_suite_text, msg=p.MSG_STORED_SUITE_SCOPE)

    def bud_broken_renderer_stores_nothing(self):
        self.print_variables({"stored": self.tc_broken})
        self.assertEqual(self.tc_broken, ([], []), msg=self.parameters.MSG_STORED_BROKEN)

    def bud_missing_run_stores_nothing(self):
        self.assertEqual(self.tc_missing, [], msg=self.parameters.MSG_STORED_MISSING)

    def bud_completing_through_the_api_stores_the_reports(self):
        p, found = self.parameters, self.tc_api
        self.print_variables(found)
        self.assertEqual(found["patched"], p.STATUS_OK, msg=p.MSG_STORED_PATCHED)
        self.assertEqual(
            found["listed"], (p.STATUS_OK, found["expected"]), msg=p.MSG_STORED_REPORTS
        )
        self.assertEqual(found["running"], [], msg=p.MSG_STORED_RUNNING)
        self.assertEqual(found["acknowledged"], p.STATUS_OK, msg=p.MSG_STORED_CLAIM)
        self.assertEqual(
            found["claimed names"], found["claimed expected"], msg=p.MSG_STORED_REPORTS
        )
