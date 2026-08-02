"""PDF report endpoints.

Two reports: a filtered summary across many runs, broken down per suite, per
Test Station and per day; and a single-run report carrying that run's identity
and its individual results. Both share the scoping rules of the dashboard
statistics, so a report always agrees with the tiles it was generated from.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Union
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_active_entity
from app.api.test_runs import _scope_conditions
from app.core.config import settings
from app.core.run_access import require_run_access
from app.db import get_db
from app.models import Runner, TestResult, TestRun
from app.models.user import User
from app.services.report_pdf import (
    Breakdown,
    Outcome,
    ReportRequest,
    RunDetail,
    render_report,
)

router = APIRouter()

MAX_RESULT_ROWS = 2000


def _pdf_response(pdf: bytes, filename: str) -> Response:
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            # RFC 5987 form as well, so non-ASCII suite names survive.
            "Content-Disposition": (
                f'attachment; filename="{filename}"; ' f"filename*=UTF-8''{quote(filename)}"
            ),
            "Cache-Control": "no-store",
        },
    )


def _safe_filename(stem: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_." else "-" for c in stem).strip("-")
    return (cleaned or "bud-report") + ".pdf"


def _sum_columns():
    return (
        func.coalesce(func.sum(TestRun.passed_tests), 0),
        func.coalesce(func.sum(TestRun.failed_tests), 0),
        func.coalesce(func.sum(TestRun.skipped_tests), 0),
    )


async def _grouped(db: AsyncSession, group_column, conditions: list, limit: int = 60):
    """Passed/failed/skipped totals grouped by one column, busiest first."""
    query = select(group_column, *_sum_columns())
    if conditions:
        query = query.where(*conditions)
    query = (
        query.group_by(group_column)
        .order_by(func.coalesce(func.sum(TestRun.total_tests), 0).desc())
        .limit(limit)
    )
    rows = (await db.execute(query)).all()
    return [
        (str(label) if label is not None else "-", Outcome(passed, failed, skipped))
        for label, passed, failed, skipped in rows
    ]


def _frontend_run_url(run_id: int) -> Optional[str]:
    base = (settings.FRONTEND_BASE_URL or "").rstrip("/")
    return f"{base}/test-runs/{run_id}" if base else None


@router.get("/test-runs.pdf")
async def test_run_summary_report(
    days: Optional[int] = Query(
        None, ge=1, le=3650, description="Only include runs created within the last N days."
    ),
    runner_account: Optional[str] = Query(
        None, description="Only include runs executed by this Test Station."
    ),
    suite: Optional[str] = Query(None, description="Only include runs for this test suite name."),
    db: AsyncSession = Depends(get_db),
    current_entity: Union[User, Runner] = Depends(get_current_active_entity),
):
    """A filtered test report: overall pie chart plus per-suite, per-station and per-day tables."""
    conditions = await _scope_conditions(
        db, current_entity, days=days, runner_account=runner_account, suite=suite
    )
    # An unknown Test Station scopes to nothing rather than erroring, matching
    # the statistics endpoint.
    conditions = conditions if conditions is not None else [TestRun.id.is_(None)]

    totals_query = select(*_sum_columns())
    if conditions:
        totals_query = totals_query.where(*conditions)
    passed, failed, skipped = (await db.execute(totals_query)).one()
    overall = Outcome(passed, failed, skipped)

    per_suite = await _grouped(db, TestRun.name, conditions)

    station_conditions = list(conditions)
    station_query = select(Runner.account, *_sum_columns()).join(
        TestRun, TestRun.runner_id == Runner.id
    )
    if station_conditions:
        station_query = station_query.where(*station_conditions)
    station_rows = (
        await db.execute(
            station_query.group_by(Runner.account)
            .order_by(func.coalesce(func.sum(TestRun.total_tests), 0).desc())
            .limit(60)
        )
    ).all()
    per_station = [(account or "-", Outcome(p, f, s)) for account, p, f, s in station_rows]

    day = func.date(TestRun.created_at)
    day_query = select(day, *_sum_columns())
    if conditions:
        day_query = day_query.where(*conditions)
    day_rows = (await db.execute(day_query.group_by(day).order_by(day.desc()).limit(60))).all()
    per_day = [(str(bucket), Outcome(p, f, s)) for bucket, p, f, s in day_rows]

    filters: list[tuple[str, str]] = [
        ("Window", f"Last {days} days" if days else "All time"),
        ("Test Station", runner_account or "All"),
        ("Suite", suite or "All"),
    ]

    pdf = render_report(
        ReportRequest(
            title="Bud Test Report",
            subtitle="Test outcomes across the selected runs",
            filters=filters,
            overall=overall,
            breakdowns=[
                Breakdown("Per suite", "Suite", per_suite),
                Breakdown("Per Test Station", "Test Station", per_station),
                Breakdown("Per day", "Day", per_day),
            ],
            generated_at=datetime.utcnow(),
            app_version=settings.BUD_APP_VERSION,
        )
    )
    stem = "bud-test-report"
    if suite:
        stem += f"-{suite}"
    if runner_account:
        stem += f"-{runner_account}"
    return _pdf_response(pdf, _safe_filename(stem))


@router.get("/test-runs/{run_id}.pdf")
async def test_run_report(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_entity: Union[User, Runner] = Depends(get_current_active_entity),
):
    """A single run: its identity, its outcome pie chart, and every result it recorded."""
    run = (
        await db.execute(
            select(TestRun)
            .where(TestRun.id == run_id)
            .options(selectinload(TestRun.runner), selectinload(TestRun.product))
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found")
    require_run_access(current_entity, run)

    results = (
        (
            await db.execute(
                select(TestResult)
                .where(TestResult.test_run_id == run_id)
                .order_by(TestResult.test_class, TestResult.test_method)
                .limit(MAX_RESULT_ROWS)
            )
        )
        .scalars()
        .all()
    )

    # The run's own counters are the source of truth for the chart: they include
    # skips, which individual result rows do not represent.
    overall = Outcome(run.passed_tests, run.failed_tests, run.skipped_tests)

    detail = RunDetail(
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
        run_url=_frontend_run_url(run.id),
    )

    pdf = render_report(
        ReportRequest(
            title="Bud Run Report",
            subtitle=f"BUD-RUN-{run.id} · {run.name}",
            filters=[],
            overall=overall,
            run=detail,
            results=[
                (r.test_class, r.test_method, r.passed, r.duration_seconds or 0.0) for r in results
            ],
            generated_at=datetime.utcnow(),
            app_version=settings.BUD_APP_VERSION,
        )
    )
    return _pdf_response(pdf, _safe_filename(f"bud-run-{run.id}-{run.name}"))
