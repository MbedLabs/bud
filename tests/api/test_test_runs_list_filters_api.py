"""Searching and locating test runs, across every page of them."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models import Runner, TestRun


@pytest.fixture
def bench(db_session):
    """Two benches at one location and one at another."""

    async def _make():
        runners = [
            Runner(
                account="station-01",
                password_hash="x",
                token="t1",
                location="Lab A",
                is_active=True,
            ),
            Runner(
                account="station-03",
                password_hash="x",
                token="t3",
                location="Lab A",
                is_active=True,
            ),
            Runner(
                account="station-02",
                password_hash="x",
                token="t2",
                location="Lab B",
                is_active=True,
            ),
        ]
        db_session.add_all(runners)
        await db_session.commit()
        return {r.account: r.id for r in runners}

    return _make


async def _seed_many(db_session, bench_ids: dict[str, int]) -> None:
    """Thirty runs, so nothing under test fits on one page of twenty."""
    now = datetime.utcnow()
    runs = [
        TestRun(
            name=f"Nightly {index:02d}",
            test_case_list="SmokeTests",
            status="Completed",
            runner_id=bench_ids["station-01"],
            created_at=now - timedelta(minutes=index),
        )
        for index in range(30)
    ]
    runs.append(
        TestRun(
            name="Powertrain Endurance",
            test_case_list="EnduranceTests",
            status="Completed",
            runner_id=bench_ids["station-02"],
            created_at=now - timedelta(days=1),
        )
    )
    db_session.add_all(runs)
    await db_session.commit()


class TestSearchReachesEveryPage:
    @pytest.mark.asyncio
    async def test_finds_a_run_that_does_not_fit_on_the_first_page(self, client, db_session, bench):
        """Without the search the run is the 31st row."""
        ids = await bench()
        await _seed_many(db_session, ids)

        first_page = client.get("/api/test-runs?limit=20&offset=0").json()
        assert "Powertrain Endurance" not in [r["name"] for r in first_page["runs"]]

        found = client.get("/api/test-runs?limit=20&q=Powertrain").json()
        assert [r["name"] for r in found["runs"]] == ["Powertrain Endurance"]

    @pytest.mark.asyncio
    async def test_the_count_describes_the_search_not_the_project(self, client, db_session, bench):
        ids = await bench()
        await _seed_many(db_session, ids)

        found = client.get("/api/test-runs?limit=20&q=Powertrain").json()

        assert found["total"] == 1

    @pytest.mark.asyncio
    async def test_matches_the_test_case_list(self, client, db_session, bench):
        ids = await bench()
        await _seed_many(db_session, ids)

        found = client.get("/api/test-runs?limit=20&q=EnduranceTests").json()

        assert [r["name"] for r in found["runs"]] == ["Powertrain Endurance"]

    @pytest.mark.asyncio
    async def test_matches_the_runner_account(self, client, db_session, bench):
        ids = await bench()
        await _seed_many(db_session, ids)

        found = client.get("/api/test-runs?limit=50&q=station-02").json()

        assert [r["name"] for r in found["runs"]] == ["Powertrain Endurance"]

    @pytest.mark.asyncio
    async def test_ignores_case(self, client, db_session, bench):
        ids = await bench()
        await _seed_many(db_session, ids)

        assert client.get("/api/test-runs?q=POWERTRAIN").json()["total"] == 1

    @pytest.mark.asyncio
    async def test_a_term_matching_nothing_returns_nothing(self, client, db_session, bench):
        ids = await bench()
        await _seed_many(db_session, ids)

        body = client.get("/api/test-runs?q=no-such-run").json()

        assert body["runs"] == []
        assert body["total"] == 0


class TestLocationCoversEveryBench:
    @pytest.mark.asyncio
    async def test_keeps_the_runs_of_every_bench_at_the_location(self, client, db_session, bench):
        """Lab A holds two benches, and the runs of both are returned."""
        ids = await bench()
        now = datetime.utcnow()
        db_session.add_all(
            [
                TestRun(
                    name="At station-01",
                    test_case_list="c",
                    status="Completed",
                    runner_id=ids["station-01"],
                    created_at=now,
                ),
                TestRun(
                    name="At station-03",
                    test_case_list="c",
                    status="Completed",
                    runner_id=ids["station-03"],
                    created_at=now - timedelta(minutes=1),
                ),
                TestRun(
                    name="At station-02",
                    test_case_list="c",
                    status="Completed",
                    runner_id=ids["station-02"],
                    created_at=now - timedelta(minutes=2),
                ),
            ]
        )
        await db_session.commit()

        body = client.get("/api/test-runs?location=Lab%20A").json()

        assert sorted(r["name"] for r in body["runs"]) == ["At station-01", "At station-03"]
        assert body["total"] == 2

    @pytest.mark.asyncio
    async def test_reaches_a_run_that_is_not_on_the_first_page(self, client, db_session, bench):
        """The one Lab B run is the oldest of thirty-one."""
        ids = await bench()
        await _seed_many(db_session, ids)

        body = client.get("/api/test-runs?location=Lab%20B&limit=20").json()

        assert [r["name"] for r in body["runs"]] == ["Powertrain Endurance"]
        assert body["total"] == 1

    @pytest.mark.asyncio
    async def test_a_location_with_no_runners_is_empty_not_everything(
        self, client, db_session, bench
    ):
        ids = await bench()
        await _seed_many(db_session, ids)

        body = client.get("/api/test-runs?location=Lab%20Z").json()

        assert body["runs"] == []
        assert body["total"] == 0


class TestLatestPerSuiteStaysInTheDatabase:
    @pytest.mark.asyncio
    async def test_still_returns_one_run_per_suite(self, client, db_session, bench):
        ids = await bench()
        now = datetime.utcnow()
        db_session.add_all(
            [
                TestRun(
                    name="Repeated",
                    test_case_list="c",
                    status="Completed",
                    runner_id=ids["station-01"],
                    created_at=now - timedelta(hours=2),
                ),
                TestRun(
                    name="Repeated",
                    test_case_list="c",
                    status="Completed",
                    runner_id=ids["station-01"],
                    created_at=now,
                ),
                TestRun(
                    name="Other",
                    test_case_list="c",
                    status="Completed",
                    runner_id=ids["station-01"],
                    created_at=now,
                ),
            ]
        )
        await db_session.commit()

        body = client.get("/api/test-runs?latest_per_suite=true").json()

        names = [r["name"] for r in body["runs"]]
        assert names.count("Repeated") == 1
        assert "Other" in names
        assert body["total"] == 2

    @pytest.mark.asyncio
    async def test_keeps_the_newest_of_a_repeated_suite(self, client, db_session, bench):
        ids = await bench()
        now = datetime.utcnow()
        db_session.add_all(
            [
                TestRun(
                    name="Repeated",
                    test_case_list="older",
                    status="Completed",
                    runner_id=ids["station-01"],
                    created_at=now - timedelta(hours=2),
                ),
                TestRun(
                    name="Repeated",
                    test_case_list="newer",
                    status="Completed",
                    runner_id=ids["station-01"],
                    created_at=now,
                ),
            ]
        )
        await db_session.commit()

        runs = client.get("/api/test-runs?latest_per_suite=true").json()["runs"]

        assert [r["test_case_list"] for r in runs] == ["newer"]

    @pytest.mark.asyncio
    async def test_counts_the_deduplicated_set_when_paging(self, client, db_session, bench):
        """Three suites run twice each: six rows, three after deduplication."""
        ids = await bench()
        now = datetime.utcnow()
        db_session.add_all(
            [
                TestRun(
                    name=f"Suite {index}",
                    test_case_list="c",
                    status="Completed",
                    runner_id=ids["station-01"],
                    created_at=now - timedelta(minutes=attempt),
                )
                for index in range(3)
                for attempt in range(2)
            ]
        )
        await db_session.commit()

        body = client.get("/api/test-runs?latest_per_suite=true&limit=2&offset=0").json()

        assert body["total"] == 3
        assert len(body["runs"]) == 2

    @pytest.mark.asyncio
    async def test_narrows_before_deduplicating(self, client, db_session, bench):
        """Both runs share a suite name; the location filter applies before deduplication."""
        ids = await bench()
        now = datetime.utcnow()
        db_session.add_all(
            [
                TestRun(
                    name="Shared",
                    test_case_list="c",
                    status="Completed",
                    runner_id=ids["station-01"],
                    created_at=now,
                ),
                TestRun(
                    name="Shared",
                    test_case_list="c",
                    status="Completed",
                    runner_id=ids["station-02"],
                    created_at=now - timedelta(hours=1),
                ),
            ]
        )
        await db_session.commit()

        body = client.get("/api/test-runs?latest_per_suite=true&location=Lab%20B").json()

        assert body["total"] == 1
        assert body["runs"][0]["runner_account"] == "station-02"
