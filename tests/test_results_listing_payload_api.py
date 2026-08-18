"""What a run's result listing carries, and what it deliberately does not.

The run detail page loads every result of a run and renders a per-assertion
table from the `assertions` blob. The trace it shows against a failure comes
from inside that blob. The result's own `traceback` column is a separate full
stack trace per failed method, and no screen reads it - so listing a run was
reading and hydrating a few kilobytes per failure that went nowhere.

These hold the listing to the columns the screen actually uses, and hold the
single-result endpoint to still carrying the trace, because "we stopped sending
it" and "we lost it" look identical from the listing alone.
"""

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
                # The assertion carries its own trace, and this is the one the
                # run detail renders.
                "traceback": "assertion-level trace",
            }
        ],
        "metadata": {"test_case_class": "SmokeTests", "tc_id": "TC-1"},
    }
    base.update(overrides)
    return base


@pytest.fixture
def run_with_a_failure(client):
    run_id = client.post(
        "/api/test-runs",
        json={"test_suite_name": "Nightly", "test_case_list": "SmokeTests"},
    ).json()["id"]
    upload = client.post("/api/results", json={"test_run_id": run_id, "results": [_result()]})
    assert upload.status_code == 201, upload.text
    return run_id


class TestTheListing:
    def test_omits_the_method_traceback(self, client, run_with_a_failure):
        rows = client.get(f"/api/results/{run_with_a_failure}").json()

        assert len(rows) == 1
        assert "traceback" not in rows[0]

    def test_keeps_every_column_the_run_detail_draws(self, client, run_with_a_failure):
        row = client.get(f"/api/results/{run_with_a_failure}").json()[0]

        # The page groups by test case out of `test_metadata`, counts pass and
        # fail out of `assertions`, and labels rows from the class and method.
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

        # This is the trace the reader sees when they expand a failure. Losing
        # it would empty the panel while the listing still looked healthy.
        assert row["assertions"][0]["traceback"] == "assertion-level trace"

    def test_orders_results_as_they_were_recorded(self, client):
        run_id = client.post(
            "/api/test-runs",
            json={"test_suite_name": "Ordered", "test_case_list": "SmokeTests"},
        ).json()["id"]
        client.post(
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

        # Dropping it from the listing must not mean dropping it from the
        # database or from the endpoint that fetches one result in full.
        assert detail["traceback"] == TRACE

    @pytest.mark.asyncio
    async def test_the_column_is_still_written_on_upload(self, run_with_a_failure, db_session):
        stored = (
            await db_session.scalars(
                select(TestResult.traceback).where(TestResult.test_run_id == run_with_a_failure)
            )
        ).first()

        assert stored == TRACE
