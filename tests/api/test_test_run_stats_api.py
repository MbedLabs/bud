from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models import Runner, TestRun


def _run(name: str, *, status: str, passed: int, failed: int, created_at: datetime, runner_id=None):
    return TestRun(
        name=name,
        test_case_list=f"{name}.cases",
        status=status,
        total_tests=passed + failed,
        passed_tests=passed,
        failed_tests=failed,
        skipped_tests=0,
        created_at=created_at,
        runner_id=runner_id,
    )


async def _seed(db_session):
    """Two suites on two stations, spread across time, with a pending run."""
    station_a = Runner(account="lab-station-01", password_hash="x", token="t1")
    station_b = Runner(account="lab-station-02", password_hash="x", token="t2")
    db_session.add_all([station_a, station_b])
    await db_session.flush()

    now = datetime.utcnow()
    db_session.add_all(
        [
            _run(
                "Nightly",
                status="Completed",
                passed=10,
                failed=0,
                created_at=now,
                runner_id=station_a.id,
            ),
            _run(
                "Nightly",
                status="Completed",
                passed=8,
                failed=2,
                created_at=now,
                runner_id=station_a.id,
            ),
            _run(
                "Smoke",
                status="Completed",
                passed=5,
                failed=0,
                created_at=now,
                runner_id=station_b.id,
            ),
            # Older than any 7-day window.
            _run(
                "Nightly",
                status="Completed",
                passed=3,
                failed=0,
                created_at=now - timedelta(days=40),
                runner_id=station_a.id,
            ),
            # Undecided: counted in the total but excluded from the pass rate.
            _run(
                "Smoke",
                status="Running",
                passed=0,
                failed=0,
                created_at=now,
                runner_id=station_b.id,
            ),
        ]
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_stats_aggregate_every_run_not_just_the_first_page(client, db_session):
    await _seed(db_session)

    body = client.get("/api/test-runs/stats").json()

    # All five runs are counted even though a listing page would show fewer.
    assert body["total_runs"] == 5
    assert body["passed_runs"] == 3  # Completed with zero failures
    assert body["failed_runs"] == 1  # the run carrying 2 failed tests
    assert body["in_progress_runs"] == 1  # the Running run is neither
    # Pending work must not drag the rate down: 3 of 4 decided runs passed.
    assert body["run_pass_rate"] == 75.0
    assert body["total_tests"] == 28
    assert body["passed_tests"] == 26
    assert body["failed_tests"] == 2


@pytest.mark.asyncio
async def test_stats_filter_by_time_window(client, db_session):
    await _seed(db_session)

    body = client.get("/api/test-runs/stats", params={"days": 7}).json()

    assert body["total_runs"] == 4  # the 40-day-old run drops out
    assert body["total_tests"] == 25


@pytest.mark.asyncio
async def test_stats_filter_by_suite(client, db_session):
    await _seed(db_session)

    body = client.get("/api/test-runs/stats", params={"suite": "Smoke"}).json()

    assert body["total_runs"] == 2
    assert body["passed_runs"] == 1
    assert body["total_tests"] == 5


@pytest.mark.asyncio
async def test_stats_filter_by_test_station(client, db_session):
    await _seed(db_session)

    body = client.get("/api/test-runs/stats", params={"runner_account": "lab-station-02"}).json()

    assert body["total_runs"] == 2
    assert body["total_tests"] == 5


@pytest.mark.asyncio
async def test_stats_filters_combine(client, db_session):
    await _seed(db_session)

    body = client.get(
        "/api/test-runs/stats",
        params={"days": 7, "suite": "Nightly", "runner_account": "lab-station-01"},
    ).json()

    assert body["total_runs"] == 2
    assert body["passed_runs"] == 1
    assert body["failed_runs"] == 1
    assert body["run_pass_rate"] == 50.0


@pytest.mark.asyncio
async def test_stats_for_unknown_station_are_empty_not_an_error(client, db_session):
    await _seed(db_session)

    response = client.get("/api/test-runs/stats", params={"runner_account": "no-such-station"})

    assert response.status_code == 200
    assert response.json()["total_runs"] == 0
    assert response.json()["run_pass_rate"] == 0.0


@pytest.mark.asyncio
async def test_filter_options_list_suites_and_stations(client, db_session):
    await _seed(db_session)

    body = client.get("/api/test-runs/filter-options").json()

    assert body["suites"] == ["Nightly", "Smoke"]
    assert body["runner_accounts"] == ["lab-station-01", "lab-station-02"]


@pytest.mark.asyncio
async def test_stats_route_is_not_shadowed_by_the_run_id_route(client, db_session):
    """`/stats` must resolve as a literal path, not as run id "stats"."""
    await _seed(db_session)

    assert client.get("/api/test-runs/stats").status_code == 200
    assert client.get("/api/test-runs/filter-options").status_code == 200
