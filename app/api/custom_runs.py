"""Custom runs: pick test cases in Bud, and let the bench that owns them run it."""

from __future__ import annotations

from datetime import datetime, timezone
from http import HTTPStatus
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    Response,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_active_entity, require_permission
from app.db import get_db
from app.models import ExecutionRequest, Runner, TestRun
from app.models.user import User
from app.schemas import (
    CatalogEntryResponse,
    ClaimedRunCompletion,
    ClaimedRunResponse,
    CustomRunRequest,
    CustomRunResponse,
    ExecutionRequestResponse,
    TestCatalogResponse,
    TestRunResponse,
    UnassignedTest,
)
from app.services.run_events import record_test_run_event
from app.services.run_reports import store_run_reports
from app.services.test_catalog import build_catalog, plan_custom_run

router = APIRouter()
from app.services.notify import notify_run_finished


@router.get("/test-catalog", response_model=TestCatalogResponse)
async def get_test_catalog(
    runner_account: str | None = Query(
        None, description="Only test cases this Test Station has run."
    ),
    suite: str | None = Query(None, description="Only test cases from this suite."),
    db: AsyncSession = Depends(get_db, scope="function"),
    current_entity: User | Runner = Depends(get_current_active_entity),
):
    """Every test case Bud has a record of, and the Test Stations it ran on."""
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
    db: AsyncSession = Depends(get_db, scope="function"),
    current_user: User = Depends(require_permission("custom_runs", "create")),
):
    """Queue a run for each Test Station the selection touches."""

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

    created: list[ExecutionRequest] = []
    for assignment in plan.assignments:
        known = {
            entry.test_path: entry
            for entry in await build_catalog(db, runner_account=assignment.runner_account)
        }
        source_run = await _most_recent_source_run(
            db, [known[path].last_run_id for path in assignment.test_paths]
        )
        suite_names = sorted({known[path].suite for path in assignment.test_paths})
        metadata = {
            "product_id": source_run.product_id if source_run else None,
            "url_test_software": source_run.url_test_software if source_run else None,
            "ref_test_software": source_run.ref_test_software if source_run else "main",
            "url_software_under_test": source_run.url_software_under_test if source_run else None,
            "ref_software_under_test": source_run.ref_software_under_test if source_run else None,
        }
        request = ExecutionRequest(
            requested_by_id=current_user.id,
            runner_id=assignment.runner_id,
            runner_account=assignment.runner_account,
            name=data.name or f"Custom run - {', '.join(suite_names)}",
            selected_tests=assignment.test_paths,
            source_run_id=source_run.id if source_run else None,
            source_metadata=metadata,
        )
        db.add(request)
        created.append(request)
    await db.flush()
    return CustomRunResponse(
        requests=[await _request_response(db, request) for request in created],
        unassigned=[UnassignedTest(**item.__dict__) for item in plan.unassigned],
    )


async def _request_response(
    db: AsyncSession, request: ExecutionRequest
) -> ExecutionRequestResponse:
    """Describe the request using the current station name when it exists."""
    station = await db.get(Runner, request.runner_id) if request.runner_id is not None else None
    return ExecutionRequestResponse(
        id=request.id,
        name=request.name,
        runner_account=station.account if station else request.runner_account,
        selected_tests=request.selected_tests,
        state=request.state,
        run_id=request.claimed_run_id,
        source_metadata=request.source_metadata,
        created_at=request.created_at,
    )


@router.get("/execution-requests", response_model=list[ExecutionRequestResponse])
async def list_execution_requests(
    db: AsyncSession = Depends(get_db, scope="function"),
    current_entity: User | Runner = Depends(get_current_active_entity),
):
    """Read execution requests, scoped to its own requests for a station."""
    query = select(ExecutionRequest).order_by(
        ExecutionRequest.created_at.desc(), ExecutionRequest.id.desc()
    )
    if isinstance(current_entity, Runner):
        query = query.where(ExecutionRequest.runner_id == current_entity.id)
    requests = (await db.execute(query)).scalars().all()
    return [await _request_response(db, request) for request in requests]


@router.get(
    "/execution-requests/{request_id}",
    response_model=ExecutionRequestResponse,
    responses={404: {"description": HTTPStatus(404).phrase}},
)
async def get_execution_request(
    request_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    current_entity: User | Runner = Depends(get_current_active_entity),
):
    """Read a request and its execution link without exposing another station's queue."""
    request = await db.get(ExecutionRequest, request_id)
    if (
        request is None
        or isinstance(current_entity, Runner)
        and request.runner_id != current_entity.id
    ):
        raise HTTPException(status_code=404, detail="Execution request not found")
    return await _request_response(db, request)


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
    db: AsyncSession = Depends(get_db, scope="function"),
    current_entity: User | Runner = Depends(get_current_active_entity),
):
    """Hand this Test Station its next queued run, if it has one."""
    if not isinstance(current_entity, Runner):
        raise HTTPException(status_code=403, detail="Only a Test Station can claim a run")

    claim_id = str(idempotency_key)
    await db.execute(select(Runner.id).where(Runner.id == current_entity.id).with_for_update())
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
    active_claim = await db.scalar(
        select(TestRun.id)
        .where(
            TestRun.runner_id == current_entity.id,
            TestRun.claim_id.is_not(None),
            TestRun.claim_acknowledged_at.is_(None),
        )
        .limit(1)
    )
    if active_claim is not None:
        raise HTTPException(
            status_code=409, detail=f"Test Station already has active claimed run {active_claim}"
        )
    request = (
        await db.execute(
            select(ExecutionRequest)
            .where(
                ExecutionRequest.runner_id == current_entity.id,
                ExecutionRequest.state == "queued",
            )
            .order_by(ExecutionRequest.created_at, ExecutionRequest.id)
            .limit(1)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if request is None:
        return Response(status_code=204)
    run = TestRun(
        name=request.name,
        test_case_list=", ".join(request.selected_tests)[:500],
        selected_tests=request.selected_tests,
        runner_id=current_entity.id,
        status="Running",
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        claim_id=claim_id,
        **request.source_metadata,
    )
    db.add(run)
    await db.flush()
    request.state = "claimed"
    request.claimed_run_id = run.id
    await record_test_run_event(
        db,
        test_run_id=run.id,
        stage="execution",
        status="running",
        title="Run claimed",
        message=f"{current_entity.account} picked up this request.",
        event_metadata={
            "runner_account": current_entity.account,
            "claim_id": claim_id,
            "request_id": request.id,
        },
    )
    await db.flush()
    loaded = (
        await db.execute(
            select(TestRun).options(selectinload(TestRun.runner)).where(TestRun.id == run.id)
        )
    ).scalar_one()
    return ClaimedRunResponse(
        claim_id=claim_id,
        run=TestRunResponse.from_orm_with_runner(loaded),
        selected_tests=loaded.selected_tests,
    )


@router.post(
    "/runners/runs/{run_id}/complete",
    response_model=TestRunResponse,
)
async def complete_claimed_run(
    run_id: int,
    data: ClaimedRunCompletion,
    background_tasks: BackgroundTasks,
    idempotency_key: UUID = Header(alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db, scope="function"),
    current_entity: User | Runner = Depends(get_current_active_entity),
):
    """Record the station's terminal answer for a claimed execution."""
    if not isinstance(current_entity, Runner):
        raise HTTPException(status_code=403, detail="Only a Test Station can complete a claim")

    run = (
        await db.execute(
            select(TestRun)
            .options(selectinload(TestRun.runner))
            .where(TestRun.id == run_id, TestRun.runner_id == current_entity.id)
            .with_for_update()
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

    if run.status not in {"Running", "Completed", "Cancelled"}:
        raise HTTPException(status_code=409, detail=f"Cannot complete a {run.status} claim")

    finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if run.status != "Cancelled":
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
    background_tasks.add_task(notify_run_finished, run.id)

    return TestRunResponse.from_orm_with_runner(run)
