"""
Results API endpoints: upload test results, list results for a run.
"""

import logging
from typing import List, Optional, Union

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status, Header
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import decode_access_token, oauth2_scheme
from app.core.config import settings
from app.db.database import get_db
from app.models import Runner, TestResult, TestRun
from app.models.user import User
from app.schemas.schemas import ResultsUpload, TestResultResponse
from app.services.bloom_sync import sync_results_to_bloom
from app.services.run_events import record_test_run_event

router = APIRouter()
logger = logging.getLogger(__name__)

# Optional OAuth2 scheme for endpoints that support dual auth (JWT or API Key)
from fastapi.security import OAuth2PasswordBearer
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_uploader_entity(
    request: Request,
    data: ResultsUpload,
    db: AsyncSession = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme_optional),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Union[User, Runner]:
    """
    Identifies the entity uploading results.
    Supports:
    1. Valid JWT (User or Runner).
    2. Valid X-API-Key + runner_account in the payload.
    """
    # 1. Try JWT first (Standard Path)
    if token:
        payload = decode_access_token(token)
        if payload:
            sub = payload.get("sub")
            entity_type = payload.get("type", "user")
            if sub:
                if entity_type == "runner":
                    result = await db.execute(select(Runner).where(Runner.account == sub))
                    entity = result.scalar_one_or_none()
                else:
                    try:
                        entity_id = int(sub)
                        result = await db.execute(select(User).where(User.id == entity_id))
                        entity = result.scalar_one_or_none()
                    except ValueError:
                        entity = None
                
                if entity and entity.is_active:
                    return entity

    # 2. Fallback to API Key + Runner Name (Persistent Path)
    if x_api_key and data.runner_account:
        expected = getattr(settings, "RUNNER_API_KEY", "")
        if expected and x_api_key == expected:
            result = await db.execute(select(Runner).where(Runner.account == data.runner_account))
            runner = result.scalar_one_or_none()
            if runner and runner.is_active:
                return runner
            
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials. Provide a valid JWT or X-API-Key + runner_account.",
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
    Identifies the uploader via JWT or persistent X-API-Key + Runner Name.
    """
    created_results = []

    # Identify target product for results not already associated with a run
    target_product_id = data.product_id

    # If we are a runner and uploading results for a run, verify we own the run
    if isinstance(_current_entity, Runner) and data.test_run_id:
        result = await db.execute(select(TestRun).where(TestRun.id == data.test_run_id))
        test_run = result.scalar_one_or_none()
        if test_run and test_run.runner_id != _current_entity.id:
             # Associate run with runner if it wasn't already (e.g. ad-hoc execution)
             if test_run.runner_id is None:
                 test_run.runner_id = _current_entity.id
             else:
                 logger.warning(f"Runner {_current_entity.account} attempting to upload to run {data.test_run_id} owned by runner_id {test_run.runner_id}")

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
            product_id=target_product_id,
        )
        db.add(result)
        created_results.append(result)

    await db.flush()

    # Update test run statistics if associated
    if data.test_run_id:
        result = await db.execute(select(TestRun).where(TestRun.id == data.test_run_id))
        test_run = result.scalar_one_or_none()
        if test_run:
            # Recalculate totals based on all results for this run
            res = await db.execute(
                select(
                    func.count(TestResult.id),
                    func.sum(TestResult.passed.cast(int))
                ).where(TestResult.test_run_id == data.test_run_id)
            )
            total, passed = res.fetchone()
            
            test_run.total_tests = total or 0
            test_run.passed_tests = passed or 0
            test_run.failed_tests = (total or 0) - (passed or 0)
            
            await record_test_run_event(
                db,
                test_run_id=test_run.id,
                stage="execution",
                status="running",
                title="Results uploaded",
                message=f"Uploaded {len(data.results)} new results. Total results: {test_run.total_tests}",
            )

    await db.commit()

    # Sync to Bloom PLM in background
    if settings.BLOOM_SYNC_ENABLED:
        background_tasks.add_task(sync_results_to_bloom, created_results)

    return {"status": "ok", "count": len(created_results)}


@router.get("/run/{test_run_id}", response_model=List[TestResultResponse])
async def list_results_for_run(
    test_run_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    List results for a specific test run.
    """
    result = await db.execute(
        select(TestResult).where(TestResult.test_run_id == test_run_id).order_by(TestResult.created_at.asc())
    )
    return result.scalars().all()
