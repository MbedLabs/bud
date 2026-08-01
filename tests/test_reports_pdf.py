"""PDF report endpoints and the renderer behind them."""

import os
from datetime import datetime, timedelta

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-at-least-32-characters-long")

import pytest

from app.services.report_pdf import (
    Breakdown,
    Outcome,
    ReportRequest,
    RunDetail,
    link,
    render_report,
)


class TestOutcome:
    def test_totals_and_rate(self):
        outcome = Outcome(passed=7, failed=2, skipped=1)
        assert outcome.total == 10
        assert outcome.pass_rate == 70.0

    def test_empty_outcome_does_not_divide_by_zero(self):
        assert Outcome().total == 0
        assert Outcome().pass_rate == 0.0

    def test_rate_is_one_decimal(self):
        assert Outcome(passed=1, failed=2).pass_rate == 33.3


class TestLinkMarkup:
    def test_defaults_the_label_to_the_url(self):
        assert 'href="https://x.test"' in link("https://x.test")
        assert ">https://x.test<" in link("https://x.test")

    def test_uses_a_supplied_label(self):
        assert ">repo<" in link("https://x.test", "repo")


def _summary_request(**overrides) -> ReportRequest:
    base = dict(
        title="Bud Test Report",
        subtitle="Test outcomes",
        filters=[("Window", "Last 7 days")],
        overall=Outcome(passed=9, failed=1, skipped=2),
        breakdowns=[
            Breakdown("Per suite", "Suite", [("smoke", Outcome(9, 1, 2))]),
            Breakdown("Per Test Station", "Test Station", [("bench-01", Outcome(9, 1, 2))]),
            Breakdown("Per day", "Day", [("2026-07-31", Outcome(9, 1, 2))]),
        ],
        app_version="1.0.0",
    )
    base.update(overrides)
    return ReportRequest(**base)


class TestRenderer:
    def test_produces_a_pdf(self):
        pdf = render_report(_summary_request())
        assert pdf.startswith(b"%PDF-")
        assert pdf.rstrip().endswith(b"%%EOF")

    def test_renders_with_no_data_at_all(self):
        """An empty selection must still produce a readable document, not a crash."""
        pdf = render_report(
            _summary_request(
                overall=Outcome(),
                breakdowns=[Breakdown("Per suite", "Suite", [])],
            )
        )
        assert pdf.startswith(b"%PDF-")

    def test_run_report_carries_the_run_identity(self):
        pdf = render_report(
            _summary_request(
                title="Bud Run Report",
                run=RunDetail(
                    run_id=42,
                    name="smoke",
                    status="Completed",
                    station="bench-01",
                    run_url="https://bud.example/test-runs/42",
                ),
                results=[("SmokeTests", "test_boot", True, 1.5)],
            )
        )
        assert pdf.startswith(b"%PDF-")


class TestRenderedContent:
    """Assertions against the parsed document rather than the byte stream."""

    @pytest.fixture(scope="class")
    def fitz(self):
        return pytest.importorskip(
            "fitz", reason="pymupdf is only needed to introspect generated PDFs"
        )

    def _open(self, fitz, pdf: bytes):
        return fitz.open(stream=pdf, filetype="pdf")

    def test_footer_links_to_embedlabs_on_every_page(self, fitz):
        pdf = render_report(
            _summary_request(
                run=RunDetail(run_id=7, name="smoke", status="Completed"),
                results=[("A", "b", True, 0.1)],
            )
        )
        doc = self._open(fitz, pdf)
        assert doc.page_count >= 2, "a run report puts results on their own page"
        for page in doc:
            uris = {link.get("uri") for link in page.get_links()}
            assert "https://www.embedlabs.net" in uris
        doc.close()

    def test_footer_wordmark_is_present(self, fitz):
        doc = self._open(fitz, render_report(_summary_request()))
        assert "Powered by EmbedLabs" in doc[0].get_text()
        doc.close()

    def test_run_report_shows_the_run_id_and_links_out(self, fitz):
        pdf = render_report(
            _summary_request(
                title="Bud Run Report",
                run=RunDetail(
                    run_id=42,
                    name="smoke",
                    status="Completed",
                    station="bench-01",
                    test_software_url="https://github.test/tests",
                    test_software_ref="main",
                    run_url="https://bud.example/test-runs/42",
                ),
            )
        )
        doc = self._open(fitz, pdf)
        text = doc[0].get_text()
        assert "BUD-RUN-42" in text
        assert "bench-01" in text
        uris = {link.get("uri") for link in doc[0].get_links()}
        assert "https://bud.example/test-runs/42" in uris
        assert "https://github.test/tests" in uris
        doc.close()

    def test_summary_shows_each_breakdown(self, fitz):
        doc = self._open(fitz, render_report(_summary_request()))
        text = doc[0].get_text()
        for heading in ("Per suite", "Per Test Station", "Per day"):
            assert heading in text
        doc.close()

    def test_chart_reports_percentages(self, fitz):
        doc = self._open(fitz, render_report(_summary_request()))
        text = doc[0].get_text()
        assert "Passed" in text and "Failed" in text and "Skipped" in text
        doc.close()

    def test_empty_selection_says_so_rather_than_drawing_an_empty_pie(self, fitz):
        doc = self._open(fitz, render_report(_summary_request(overall=Outcome())))
        assert "No test outcomes recorded" in doc[0].get_text()
        doc.close()


class TestFilenameSafety:
    """A suite name reaches Content-Disposition, so it must not break the header."""

    def test_keeps_an_ordinary_name(self):
        from app.api.reports import _safe_filename

        assert _safe_filename("bud-run-1-smoke") == "bud-run-1-smoke.pdf"

    @pytest.mark.parametrize(
        "hostile",
        [
            "../../etc/passwd",
            "a/b\\c",
            'quote"inside',
            "crlf\r\ninjected: yes",
            "semi;colon",
        ],
    )
    def test_removes_every_character_that_could_break_the_header(self, hostile):
        from app.api.reports import _safe_filename

        name = _safe_filename(hostile)
        assert name.endswith(".pdf")
        for forbidden in ("/", "\\", '"', "\r", "\n", ";"):
            assert forbidden not in name

    def test_falls_back_when_nothing_survives(self):
        from app.api.reports import _safe_filename

        assert _safe_filename("///") == "bud-report.pdf"


class TestReportEndpoints:
    """Against the real routes, with runs seeded into the test database."""

    async def _seed(self, db_session):
        from app.models import Runner, TestRun

        station = Runner(account="report-station", password_hash="x", token="t")
        db_session.add(station)
        await db_session.flush()
        now = datetime.utcnow()
        db_session.add_all(
            [
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
                    url_test_software="https://github.test/tests",
                    ref_test_software="main",
                ),
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
                ),
            ]
        )
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_summary_report_downloads_a_pdf(self, client, db_session):
        await self._seed(db_session)
        response = client.get("/api/reports/test-runs.pdf")
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert response.content.startswith(b"%PDF-")

    @pytest.mark.asyncio
    async def test_summary_report_reflects_the_seeded_runs(self, client, db_session):
        fitz = pytest.importorskip("fitz")
        await self._seed(db_session)
        response = client.get("/api/reports/test-runs.pdf")
        doc = fitz.open(stream=response.content, filetype="pdf")
        text = doc[0].get_text()
        doc.close()
        assert "report-suite" in text
        assert "other-suite" in text
        assert "report-station" in text
        assert "16 tests" in text  # 12 + 4 across both runs

    @pytest.mark.asyncio
    async def test_suite_filter_narrows_the_report(self, client, db_session):
        fitz = pytest.importorskip("fitz")
        await self._seed(db_session)
        response = client.get("/api/reports/test-runs.pdf", params={"suite": "report-suite"})
        doc = fitz.open(stream=response.content, filetype="pdf")
        text = doc[0].get_text()
        doc.close()
        assert "report-suite" in text
        assert "other-suite" not in text

    @pytest.mark.asyncio
    async def test_unknown_station_yields_an_empty_report_not_an_error(self, client, db_session):
        await self._seed(db_session)
        response = client.get(
            "/api/reports/test-runs.pdf", params={"runner_account": "no-such-station"}
        )
        assert response.status_code == 200
        assert response.content.startswith(b"%PDF-")

    @pytest.mark.asyncio
    async def test_run_report_carries_the_run_id(self, client, db_session):
        fitz = pytest.importorskip("fitz")
        from sqlalchemy import select

        from app.models import TestRun

        await self._seed(db_session)
        run_id = (
            await db_session.execute(select(TestRun.id).where(TestRun.name == "report-suite"))
        ).scalar_one()

        response = client.get(f"/api/reports/test-runs/{run_id}.pdf")
        assert response.status_code == 200, response.text
        assert f"bud-run-{run_id}" in response.headers["content-disposition"]
        doc = fitz.open(stream=response.content, filetype="pdf")
        text = doc[0].get_text()
        uris = {link.get("uri") for link in doc[0].get_links()}
        doc.close()
        assert f"BUD-RUN-{run_id}" in text
        assert "report-station" in text
        assert "https://github.test/tests" in uris

    def test_run_report_404s_for_an_unknown_run(self, client):
        assert client.get("/api/reports/test-runs/99999999.pdf").status_code == 404

    def test_summary_report_requires_authentication(self, unauthenticated_client):
        assert unauthenticated_client.get("/api/reports/test-runs.pdf").status_code == 401

    def test_run_report_requires_authentication(self, unauthenticated_client):
        assert unauthenticated_client.get("/api/reports/test-runs/1.pdf").status_code == 401
