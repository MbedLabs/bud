"""
Test runs API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import datetime

from app.db import get_db
from app.models import TestRun, Runner
from app.schemas import (
    TestRunCreate,
    TestRunUpdate,
    TestRunResponse,
    TestRunList,
)
from app.api.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("", response_model=TestRunResponse, status_code=201)
async def create_test_run(
    data: TestRunCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    Create a new test run.
    
    This endpoint is called by bud_runner when starting a test suite.
    """
    # Find runner if specified
    runner_id = None
    if data.runner_account:
        result = await db.execute(
            select(Runner).where(Runner.account == data.runner_account)
        )
        runner = result.scalar_one_or_none()
        if runner:
            runner_id = runner.id

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
    await db.flush()
    await db.refresh(test_run)

    return test_run


@router.get("", response_model=TestRunList)
async def list_test_runs(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    List test runs with optional filtering and pagination.
    """
    query = select(TestRun).order_by(TestRun.created_at.desc())
    
    if status:
        query = query.where(TestRun.status == status)
    
    # Get total count
    count_query = select(func.count(TestRun.id))
    if status:
        count_query = count_query.where(TestRun.status == status)
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get paginated results
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    runs = result.scalars().all()

    return TestRunList(
        runs=[TestRunResponse.model_validate(r) for r in runs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{run_id}", response_model=TestRunResponse)
async def get_test_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    Get a test run by ID.
    """
    result = await db.execute(
        select(TestRun).where(TestRun.id == run_id)
    )
    test_run = result.scalar_one_or_none()
    
    if not test_run:
        raise HTTPException(status_code=404, detail="Test run not found")
    
    return test_run


@router.patch("/{run_id}", response_model=TestRunResponse)
async def update_test_run(
    run_id: int,
    data: TestRunUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    Update a test run with results or status.
    """
    result = await db.execute(
        select(TestRun).where(TestRun.id == run_id)
    )
    test_run = result.scalar_one_or_none()
    
    if not test_run:
        raise HTTPException(status_code=404, detail="Test run not found")
    
    # Update fields
    if data.status is not None:
        test_run.status = data.status.value
        if data.status.value in ("Completed", "Failed"):
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
    
    await db.flush()
    await db.refresh(test_run)
    
    return test_run


@router.delete("/{run_id}", status_code=204)
async def delete_test_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    Delete a test run.
    """
    result = await db.execute(
        select(TestRun).where(TestRun.id == run_id)
    )
    test_run = result.scalar_one_or_none()
    
    if not test_run:
        raise HTTPException(status_code=404, detail="Test run not found")
    
    await db.delete(test_run)
