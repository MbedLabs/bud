"""HTTP regression checks for station ownership of test-run records."""

from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.api.auth import get_current_active_entity
from app.main import app
from app.models import Runner, TestRun, TestRunEvent
from app.models.user import UserRole


@pytest.mark.asyncio
@pytest.mark.parametrize("role", list(UserRole))
@pytest.mark.parametrize("operation", ["create", "patch", "results-create", "results-update"])
async def test_human_cannot_write_run_records(client, db_session, test_user, role, operation):
    test_user.role = role
    station = Runner(
        account="station-01", password_hash="x", token="station-token", socket_port=53035
    )
    db_session.add(station)
    await db_session.flush()
    run = TestRun(
        name="Station run",
        test_case_list="suite",
        status="Running",
        runner_id=station.id,
        started_at=datetime.utcnow(),
    )
    db_session.add(run)
    await db_session.commit()

    if operation == "create":
        response = client.post(
            "/api/test-runs",
            json={
                "test_suite_name": "Human-created run",
                "test_case_list": "suite",
                "runner_account": station.account,
                "status": "Running",
            },
        )
    elif operation == "patch":
        response = client.patch(
            f"/api/test-runs/{run.id}", json={"status": "Cancelled", "total_tests": 99}
        )
    else:
        payload = {
            "test_suite_name": "Human results",
            "results": [{"test_class": "Suite", "test_method": "test_one", "passed": True}],
        }
        if operation == "results-update":
            payload["test_run_id"] = run.id
        response = client.post("/api/results", json=payload)

    assert response.status_code == 403, response.text
    await db_session.refresh(run)
    assert run.status == "Running"
    assert run.total_tests == 0
    assert run.completed_at is None
    assert await db_session.scalar(select(func.count()).select_from(TestRun)) == 1
    assert await db_session.scalar(select(func.count()).select_from(TestRunEvent)) == 0


@pytest.mark.asyncio
async def test_station_creates_and_updates_its_run(client, db_session):
    station = Runner(
        account="station-01", password_hash="x", token="station-token", socket_port=53035
    )
    db_session.add(station)
    await db_session.commit()

    async def current_station():
        return station

    app.dependency_overrides[get_current_active_entity] = current_station
    response = client.post(
        "/api/test-runs",
        json={
            "test_suite_name": "Station run",
            "test_case_list": "suite",
            "runner_account": station.account,
            "status": "Running",
            "url_test_software": "https://example.com/tests.git",
            "ref_test_software": "release",
        },
    )
    assert response.status_code == 201, response.text
    run_id = response.json()["id"]
    response = client.patch(
        f"/api/test-runs/{run_id}", json={"total_tests": 7, "passed_tests": 5, "failed_tests": 2}
    )
    assert response.status_code == 200, response.text
    run = await db_session.get(TestRun, run_id)
    assert run.runner_id == station.id
    assert (run.total_tests, run.passed_tests, run.failed_tests) == (7, 5, 2)
    assert run.ref_test_software == "release"
