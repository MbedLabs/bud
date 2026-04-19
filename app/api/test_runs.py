"""
Test runs API endpoints.
"""

from datetime import datetime
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_active_entity, get_current_user
from app.db import get_db
from app.models import Runner, TestRun
from app.models.user import User
from app.schemas import TestRunCreate, TestRunList, TestRunResponse, TestRunUpdate

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
    # Find runner if specified
    runner_id = None
    if data.runner_account:
        result = await db.execute(select(Runner).where(Runner.account == data.runner_account))
        runner = result.scalar_one_or_none()
        if runner:
            runner_id = runner.id

    # Auto-associate if created by a runner and no account was explicitly provided
    if isinstance(_current_entity, Runner) and not runner_id:
        runner_id = _current_entity.id

    test_run = TestRun(
        name=data.test_suite_name,
        test_case_list=data.test_case_list,
        status=data.status.value,
        url_test_software=data.url_test_software,
        ref_test_software=data.ref_test_software,
        product_id=data.product_composition_id,
        runner_id=runner_id,
        started_at=datetime.utcnow() if data.status.value == "Running" else None,
    )

    db.add(test_run)
    await db.commit()
    await db.refresh(test_run)

    # Eager-load the runner relationship so the response can expose
    # runner_account without a second round-trip.
    result = await db.execute(
        select(TestRun).options(selectinload(TestRun.runner)).where(TestRun.id == test_run.id)
    )
    test_run = result.scalar_one()

    return TestRunResponse.from_orm_with_runner(test_run)


@router.get("", response_model=TestRunList)
async def list_test_runs(
    status: Optional[str] = Query(None, description="Filter by status"),
    runner_account: Optional[str] = Query(
        None,
        description=(
            "Filter to test runs executed by the given Bud runner account " "(a.k.a. Test Station)."
        ),
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
        select(TestRun).options(selectinload(TestRun.runner)).order_by(TestRun.created_at.desc())
    )
    count_query = select(func.count(TestRun.id))

    if status:
        query = query.where(TestRun.status == status)
        count_query = count_query.where(TestRun.status == status)

    if runner_account:
        # Resolve the account → id once; avoids a join per row.
        runner_result = await db.execute(select(Runner.id).where(Runner.account == runner_account))
        runner_id = runner_result.scalar_one_or_none()
        if runner_id is None:
            return TestRunList(runs=[], total=0, limit=limit, offset=offset)
        query = query.where(TestRun.runner_id == runner_id)
        count_query = count_query.where(TestRun.runner_id == runner_id)

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

    # Update fields
    if data.status is not None:
        test_run.status = data.status.value
        if data.status.value in ("Completed", "Cancelled"):
            test_run.completed_at = datetime.utcnow()

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
    _current_user: User = Depends(get_current_user),
):
    """
    Delete a test run.
    """
    result = await db.execute(select(TestRun).where(TestRun.id == run_id))
    test_run = result.scalar_one_or_none()

    if not test_run:
        raise HTTPException(status_code=404, detail="Test run not found")

    await db.delete(test_run)
    await db.commit()
