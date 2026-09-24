"""PDF report endpoints."""

from __future__ import annotations

from typing import Optional, Union
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_active_entity
from app.api.company_logo import load_report_logo
from app.api.test_runs import _scope_conditions
from app.core.run_access import require_run_access
from app.db import get_db
from app.models import Runner, TestRun
from app.models.user import User
from app.services.audit import record_audit_event
from app.services.report_pdf import render_report
from app.services.run_reports import build_run_report, build_summary_report

router = APIRouter()


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


@router.get("/test-runs.pdf")
async def test_run_summary_report(
    days: Optional[int] = Query(
        None, ge=1, le=3650, description="Only include runs created within the last N days."
    ),
    runner_account: Optional[str] = Query(
        None, description="Only include runs executed by this Test Station."
    ),
    suite: Optional[str] = Query(None, description="Only include runs for this test suite name."),
    db: AsyncSession = Depends(get_db, scope="function"),
    current_entity: Union[User, Runner] = Depends(get_current_active_entity),
):
    """A filtered test report: overall pie chart plus per-suite, per-station and per-day tables."""
    conditions = await _scope_conditions(
        db, current_entity, days=days, runner_account=runner_account, suite=suite
    )
    # An unknown Test Station scopes to nothing rather than erroring, matching
    # the statistics endpoint.
    conditions = conditions if conditions is not None else [TestRun.id.is_(None)]

    await record_audit_event(
        db,
        "export.generated",
        target_type="report",
        details={"kind": "summary_pdf"},
    )
    pdf = render_report(
        await build_summary_report(
            db, conditions, days=days, runner_account=runner_account, suite=suite
        ),
        await load_report_logo(db),
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
    db: AsyncSession = Depends(get_db, scope="function"),
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
    await require_run_access(db, current_entity, run)

    await record_audit_event(
        db,
        "export.generated",
        target_type="test_run",
        target_id=run.id,
        product_id=run.product_id,
        details={"kind": "run_pdf"},
    )
    pdf = render_report(await build_run_report(db, run), await load_report_logo(db))
    return _pdf_response(pdf, _safe_filename(f"bud-run-{run.id}-{run.name}"))
