"""What a run's result listing carries, and what it deliberately does not."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import TestResult

TRACE = 'Traceback (most recent call last):\n  File "t.py", line 9\nAssertionError: 3 != 4'


def _result(passed: bool = False, **overrides) -> dict:
    base = {
        "test_class": "SmokeTests",
        "test_method": "test_boot",
        "passed": passed,
        "duration_seconds": 1.5,
        "error_message": "3 != 4",
        "traceback": TRACE,
        "assertions": [
            {
                "passed": False,
                "message": "3 != 4",
                "traceback": "assertion-level trace",
            }
        ],
        "metadata": {"test_case_class": "SmokeTests", "tc_id": "TC-1"},
    }
    base.update(overrides)
    return base


@pytest.fixture
def run_with_a_failure(client, station_request):
    run_id = station_request(
        "POST",
        "/api/test-runs",
        json={"test_suite_name": "Nightly", "test_case_list": "SmokeTests"},
    ).json()["id"]
    upload = station_request(
        "POST", "/api/results", json={"test_run_id": run_id, "results": [_result()]}
    )
    assert upload.status_code == 201, upload.text
    return run_id


class TestTheListing:
    def test_omits_the_method_traceback(self, client, run_with_a_failure):
        rows = client.get(f"/api/results/{run_with_a_failure}").json()

        assert len(rows) == 1
        assert "traceback" not in rows[0]

    def test_keeps_every_column_the_run_detail_draws(self, client, run_with_a_failure):
        row = client.get(f"/api/results/{run_with_a_failure}").json()[0]

        for field in (
            "id",
            "test_class",
            "test_method",
            "passed",
            "duration_seconds",
            "error_message",
            "assertions",
            "test_metadata",
            "work_package_id",
            "created_at",
            "test_run_id",
        ):
            assert field in row, field

    def test_keeps_the_trace_that_lives_inside_an_assertion(self, client, run_with_a_failure):
        row = client.get(f"/api/results/{run_with_a_failure}").json()[0]

        assert row["assertions"][0]["traceback"] == "assertion-level trace"

    def test_orders_results_as_they_were_recorded(self, client, station_request):
        run_id = station_request(
            "POST",
            "/api/test-runs",
            json={"test_suite_name": "Ordered", "test_case_list": "SmokeTests"},
        ).json()["id"]
        station_request(
            "POST",
            "/api/results",
            json={
                "test_run_id": run_id,
                "results": [
                    _result(test_method="test_a", passed=True),
                    _result(test_method="test_b", passed=True),
                ],
            },
        )

        methods = [row["test_method"] for row in client.get(f"/api/results/{run_id}").json()]

        assert methods == ["test_a", "test_b"]

    def test_an_unknown_run_is_still_a_404(self, client):
        assert client.get("/api/results/999999").status_code == 404


class TestTheSingleResult:
    @pytest.mark.asyncio
    async def test_still_carries_the_method_traceback(self, client, run_with_a_failure, db_session):
        result_id = (
            await db_session.scalars(
                select(TestResult.id).where(TestResult.test_run_id == run_with_a_failure)
            )
        ).first()

        detail = client.get(f"/api/results/detail/{result_id}").json()

        assert detail["traceback"] == TRACE

    @pytest.mark.asyncio
    async def test_the_column_is_still_written_on_upload(self, run_with_a_failure, db_session):
        stored = (
            await db_session.scalars(
                select(TestResult.traceback).where(TestResult.test_run_id == run_with_a_failure)
            )
        ).first()

        assert stored == TRACE
