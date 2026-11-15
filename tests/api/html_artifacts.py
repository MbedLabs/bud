"""
* @file     ${tests/api/html_artifacts.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests HTML reports uploaded as artifacts.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of the HTML report upload and download.
"""

from tests.bud_test_base import BudAppTestCase


class HtmlArtifactsBase(BudAppTestCase):

    def bud_html_report_is_accepted(self):
        self.print_variables({"status": self.tc_upload.status_code, "body": self.tc_upload.text})
        self.assertEqual(
            self.tc_upload.status_code,
            self.parameters.STATUS_CREATED,
            msg=self.parameters.MSG_HTML_ACCEPTED,
            abort_on_fail=True,
        )

    def bud_html_report_keeps_its_type(self):
        self.assertEqual(
            self.tc_upload.json()["content_type"],
            self.parameters.HTML_TYPE,
            msg=self.parameters.MSG_HTML_TYPE,
            abort_on_fail=False,
        )

    def bud_html_report_downloads(self):
        self.print_variables(
            {"status": self.tc_download.status_code, "headers": dict(self.tc_download.headers)}
        )
        self.assertEqual(
            self.tc_download.status_code,
            self.parameters.STATUS_OK,
            msg=self.parameters.MSG_HTML_DOWNLOADS,
            abort_on_fail=True,
        )

    def bud_download_is_an_attachment(self):
        self.assertRegex(
            self.tc_download.headers["content-disposition"],
            self.parameters.ATTACHMENT_PATTERN,
            msg=self.parameters.MSG_HTML_ATTACHMENT,
            abort_on_fail=False,
        )

    def bud_download_keeps_the_file_name(self):
        self.assertIn(
            self.parameters.HTML_REPORT_FILENAME,
            self.tc_download.headers["content-disposition"],
            msg=self.parameters.MSG_HTML_FILENAME,
            abort_on_fail=False,
        )

    def bud_download_is_sandboxed(self):
        self.assertEqual(
            self.tc_download.headers["content-security-policy"],
            self.parameters.SANDBOX_POLICY,
            msg=self.parameters.MSG_HTML_SANDBOX,
            abort_on_fail=False,
        )

    def bud_download_is_not_sniffed(self):
        self.assertEqual(
            self.tc_download.headers["x-content-type-options"],
            self.parameters.NO_SNIFF,
            msg=self.parameters.MSG_HTML_NOSNIFF,
            abort_on_fail=False,
        )
