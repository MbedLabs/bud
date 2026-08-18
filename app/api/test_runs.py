"""
Test runs API endpoints.
"""

from datetime import datetime, timedelta
from typing import Optional, Union

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_active_entity, require_role
from app.api.uploads import get_upload_root
from app.core.run_access import require_mutating_user, require_run_access
from app.db import get_db
from app.models import Artifact, Runner, TestRun, TestRunEvent
from app.models.user import User, UserRole
from app.schemas import (
    ArtifactResponse,
    BloomPublishResponse,
    TestRunCreate,
    TestRunEventResponse,
    TestRunFilterOptions,
    TestRunList,
    TestRunResponse,
    TestRunStats,
    TestRunUpdate,
)
from app.services.artifact_cleanup import unlink_storage_key
from app.services.bloom_publish import (
    BloomNotConfigured,
    BloomProjectNotIdentifiable,
    bloom_credentials,
    build_payload,
    post_to_bloom,
    project_prefix_for_tc_ids,
    publishable_artifacts,
    tc_ids_for_run,
)
from app.services.run_events import record_test_run_event
from app.services.run_reports import frontend_run_url as _frontend_run_url
from app.services.run_reports import store_run_reports

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


@router.get("/{run_id}/artifacts", response_model=list[ArtifactResponse])
async def get_test_run_artifacts(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _current_entity: Union[User, Runner] = Depends(get_current_active_entity),
):
    """
    List the artifacts uploaded against a test run.

    Artifacts could be uploaded and fetched by id, but nothing could enumerate
    them, so a screenshot or a trace attached to a run was only reachable by
    someone who already knew its integer id. Access is the run's own: whoever
    may read the run may read what was attached to it.
    """
    run_result = await db.execute(select(TestRun).where(TestRun.id == run_id))
    test_run = run_result.scalar_one_or_none()
    if test_run is None:
        raise HTTPException(status_code=404, detail="Test run not found")
    require_run_access(_current_entity, test_run)

    result = await db.execute(
        select(Artifact)
        .where(Artifact.test_run_id == run_id)
        .order_by(Artifact.created_at, Artifact.id)
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
    location: Optional[str] = Query(
        None,
        description=(
            "Filter to test runs executed at the given location. A location "
            "usually holds several runners, and this covers all of them."
        ),
    ),
    q: Optional[str] = Query(
        None,
        description="Match the run name, the test case list, or the runner account.",
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
    ``TestRun`` tied to that runner — not just the latest. ``location`` is the
    same question asked of a whole bench: one location, several runners.

    Every filter here narrows the set the count and the page are taken from, so
    the pager describes what the reader is actually looking at.
    """
    conditions = []

    if isinstance(_current_entity, Runner):
        if runner_account and runner_account != _current_entity.account:
            raise HTTPException(status_code=403, detail="Runner cannot list another runner's runs")
        conditions.append(TestRun.runner_id == _current_entity.id)

    if status:
        conditions.append(TestRun.status == status)

    if suite:
        conditions.append(TestRun.name == suite)

    if runner_account:
        # Resolve the account → id once; avoids a join per row.
        runner_result = await db.execute(select(Runner.id).where(Runner.account == runner_account))
        runner_id = runner_result.scalar_one_or_none()
        if runner_id is None:
            return TestRunList(runs=[], total=0, limit=limit, offset=offset)
        conditions.append(TestRun.runner_id == runner_id)

    if location:
        # A location is a set of runners, not one - "every bench in Lab A" is
        # the question this answers, and it has to reach every run at that
        # location rather than the ones that happen to be on this page.
        located = await db.execute(select(Runner.id).where(Runner.location == location))
        located_ids = list(located.scalars().all())
        if not located_ids:
            return TestRunList(runs=[], total=0, limit=limit, offset=offset)
        conditions.append(TestRun.runner_id.in_(located_ids))

    if q and q.strip():
        needle = f"%{q.strip()}%"
        matching_accounts = select(Runner.id).where(Runner.account.ilike(needle))
        conditions.append(
            or_(
                TestRun.name.ilike(needle),
                TestRun.test_case_list.ilike(needle),
                TestRun.runner_id.in_(matching_accounts),
            )
        )

    if latest_per_suite:
        # One row per suite, the most recent. This used to load every test run
        # in the database and dedupe them in Python on every page view - the
        # list screen asks for it by default, so the cost grew with every run
        # ever recorded. A window function does the same in one pass and lets
        # the count and the page stay in SQL.
        ranked = (
            select(
                TestRun.id,
                func.row_number()
                .over(
                    partition_by=TestRun.name,
                    order_by=(TestRun.created_at.desc(), TestRun.id.desc()),
                )
                .label("rank"),
            )
            .where(*conditions)
            .subquery("ranked")
        )
        latest_ids = select(ranked.c.id).where(ranked.c.rank == 1)
        conditions = [TestRun.id.in_(latest_ids)]

    count_query = select(func.count(TestRun.id)).where(*conditions)
    total = (await db.execute(count_query)).scalar()

    query = (
        select(TestRun)
        .options(selectinload(TestRun.runner))
        .where(*conditions)
        .order_by(TestRun.created_at.desc(), TestRun.id.desc())
        .offset(offset)
        .limit(limit)
    )
    runs = (await db.execute(query)).scalars().all()

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

    # After the run's own state is committed; a report never blocks recording it.
    if data.status is not None and data.status.value == "Completed":
        await store_run_reports(db, test_run.id)
        await db.commit()

    result = await db.execute(
        select(TestRun).options(selectinload(TestRun.runner)).where(TestRun.id == test_run.id)
    )
    test_run = result.scalar_one()

    return TestRunResponse.from_orm_with_runner(test_run)


@router.post("/{run_id}/publish-to-bloom", response_model=BloomPublishResponse)
async def publish_run_to_bloom(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_entity),
):
    """Send this run's report documents to Bloom as a Report (RPT) document.

    On request only. Bloom keeps what a project is answerable for, and a suite
    that runs nightly would fill it with a Report a night.
    """
    if isinstance(current_user, Runner):
        raise HTTPException(status_code=403, detail="A Test Station cannot publish to Bloom")
    require_mutating_user(current_user)

    test_run = (await db.execute(select(TestRun).where(TestRun.id == run_id))).scalar_one_or_none()
    if not test_run:
        raise HTTPException(status_code=404, detail="Test run not found")
    require_run_access(current_user, test_run, mutate=True)

    if test_run.status != "Completed":
        raise HTTPException(
            status_code=409,
            detail="Only a completed run can publish a report to Bloom.",
        )

    tc_ids = await tc_ids_for_run(db, run_id)
    try:
        project_prefix = project_prefix_for_tc_ids(tc_ids)
    except BloomProjectNotIdentifiable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        bloom_url, bloom_token = await bloom_credentials(db)
    except BloomNotConfigured as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    artifacts = await publishable_artifacts(db, run_id)
    if not artifacts:
        await store_run_reports(db, run_id)
        await db.commit()
        artifacts = await publishable_artifacts(db, run_id)
        if not artifacts:
            raise HTTPException(
                status_code=409,
                detail="Bud could not generate this completed run's report.",
            )

    files = []
    for artifact in artifacts:
        path = get_upload_root() / artifact.storage_path
        if not path.exists():
            continue
        files.append((artifact.original_filename, artifact.content_type, path.read_bytes()))
    if not files:
        raise HTTPException(
            status_code=409, detail="This run's report files are no longer on disk."
        )

    payload = build_payload(
        test_run,
        project_prefix,
        files,
        tc_ids,
        _frontend_run_url(run_id),
    )

    try:
        published = await post_to_bloom(bloom_url, bloom_token, payload)
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:400] if exc.response is not None else str(exc)
        await record_test_run_event(
            db,
            test_run_id=run_id,
            stage="bloom_sync",
            status="failed",
            title="Publishing to Bloom failed",
            message=detail,
        )
        await db.commit()
        raise HTTPException(status_code=502, detail=f"Bloom refused the report: {detail}") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach Bloom: {exc}") from exc

    await record_test_run_event(
        db,
        test_run_id=run_id,
        stage="bloom_sync",
        status="completed",
        title="Report published to Bloom",
        message=f"{published.get('doc_id') or 'Report'} now holds {len(files)} file(s).",
        event_metadata={
            "project_prefix": project_prefix,
            "bloom_document_id": published.get("document_id"),
            "bloom_doc_id": published.get("doc_id"),
        },
    )
    await db.commit()

    return BloomPublishResponse(
        document_id=published.get("document_id"),
        doc_id=published.get("doc_id"),
        created=bool(published.get("created")),
        published_files=[name for name, _, _ in files],
    )


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
