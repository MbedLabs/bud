"""Run and suite reports, stored as artifacts when a run finishes."""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-at-least-32-characters-long")

from datetime import datetime  # noqa: E402
from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.models import Artifact, Runner, TestResult, TestRun  # noqa: E402
from app.services.run_reports import store_run_reports  # noqa: E402


async def _finished_run(db_session, name="stored-report-suite"):
    run = TestRun(
        name=name,
        test_case_list="Suite.CASES",
        status="Completed",
        total_tests=6,
        passed_tests=5,
        failed_tests=1,
        skipped_tests=0,
        created_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db_session.add(run)
    await db_session.flush()
    db_session.add(
        TestResult(
            test_run_id=run.id,
            test_class="StoredTests",
            test_method="test_assertions",
            passed=False,
            assertions=[
                {
                    "passed": True,
                    "assertion_type": "AssertInRange",
                    "message": "current-run-marker",
                    "expected": "[11.5, 14.8] V",
                    "actual": "13.6 V",
                    "source_file": "test_stored.py",
                    "source_line": 42,
                },
                {"passed": False, "message": "current-run-failure"},
            ],
            test_metadata={"tc_id": "VCU-TC-001"},
        )
    )
    await db_session.commit()
    await db_session.refresh(run)
    return run


async def _artifact_names(db_session, run_id):
    rows = (
        await db_session.scalars(
            select(Artifact.original_filename).where(Artifact.test_run_id == run_id)
        )
    ).all()
    return sorted(rows)


class TestWhatAFinishedRunLeaves:
    @pytest.mark.asyncio
    async def test_stores_the_run_report_and_the_suite_report(self, db_session):
        run = await _finished_run(db_session)

        await store_run_reports(db_session, run.id)
        await db_session.commit()

        names = await _artifact_names(db_session, run.id)
        assert names == [
            f"bud-run-{run.id}-stored-report-suite.pdf",
            "bud-suite-stored-report-suite.pdf",
        ]

    @pytest.mark.asyncio
    async def test_what_it_stores_is_a_pdf(self, db_session):
        from app.api.uploads import get_upload_root

        run = await _finished_run(db_session)
        stored = await store_run_reports(db_session, run.id)
        await db_session.commit()

        for artifact in stored:
            payload = (get_upload_root() / artifact.storage_path).read_bytes()
            assert payload.startswith(b"%PDF-")
            assert artifact.size_bytes == len(payload)
            assert artifact.content_type == "application/pdf"

    @pytest.mark.asyncio
    async def test_storing_twice_does_not_duplicate(self, db_session):
        """A claimed run finishes twice over: the PATCH, then the acknowledgement."""
        run = await _finished_run(db_session)

        await store_run_reports(db_session, run.id)
        await db_session.commit()
        await store_run_reports(db_session, run.id)
        await db_session.commit()

        names = await _artifact_names(db_session, run.id)
        assert len(names) == 2, names

    @pytest.mark.asyncio
    async def test_suite_report_is_detailed_and_scoped_to_its_generating_run(self, db_session):
        fitz = pytest.importorskip("fitz")
        from app.api.uploads import get_upload_root

        historical = await _finished_run(db_session, name="repeated-suite")
        historical_result = (
            await db_session.scalars(
                select(TestResult).where(TestResult.test_run_id == historical.id)
            )
        ).one()
        historical_result.assertions = [
            {"passed": False, "message": "historical-run-must-not-appear"}
        ]
        current = await _finished_run(db_session, name="repeated-suite")
        await db_session.commit()

        stored = await store_run_reports(db_session, current.id)
        suite = next(a for a in stored if a.original_filename.startswith("bud-suite-"))
        payload = (get_upload_root() / suite.storage_path).read_bytes()
        doc = fitz.open(stream=payload, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        doc.close()

        assert f"BUD-RUN-{current.id}" in text
        assert "2 assertions" in text
        assert "AssertInRange" in text
        assert "current-run-marker" in text
        assert "[11.5, 14.8] V" in text
        assert "13.6 V" in text
        assert "test_stored.py:42" in text
        assert "historical-run-must-not-appear" not in text

    @pytest.mark.asyncio
    async def test_a_broken_renderer_does_not_fail_the_run(self, db_session):
        """A report that will not render must not fail the run."""
        run = await _finished_run(db_session)

        with patch("app.services.run_reports.render_report", side_effect=RuntimeError("no fonts")):
            stored = await store_run_reports(db_session, run.id)
        await db_session.commit()

        assert stored == []
        assert await _artifact_names(db_session, run.id) == []

    @pytest.mark.asyncio
    async def test_a_run_that_does_not_exist_is_not_an_error(self, db_session):
        assert await store_run_reports(db_session, 999_999) == []


class TestReachingItThroughTheApi:
    @pytest.mark.asyncio
    async def test_marking_a_run_completed_stores_its_reports(self, client, db_session):
        run = TestRun(
            name="api-completed-suite",
            test_case_list="Suite.CASES",
            status="Running",
            total_tests=2,
            passed_tests=2,
            created_at=datetime.utcnow(),
        )
        db_session.add(run)
        await db_session.commit()
        await db_session.refresh(run)

        response = client.patch(f"/api/test-runs/{run.id}", json={"status": "Completed"})
        assert response.status_code == 200, response.text

        listed = client.get(f"/api/test-runs/{run.id}/artifacts")
        assert listed.status_code == 200
        names = sorted(item["original_filename"] for item in listed.json())
        assert names == [
            f"bud-run-{run.id}-api-completed-suite.pdf",
            "bud-suite-api-completed-suite.pdf",
        ]

    @pytest.mark.asyncio
    async def test_a_run_still_running_has_no_reports_yet(self, client, db_session):
        run = TestRun(
            name="api-running-suite",
            test_case_list="Suite.CASES",
            status="Pending",
            created_at=datetime.utcnow(),
        )
        db_session.add(run)
        await db_session.commit()
        await db_session.refresh(run)

        client.patch(f"/api/test-runs/{run.id}", json={"status": "Running"})

        listed = client.get(f"/api/test-runs/{run.id}/artifacts")
        assert listed.json() == []

    @pytest.mark.asyncio
    async def test_acknowledging_a_claim_stores_the_reports_too(self, client, db_session):
        """A claimed run reaches Completed through the acknowledgement, not the PATCH."""
        station = Runner(
            account="report-claim-station",
            password_hash="x",
            token="t",
            is_active=True,
        )
        db_session.add(station)
        await db_session.commit()
        await db_session.refresh(station)

        claim = "22222222-2222-4222-8222-222222222222"
        run = TestRun(
            name="claimed-suite",
            test_case_list="Suite.CASES",
            status="Running",
            runner_id=station.id,
            claim_id=claim,
            total_tests=1,
            passed_tests=1,
            created_at=datetime.utcnow(),
            started_at=datetime.utcnow(),
        )
        db_session.add(run)
        await db_session.commit()
        await db_session.refresh(run)

        from app.api.auth import get_current_active_entity
        from app.main import app

        app.dependency_overrides[get_current_active_entity] = lambda: station
        try:
            response = client.post(
                f"/api/runners/runs/{run.id}/complete",
                json={"exit_code": 0, "error": None},
                headers={"Idempotency-Key": claim},
            )
            assert response.status_code == 200, response.text
        finally:
            app.dependency_overrides.pop(get_current_active_entity, None)

        names = await _artifact_names(db_session, run.id)
        assert names == [
            f"bud-run-{run.id}-claimed-suite.pdf",
            "bud-suite-claimed-suite.pdf",
        ]
