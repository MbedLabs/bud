from __future__ import annotations

from datetime import datetime

import pytest

from app.api.auth import get_current_active_entity, get_current_user
from app.api.results import get_uploader_entity
from app.main import app
from app.models import Runner, TestResult, TestRun, TestRunEvent
from app.models.user import User, UserRole


async def _seed_runner_runs(db_session):
    runner_a = Runner(
        account="runner-auth-a",
        password_hash="x",
        token="token-a",
        socket_port=53035,
    )
    runner_b = Runner(
        account="runner-auth-b",
        password_hash="x",
        token="token-b",
        socket_port=53036,
    )
    db_session.add_all([runner_a, runner_b])
    await db_session.flush()

    run_a = TestRun(
        name="run-a",
        test_case_list="suite-a",
        status="Running",
        runner_id=runner_a.id,
        started_at=datetime.utcnow(),
    )
    run_b = TestRun(
        name="run-b",
        test_case_list="suite-b",
        status="Running",
        runner_id=runner_b.id,
        started_at=datetime.utcnow(),
    )
    db_session.add_all([run_a, run_b])
    await db_session.flush()
    event_b = TestRunEvent(
        test_run_id=run_b.id,
        sequence=1,
        stage="execution",
        status="running",
        title="Run B started",
    )
    result_b = TestResult(
        test_class="SecretTest",
        test_method="secret_method",
        passed=False,
        traceback="sensitive traceback",
        test_run_id=run_b.id,
    )
    db_session.add_all([event_b, result_b])
    await db_session.commit()
    return runner_a, runner_b, run_a, run_b, result_b


def _override_entity(entity):
    async def override():
        return entity

    app.dependency_overrides[get_current_active_entity] = override
    app.dependency_overrides[get_uploader_entity] = override


def _clear_entity_overrides():
    app.dependency_overrides.pop(get_current_active_entity, None)
    app.dependency_overrides.pop(get_uploader_entity, None)


@pytest.mark.asyncio
async def test_runner_cannot_create_run_for_another_runner(client, db_session):
    runner_a, runner_b, *_ = await _seed_runner_runs(db_session)
    _override_entity(runner_a)
    try:
        response = client.post(
            "/api/test-runs",
            json={
                "test_case_list": "suite",
                "test_suite_name": "cross-owned",
                "runner_account": runner_b.account,
                "status": "Running",
            },
        )
    finally:
        _clear_entity_overrides()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_runner_can_only_list_its_own_runs(client, db_session):
    runner_a, _, run_a, run_b, _ = await _seed_runner_runs(db_session)
    _override_entity(runner_a)
    try:
        response = client.get("/api/test-runs")
    finally:
        _clear_entity_overrides()

    assert response.status_code == 200, response.text
    ids = {run["id"] for run in response.json()["runs"]}
    assert run_a.id in ids
    assert run_b.id not in ids


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["detail", "events", "patch", "results"])
async def test_runner_cannot_access_another_runners_run(client, db_session, operation):
    runner_a, _, _, run_b, _ = await _seed_runner_runs(db_session)
    _override_entity(runner_a)
    try:
        if operation == "detail":
            response = client.get(f"/api/test-runs/{run_b.id}")
        elif operation == "events":
            response = client.get(f"/api/test-runs/{run_b.id}/events")
        elif operation == "patch":
            response = client.patch(
                f"/api/test-runs/{run_b.id}",
                json={"status": "Completed"},
            )
        else:
            response = client.get(f"/api/results/{run_b.id}")
    finally:
        _clear_entity_overrides()

    assert response.status_code in {403, 404}


@pytest.mark.asyncio
async def test_runner_cannot_upload_results_to_another_runners_run(client, db_session):
    runner_a, _, _, run_b, _ = await _seed_runner_runs(db_session)
    _override_entity(runner_a)
    try:
        response = client.post(
            "/api/results",
            json={
                "test_run_id": run_b.id,
                "results": [
                    {
                        "test_class": "CrossRunner",
                        "test_method": "forbidden",
                        "passed": True,
                    }
                ],
            },
        )
    finally:
        _clear_entity_overrides()

    assert response.status_code in {403, 404}


@pytest.mark.asyncio
async def test_result_reads_require_authentication(unauthenticated_client, db_session):
    _, _, _, run_b, result_b = await _seed_runner_runs(db_session)

    list_response = unauthenticated_client.get(f"/api/results/{run_b.id}")
    detail_response = unauthenticated_client.get(f"/api/results/detail/{result_b.id}")

    assert list_response.status_code == 401
    assert detail_response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    ["product-create", "run-create", "run-patch", "run-delete", "results-upload"],
)
async def test_viewer_is_read_only(client, db_session, operation):
    _, _, run_a, _, _ = await _seed_runner_runs(db_session)
    viewer = User(
        id=44,
        email="readonly@example.com",
        full_name="Read Only",
        hashed_password="x",
        role=UserRole.viewer,
        is_active=True,
    )
    db_session.add(viewer)
    await db_session.commit()

    async def override_viewer():
        return viewer

    app.dependency_overrides[get_current_active_entity] = override_viewer
    app.dependency_overrides[get_current_user] = override_viewer
    app.dependency_overrides[get_uploader_entity] = override_viewer
    try:
        if operation == "product-create":
            response = client.post("/api/products", json={"name": "viewer-product"})
        elif operation == "run-create":
            response = client.post(
                "/api/test-runs",
                json={"test_case_list": "suite", "test_suite_name": "viewer-run"},
            )
        elif operation == "run-patch":
            response = client.patch(
                f"/api/test-runs/{run_a.id}",
                json={"status": "Completed"},
            )
        elif operation == "run-delete":
            response = client.delete(f"/api/test-runs/{run_a.id}")
        else:
            response = client.post(
                "/api/results",
                json={
                    "test_run_id": run_a.id,
                    "results": [
                        {
                            "test_class": "ViewerUpload",
                            "test_method": "must_be_denied",
                            "passed": True,
                        }
                    ],
                },
            )
    finally:
        app.dependency_overrides.pop(get_current_active_entity, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_uploader_entity, None)

    assert response.status_code == 403
