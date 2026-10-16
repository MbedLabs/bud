from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import Runner, TestRun


@pytest.mark.asyncio
async def test_create_test_run_persists_test_software_metadata(client, station_request, db_session):
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

    response = station_request("POST", "/api/test-runs", json=payload)
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
    assert [run["id"] for run in body["runs"]] == [
        latest_suite_run.id,
        other_suite_run.id,
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field",
    [
        "name",
        "status",
        "runner_account",
        "duration_seconds",
        "started_at",
        "completed_at",
    ],
)
async def test_run_display_sorting_both_directions_and_missing_values(client, db_session, field):
    base = datetime(2026, 10, 1, 10)
    stations = [
        Runner(
            account="Zulu",
            password_hash="test",
            token="z-test",
            socket_port=55001,
            location="Room B",
        ),
        Runner(
            account="Alpha",
            password_hash="test",
            token="a-test",
            socket_port=55002,
            location="Room A",
        ),
    ]
    db_session.add_all(stations)
    await db_session.flush()
    high = TestRun(
        name="Zulu",
        test_case_list="suite",
        status="Running",
        runner_id=stations[0].id,
        duration_seconds=20,
        started_at=base + timedelta(hours=2),
        completed_at=base + timedelta(hours=3),
        created_at=base,
    )
    low = TestRun(
        name="Alpha",
        test_case_list="suite",
        status="Completed",
        runner_id=stations[1].id,
        duration_seconds=5,
        started_at=base,
        completed_at=base + timedelta(hours=1),
        created_at=base + timedelta(minutes=1),
    )
    db_session.add_all([high, low])
    missing = None
    if field not in ("name", "status"):
        missing = TestRun(
            name="Missing", test_case_list="suite", created_at=base + timedelta(hours=4)
        )
        db_session.add(missing)
    await db_session.commit()
    for direction, expected in [
        ("asc", [low.id, high.id]),
        ("desc", [high.id, low.id]),
    ]:
        response = client.get("/api/test-runs", params={"sort_by": field, "sort_dir": direction})
        assert response.status_code == 200, response.text
        if missing:
            expected.append(missing.id)
        assert [run["id"] for run in response.json()["runs"]] == expected
    if field == "runner_account":
        for filters in [
            {"runner_account": "Alpha"},
            {"location": "Room A"},
            {"runner_account": "Alpha", "location": "Room A", "q": "suite"},
        ]:
            response = client.get(
                "/api/test-runs", params={"sort_by": field, "sort_dir": "asc", **filters}
            )
            assert response.status_code == 200, response.text
            assert response.json()["total"] == 1
            assert [run["id"] for run in response.json()["runs"]] == [low.id]


@pytest.mark.asyncio
async def test_run_sorting_happens_before_filtered_pagination(client, db_session):
    runs = [
        TestRun(name=f"Match {index:02d}", test_case_list="suite", status="Completed")
        for index in reversed(range(30))
    ]
    db_session.add_all(runs + [TestRun(name="Excluded", test_case_list="suite", status="Running")])
    await db_session.commit()
    for offset in [0, 5, 25]:
        response = client.get(
            "/api/test-runs",
            params={
                "q": "Match",
                "status": "Completed",
                "sort_by": "name",
                "sort_dir": "asc",
                "limit": 5,
                "offset": offset,
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 30
        assert [run["name"] for run in response.json()["runs"]] == [
            f"Match {index:02d}" for index in range(offset, offset + 5)
        ]


@pytest.mark.asyncio
async def test_display_sort_keeps_latest_suite_winner_and_stable_ties(client, db_session):
    base = datetime(2026, 10, 1)
    older = TestRun(name="Nightly", test_case_list="suite", created_at=base, duration_seconds=100)
    newer = TestRun(
        name="Nightly",
        test_case_list="suite",
        created_at=base + timedelta(hours=1),
        duration_seconds=5,
    )
    other = TestRun(
        name="Smoke",
        test_case_list="suite",
        created_at=base + timedelta(minutes=30),
        duration_seconds=10,
    )
    db_session.add_all([older, newer, other])
    await db_session.commit()
    for direction, expected in [
        ("asc", [newer.id, other.id]),
        ("desc", [other.id, newer.id]),
    ]:
        response = client.get(
            "/api/test-runs",
            params={
                "latest_per_suite": True,
                "sort_by": "duration_seconds",
                "sort_dir": direction,
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 2
        assert [run["id"] for run in response.json()["runs"]] == expected
    for direction, expected in [
        ("asc", [older.id, newer.id]),
        ("desc", [newer.id, older.id]),
    ]:
        response = client.get(
            "/api/test-runs",
            params={"q": "Nightly", "sort_by": "name", "sort_dir": direction},
        )
        assert [run["id"] for run in response.json()["runs"]] == expected


@pytest.mark.parametrize("params", [{"sort_by": "unknown"}, {"sort_dir": "invalid"}])
def test_invalid_run_sorting_is_rejected(client, params):
    assert client.get("/api/test-runs", params=params).status_code == 422
