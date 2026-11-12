"""
* @file     ${tests/api/BUD_reports_pdf.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Reports render as complete PDFs with their footer, run identity, breakdowns and assertions; endpoints serve them.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests the renderer directly and the endpoints on a fresh app database holding two runs.
"""

from datetime import datetime, timedelta

import pymupdf

from app.api import reports
from app.models import Runner, TestResult, TestRun
from app.services import report_pdf
from app.services.report_pdf import AssertionDetail, Breakdown, Outcome, ReportRequest, RunDetail
from tests.api.reports_pdf import ReportsPdfBase


def request(**changes):
    """A summary report request with changes."""
    values = {
        "title": "Bud Test Report",
        "subtitle": "Test outcomes",
        "filters": [("Window", "Last 7 days")],
        "overall": Outcome(passed=9, failed=1, skipped=2),
        "breakdowns": [
            Breakdown("Per suite", "Suite", [("smoke", Outcome(9, 1, 2))]),
            Breakdown("Per Test Station", "Test Station", [("station-01", Outcome(9, 1, 2))]),
            Breakdown("Per day", "Day", [("2026-07-31", Outcome(9, 1, 2))]),
        ],
        "app_version": "1.0.0",
    }
    return ReportRequest(**{**values, **changes})


def document(pdf):
    """The parsed pages of a PDF: their text, links and image counts."""
    try:
        doc = pymupdf.open(stream=pdf, filetype="pdf")
    except Exception:
        return []
    pages = [
        {
            "text": page.get_text(),
            "uris": {item.get("uri") for item in page.get_links()},
            "images": len(page.get_images(full=True)),
        }
        for page in doc
    ]
    doc.close()
    return pages


def first(pages):
    """The first page, or an empty one."""
    return pages[0] if pages else {"text": "", "uris": set(), "images": 0}


class ReportsPdfTest(ReportsPdfBase):

    def setUpClass(self):
        super().setUpClass()
        self.tc_checks = {}
        for scenario in (
            self.outcome,
            self.links,
            self.renderer,
            self.footer,
            self.run_content,
            self.summary_content,
            self.assertions,
            self.file_name,
            self.summary_endpoint,
            self.run_endpoint,
            self.signed_out,
        ):
            scenario()

    def outcome(self):
        self.tc_checks["outcome"] = {
            "the total sums the counts": (Outcome(passed=7, failed=2, skipped=1).total, 10),
            "the rate is the passed share": (
                Outcome(passed=7, failed=2, skipped=1).pass_rate,
                70.0,
            ),
            "an empty outcome totals zero": (Outcome().total, 0),
            "an empty outcome has a zero rate": (Outcome().pass_rate, 0.0),
            "the rate has one decimal": (Outcome(passed=1, failed=2).pass_rate, 33.3),
        }

    def links(self):
        self.tc_checks["links"] = {
            "the link targets its address": (
                'href="https://x.test"' in report_pdf.link("https://x.test"),
                True,
            ),
            "the address is the default label": (
                ">https://x.test<" in report_pdf.link("https://x.test"),
                True,
            ),
            "a supplied label is used": (
                ">repo<" in report_pdf.link("https://x.test", "repo"),
                True,
            ),
        }

    def renderer(self):
        p = self.parameters
        summary = report_pdf.render_report(request())
        empty = report_pdf.render_report(
            request(overall=Outcome(), breakdowns=[Breakdown("Per suite", "Suite", [])])
        )
        trace = "\n".join(
            f'  File "/app/tests/test_module_{n}.py", line {n}, in test_step_{n}'
            for n in range(400)
        )
        tall = report_pdf.render_report(
            request(
                title="Bud Run Report",
                run=RunDetail(run_id=7, name="long-trace", status="Completed"),
                assertions=[
                    AssertionDetail(
                        test_class="FlashTests",
                        test_method="test_write_block",
                        index=1,
                        passed=False,
                        message="payload mismatch",
                        traceback=trace,
                    )
                ],
            )
        )
        identity = report_pdf.render_report(
            request(
                title="Bud Run Report",
                run=RunDetail(
                    run_id=42,
                    name="smoke",
                    status="Completed",
                    station="station-01",
                    run_url=p.PDF_RUN_URL,
                ),
                assertions=[
                    AssertionDetail(
                        test_class="SmokeTests",
                        test_method="test_boot",
                        index=1,
                        passed=True,
                        assertion_type="AssertEqual",
                        message="boot state matches",
                        expected="ready",
                        actual="ready",
                    )
                ],
            )
        )
        self.tc_checks["renderer"] = {
            "a summary starts as a PDF": (summary.startswith(p.PDF_START), True),
            "a summary ends as a PDF": (summary.rstrip().endswith(p.PDF_END), True),
            "an empty selection renders": (empty.startswith(p.PDF_START), True),
            "an assertion taller than a page renders": (tall.startswith(p.PDF_START), True),
            "a run report renders": (identity.startswith(p.PDF_START), True),
        }

    def footer(self):
        p = self.parameters
        run_pages = document(
            report_pdf.render_report(
                request(
                    run=RunDetail(run_id=7, name="smoke", status="Completed"),
                    assertions=[AssertionDetail("A", "b", 1, True, message="ok")],
                )
            )
        )
        summary_pages = document(report_pdf.render_report(request()))
        self.tc_checks["footer"] = {
            "a run report has a results page": (len(run_pages) >= 2, True),
            "every page links to EmbedLabs": (
                bool(run_pages) and all(p.PDF_EMBEDLABS in page["uris"] for page in run_pages),
                True,
            ),
            "the footer wordmark is shown": (p.PDF_WORDMARK in first(summary_pages)["text"], True),
            "the Bud logo ships": (report_pdf.BUD_LOGO.exists(), True),
            "the EmbedLabs logo ships": (report_pdf.EMBEDLABS_LOGO.exists(), True),
            "the header and footer marks are embedded": (first(summary_pages)["images"] >= 2, True),
            "every page has the footer mark": (
                bool(run_pages) and all(page["images"] for page in run_pages),
                True,
            ),
        }

    def run_content(self):
        p = self.parameters
        page = first(
            document(
                report_pdf.render_report(
                    request(
                        title="Bud Run Report",
                        run=RunDetail(
                            run_id=42,
                            name="smoke",
                            status="Completed",
                            station="station-01",
                            test_software_url=p.PDF_SOFTWARE_URL,
                            test_software_ref="main",
                            run_url=p.PDF_RUN_URL,
                        ),
                    )
                )
            )
        )
        self.tc_checks["run content"] = {
            "the run id is shown": ("BUD-RUN-42" in page["text"], True),
            "the station is shown": ("station-01" in page["text"], True),
            "the run page is linked": (p.PDF_RUN_URL in page["uris"], True),
            "the test software is linked": (p.PDF_SOFTWARE_URL in page["uris"], True),
        }

    def summary_content(self):
        p = self.parameters
        text = first(document(report_pdf.render_report(request())))["text"]
        empty = first(document(report_pdf.render_report(request(overall=Outcome()))))["text"]
        checks = {
            f"the {heading} breakdown is shown": (heading in text, True)
            for heading in p.PDF_BREAKDOWNS
        }
        checks.update({f"the chart names {label}": (label in text, True) for label in p.PDF_CHART})
        checks["an empty selection says so"] = (p.PDF_EMPTY in empty, True)
        self.tc_checks["summary content"] = checks

    def assertions(self):
        p = self.parameters
        pages = document(
            report_pdf.render_report(
                request(
                    title="Bud Run Report",
                    overall=Outcome(passed=1, failed=1),
                    run=RunDetail(run_id=17, name="thermal", status="Completed"),
                    assertions=[
                        AssertionDetail(
                            test_class="ThermalTests",
                            test_method="test_supply",
                            index=1,
                            passed=True,
                            assertion_type="AssertInRange",
                            message="supply stayed inside the safe window",
                            expected="[11.5, 14.8] V",
                            actual="13.6 V",
                            source="test_thermal.py:84",
                        ),
                        AssertionDetail(
                            test_class="ThermalTests",
                            test_method="test_supply",
                            index=2,
                            passed=False,
                            assertion_type="AssertEqual",
                            message="fan state mismatch",
                            expected="on",
                            actual="off",
                            traceback="assertion-level trace marker",
                        ),
                    ],
                )
            )
        )
        flat = " ".join("\n".join(page["text"] for page in pages).split())
        checks = {
            f"the report shows {text}": (text in flat, True) for text in p.PDF_ASSERTION_TEXTS
        }
        checks["the report does not count methods"] = ("2 tests" in flat, False)
        self.tc_checks["assertions"] = checks

    def file_name(self):
        p = self.parameters
        checks = {
            "an ordinary name is kept": (
                reports._safe_filename("bud-run-1-smoke"),
                "bud-run-1-smoke.pdf",
            )
        }
        for hostile in p.PDF_HOSTILE_NAMES:
            name = reports._safe_filename(hostile)
            checks[f"{hostile!r} ends as a PDF"] = (name.endswith(".pdf"), True)
            checks[f"{hostile!r} keeps no header-breaking character"] = (
                [c for c in p.PDF_FORBIDDEN if c in name],
                [],
            )
        checks["a name with nothing left falls back"] = (
            reports._safe_filename("///"),
            "bud-report.pdf",
        )
        self.tc_checks["file name"] = checks

    def seed(self):
        """A fresh app with a report run and an older run of another suite at one station."""
        self.bud.bud_start_app()
        station = self.bud.bud_add_to_app(
            Runner(account="report-station", password_hash="x", token="t")
        )
        now = datetime.utcnow()
        report_run = self.bud.bud_add_to_app(
            TestRun(
                name="report-suite",
                test_case_list="SmokeTests",
                status="Completed",
                total_tests=12,
                passed_tests=9,
                failed_tests=2,
                skipped_tests=1,
                created_at=now,
                runner_id=station.id,
                url_test_software=self.parameters.PDF_SOFTWARE_URL,
                ref_test_software="main",
            )
        )
        other_run = self.bud.bud_add_to_app(
            TestRun(
                name="other-suite",
                test_case_list="Other",
                status="Completed",
                total_tests=4,
                passed_tests=4,
                failed_tests=0,
                skipped_tests=0,
                created_at=now - timedelta(days=1),
                runner_id=station.id,
            )
        )
        self.bud.bud_add_to_app(
            TestResult(
                test_run_id=report_run.id,
                test_class="ReportTests",
                test_method="test_report",
                passed=False,
                assertions=[
                    {"passed": True, "message": "first report assertion"},
                    {"passed": False, "message": "second report assertion"},
                ],
            )
        )
        self.bud.bud_add_to_app(
            TestResult(
                test_run_id=other_run.id,
                test_class="OtherTests",
                test_method="test_other",
                passed=True,
                assertions=[
                    {"passed": True, "message": f"other assertion {n}"}
                    for n in ("one", "two", "three")
                ],
            )
        )
        return report_run.id

    def summary_endpoint(self):
        p = self.parameters
        self.seed()
        response = self.bud.bud_request(p.GET, p.PDF_SUMMARY_PATH)
        text = first(document(response.content))["text"]
        narrowed = first(
            document(
                self.bud.bud_request(
                    p.GET, p.PDF_SUMMARY_PATH, params={"suite": "report-suite"}
                ).content
            )
        )["text"]
        unknown = self.bud.bud_request(
            p.GET, p.PDF_SUMMARY_PATH, params={"runner_account": "no-such-station"}
        )
        checks = {
            "the summary is served": (response.status_code, p.STATUS_OK),
            "the summary is a PDF": (response.headers.get("content-type"), "application/pdf"),
            "the summary is an attachment": (
                "attachment" in response.headers.get("content-disposition", ""),
                True,
            ),
            "the summary starts as a PDF": (response.content.startswith(p.PDF_START), True),
        }
        checks.update(
            {f"the summary shows {seeded}": (seeded in text, True) for seeded in p.PDF_SEEDED_TEXTS}
        )
        checks["the summary does not count methods"] = ("16 tests" in text, False)
        checks["the suite filter keeps its suite"] = ("report-suite" in narrowed, True)
        checks["the suite filter leaves the other suite out"] = ("other-suite" in narrowed, False)
        checks["an unknown station is served"] = (unknown.status_code, p.STATUS_OK)
        checks["an unknown station gets an empty PDF"] = (
            unknown.content.startswith(p.PDF_START),
            True,
        )
        self.tc_checks["summary endpoint"] = checks

    def run_endpoint(self):
        p = self.parameters
        run_id = self.seed()
        response = self.bud.bud_request(p.GET, p.PDF_RUN_PATH.format(run_id))
        page = first(document(response.content))
        missing = self.bud.bud_request(p.GET, p.PDF_RUN_PATH.format(p.PDF_MISSING_RUN))
        self.tc_checks["run endpoint"] = {
            "the run report is served": (response.status_code, p.STATUS_OK),
            "the file is named after the run": (
                f"bud-run-{run_id}" in response.headers.get("content-disposition", ""),
                True,
            ),
            "the run id is shown": (f"BUD-RUN-{run_id}" in page["text"], True),
            "the station is shown": ("report-station" in page["text"], True),
            "the test software is linked": (p.PDF_SOFTWARE_URL in page["uris"], True),
            "an unknown run is not found": (missing.status_code, p.STATUS_NOT_FOUND),
        }

    def signed_out(self):
        p = self.parameters
        self.bud.bud_start_app(signed_in=False)
        self.tc_checks["signed out"] = {
            "the summary needs a signed-in entity": (
                self.bud.bud_request(p.GET, p.PDF_SUMMARY_PATH).status_code,
                p.STATUS_UNAUTHORIZED,
            ),
            "a run report needs a signed-in entity": (
                self.bud.bud_request(p.GET, p.PDF_RUN_PATH.format(1)).status_code,
                p.STATUS_UNAUTHORIZED,
            ),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ReportsPdfTest().run()
