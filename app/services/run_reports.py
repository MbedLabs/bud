"""Run and suite PDF reports: built here, rendered on demand by app.api.reports
and stored as artifacts when a run finishes.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models import Artifact, Runner, TestResult, TestRun
from app.services.report_pdf import (
    AssertionDetail,
    Breakdown,
    Outcome,
    ReportRequest,
    RunDetail,
    render_report,
)

logger = logging.getLogger(__name__)

MAX_RESULT_ROWS = 2000


def frontend_run_url(run_id: int) -> str | None:
    base = (settings.FRONTEND_BASE_URL or "").rstrip("/")
    return f"{base}/test-runs/{run_id}" if base else None


def _assertion_details(results: list[TestResult]) -> list[AssertionDetail]:
    details: list[AssertionDetail] = []
    for result in results:
        assertions = result.assertions if isinstance(result.assertions, list) else []
        for index, raw in enumerate(assertions, start=1):
            assertion = raw if isinstance(raw, dict) else {}
            passed_value = assertion.get("passed")
            passed = passed_value if isinstance(passed_value, bool) else None
            source = str(assertion.get("source_file") or "")
            if assertion.get("source_line") is not None:
                source = f"{source or '-'}:{assertion['source_line']}"
            details.append(
                AssertionDetail(
                    test_class=result.test_class,
                    test_method=result.test_method,
                    index=index,
                    passed=passed,
                    assertion_type=str(
                        assertion.get("assertion_type") or assertion.get("name") or "Assertion"
                    ),
                    message=str(assertion.get("message") or ""),
                    expected=assertion.get("expected"),
                    actual=assertion.get("actual", assertion.get("result")),
                    source=source,
                    metadata=assertion.get("metadata"),
                    traceback=str(assertion.get("traceback") or ""),
                )
            )
    return details


def _outcome_for_assertions(assertions: list[AssertionDetail]) -> Outcome:
    return Outcome(
        passed=sum(assertion.passed is True for assertion in assertions),
        failed=sum(assertion.passed is False for assertion in assertions),
        skipped=sum(assertion.passed is None for assertion in assertions),
    )


async def _build_run_scoped_report(db: AsyncSession, run: TestRun, *, title: str) -> ReportRequest:
    """One run: its identity and every assertion it recorded."""
    results = (
        (
            await db.execute(
                select(TestResult)
                .where(TestResult.test_run_id == run.id)
                .order_by(TestResult.test_class, TestResult.test_method)
                .limit(MAX_RESULT_ROWS)
            )
        )
        .scalars()
        .all()
    )
    assertions = _assertion_details(results)

    return ReportRequest(
        title=title,
        subtitle=f"BUD-RUN-{run.id} · {run.name}",
        filters=[],
        overall=_outcome_for_assertions(assertions),
        run=RunDetail(
            run_id=run.id,
            name=run.name,
            status=run.status,
            station=run.runner.account if run.runner else None,
            product=run.product.name if run.product else None,
            started_at=run.started_at,
            completed_at=run.completed_at,
            duration_seconds=run.duration_seconds,
            test_software_url=run.url_test_software,
            test_software_ref=run.ref_test_software,
            software_under_test_url=run.url_software_under_test,
            software_under_test_ref=run.ref_software_under_test,
            run_url=frontend_run_url(run.id),
        ),
        assertions=assertions,
        generated_at=datetime.utcnow(),
        app_version=settings.BUD_APP_VERSION,
    )


async def build_run_report(db: AsyncSession, run: TestRun) -> ReportRequest:
    return await _build_run_scoped_report(db, run, title="Bud Run Report")


async def build_suite_report(db: AsyncSession, run: TestRun) -> ReportRequest:
    """The generating run's suite report, never historical runs with the same name."""
    return await _build_run_scoped_report(db, run, title="Bud Suite Report")


async def build_summary_report(
    db: AsyncSession,
    conditions: list,
    *,
    days: int | None = None,
    runner_account: str | None = None,
    suite: str | None = None,
) -> ReportRequest:
    """Many runs, with assertion outcomes grouped by suite, Test Station and day.

    `conditions` carries the caller's dashboard/viewer scoping.
    """
    query = (
        select(TestRun.name, Runner.account, TestRun.created_at, TestResult.assertions)
        .select_from(TestRun)
        .outerjoin(Runner, TestRun.runner_id == Runner.id)
        .outerjoin(TestResult, TestResult.test_run_id == TestRun.id)
    )
    if conditions:
        query = query.where(*conditions)

    overall = Outcome()
    suite_outcomes: dict[str, Outcome] = {}
    station_outcomes: dict[str, Outcome] = {}
    day_outcomes: dict[str, Outcome] = {}

    def add(outcome: Outcome, passed: bool | None) -> None:
        if passed is True:
            outcome.passed += 1
        elif passed is False:
            outcome.failed += 1
        else:
            outcome.skipped += 1

    for suite_name, station, created_at, raw_assertions in (await db.execute(query)).all():
        suite_key = str(suite_name or "-")
        station_key = str(station or "-")
        day_key = created_at.date().isoformat() if created_at else "-"
        suite_outcome = suite_outcomes.setdefault(suite_key, Outcome())
        station_outcome = station_outcomes.setdefault(station_key, Outcome())
        day_outcome = day_outcomes.setdefault(day_key, Outcome())
        assertions = raw_assertions if isinstance(raw_assertions, list) else []
        for raw in assertions:
            value = raw.get("passed") if isinstance(raw, dict) else None
            passed = value if isinstance(value, bool) else None
            for target in (overall, suite_outcome, station_outcome, day_outcome):
                add(target, passed)

    def ranked(values: dict[str, Outcome]) -> list[tuple[str, Outcome]]:
        return sorted(values.items(), key=lambda item: (-item[1].total, item[0]))[:60]

    per_suite = ranked(suite_outcomes)
    per_station = ranked(station_outcomes)
    per_day = sorted(day_outcomes.items(), key=lambda item: item[0], reverse=True)[:60]

    return ReportRequest(
        title="Bud Test Report",
        subtitle="Test outcomes across the selected runs",
        filters=[
            ("Window", f"Last {days} days" if days else "All time"),
            ("Test Station", runner_account or "All"),
            ("Suite", suite or "All"),
        ],
        overall=overall,
        breakdowns=[
            Breakdown("Per suite", "Suite", per_suite),
            Breakdown("Per Test Station", "Test Station", per_station),
            Breakdown("Per day", "Day", per_day),
        ],
        generated_at=datetime.utcnow(),
        app_version=settings.BUD_APP_VERSION,
    )


def safe_filename(stem: str, suffix: str = ".pdf") -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_." else "-" for c in stem).strip("-")
    return (cleaned or "bud-report") + suffix


async def _store_bytes(
    db: AsyncSession,
    payload: bytes,
    *,
    original_filename: str,
    content_type: str,
    run_id: int,
) -> Artifact:
    """Write generated bytes into the artifact store, as an upload would."""
    from app.api.uploads import ensure_upload_dir

    upload_dir = await ensure_upload_dir()
    suffix = Path(original_filename).suffix
    stored_name = f"{uuid.uuid4()}{suffix if suffix[1:].isalnum() else ''}"
    (upload_dir / stored_name).write_bytes(payload)

    artifact = Artifact(
        filename=stored_name,
        original_filename=original_filename,
        content_type=content_type,
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        storage_path=stored_name,
        test_run_id=run_id,
    )
    db.add(artifact)
    await db.flush()
    return artifact


async def store_run_reports(db: AsyncSession, run_id: int) -> list[Artifact]:
    """Write the run's report and its suite's report as artifacts of the run.

    Idempotent: a claimed run finishes through both the PATCH and the claim
    acknowledgement. A report that will not render is logged, not raised.
    """
    run = (
        await db.execute(
            select(TestRun)
            .where(TestRun.id == run_id)
            .options(selectinload(TestRun.runner), selectinload(TestRun.product))
        )
    ).scalar_one_or_none()
    if run is None:
        return []

    already = set(
        (
            await db.scalars(
                select(Artifact.original_filename).where(Artifact.test_run_id == run_id)
            )
        ).all()
    )

    async def store(name: str, render) -> Artifact | None:
        if name in already:
            return None
        try:
            return await _store_bytes(
                db,
                render_report(await render()),
                original_filename=name,
                content_type="application/pdf",
                run_id=run.id,
            )
        except Exception:
            logger.exception("Could not store %s for run %s", name, run_id)
            return None

    stored = [
        await store(
            safe_filename(f"bud-run-{run.id}-{run.name}"),
            lambda: build_run_report(db, run),
        ),
        await store(
            safe_filename(f"bud-suite-{run.name}"),
            lambda: build_suite_report(db, run),
        ),
    ]
    return [artifact for artifact in stored if artifact is not None]
