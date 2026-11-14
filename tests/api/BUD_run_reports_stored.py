"""
* @file     ${tests/api/BUD_run_reports_stored.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    A finished run stores its run report and its suite report as artifacts.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests the report service on a fresh app database and runs finished through the API.
"""

from datetime import datetime, timezone
from unittest import mock

import fitz

from app.api import uploads
from app.models import Artifact, TestResult, TestRun
from app.services import run_reports
from tests.api.run_reports_stored import RunReportsStoredBase


class RunReportsStoredTest(RunReportsStoredBase):

    def setUpClass(self):
        super().setUpClass()
        p, run = self.parameters, self.bud.bud_await
        db, finished = self.fresh()
        run(run_reports.store_run_reports(db, finished.id))
        run(db.commit())
        self.tc_names = self.names(finished.id)
        self.tc_expected_names = self.expected(finished.id, p.STORED_SUITE)
        db, finished = self.fresh()
        stored = run(run_reports.store_run_reports(db, finished.id))
        run(db.commit())
        self.tc_pdfs = []
        for artifact in stored:
            payload = (uploads.get_upload_root() / artifact.storage_path).read_bytes()
            self.tc_pdfs.append(
                (
                    payload[: len(p.PDF_MAGIC)],
                    artifact.size_bytes,
                    len(payload),
                    artifact.content_type,
                )
            )
        db, finished = self.fresh()
        for _ in range(2):
            run(run_reports.store_run_reports(db, finished.id))
            run(db.commit())
        self.tc_twice = self.names(finished.id)
        self.suite_scope()
        db, finished = self.fresh()
        with mock.patch.object(run_reports, "render_report", side_effect=RuntimeError("no fonts")):
            stored = run(run_reports.store_run_reports(db, finished.id))
        run(db.commit())
        self.tc_broken = (stored, self.names(finished.id))
        db, _ = self.fresh()
        self.tc_missing = run(run_reports.store_run_reports(db, p.STORED_MISSING_RUN))
        self.tc_api = self.through_the_api()

    def fresh(self, name=None):
        """A fresh app database with one finished run; its session and the run."""
        self.bud.bud_start_app()
        return self.bud.bud_open_session(on_app=True), self.finished(
            name or self.parameters.STORED_SUITE
        )

    def finished(self, name):
        """Store a finished run with one result of two assertions."""
        p = self.parameters
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        run = self.bud.bud_add_to_app(
            TestRun(
                name=name,
                test_case_list=p.STORED_CASES,
                status="Completed",
                created_at=now,
                completed_at=now,
                **p.STORED_COUNTS,
            )
        )
        self.bud.bud_add_to_app(TestResult(test_run_id=run.id, **p.STORED_RESULT))
        return run

    def names(self, run_id):
        """The sorted names of a run's artifacts."""
        return sorted(
            artifact.original_filename
            for artifact in self.bud.bud_find_in_app(Artifact, test_run_id=run_id)
        )

    def expected(self, run_id, name):
        """The names of a run's two reports."""
        p = self.parameters
        return [p.STORED_RUN_REPORT.format(run_id, name), p.STORED_SUITE_REPORT.format(name)]

    def suite_scope(self):
        """The suite report of the newer of two runs of one suite."""
        p, run = self.parameters, self.bud.bud_await
        self.bud.bud_start_app()
        historical = self.finished(p.STORED_REPEATED)
        self.bud.bud_delete_in_app(TestResult, test_run_id=historical.id)
        self.bud.bud_add_to_app(
            TestResult(
                test_run_id=historical.id, **{**p.STORED_RESULT, "assertions": p.STORED_HISTORICAL}
            )
        )
        current = self.finished(p.STORED_REPEATED)
        db = self.bud.bud_open_session(on_app=True)
        stored = run(run_reports.store_run_reports(db, current.id))
        suite = next(
            (a for a in stored if a.original_filename.startswith(p.STORED_SUITE_PREFIX)), None
        )
        text = ""
        if suite is not None:
            document = fitz.open(
                stream=(uploads.get_upload_root() / suite.storage_path).read_bytes(),
                filetype=p.PDF_FORMAT,
            )
            text = "\n".join(page.get_text() for page in document)
            document.close()
        self.tc_suite_text, self.tc_current_id = text, current.id

    def through_the_api(self):
        """Finish runs through the station's PATCH and a claim's acknowledgement."""
        p = self.parameters
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        self.bud.bud_start_app()
        station = self.bud.bud_add_test_station(with_run=False)
        completed = self.bud.bud_add_to_app(
            TestRun(
                runner_id=station.id,
                name=p.STORED_API_COMPLETED,
                test_case_list=p.STORED_CASES,
                status="Running",
                total_tests=2,
                passed_tests=2,
                created_at=now,
            )
        )
        patched = self.bud.bud_station_request(
            p.PATCH, p.TEST_RUN_PATH.format(completed.id), json={"status": "Completed"}
        )
        listed = self.bud.bud_request(p.GET, p.RUN_ARTIFACTS_PATH.format(completed.id))
        running = self.bud.bud_add_to_app(
            TestRun(
                runner_id=station.id,
                name=p.STORED_API_RUNNING,
                test_case_list=p.STORED_CASES,
                status="Pending",
                created_at=now,
            )
        )
        self.bud.bud_station_request(
            p.PATCH, p.TEST_RUN_PATH.format(running.id), json={"status": "Running"}
        )
        claimed = self.bud.bud_add_to_app(
            TestRun(
                name=p.STORED_CLAIMED,
                test_case_list=p.STORED_CASES,
                status="Running",
                runner_id=station.id,
                claim_id=p.STORED_CLAIM,
                total_tests=1,
                passed_tests=1,
                created_at=now,
                started_at=now,
            )
        )
        acknowledged = self.bud.bud_station_request(
            p.POST,
            p.STORED_COMPLETE_PATH.format(claimed.id),
            json={"exit_code": 0, "error": None},
            headers={p.STORED_IDEMPOTENCY_HEADER: p.STORED_CLAIM},
        )
        return {
            "patched": patched.status_code,
            "listed": (
                listed.status_code,
                sorted(item["original_filename"] for item in listed.json()),
            ),
            "expected": self.expected(completed.id, p.STORED_API_COMPLETED),
            "running": self.bud.bud_request(p.GET, p.RUN_ARTIFACTS_PATH.format(running.id)).json(),
            "acknowledged": acknowledged.status_code,
            "claimed names": self.names(claimed.id),
            "claimed expected": self.expected(claimed.id, p.STORED_CLAIMED),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    RunReportsStoredTest().run()
