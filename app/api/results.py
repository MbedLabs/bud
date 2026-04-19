"""
Test results API endpoints.
"""

from typing import List, Union

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_active_entity, get_current_user
from app.db import get_db
from app.models import Runner, TestResult, TestRun
from app.models.user import User
from app.schemas import ResultsUpload, TestResultCreate, TestResultResponse

router = APIRouter()


@router.post("", status_code=201)
async def upload_results(
    data: ResultsUpload,
    db: AsyncSession = Depends(get_db),
    _current_entity: Union[User, Runner] = Depends(get_current_active_entity),
):
    """
    Upload test results.

    Accepts multiple test results and optionally associates them with a test run.
    """
    created_results = []

    for result_data in data.results:
        result = TestResult(
            test_class=result_data.test_class,
            test_method=result_data.test_method,
            passed=result_data.passed,
            duration_seconds=result_data.duration_seconds,
            error_message=result_data.error_message,
            traceback=result_data.traceback,
            assertions=result_data.assertions,
            test_metadata=result_data.metadata,
            work_package_id=result_data.work_package_id,
            test_run_id=data.test_run_id,
        )
        db.add(result)
        created_results.append(result)

    await db.flush()

    # Update test run statistics if associated
    if data.test_run_id:
        result = await db.execute(select(TestRun).where(TestRun.id == data.test_run_id))
        test_run = result.scalar_one_or_none()

        if test_run:
            passed = sum(1 for r in created_results if r.passed)
            failed = len(created_results) - passed

            test_run.total_tests += len(created_results)
            test_run.passed_tests += passed
            test_run.failed_tests += failed

    return {
        "message": f"Uploaded {len(created_results)} results",
        "count": len(created_results),
    }


@router.get("/{run_id}", response_model=List[TestResultResponse])
async def get_results_for_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    Get all results for a test run.
    """
    # Verify test run exists
    run_result = await db.execute(select(TestRun).where(TestRun.id == run_id))
    if not run_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Test run not found")

    # Get results
    result = await db.execute(
        select(TestResult).where(TestResult.test_run_id == run_id).order_by(TestResult.created_at)
    )
    results = result.scalars().all()

    return results


@router.get("/detail/{result_id}", response_model=TestResultResponse)
async def get_result(
    result_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    Get a single test result by ID.
    """
    result = await db.execute(select(TestResult).where(TestResult.id == result_id))
    test_result = result.scalar_one_or_none()

    if not test_result:
        raise HTTPException(status_code=404, detail="Test result not found")

    return test_result
