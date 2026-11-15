"""
* @file     ${tests/logic/BUD_company_logo.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    An administrator stores, serves and deletes the company logo; reports show it.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module tests the logo endpoints on one session and a report rendered with and without it.
"""

import io

from starlette.datastructures import Headers, UploadFile

from app.api import company_logo
from app.services import report_pdf
from tests.logic.company_logo import CompanyLogoBase


class CompanyLogoTest(CompanyLogoBase):

    def setUpClass(self):
        super().setUpClass()
        db = self.bud.bud_open_session()
        run, attempt = self.bud.bud_await, self.bud.bud_attempt
        self.tc_stored = run(
            company_logo.set_company_logo(
                file=self.upload(self.parameters.LOGO_PNG, self.parameters.LOGO_TYPE),
                db=db,
                _admin=None,
            )
        )
        self.tc_served = attempt(lambda: run(company_logo.get_company_logo(db=db, _entity=None)))
        self.tc_report_logo = run(company_logo.load_report_logo(db))
        run(company_logo.delete_company_logo(db=db, _admin=None))
        self.tc_served_after_delete = attempt(
            lambda: run(company_logo.get_company_logo(db=db, _entity=None))
        )
        self.tc_report_logo_after_delete = run(company_logo.load_report_logo(db))
        self.tc_text_logo = attempt(
            lambda: run(
                company_logo.set_company_logo(
                    file=self.upload(
                        self.parameters.LOGO_NOT_AN_IMAGE, self.parameters.LOGO_TEXT_TYPE
                    ),
                    db=db,
                    _admin=None,
                )
            )
        )
        self.tc_report = report_pdf.render_report(self.report_request())
        self.tc_branded_report = report_pdf.render_report(
            self.report_request(), self.parameters.LOGO_PNG
        )

    def upload(self, data, content_type):
        """An uploaded logo file with the given bytes and content type."""
        return UploadFile(
            io.BytesIO(data),
            filename=self.parameters.LOGO_NAME,
            headers=Headers({"content-type": content_type}),
        )

    def report_request(self):
        """A one-page report with one breakdown."""
        return report_pdf.ReportRequest(
            title=self.parameters.REPORT_TITLE,
            subtitle=self.parameters.REPORT_SUBTITLE,
            filters=self.parameters.REPORT_FILTERS,
            overall=report_pdf.Outcome(*self.parameters.REPORT_OVERALL),
            breakdowns=[
                report_pdf.Breakdown(
                    self.parameters.REPORT_BREAKDOWN_TITLE,
                    self.parameters.REPORT_BREAKDOWN_LABEL,
                    [
                        (
                            self.parameters.REPORT_BREAKDOWN_ROW,
                            report_pdf.Outcome(*self.parameters.REPORT_OVERALL),
                        )
                    ],
                )
            ],
            app_version=self.parameters.REPORT_APP_VERSION,
        )

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    CompanyLogoTest().run()
