from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import TestRun


@pytest.mark.asyncio
async def test_create_test_run_persists_software_under_test_metadata(client, db_session):
    payload = {
        "test_case_list": "Bud_Test_Suite.HIL_TEST_CASES",
        "test_suite_name": "Nightly Firmware Validation",
        "url_test_software": "https://github.com/example/fw-under-test",
        "ref_test_software": "abc123def",
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
    assert created_run.url_test_software == "https://github.com/example/fw-under-test"
    assert created_run.ref_test_software == "abc123def"
