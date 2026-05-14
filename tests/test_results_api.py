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

from app.models import TestResult, TestRun, TestRunEvent


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

    # Counters roll up at the test-class (file) level: both methods belong to
    # "VoltageTest", and one method failed → the whole class counts as failed.
    assert run.total_tests == 1
    assert run.passed_tests == 0
    assert run.failed_tests == 1

    events_q = await db_session.execute(
        select(TestRunEvent).where(TestRunEvent.test_run_id == run_id).order_by(TestRunEvent.id)
    )
    events = events_q.scalars().all()
    assert any(event.title == "Results uploaded" for event in events)

    events_response = client.get(f"/api/test-runs/{run_id}/events")
    assert events_response.status_code == 200, events_response.text
    assert events_response.json()[0]["title"] == "Results uploaded"


@pytest.mark.asyncio
async def test_upload_results_two_classes_mixed(client, db_session):
    """Two test classes: one all-pass, one mixed → total 2, passed 1, failed 1."""
    run = TestRun(
        name="CI-2-multi",
        test_case_list="Bud_Test_Suite.MULTI",
        status="Running",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)

    payload = {
        "test_run_id": run.id,
        "results": [
            {
                "test_class": "AlphaTest",
                "test_method": "bud_step_one",
                "passed": True,
                "duration_seconds": 0.5,
            },
            {
                "test_class": "AlphaTest",
                "test_method": "bud_step_two",
                "passed": True,
                "duration_seconds": 0.3,
            },
            {
                "test_class": "BetaTest",
                "test_method": "bud_step_one",
                "passed": True,
                "duration_seconds": 0.4,
            },
            {
                "test_class": "BetaTest",
                "test_method": "bud_step_two",
                "passed": False,
                "duration_seconds": 0.6,
                "error_message": "assertion failed",
            },
        ],
    }

    response = client.post("/api/results", json=payload)
    assert response.status_code == 201, response.text

    await db_session.refresh(run)
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
    body = response.json()
    assert body["count"] == 1

    run_id = body["test_run_id"]
    run_q = await db_session.execute(select(TestRun).where(TestRun.id == run_id))
    auto_run = run_q.scalar_one()
    assert auto_run.started_at is not None
    assert auto_run.completed_at is not None
    assert auto_run.completed_at >= auto_run.started_at
