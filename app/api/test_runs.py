"""
Test runs API endpoints.
"""

from datetime import datetime, timedelta
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_active_entity, require_role
from app.core.run_access import require_mutating_user, require_run_access
from app.db import get_db
from app.models import Artifact, Runner, TestRun, TestRunEvent
from app.models.user import User, UserRole
from app.schemas import (
    TestRunCreate,
    TestRunEventResponse,
    TestRunFilterOptions,
    TestRunList,
    TestRunResponse,
    TestRunStats,
    TestRunUpdate,
)
from app.services.artifact_cleanup import unlink_storage_key
from app.services.run_events import record_test_run_event

router = APIRouter()


@router.post("", response_model=TestRunResponse, status_code=201)
async def create_test_run(
    data: TestRunCreate,
    db: AsyncSession = Depends(get_db),
    _current_entity: Union[User, Runner] = Depends(get_current_active_entity),
):
    """
    Create a new test run.

    This endpoint is called by bud_runner when starting a test suite.
    """
    if isinstance(_current_entity, Runner):
        if data.runner_account and data.runner_account != _current_entity.account:
            raise HTTPException(
                status_code=403, detail="Runner cannot create runs for another runner"
            )
        runner_id = _current_entity.id
    else:
        require_mutating_user(_current_entity)
        runner_id = None

    if isinstance(_current_entity, User) and data.runner_account:
        result = await db.execute(select(Runner).where(Runner.account == data.runner_account))
        runner = result.scalar_one_or_none()
        if runner is None:
            raise HTTPException(status_code=404, detail="Runner not found")
        runner_id = runner.id

    test_run = TestRun(
        name=data.test_suite_name,
        test_case_list=data.test_case_list,
        status=data.status.value,
        url_test_software=data.url_test_software,
        ref_test_software=data.ref_test_software,
        url_software_under_test=data.url_software_under_test,
        ref_software_under_test=data.ref_software_under_test,
        product_id=data.product_composition_id,
        runner_id=runner_id,
        started_at=datetime.utcnow() if data.status.value == "Running" else None,
    )

    db.add(test_run)
    await db.flush()
    await record_test_run_event(
        db,
        test_run_id=test_run.id,
        stage="execution",
        status="running" if data.status.value == "Running" else "queued",
        title="Test run created",
        message=(
            f"{data.test_suite_name} was created from {data.test_case_list}."
            if data.test_case_list
            else None
        ),
        event_metadata={"runner_account": data.runner_account} if data.runner_account else None,
    )
    await db.commit()
    await db.refresh(test_run)

    # Eager-load the runner relationship so the response can expose
    # runner_account without a second round-trip.
    result = await db.execute(
        select(TestRun).options(selectinload(TestRun.runner)).where(TestRun.id == test_run.id)
    )
    test_run = result.scalar_one()

    return TestRunResponse.from_orm_with_runner(test_run)


@router.get("/{run_id}/events", response_model=list[TestRunEventResponse])
async def get_test_run_events(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _current_entity: Union[User, Runner] = Depends(get_current_active_entity),
):
    """
    Get system-reported execution and integration events for a test run.
    """
    run_result = await db.execute(select(TestRun).where(TestRun.id == run_id))
    test_run = run_result.scalar_one_or_none()
    if test_run is None:
        raise HTTPException(status_code=404, detail="Test run not found")
    require_run_access(_current_entity, test_run)

    result = await db.execute(
        select(TestRunEvent)
        .where(TestRunEvent.test_run_id == run_id)
        .order_by(TestRunEvent.sequence, TestRunEvent.created_at, TestRunEvent.id)
    )
    return result.scalars().all()


@router.get("", response_model=TestRunList)
async def list_test_runs(
    status: Optional[str] = Query(None, description="Filter by status"),
    runner_account: Optional[str] = Query(
        None,
        description=(
            "Filter to test runs executed by the given Bud runner account " "(a.k.a. Test Station)."
        ),
    ),
    suite: Optional[str] = Query(None, description="Filter to runs for this test suite name."),
    latest_per_suite: bool = Query(
        False,
        description="When true, return only the latest run for each test suite name.",
    ),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _current_entity: Union[User, Runner] = Depends(get_current_active_entity),
):
    """
    List test runs with optional filtering and pagination.

    ``runner_account`` filters by the Bud runner (Test Station) that executed
    the run. Many suites can share one runner, so this returns every
    ``TestRun`` tied to that runner — not just the latest.
    """
    query = (
        select(TestRun)
        .options(selectinload(TestRun.runner))
        .order_by(TestRun.created_at.desc(), TestRun.id.desc())
    )
    count_query = select(func.count(TestRun.id))

    if isinstance(_current_entity, Runner):
        if runner_account and runner_account != _current_entity.account:
            raise HTTPException(status_code=403, detail="Runner cannot list another runner's runs")
        query = query.where(TestRun.runner_id == _current_entity.id)
        count_query = count_query.where(TestRun.runner_id == _current_entity.id)

    if status:
        query = query.where(TestRun.status == status)
        count_query = count_query.where(TestRun.status == status)

    if suite:
        query = query.where(TestRun.name == suite)
        count_query = count_query.where(TestRun.name == suite)

    if runner_account:
        # Resolve the account → id once; avoids a join per row.
        runner_result = await db.execute(select(Runner.id).where(Runner.account == runner_account))
        runner_id = runner_result.scalar_one_or_none()
        if runner_id is None:
            return TestRunList(runs=[], total=0, limit=limit, offset=offset)
        query = query.where(TestRun.runner_id == runner_id)
        count_query = count_query.where(TestRun.runner_id == runner_id)

    if latest_per_suite:
        result = await db.execute(query)
        latest_runs: list[TestRun] = []
        seen_suite_names: set[str] = set()
        for run in result.scalars().all():
            if run.name in seen_suite_names:
                continue
            seen_suite_names.add(run.name)
            latest_runs.append(run)

        total = len(latest_runs)
        paginated_runs = latest_runs[offset : offset + limit]
        return TestRunList(
            runs=[TestRunResponse.from_orm_with_runner(r) for r in paginated_runs],
            total=total,
            limit=limit,
            offset=offset,
        )

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    runs = result.scalars().all()

    return TestRunList(
        runs=[TestRunResponse.from_orm_with_runner(r) for r in runs],
        total=total,
        limit=limit,
        offset=offset,
    )


async def _scope_conditions(
    db: AsyncSession,
    current_entity: Union[User, Runner],
    *,
    days: Optional[int],
    runner_account: Optional[str],
    suite: Optional[str],
) -> Optional[list]:
    """Build the WHERE terms shared by the dashboard aggregate endpoints.

    Returns ``None`` when the requested Test Station does not exist, which the
    callers translate into an empty result rather than an error.
    """
    conditions: list = []

    if isinstance(current_entity, Runner):
        if runner_account and runner_account != current_entity.account:
            raise HTTPException(
                status_code=403, detail="Runner cannot read another runner's statistics"
            )
        conditions.append(TestRun.runner_id == current_entity.id)
    elif runner_account:
        runner_result = await db.execute(select(Runner.id).where(Runner.account == runner_account))
        runner_id = runner_result.scalar_one_or_none()
        if runner_id is None:
            return None
        conditions.append(TestRun.runner_id == runner_id)

    if suite:
        conditions.append(TestRun.name == suite)

    if days is not None:
        conditions.append(TestRun.created_at >= datetime.utcnow() - timedelta(days=days))

    return conditions


@router.get("/stats", response_model=TestRunStats)
async def get_test_run_stats(
    days: Optional[int] = Query(
        None, ge=1, le=3650, description="Only count runs created within the last N days."
    ),
    runner_account: Optional[str] = Query(
        None, description="Only count runs executed by this Bud runner account (Test Station)."
    ),
    suite: Optional[str] = Query(None, description="Only count runs for this test suite name."),
    db: AsyncSession = Depends(get_db),
    _current_entity: Union[User, Runner] = Depends(get_current_active_entity),
):
    """Aggregate the dashboard counters over every run matching the filters.

    The dashboard used to derive these from the handful of runs on the first page,
    so the pass rate silently depended on the page size. Counting in the database
    keeps the tiles consistent with the full filtered set.
    """
    conditions = await _scope_conditions(
        db, _current_entity, days=days, runner_account=runner_account, suite=suite
    )
    if conditions is None:
        return TestRunStats(
            total_runs=0,
            passed_runs=0,
            failed_runs=0,
            in_progress_runs=0,
            run_pass_rate=0.0,
            total_tests=0,
            passed_tests=0,
            failed_tests=0,
            skipped_tests=0,
            test_pass_rate=0.0,
        )

    passed_run = and_(TestRun.status == "Completed", TestRun.failed_tests == 0)
    failed_run = or_(TestRun.status == "Failed", TestRun.failed_tests > 0)

    query = select(
        func.count(TestRun.id),
        func.count(case((passed_run, 1))),
        func.count(case((failed_run, 1))),
        func.coalesce(func.sum(TestRun.total_tests), 0),
        func.coalesce(func.sum(TestRun.passed_tests), 0),
        func.coalesce(func.sum(TestRun.failed_tests), 0),
        func.coalesce(func.sum(TestRun.skipped_tests), 0),
    )
    if conditions:
        query = query.where(*conditions)

    (
        total_runs,
        passed_runs,
        failed_runs,
        total_tests,
        passed_tests,
        failed_tests,
        skipped_tests,
    ) = (await db.execute(query)).one()

    decided_runs = passed_runs + failed_runs
    return TestRunStats(
        total_runs=total_runs,
        passed_runs=passed_runs,
        failed_runs=failed_runs,
        in_progress_runs=max(total_runs - decided_runs, 0),
        run_pass_rate=round(passed_runs / decided_runs * 100, 1) if decided_runs else 0.0,
        total_tests=total_tests,
        passed_tests=passed_tests,
        failed_tests=failed_tests,
        skipped_tests=skipped_tests,
        test_pass_rate=round(passed_tests / total_tests * 100, 1) if total_tests else 0.0,
    )


@router.get("/filter-options", response_model=TestRunFilterOptions)
async def get_test_run_filter_options(
    days: Optional[int] = Query(
        None, ge=1, le=3650, description="Only consider runs created within the last N days."
    ),
    db: AsyncSession = Depends(get_db),
    _current_entity: Union[User, Runner] = Depends(get_current_active_entity),
):
    """List the suite names and Test Stations that actually appear in test runs."""
    conditions = await _scope_conditions(
        db, _current_entity, days=days, runner_account=None, suite=None
    )
    conditions = conditions or []

    suite_query = select(TestRun.name).distinct().order_by(TestRun.name).limit(500)
    account_query = (
        select(Runner.account)
        .join(TestRun, TestRun.runner_id == Runner.id)
        .distinct()
        .order_by(Runner.account)
        .limit(500)
    )
    if conditions:
        suite_query = suite_query.where(*conditions)
        account_query = account_query.where(*conditions)

    suites = (await db.execute(suite_query)).scalars().all()
    accounts = (await db.execute(account_query)).scalars().all()

    return TestRunFilterOptions(
        suites=[s for s in suites if s],
        runner_accounts=[a for a in accounts if a],
    )


@router.get("/{run_id}", response_model=TestRunResponse)
async def get_test_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _current_entity: Union[User, Runner] = Depends(get_current_active_entity),
):
    """
    Get a test run by ID.
    """
    result = await db.execute(
        select(TestRun).options(selectinload(TestRun.runner)).where(TestRun.id == run_id)
    )
    test_run = result.scalar_one_or_none()

    if not test_run:
        raise HTTPException(status_code=404, detail="Test run not found")
    require_run_access(_current_entity, test_run)

    return TestRunResponse.from_orm_with_runner(test_run)


@router.patch("/{run_id}", response_model=TestRunResponse)
async def update_test_run(
    run_id: int,
    data: TestRunUpdate,
    db: AsyncSession = Depends(get_db),
    _current_entity: Union[User, Runner] = Depends(get_current_active_entity),
):
    """
    Update a test run with results or status.
    """
    result = await db.execute(select(TestRun).where(TestRun.id == run_id))
    test_run = result.scalar_one_or_none()

    if not test_run:
        raise HTTPException(status_code=404, detail="Test run not found")
    require_run_access(_current_entity, test_run, mutate=True)

    # Update fields
    if data.status is not None:
        test_run.status = data.status.value
        if data.status.value in ("Completed", "Cancelled"):
            test_run.completed_at = datetime.utcnow()
        await record_test_run_event(
            db,
            test_run_id=test_run.id,
            stage="execution",
            status=data.status.value.lower(),
            title=f"Run marked {data.status.value}",
            message=(
                "The runner reported the final execution state."
                if data.status.value in ("Completed", "Cancelled")
                else "The runner updated the execution state."
            ),
        )

    if data.total_tests is not None:
        test_run.total_tests = data.total_tests
    if data.passed_tests is not None:
        test_run.passed_tests = data.passed_tests
    if data.failed_tests is not None:
        test_run.failed_tests = data.failed_tests
    if data.skipped_tests is not None:
        test_run.skipped_tests = data.skipped_tests
    if data.duration_seconds is not None:
        test_run.duration_seconds = data.duration_seconds

    await db.commit()
    await db.refresh(test_run)

    result = await db.execute(
        select(TestRun).options(selectinload(TestRun.runner)).where(TestRun.id == test_run.id)
    )
    test_run = result.scalar_one()

    return TestRunResponse.from_orm_with_runner(test_run)


@router.delete("/{run_id}", status_code=204)
async def delete_test_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.admin)),
):
    """
    Delete a test run.
    """
    result = await db.execute(select(TestRun).where(TestRun.id == run_id))
    test_run = result.scalar_one_or_none()

    if not test_run:
        raise HTTPException(status_code=404, detail="Test run not found")

    storage_keys = list(
        (
            await db.scalars(select(Artifact.storage_path).where(Artifact.test_run_id == run_id))
        ).all()
    )
    await db.delete(test_run)
    await db.commit()
    for storage_key in storage_keys:
        unlink_storage_key(storage_key)
