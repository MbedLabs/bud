from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import TestRun


@pytest.mark.asyncio
async def test_create_test_run_persists_test_software_metadata(client, db_session):
    payload = {
        "test_case_list": "Bud_Test_Suite.HIL_TEST_CASES",
        "test_suite_name": "Nightly Firmware Validation",
        "url_test_software": "https://github.com/example/test-suite-repo",
        "ref_test_software": "tests-abc123def",
        "url_software_under_test": "https://github.com/example/fw-under-test",
        "ref_software_under_test": "fw-abc123def",
        "product_composition_id": 1,
        "status": "Running",
    }

    response = client.post("/api/test-runs", json=payload)
    assert response.status_code == 201, response.text

    run_id = response.json()["id"]
    run_q = await db_session.execute(select(TestRun).where(TestRun.id == run_id))
    created_run = run_q.scalar_one()

    assert created_run.test_case_list == "Bud_Test_Suite.HIL_TEST_CASES"
    assert created_run.name == "Nightly Firmware Validation"
    assert created_run.url_test_software == "https://github.com/example/test-suite-repo"
    assert created_run.ref_test_software == "tests-abc123def"
    assert created_run.url_software_under_test == "https://github.com/example/fw-under-test"
    assert created_run.ref_software_under_test == "fw-abc123def"


@pytest.mark.asyncio
async def test_list_test_runs_can_return_latest_run_per_suite(client, db_session):
    base = datetime(2026, 7, 2, 10, 0, 0)
    older_suite_run = TestRun(
        name="Nightly Firmware Validation",
        test_case_list="Bud_Test_Suite.HIL_TEST_CASES",
        status="Completed",
        created_at=base,
    )
    latest_suite_run = TestRun(
        name="Nightly Firmware Validation",
        test_case_list="Bud_Test_Suite.HIL_TEST_CASES",
        status="Failed",
        created_at=base + timedelta(hours=1),
    )
    other_suite_run = TestRun(
        name="Smoke Validation",
        test_case_list="Bud_Test_Suite.SMOKE",
        status="Completed",
        created_at=base + timedelta(minutes=30),
    )
    db_session.add_all([older_suite_run, latest_suite_run, other_suite_run])
    await db_session.commit()

    response = client.get("/api/test-runs", params={"latest_per_suite": "true"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    assert [run["id"] for run in body["runs"]] == [latest_suite_run.id, other_suite_run.id]
