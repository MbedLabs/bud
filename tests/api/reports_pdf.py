"""
* @file     ${tests/api/reports_pdf.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the PDF report endpoints and the renderer behind them.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the outcome, the renderer, its content, the file name and the endpoints.
"""

from tests.bud_test_base import BudAppTestCase


class ReportsPdfBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_PDF_CHECK}")

    def bud_the_outcome_totals_and_rates_its_counts(self):
        self.check("outcome")

    def bud_links_carry_their_address_and_label(self):
        self.check("links")

    def bud_the_renderer_produces_a_pdf_in_every_case(self):
        self.check("renderer")

    def bud_every_page_carries_the_footer(self):
        self.check("footer")

    def bud_the_run_report_shows_the_run_and_links_out(self):
        self.check("run content")

    def bud_the_summary_shows_breakdowns_and_percentages(self):
        self.check("summary content")

    def bud_the_run_report_renders_assertions_not_methods(self):
        self.check("assertions")

    def bud_the_file_name_cannot_break_the_header(self):
        self.check("file name")

    def bud_the_summary_endpoint_reports_the_stored_runs(self):
        self.check("summary endpoint")

    def bud_the_run_endpoint_reports_one_run(self):
        self.check("run endpoint")

    def bud_the_reports_need_a_signed_in_entity(self):
        self.check("signed out")
