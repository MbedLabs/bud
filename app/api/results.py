"""
Test results API endpoints.
"""

import hmac
import logging
from datetime import datetime, timezone
from typing import List, Optional, Union

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import decode_access_token
from app.core.config import settings
from app.core.runner_auth import authenticate_runner_token
from app.db import get_db
from app.models import Product, Runner, TestResult, TestRun
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
    # 1. Try JWT first (standard path for UI; runners may use expired JWT + heartbeat)
    if token:
        runner = await authenticate_runner_token(token, db)
        if runner:
            return runner

        payload = decode_access_token(token)
        if payload:
            sub = payload.get("sub")
            entity_type = payload.get("type", "user")
            if sub and entity_type != "runner":
                try:
                    entity_id = int(sub)
                    res = await db.execute(select(User).where(User.id == entity_id))
                    entity = res.scalar_one_or_none()
                    if entity and entity.is_active:
                        return entity
                except ValueError:
                    pass

    # 2. Fallback to Persistent Auth (API Key + Account Name)
    if x_api_key and data.runner_account:
        expected = getattr(settings, "RUNNER_API_KEY", "")
        # Constant-time comparison so the key can't be guessed via timing differences.
        if expected and hmac.compare_digest(x_api_key.encode(), expected.encode()):
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
        # Determine a meaningful name
        suite_name = data.test_suite_name or "Ad-hoc"
        product_name = "Unknown Project"

        if target_product_id:
            res = await db.execute(select(Product.name).where(Product.id == target_product_id))
            p_name = res.scalar_one_or_none()
            if p_name:
                product_name = p_name

        run_name = f"{product_name} - {suite_name}"

        new_run = TestRun(
            runner_id=_current_entity.id if isinstance(_current_entity, Runner) else None,
            product_id=target_product_id,
            status="Completed",
            name=run_name,
            test_case_list=suite_name,
            url_test_software=data.url_test_software,
            ref_test_software=data.ref_test_software or "main",
            url_software_under_test=data.url_software_under_test,
            ref_software_under_test=data.ref_software_under_test,
            started_at=datetime.utcnow(),
            completed_at=None,
        )
        db.add(new_run)
        await db.flush()
        target_run_id = new_run.id
        logger.info(f"Auto-created TestRun {target_run_id} ({run_name})")

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
        # Aggregate at the test-class (test file) level: a class passes
        # only when every method inside it passed.
        class_stats = await db.execute(
            select(
                TestResult.test_class,
                func.min(TestResult.passed.cast(Integer)).label("all_passed"),
            )
            .where(TestResult.test_run_id == target_run_id)
            .group_by(TestResult.test_class)
        )
        rows = class_stats.fetchall()
        total = len(rows)
        passed = sum(1 for r in rows if r.all_passed == 1)

        # Duration stays as the sum across all method rows.
        dur_res = await db.execute(
            select(func.sum(TestResult.duration_seconds)).where(
                TestResult.test_run_id == target_run_id
            )
        )
        duration = dur_res.scalar() or 0.0

        test_run.total_tests = total
        test_run.passed_tests = passed
        test_run.failed_tests = total - passed
        test_run.duration_seconds = duration

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
            message=f"{len(created_results)} method results accepted. {test_run.total_tests} test case(s): {test_run.passed_tests} passed, {test_run.failed_tests} failed.",
        )

    await db.commit()

    # Trigger Bloom Sync in background
    if settings.BLOOM_SYNC_ENABLED:
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
