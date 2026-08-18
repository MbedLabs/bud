"""Searching and locating test runs, across every page of them.

The run list pages server-side, but its search box and its location picker used
to narrow the page that had already arrived - so a run on page three was
invisible to a search that named it, and picking a location showed only the
runs at that location that happened to be on screen. Meanwhile the footer went
on counting the server's unfiltered total, so the page claimed "1 to 20 of 137"
beside a table holding three.

These drive the endpoint that now answers both questions, with more runs than
fit on a page, because a filter that only works within one page passes every
test written against one page.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models import Runner, TestRun


@pytest.fixture
def bench(db_session):
    """Two benches at one location and one at another.

    A location holds as many runners as the lab has, so a filter on it is a set
    membership test rather than a lookup - and a fixture with one bench per
    location cannot tell the two apart.
    """

    async def _make():
        runners = [
            Runner(
                account="bench-01",
                password_hash="x",
                token="t1",
                location="Lab A",
                is_active=True,
            ),
            Runner(
                account="bench-03",
                password_hash="x",
                token="t3",
                location="Lab A",
                is_active=True,
            ),
            Runner(
                account="bench-02",
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
    """Thirty runs, so nothing under test fits on one page of twenty.

    The one that matters sits last by recency, which puts it on the second
    page: a search that only reads the page it was given cannot find it.
    """
    now = datetime.utcnow()
    runs = [
        TestRun(
            name=f"Nightly {index:02d}",
            test_case_list="SmokeTests",
            status="Completed",
            runner_id=bench_ids["bench-01"],
            created_at=now - timedelta(minutes=index),
        )
        for index in range(30)
    ]
    runs.append(
        TestRun(
            name="Powertrain Endurance",
            test_case_list="EnduranceTests",
            status="Completed",
            runner_id=bench_ids["bench-02"],
            created_at=now - timedelta(days=1),
        )
    )
    db_session.add_all(runs)
    await db_session.commit()


class TestSearchReachesEveryPage:
    @pytest.mark.asyncio
    async def test_finds_a_run_that_does_not_fit_on_the_first_page(self, client, db_session, bench):
        ids = await bench()
        await _seed_many(db_session, ids)

        # Without the search it is the 31st row, so page one cannot hold it.
        first_page = client.get("/api/test-runs?limit=20&offset=0").json()
        assert "Powertrain Endurance" not in [r["name"] for r in first_page["runs"]]

        found = client.get("/api/test-runs?limit=20&q=Powertrain").json()
        assert [r["name"] for r in found["runs"]] == ["Powertrain Endurance"]

    @pytest.mark.asyncio
    async def test_the_count_describes_the_search_not_the_project(self, client, db_session, bench):
        ids = await bench()
        await _seed_many(db_session, ids)

        found = client.get("/api/test-runs?limit=20&q=Powertrain").json()

        # The pager reads this. Reporting 31 beside one row is the bug.
        assert found["total"] == 1

    @pytest.mark.asyncio
    async def test_matches_the_test_case_list(self, client, db_session, bench):
        ids = await bench()
        await _seed_many(db_session, ids)

        found = client.get("/api/test-runs?limit=20&q=EnduranceTests").json()

        # Which is not the run's name, so a name-only search would miss it.
        assert [r["name"] for r in found["runs"]] == ["Powertrain Endurance"]

    @pytest.mark.asyncio
    async def test_matches_the_runner_account(self, client, db_session, bench):
        ids = await bench()
        await _seed_many(db_session, ids)

        found = client.get("/api/test-runs?limit=50&q=bench-02").json()

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
        ids = await bench()
        now = datetime.utcnow()
        db_session.add_all(
            [
                TestRun(
                    name="At bench-01",
                    test_case_list="c",
                    status="Completed",
                    runner_id=ids["bench-01"],
                    created_at=now,
                ),
                TestRun(
                    name="At bench-03",
                    test_case_list="c",
                    status="Completed",
                    runner_id=ids["bench-03"],
                    created_at=now - timedelta(minutes=1),
                ),
                TestRun(
                    name="At bench-02",
                    test_case_list="c",
                    status="Completed",
                    runner_id=ids["bench-02"],
                    created_at=now - timedelta(minutes=2),
                ),
            ]
        )
        await db_session.commit()

        body = client.get("/api/test-runs?location=Lab%20A").json()

        # Lab A holds two benches; taking only the first would drop bench-03's
        # run along with Lab B's.
        assert sorted(r["name"] for r in body["runs"]) == ["At bench-01", "At bench-03"]
        assert body["total"] == 2

    @pytest.mark.asyncio
    async def test_reaches_a_run_that_is_not_on_the_first_page(self, client, db_session, bench):
        ids = await bench()
        await _seed_many(db_session, ids)

        body = client.get("/api/test-runs?location=Lab%20B&limit=20").json()

        # The one Lab B run is the oldest of the thirty-one, so a filter
        # applied to page one finds nothing at all.
        assert [r["name"] for r in body["runs"]] == ["Powertrain Endurance"]
        assert body["total"] == 1

    @pytest.mark.asyncio
    async def test_a_location_with_no_runners_is_empty_not_everything(
        self, client, db_session, bench
    ):
        ids = await bench()
        await _seed_many(db_session, ids)

        body = client.get("/api/test-runs?location=Lab%20Z").json()

        # Falling through to an unfiltered list would be the worst outcome: the
        # reader would believe every run happened at a lab that has no benches.
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
                    runner_id=ids["bench-01"],
                    created_at=now - timedelta(hours=2),
                ),
                TestRun(
                    name="Repeated",
                    test_case_list="c",
                    status="Completed",
                    runner_id=ids["bench-01"],
                    created_at=now,
                ),
                TestRun(
                    name="Other",
                    test_case_list="c",
                    status="Completed",
                    runner_id=ids["bench-01"],
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
                    runner_id=ids["bench-01"],
                    created_at=now - timedelta(hours=2),
                ),
                TestRun(
                    name="Repeated",
                    test_case_list="newer",
                    status="Completed",
                    runner_id=ids["bench-01"],
                    created_at=now,
                ),
            ]
        )
        await db_session.commit()

        runs = client.get("/api/test-runs?latest_per_suite=true").json()["runs"]

        # "Latest" has to mean the most recent, not merely the first one the
        # query happened to reach.
        assert [r["test_case_list"] for r in runs] == ["newer"]

    @pytest.mark.asyncio
    async def test_counts_the_deduplicated_set_when_paging(self, client, db_session, bench):
        ids = await bench()
        now = datetime.utcnow()
        # Three suites, run twice each: six rows, three after deduplication.
        db_session.add_all(
            [
                TestRun(
                    name=f"Suite {index}",
                    test_case_list="c",
                    status="Completed",
                    runner_id=ids["bench-01"],
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
        ids = await bench()
        now = datetime.utcnow()
        db_session.add_all(
            [
                TestRun(
                    name="Shared",
                    test_case_list="c",
                    status="Completed",
                    runner_id=ids["bench-01"],
                    created_at=now,
                ),
                TestRun(
                    name="Shared",
                    test_case_list="c",
                    status="Completed",
                    runner_id=ids["bench-02"],
                    created_at=now - timedelta(hours=1),
                ),
            ]
        )
        await db_session.commit()

        body = client.get("/api/test-runs?latest_per_suite=true&location=Lab%20B").json()

        # Both runs share a suite name. Deduplicating first would keep only
        # bench-01's and then filter it away, leaving Lab B looking idle.
        assert body["total"] == 1
        assert body["runs"][0]["runner_account"] == "bench-02"
