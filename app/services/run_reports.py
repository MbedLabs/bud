"""Run and suite PDF reports: built here, rendered on demand by app.api.reports
and stored as artifacts when a run finishes.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models import Artifact, Runner, TestResult, TestRun
from app.services.report_pdf import (
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


def sum_columns():
    return (
        func.coalesce(func.sum(TestRun.passed_tests), 0),
        func.coalesce(func.sum(TestRun.failed_tests), 0),
        func.coalesce(func.sum(TestRun.skipped_tests), 0),
    )


async def _grouped(db: AsyncSession, label_column, conditions) -> list[tuple[str, Outcome]]:
    query = select(label_column, *sum_columns())
    if conditions:
        query = query.where(*conditions)
    rows = (
        await db.execute(
            query.group_by(label_column)
            .order_by(func.coalesce(func.sum(TestRun.total_tests), 0).desc())
            .limit(60)
        )
    ).all()
    return [(str(label or "-"), Outcome(p, f, s)) for label, p, f, s in rows]


async def build_run_report(db: AsyncSession, run: TestRun) -> ReportRequest:
    """One run: its identity, its outcome, and every result it recorded."""
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

    return ReportRequest(
        title="Bud Run Report",
        subtitle=f"BUD-RUN-{run.id} · {run.name}",
        filters=[],
        # The counters include skips; result rows do not.
        overall=Outcome(run.passed_tests, run.failed_tests, run.skipped_tests),
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
        results=[
            (r.test_class, r.test_method, r.passed, r.duration_seconds or 0.0) for r in results
        ],
        generated_at=datetime.utcnow(),
        app_version=settings.BUD_APP_VERSION,
    )


async def build_summary_report(
    db: AsyncSession,
    conditions: list,
    *,
    days: int | None = None,
    runner_account: str | None = None,
    suite: str | None = None,
) -> ReportRequest:
    """Many runs, broken down per suite, per Test Station and per day.

    `conditions` carries the caller's scoping: the viewer's for a request, the
    run's suite for a stored report.
    """
    totals_query = select(*sum_columns())
    if conditions:
        totals_query = totals_query.where(*conditions)
    passed, failed, skipped = (await db.execute(totals_query)).one()

    per_suite = await _grouped(db, TestRun.name, conditions)

    station_query = select(Runner.account, *sum_columns()).join(
        TestRun, TestRun.runner_id == Runner.id
    )
    if conditions:
        station_query = station_query.where(*conditions)
    station_rows = (
        await db.execute(
            station_query.group_by(Runner.account)
            .order_by(func.coalesce(func.sum(TestRun.total_tests), 0).desc())
            .limit(60)
        )
    ).all()
    per_station = [(account or "-", Outcome(p, f, s)) for account, p, f, s in station_rows]

    day = func.date(TestRun.created_at)
    day_query = select(day, *sum_columns())
    if conditions:
        day_query = day_query.where(*conditions)
    day_rows = (await db.execute(day_query.group_by(day).order_by(day.desc()).limit(60))).all()
    per_day = [(str(bucket), Outcome(p, f, s)) for bucket, p, f, s in day_rows]

    return ReportRequest(
        title="Bud Test Report",
        subtitle="Test outcomes across the selected runs",
        filters=[
            ("Window", f"Last {days} days" if days else "All time"),
            ("Test Station", runner_account or "All"),
            ("Suite", suite or "All"),
        ],
        overall=Outcome(passed, failed, skipped),
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
            lambda: build_summary_report(db, [TestRun.name == run.name], suite=run.name),
        ),
    ]
    return [artifact for artifact in stored if artifact is not None]
