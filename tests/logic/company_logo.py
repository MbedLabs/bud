"""
* @file     ${tests/logic/company_logo.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the company logo on report letterheads.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of the logo storage and the branded report.
"""

import fitz

from tests.bud_test_base import BudAppTestCase


class CompanyLogoBase(BudAppTestCase):

    def bud_logo_is_stored(self):
        self.print_variables({"stored": self.tc_stored})
        self.assertEqual(
            self.tc_stored["content_type"],
            self.parameters.LOGO_TYPE,
            msg=self.parameters.MSG_LOGO_STORED,
            abort_on_fail=False,
        )

    def bud_logo_is_served(self):
        self.assertEqual(
            getattr(self.tc_served, "body", self.tc_served),
            self.parameters.LOGO_PNG,
            msg=self.parameters.MSG_LOGO_SERVED,
            abort_on_fail=False,
        )

    def bud_reports_load_the_logo(self):
        self.assertEqual(
            self.tc_report_logo,
            self.parameters.LOGO_PNG,
            msg=self.parameters.MSG_LOGO_FOR_REPORTS,
            abort_on_fail=False,
        )

    def bud_deleted_logo_is_not_found(self):
        self.print_variables({"after delete": self.tc_served_after_delete})
        self.assertEqual(
            type(self.tc_served_after_delete).__name__,
            self.parameters.HTTP_EXCEPTION,
            msg=self.parameters.MSG_LOGO_DELETED,
            abort_on_fail=True,
        )
        self.assertEqual(
            self.tc_served_after_delete.status_code,
            self.parameters.STATUS_NOT_FOUND,
            msg=self.parameters.MSG_LOGO_DELETED_STATUS,
            abort_on_fail=False,
        )

    def bud_reports_load_no_deleted_logo(self):
        self.assertEqual(
            type(self.tc_report_logo_after_delete).__name__,
            self.parameters.NONE_TYPE,
            msg=self.parameters.MSG_LOGO_DELETED_REPORTS,
            abort_on_fail=False,
        )

    def bud_logo_that_is_not_an_image_is_refused(self):
        self.print_variables({"text upload": self.tc_text_logo})
        self.assertEqual(
            type(self.tc_text_logo).__name__,
            self.parameters.HTTP_EXCEPTION,
            msg=self.parameters.MSG_LOGO_NOT_IMAGE,
            abort_on_fail=True,
        )
        self.assertEqual(
            self.tc_text_logo.status_code,
            self.parameters.STATUS_UNSUPPORTED_MEDIA,
            msg=self.parameters.MSG_LOGO_NOT_IMAGE_STATUS,
            abort_on_fail=False,
        )

    def bud_report_without_logo_is_a_pdf(self):
        self.assertEqual(
            self.tc_report[: len(self.parameters.PDF_MAGIC)],
            self.parameters.PDF_MAGIC,
            msg=self.parameters.MSG_REPORT_PDF,
            abort_on_fail=False,
        )

    def bud_report_with_logo_is_a_pdf(self):
        self.assertEqual(
            self.tc_branded_report[: len(self.parameters.PDF_MAGIC)],
            self.parameters.PDF_MAGIC,
            msg=self.parameters.MSG_REPORT_LOGO_PDF,
            abort_on_fail=False,
        )

    def bud_report_with_logo_has_one_image_more(self):
        without = len(
            fitz.open(stream=self.tc_report, filetype=self.parameters.PDF_FORMAT)[0].get_images()
        )
        branded = len(
            fitz.open(stream=self.tc_branded_report, filetype=self.parameters.PDF_FORMAT)[
                0
            ].get_images()
        )
        self.print_variables({"images without logo": without, "images with logo": branded})
        self.assertEqual(
            branded,
            without + self.parameters.REPORT_LOGO_IMAGES,
            msg=self.parameters.MSG_REPORT_LOGO_IMAGE,
            abort_on_fail=False,
        )
