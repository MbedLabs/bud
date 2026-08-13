"""Custom runs: pick test cases in Bud, and let the bench that owns them run it.

The shape here is a queue, not a push. Bud never reaches into a bench - it marks
a run Pending against a Test Station, and the station asks for its next one on
its own schedule. That keeps the direction of every connection outward from the
lab, which is what lets a bench sit behind a firewall with no inbound port and
no control socket exposed to anything.

A test case runs where it has run before. A selection spanning two benches is
therefore two queued runs, one per bench, rather than a refusal - and the reader
is told that is what happened.
"""

from __future__ import annotations

from datetime import datetime
from typing import Union
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_active_entity
from app.core.run_access import require_mutating_user
from app.db import get_db
from app.models import Runner, TestRun
from app.models.user import User
from app.schemas import (
    CatalogEntryResponse,
    ClaimedRunCompletion,
    ClaimedRunResponse,
    CustomRunRequest,
    CustomRunResponse,
    TestCatalogResponse,
    TestRunResponse,
    UnassignedTest,
)
from app.services.run_events import record_test_run_event
from app.services.run_reports import store_run_reports
from app.services.test_catalog import build_catalog, plan_custom_run

router = APIRouter()


@router.get("/test-catalog", response_model=TestCatalogResponse)
async def get_test_catalog(
    runner_account: str | None = Query(
        None, description="Only test cases this Test Station has run."
    ),
    suite: str | None = Query(None, description="Only test cases from this suite."),
    db: AsyncSession = Depends(get_db),
    current_entity: Union[User, Runner] = Depends(get_current_active_entity),
):
    """Every test case Bud has a record of, and the Test Stations it ran on.

    Built from what has executed rather than from a declared inventory: Bud does
    not read the benches' workspaces, so evidence is the only honest source. A
    test case that has never run does not appear, and cannot be selected - there
    would be no way to know which bench holds it.
    """
    if isinstance(current_entity, Runner):
        # A station may see its own catalogue; it has no business enumerating
        # what the rest of the lab runs.
        runner_account = current_entity.account

    entries = await build_catalog(db, runner_account=runner_account, suite=suite)
    return TestCatalogResponse(
        entries=[CatalogEntryResponse(**entry.__dict__) for entry in entries],
        total=len(entries),
    )


@router.post("/test-runs/custom", response_model=CustomRunResponse, status_code=201)
async def create_custom_run(
    data: CustomRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_entity),
):
    """Queue a run for each Test Station the selection touches.

    Nothing is written until the whole selection has been resolved, so a request
    that turns out to be entirely unrunnable leaves no half-built run behind.
    """
    if isinstance(current_user, Runner):
        raise HTTPException(status_code=403, detail="A Test Station cannot queue runs for the lab")
    require_mutating_user(current_user)

    requested: list[str] = []
    for path in data.test_paths:
        cleaned = path.strip()
        if cleaned and cleaned not in requested:
            requested.append(cleaned)
    if not requested:
        raise HTTPException(status_code=422, detail="Select at least one test case.")

    stations = (await db.execute(select(Runner).where(Runner.is_active.is_(True)))).scalars().all()
    runner_ids = {station.account: station.id for station in stations}

    if data.runner_account and data.runner_account not in runner_ids:
        raise HTTPException(
            status_code=404, detail=f"Test Station '{data.runner_account}' is not registered"
        )

    catalog = await build_catalog(db)
    plan = plan_custom_run(
        catalog, requested, runner_ids=runner_ids, pinned_runner=data.runner_account
    )

    if not plan.assignments:
        raise HTTPException(
            status_code=422,
            detail=(
                "None of the selected test cases can be run: "
                + "; ".join(f"{item.test_path} - {item.reason}" for item in plan.unassigned)
            ),
        )

    known = {entry.test_path: entry for entry in catalog}
    created: list[TestRun] = []

    for assignment in plan.assignments:
        # A custom run inherits the repository and ref of the most recent run
        # that produced one of its tests, so the bench checks out the same code
        # it last ran them from rather than whatever happens to be on disk.
        source_run = await _most_recent_source_run(
            db, [known[path].last_run_id for path in assignment.test_paths]
        )
        suite_names = sorted({known[path].suite for path in assignment.test_paths})

        run = TestRun(
            name=data.name or f"Custom run - {', '.join(suite_names)}",
            # Kept human-readable: the authoritative selection is selected_tests,
            # and this is what a reader sees in the run list.
            test_case_list=", ".join(assignment.test_paths)[:500],
            selected_tests=assignment.test_paths,
            status="Pending",
            runner_id=assignment.runner_id,
            url_test_software=source_run.url_test_software if source_run else None,
            ref_test_software=source_run.ref_test_software if source_run else "main",
            url_software_under_test=source_run.url_software_under_test if source_run else None,
            ref_software_under_test=source_run.ref_software_under_test if source_run else None,
            product_id=source_run.product_id if source_run else None,
        )
        db.add(run)
        await db.flush()
        await record_test_run_event(
            db,
            test_run_id=run.id,
            stage="execution",
            status="queued",
            title="Custom run queued",
            message=(
                f"{len(assignment.test_paths)} test case"
                f"{'' if len(assignment.test_paths) == 1 else 's'} queued for "
                f"{assignment.runner_account}."
            ),
            event_metadata={
                "runner_account": assignment.runner_account,
                "selected_tests": assignment.test_paths,
            },
        )
        created.append(run)

    await db.commit()

    runs = []
    for run in created:
        loaded = (
            await db.execute(
                select(TestRun).options(selectinload(TestRun.runner)).where(TestRun.id == run.id)
            )
        ).scalar_one()
        runs.append(TestRunResponse.from_orm_with_runner(loaded))

    return CustomRunResponse(
        runs=runs,
        unassigned=[UnassignedTest(**item.__dict__) for item in plan.unassigned],
    )


async def _most_recent_source_run(db: AsyncSession, run_ids: list[int | None]) -> TestRun | None:
    """The newest of the runs that last produced the selected tests."""
    ids = [run_id for run_id in run_ids if run_id is not None]
    if not ids:
        return None
    return (
        await db.execute(
            select(TestRun)
            .where(TestRun.id.in_(ids))
            .order_by(TestRun.created_at.desc(), TestRun.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


@router.post(
    "/runners/claim-run",
    response_model=ClaimedRunResponse,
    responses={204: {"description": "Nothing queued for this Test Station."}},
)
async def claim_next_run(
    idempotency_key: UUID = Header(alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    current_entity: Union[User, Runner] = Depends(get_current_active_entity),
):
    """Hand this Test Station its next queued run, if it has one.

    Returns 204 when there is nothing waiting, because a station polls on an
    interval and "nothing for you" is the ordinary answer, not an error.

    The claim is a compare-and-set on the status column: two pollers racing -
    the same station restarted, or a duplicated deployment - cannot both take
    the same run, because only the update that still sees `Pending` matches a
    row. Whoever loses simply looks again.
    """
    if not isinstance(current_entity, Runner):
        raise HTTPException(status_code=403, detail="Only a Test Station can claim a run")

    claim_id = str(idempotency_key)
    while True:
        existing = (
            await db.execute(
                select(TestRun)
                .options(selectinload(TestRun.runner))
                .where(
                    TestRun.runner_id == current_entity.id,
                    TestRun.claim_id == claim_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return ClaimedRunResponse(
                claim_id=claim_id,
                run=TestRunResponse.from_orm_with_runner(existing),
                selected_tests=existing.selected_tests,
            )

        active_claim = (
            await db.execute(
                select(TestRun.id)
                .where(
                    TestRun.runner_id == current_entity.id,
                    TestRun.status == "Running",
                    TestRun.claim_id.is_not(None),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if active_claim is not None:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail=f"Test Station already has active claimed run {active_claim}",
            )

        candidate = (
            await db.execute(
                select(TestRun.id)
                .where(TestRun.runner_id == current_entity.id, TestRun.status == "Pending")
                .order_by(TestRun.created_at, TestRun.id)
                .limit(1)
            )
        ).scalar_one_or_none()
        if candidate is None:
            await db.rollback()
            return Response(status_code=204)

        claimed = await db.execute(
            update(TestRun)
            .where(TestRun.id == candidate, TestRun.status == "Pending")
            .values(status="Running", started_at=datetime.utcnow(), claim_id=claim_id)
        )
        if claimed.rowcount == 0:
            # Someone else took it between the select and the update. Look again
            # rather than reporting an empty queue that is not empty.
            await db.rollback()
            continue

        await record_test_run_event(
            db,
            test_run_id=candidate,
            stage="execution",
            status="running",
            title="Run claimed",
            message=f"{current_entity.account} picked up this run.",
            event_metadata={
                "runner_account": current_entity.account,
                "claim_id": claim_id,
            },
        )
        await db.commit()

        run = (
            await db.execute(
                select(TestRun).options(selectinload(TestRun.runner)).where(TestRun.id == candidate)
            )
        ).scalar_one()
        return ClaimedRunResponse(
            claim_id=claim_id,
            run=TestRunResponse.from_orm_with_runner(run),
            selected_tests=run.selected_tests,
        )


@router.post(
    "/runners/runs/{run_id}/complete",
    response_model=TestRunResponse,
)
async def complete_claimed_run(
    run_id: int,
    data: ClaimedRunCompletion,
    idempotency_key: UUID = Header(alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    current_entity: Union[User, Runner] = Depends(get_current_active_entity),
):
    """Record the station's terminal answer for a claimed execution.

    Execution status is always ``Completed`` once the process ends. Individual
    test outcomes remain represented by the result counters and result rows.
    Retrying the same answer is safe and does not append duplicate events.
    """
    if not isinstance(current_entity, Runner):
        raise HTTPException(status_code=403, detail="Only a Test Station can complete a claim")

    run = (
        await db.execute(
            select(TestRun).options(selectinload(TestRun.runner)).where(TestRun.id == run_id)
        )
    ).scalar_one_or_none()
    if run is None or run.runner_id != current_entity.id:
        raise HTTPException(status_code=404, detail="Claimed run not found")

    claim_id = str(idempotency_key)
    if run.claim_id != claim_id:
        raise HTTPException(status_code=409, detail="Claim key does not match this run")

    if run.claim_acknowledged_at is not None:
        if run.runner_exit_code != data.exit_code or run.runner_error != data.error:
            raise HTTPException(
                status_code=409,
                detail="A different terminal answer was already recorded for this claim",
            )
        return TestRunResponse.from_orm_with_runner(run)

    if run.status not in {"Running", "Completed"}:
        raise HTTPException(status_code=409, detail=f"Cannot complete a {run.status} claim")

    finished_at = datetime.utcnow()
    run.status = "Completed"
    run.completed_at = run.completed_at or finished_at
    run.claim_acknowledged_at = finished_at
    run.runner_exit_code = data.exit_code
    run.runner_error = data.error
    await record_test_run_event(
        db,
        test_run_id=run.id,
        stage="execution",
        status="completed",
        title="Runner acknowledged completion",
        message=f"Test Station process exited with code {data.exit_code}.",
        event_metadata={
            "runner_account": current_entity.account,
            "claim_id": claim_id,
            "exit_code": data.exit_code,
            "error": data.error,
        },
    )
    await db.commit()

    # A claimed run reaches Completed here, not through the PATCH.
    await store_run_reports(db, run.id)
    await db.commit()

    return TestRunResponse.from_orm_with_runner(run)
