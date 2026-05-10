"""
Test results API endpoints.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Union

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import decode_access_token
from app.core.config import settings
from app.db import get_db
from app.models import Runner, TestResult, TestRun
from app.models.user import User
from app.schemas import ResultsUpload, TestResultCreate, TestResultResponse
from app.services.bloom_sync import sync_results_to_bloom
from app.services.run_events import record_test_run_event

router = APIRouter()
logger = logging.getLogger(__name__)

# Optional OAuth2 scheme for identifying the uploader
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_uploader_entity(
    data: ResultsUpload,
    db: AsyncSession = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme_optional),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Union[User, Runner]:
    """
    Identifies the uploader via either:
    1. A valid JWT (User or Runner).
    2. A valid machine-level X-API-Key + runner_account in payload.
    """
    # 1. Try JWT first (Standard path for UI and existing tests)
    if token:
        payload = decode_access_token(token)
        if payload:
            sub = payload.get("sub")
            entity_type = payload.get("type", "user")
            if sub:
                if entity_type == "runner":
                    res = await db.execute(select(Runner).where(Runner.account == sub))
                    entity = res.scalar_one_or_none()
                else:
                    try:
                        entity_id = int(sub)
                        res = await db.execute(select(User).where(User.id == entity_id))
                        entity = res.scalar_one_or_none()
                    except ValueError:
                        entity = None

                if entity and entity.is_active:
                    return entity

    # 2. Fallback to Persistent Auth (API Key + Account Name)
    if x_api_key and data.runner_account:
        expected = getattr(settings, "RUNNER_API_KEY", "")
        if expected and x_api_key == expected:
            res = await db.execute(select(Runner).where(Runner.account == data.runner_account))
            runner = res.scalar_one_or_none()
            if runner and runner.is_active:
                return runner

    # 3. If no valid auth method found
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide a valid JWT or X-API-Key and runner_account.",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("", status_code=201)
async def upload_results(
    data: ResultsUpload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _current_entity: Union[User, Runner] = Depends(get_uploader_entity),
):
    """
    Upload test results.

    Accepts multiple test results and optionally associates them with a test run.
    Identifies uploader via JWT or persistent machine credentials.
    Automatically creates a TestRun if missing.
    """
    target_run_id = data.test_run_id
    target_product_id = data.product_id

    # AUTO-ALIGNMENT: Create a TestRun if results are uploaded without one
    if not target_run_id:
        new_run = TestRun(
            runner_id=_current_entity.id if isinstance(_current_entity, Runner) else None,
            product_id=target_product_id,
            status="Completed",
            name=f"Ad-hoc Upload ({datetime.now().strftime('%Y-%m-%d %H:%M')})",
            test_case_list="ad-hoc",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        db.add(new_run)
        await db.flush()
        target_run_id = new_run.id
        logger.info(f"Auto-created TestRun {target_run_id} for results upload")

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
            test_run_id=target_run_id,
            product_id=target_product_id,
        )
        db.add(result)
        created_results.append(result)

    await db.flush()

    # Update test run statistics
    res = await db.execute(select(TestRun).where(TestRun.id == target_run_id))
    test_run = res.scalar_one_or_none()

    if test_run:
        # Recalculate totals based on all results for this run
        res = await db.execute(
            select(func.count(TestResult.id), func.sum(TestResult.passed.cast(Integer))).where(
                TestResult.test_run_id == target_run_id
            )
        )
        row = res.fetchone()
        total = row[0] if row else 0
        passed = row[1] if row and row[1] is not None else 0

        test_run.total_tests = total
        test_run.passed_tests = passed
        test_run.failed_tests = total - passed

        # Ensure completion status
        if test_run.status != "Completed":
            test_run.status = "Completed"
        if not test_run.completed_at:
            test_run.completed_at = datetime.utcnow()

        await record_test_run_event(
            db,
            test_run_id=target_run_id,
            stage="results",
            status="completed",
            title="Results uploaded",
            message=f"{len(created_results)} results accepted. Total in run: {test_run.total_tests}",
        )

    await db.commit()

    # Trigger Bloom Sync in background
    # Note: sync_results_to_bloom handles checking if bloom is configured
    background_tasks.add_task(sync_results_to_bloom, target_run_id)

    return {
        "message": f"Uploaded {len(created_results)} results to run {target_run_id}",
        "test_run_id": target_run_id,
        "count": len(created_results),
    }


@router.get("/{run_id}", response_model=List[TestResultResponse])
async def get_results_for_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all results for a test run.
    """
    # Verify test run exists
    run_result = await db.execute(select(TestRun.id).where(TestRun.id == run_id))
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
):
    """
    Get a single test result by ID.
    """
    result = await db.execute(select(TestResult).where(TestResult.id == result_id))
    test_result = result.scalar_one_or_none()

    if not test_result:
        raise HTTPException(status_code=404, detail="Test result not found")

    return test_result
