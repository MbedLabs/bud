"""
Tests for ``POST /api/results`` — the endpoint CI runners (bud_runner)
use to upload test results after executing a test run.

Covers the critical invariant for the CI → Bud pipeline: the backend
accepts the flat ``TestResultCreate`` shape produced by
``bud_runner.api_client._flatten_results``, persists per-method
``assertions`` as JSON, and updates the parent TestRun's counters.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import TestResult, TestRun


@pytest.mark.asyncio
async def test_upload_results_persists_assertions_and_updates_counters(client, db_session):
    # Seed a TestRun that uploaded results will attach to.
    run = TestRun(
        name="CI-1-abcdef",
        test_case_list="Bud_Test_Suite.HIL_TEST_CASES",
        status="Running",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    run_id = run.id

    payload = {
        "test_run_id": run_id,
        "results": [
            {
                "test_class": "VoltageTest",
                "test_method": "bud_check_cell_voltages",
                "passed": False,
                "duration_seconds": 1.23,
                "error_message": "cell 3 out of range",
                "traceback": "Traceback (most recent call last): ...",
                "assertions": [
                    {
                        "passed": True,
                        "message": "cell 1 within tolerance",
                        "expected": "3.7±0.05",
                        "actual": "3.71",
                        "timestamp": "2026-04-18T10:00:00",
                        "metadata": {"cell": 1},
                    },
                    {
                        "passed": False,
                        "message": "cell 3 within tolerance",
                        "expected": "3.7±0.05",
                        "actual": "3.50",
                        "timestamp": "2026-04-18T10:00:01",
                        "metadata": {"cell": 3, "tolerance": "±0.05"},
                    },
                ],
                "metadata": {"station": "hil-01"},
            },
            {
                "test_class": "VoltageTest",
                "test_method": "bud_check_pack_voltage",
                "passed": True,
                "duration_seconds": 0.42,
                "assertions": [
                    {"passed": True, "message": "pack voltage ok"},
                ],
            },
        ],
    }

    response = client.post("/api/results", json=payload)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["count"] == 2

    # HTTP handler commits on another session; refresh our ORM copy of the run.
    await db_session.refresh(run)

    # Rows persisted with assertions JSON intact.
    rows_q = await db_session.execute(
        select(TestResult).where(TestResult.test_run_id == run_id).order_by(TestResult.id)
    )
    rows = rows_q.scalars().all()
    assert len(rows) == 2

    failing = next(r for r in rows if r.test_method == "bud_check_cell_voltages")
    assert failing.passed is False
    assert failing.traceback and "Traceback" in failing.traceback
    assert isinstance(failing.assertions, list) and len(failing.assertions) == 2
    failed_assertion = next(a for a in failing.assertions if a["passed"] is False)
    assert failed_assertion["actual"] == "3.50"
    assert failed_assertion["metadata"]["cell"] == 3

    passing = next(r for r in rows if r.test_method == "bud_check_pack_voltage")
    assert passing.passed is True

    # Counters on TestRun must reflect the 2 uploads.
    assert run.total_tests == 2
    assert run.passed_tests == 1
    assert run.failed_tests == 1


@pytest.mark.asyncio
async def test_upload_results_without_test_run_id_still_accepts_assertions(client, db_session):
    """A sanity check that assertions JSON round-trips even for detached uploads."""
    payload = {
        "results": [
            {
                "test_class": "SmokeTest",
                "test_method": "bud_hello",
                "passed": True,
                "assertions": [{"passed": True, "message": "ok"}],
            }
        ]
    }

    response = client.post("/api/results", json=payload)
    assert response.status_code == 201, response.text
    assert response.json()["count"] == 1
