"""Choosing test cases in Bud and having the right bench run them."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.api.auth import get_current_active_entity, get_current_user
from app.api.results import get_uploader_entity
from app.main import app
from app.models import Runner, TestResult, TestRun


def _result(test_class: str, method: str, source_file: str, run_id: int, when: datetime):
    return TestResult(
        test_class=test_class,
        test_method=method,
        passed=True,
        duration_seconds=1.0,
        test_metadata={"test_case_file": source_file, "test_case_class": test_class},
        test_run_id=run_id,
        created_at=when,
    )


@pytest.fixture
def lab(db_session):
    """Two benches with different test cases, and one they share.

    Seed a run on bench-01 (Lab A, two hours ago) with VoltageTest and BootTest, and a run on
    bench-02 (Lab B, an hour ago) with ThermalTest and BootTest. LegacyTest has no source file
    and no importable path.
    """

    async def _make():
        bench_a = Runner(account="bench-01", password_hash="x", token="t1", location="Lab A")
        bench_b = Runner(account="bench-02", password_hash="x", token="t2", location="Lab B")
        db_session.add_all([bench_a, bench_b])
        await db_session.flush()

        now = datetime.utcnow()
        run_a = TestRun(
            name="Nightly",
            test_case_list="Bud_Suite.NIGHTLY",
            status="Completed",
            runner_id=bench_a.id,
            url_test_software="https://git.test/tests.git",
            ref_test_software="release-2026",
            created_at=now - timedelta(hours=2),
        )
        run_b = TestRun(
            name="Powertrain",
            test_case_list="Bud_Suite.POWERTRAIN",
            status="Completed",
            runner_id=bench_b.id,
            created_at=now - timedelta(hours=1),
        )
        db_session.add_all([run_a, run_b])
        await db_session.flush()

        db_session.add_all(
            [
                _result("VoltageTest", "test_idle", "/w/example_voltage.py", run_a.id, now),
                _result("VoltageTest", "test_load", "/w/example_voltage.py", run_a.id, now),
                _result("BootTest", "test_cold", "/w/boot_suite.py", run_a.id, now),
                _result("ThermalTest", "test_soak", "/w/thermal.py", run_b.id, now),
                _result("BootTest", "test_cold", "/w/boot_suite.py", run_b.id, now),
                TestResult(
                    test_class="LegacyTest",
                    test_method="test_old",
                    passed=True,
                    duration_seconds=1.0,
                    test_metadata={"test_case_class": "LegacyTest"},
                    test_run_id=run_a.id,
                    created_at=now,
                ),
            ]
        )
        await db_session.commit()
        return {"a": bench_a, "b": bench_b, "run_a": run_a.id, "run_b": run_b.id}

    return _make


def _as_runner(runner):
    async def override():
        return runner

    app.dependency_overrides[get_current_active_entity] = override
    app.dependency_overrides[get_uploader_entity] = override


def _clear():
    human = app.dependency_overrides.get(get_current_user)
    if human is None:
        app.dependency_overrides.pop(get_current_active_entity, None)
        app.dependency_overrides.pop(get_uploader_entity, None)
    else:
        app.dependency_overrides[get_current_active_entity] = human
        app.dependency_overrides[get_uploader_entity] = human


def _claim(client, claim_id: str = "11111111-1111-4111-8111-111111111111"):
    return client.post(
        "/api/runners/claim-run",
        headers={"Idempotency-Key": claim_id},
    )


class TestTheCatalogue:
    @pytest.mark.asyncio
    async def test_lists_a_test_case_once_however_often_it_ran(self, client, lab):
        await lab()

        entries = client.get("/api/test-catalog").json()["entries"]

        paths = [entry["test_path"] for entry in entries]
        assert paths.count("example_voltage.VoltageTest") == 1

    @pytest.mark.asyncio
    async def test_derives_the_importable_path_the_runner_takes(self, client, lab):
        """The path is module.Class, the form the runner's loader splits on its last dot."""
        await lab()

        paths = {entry["test_path"] for entry in client.get("/api/test-catalog").json()["entries"]}

        assert "example_voltage.VoltageTest" in paths
        assert "thermal.ThermalTest" in paths

    @pytest.mark.asyncio
    async def test_omits_a_result_with_no_source_file(self, client, lab):
        await lab()

        paths = {entry["test_path"] for entry in client.get("/api/test-catalog").json()["entries"]}

        assert not any(path.endswith("LegacyTest") for path in paths)

    @pytest.mark.asyncio
    async def test_names_every_bench_a_case_has_run_on(self, client, lab):
        await lab()

        entries = {e["test_path"]: e for e in client.get("/api/test-catalog").json()["entries"]}

        assert sorted(entries["boot_suite.BootTest"]["runner_accounts"]) == [
            "bench-01",
            "bench-02",
        ]
        assert entries["thermal.ThermalTest"]["runner_accounts"] == ["bench-02"]

    @pytest.mark.asyncio
    async def test_counts_the_methods_inside_a_case(self, client, lab):
        await lab()

        entries = {e["test_path"]: e for e in client.get("/api/test-catalog").json()["entries"]}

        assert entries["example_voltage.VoltageTest"]["method_count"] == 2
        assert entries["thermal.ThermalTest"]["method_count"] == 1

    @pytest.mark.asyncio
    async def test_can_be_narrowed_to_one_bench(self, client, lab):
        await lab()

        entries = client.get("/api/test-catalog?runner_account=bench-02").json()["entries"]

        paths = {entry["test_path"] for entry in entries}
        assert paths == {"boot_suite.BootTest", "thermal.ThermalTest"}

    @pytest.mark.asyncio
    async def test_a_bench_sees_only_its_own(self, client, lab):
        benches = await lab()
        _as_runner(benches["a"])
        try:
            entries = client.get("/api/test-catalog").json()["entries"]
        finally:
            _clear()

        assert "thermal.ThermalTest" not in {entry["test_path"] for entry in entries}

    def test_requires_authentication(self, unauthenticated_client):
        assert unauthenticated_client.get("/api/test-catalog").status_code == 401


class TestQueueingACustomRun:
    @pytest.mark.asyncio
    async def test_request_metadata_comes_from_the_assigned_station(self, client, lab):
        await lab()
        queued = client.post(
            "/api/test-runs/custom",
            json={
                "test_paths": ["boot_suite.BootTest"],
                "runner_account": "bench-01",
            },
        )
        assert queued.status_code == 201, queued.text
        request = queued.json()["requests"][0]
        assert request["runner_account"] == "bench-01"
        assert request["source_metadata"]["url_test_software"] == "https://git.test/tests.git"
        assert request["source_metadata"]["ref_test_software"] == "release-2026"

    @pytest.mark.asyncio
    async def test_human_request_creates_no_execution_evidence(self, client, lab, db_session):
        await lab()
        before = await db_session.scalar(select(func.count()).select_from(TestRun))
        response = client.post(
            "/api/test-runs/custom", json={"test_paths": ["example_voltage.VoltageTest"]}
        )
        assert response.status_code == 201, response.text
        assert await db_session.scalar(select(func.count()).select_from(TestRun)) == before
        body = response.json()
        assert "runs" not in body
        assert body["requests"][0]["state"] == "queued"
        assert body["requests"][0]["run_id"] is None

    @pytest.mark.asyncio
    async def test_queues_one_run_for_a_single_bench_selection(self, client, lab):
        await lab()

        response = client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["example_voltage.VoltageTest", "boot_suite.BootTest"]},
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert len(body["requests"]) == 1
        assert body["requests"][0]["state"] == "queued"
        assert body["unassigned"] == []

    @pytest.mark.asyncio
    async def test_splits_a_selection_that_spans_two_benches(self, client, lab):
        await lab()

        body = client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["example_voltage.VoltageTest", "thermal.ThermalTest"]},
        ).json()

        assert len(body["requests"]) == 2
        assert sorted(run["runner_account"] for run in body["requests"]) == ["bench-01", "bench-02"]

    @pytest.mark.asyncio
    async def test_a_case_that_runs_anywhere_follows_the_ones_that_cannot(self, client, lab):
        await lab()

        body = client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["example_voltage.VoltageTest", "boot_suite.BootTest"]},
        ).json()

        assert len(body["requests"]) == 1
        assert body["requests"][0]["runner_account"] == "bench-01"
        assert sorted(body["requests"][0]["selected_tests"]) == [
            "example_voltage.VoltageTest",
            "boot_suite.BootTest",
        ]

    @pytest.mark.asyncio
    async def test_a_case_that_runs_anywhere_falls_back_to_the_most_recent_bench(self, client, lab):
        await lab()

        body = client.post(
            "/api/test-runs/custom", json={"test_paths": ["boot_suite.BootTest"]}
        ).json()

        assert body["requests"][0]["runner_account"] == "bench-02"

    @pytest.mark.asyncio
    async def test_carries_the_selection_on_the_run(self, client, lab):
        await lab()

        run = client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["example_voltage.VoltageTest"]},
        ).json()["requests"][0]

        assert run["selected_tests"] == ["example_voltage.VoltageTest"]

    @pytest.mark.asyncio
    async def test_inherits_the_repository_of_the_run_that_produced_the_tests(self, client, lab):
        await lab()

        run = client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["example_voltage.VoltageTest"]},
        ).json()["requests"][0]

        assert run["source_metadata"]["url_test_software"] == "https://git.test/tests.git"
        assert run["source_metadata"]["ref_test_software"] == "release-2026"

    @pytest.mark.asyncio
    async def test_pinning_a_bench_keeps_everything_on_it(self, client, lab):
        await lab()

        body = client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["boot_suite.BootTest"], "runner_account": "bench-02"},
        ).json()

        assert len(body["requests"]) == 1
        assert body["requests"][0]["runner_account"] == "bench-02"

    @pytest.mark.asyncio
    async def test_pinning_reports_what_that_bench_has_never_run(self, client, lab):
        await lab()

        body = client.post(
            "/api/test-runs/custom",
            json={
                "test_paths": ["boot_suite.BootTest", "thermal.ThermalTest"],
                "runner_account": "bench-01",
            },
        ).json()

        assert [run["runner_account"] for run in body["requests"]] == ["bench-01"]
        assert [item["test_path"] for item in body["unassigned"]] == ["thermal.ThermalTest"]
        assert "bench-02" in body["unassigned"][0]["reason"]

    @pytest.mark.asyncio
    async def test_reports_a_test_bud_has_never_seen(self, client, lab):
        await lab()

        body = client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["example_voltage.VoltageTest", "nowhere.GhostTest"]},
        ).json()

        assert len(body["requests"]) == 1
        assert body["unassigned"][0]["test_path"] == "nowhere.GhostTest"

    @pytest.mark.asyncio
    async def test_refuses_when_nothing_can_run(self, client, lab):
        await lab()

        response = client.post("/api/test-runs/custom", json={"test_paths": ["nowhere.GhostTest"]})

        assert response.status_code == 422
        assert "nowhere.GhostTest" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_a_duplicate_selection_is_queued_once(self, client, lab):
        await lab()

        run = client.post(
            "/api/test-runs/custom",
            json={
                "test_paths": [
                    "example_voltage.VoltageTest",
                    "example_voltage.VoltageTest",
                ]
            },
        ).json()["requests"][0]

        assert run["selected_tests"] == ["example_voltage.VoltageTest"]

    @pytest.mark.asyncio
    async def test_an_unknown_bench_is_a_404(self, client, lab):
        await lab()

        response = client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["boot_suite.BootTest"], "runner_account": "bench-99"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_a_bench_cannot_queue_work_for_the_lab(self, client, lab):
        benches = await lab()
        _as_runner(benches["a"])
        user_override = app.dependency_overrides.pop(get_current_user, None)
        try:
            response = client.post(
                "/api/test-runs/custom", json={"test_paths": ["boot_suite.BootTest"]}
            )
        finally:
            _clear()
            if user_override is not None:
                app.dependency_overrides[get_current_user] = user_override

        assert response.status_code == 403
        assert response.json()["detail"] == "User privileges required."

    def test_requires_authentication(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/test-runs/custom", json={"test_paths": ["a.B"]}
        )
        assert response.status_code == 401


class TestClaimingAQueuedRun:
    @pytest.mark.asyncio
    async def test_a_bench_takes_its_own_queued_run(self, client, lab):
        benches = await lab()
        client.post("/api/test-runs/custom", json={"test_paths": ["example_voltage.VoltageTest"]})

        _as_runner(benches["a"])
        try:
            response = _claim(client)
        finally:
            _clear()

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["claim_id"] == "11111111-1111-4111-8111-111111111111"
        assert body["selected_tests"] == ["example_voltage.VoltageTest"]
        assert body["run"]["status"] == "Running"

    @pytest.mark.asyncio
    async def test_claiming_marks_it_started(self, client, lab):
        benches = await lab()
        client.post("/api/test-runs/custom", json={"test_paths": ["example_voltage.VoltageTest"]})

        _as_runner(benches["a"])
        try:
            body = _claim(client).json()
        finally:
            _clear()

        assert body["run"]["started_at"] is not None

    @pytest.mark.asyncio
    async def test_a_bench_never_sees_another_benchs_queue(self, client, lab):
        benches = await lab()
        client.post("/api/test-runs/custom", json={"test_paths": ["thermal.ThermalTest"]})

        _as_runner(benches["a"])
        try:
            response = _claim(client)
        finally:
            _clear()

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_an_empty_queue_is_not_an_error(self, client, lab):
        benches = await lab()
        _as_runner(benches["a"])
        try:
            response = _claim(client)
        finally:
            _clear()

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_a_retried_claim_returns_the_original_claim(self, client, lab):
        benches = await lab()
        client.post("/api/test-runs/custom", json={"test_paths": ["example_voltage.VoltageTest"]})

        _as_runner(benches["a"])
        try:
            first = _claim(client)
            second = _claim(client)
        finally:
            _clear()

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["run"]["id"] == first.json()["run"]["id"]

    @pytest.mark.asyncio
    async def test_an_active_claim_blocks_a_second_claim(self, client, lab):
        benches = await lab()
        client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["example_voltage.VoltageTest"], "name": "First"},
        )
        client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["boot_suite.BootTest"], "name": "Second"},
        )

        _as_runner(benches["a"])
        try:
            first = _claim(client)
            second = _claim(client, "22222222-2222-4222-8222-222222222222")
        finally:
            _clear()

        assert first.status_code == 200
        assert second.status_code == 409
        assert "active claimed run" in second.json()["detail"]

    @pytest.mark.asyncio
    async def test_takes_the_oldest_queued_run_first(self, client, lab):
        benches = await lab()
        first = client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["example_voltage.VoltageTest"], "name": "First"},
        ).json()["requests"][0]
        client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["boot_suite.BootTest"], "name": "Second"},
        )

        _as_runner(benches["a"])
        try:
            claimed = _claim(client).json()
        finally:
            _clear()

        assert claimed["run"]["name"] == first["name"]
        assert (
            client.get(f"/api/execution-requests/{first['id']}").json()["run_id"]
            == claimed["run"]["id"]
        )

    @pytest.mark.asyncio
    async def test_a_user_cannot_claim_a_run(self, client, lab):
        await lab()
        client.post("/api/test-runs/custom", json={"test_paths": ["example_voltage.VoltageTest"]})

        response = _claim(client)

        assert response.status_code == 403

    def test_requires_authentication(self, unauthenticated_client):
        assert _claim(unauthenticated_client).status_code == 401


class TestCompletingAClaimedRun:
    @pytest.mark.asyncio
    async def test_station_can_acknowledge_a_cancelled_claim_and_take_next_request(
        self, client, lab
    ):
        benches = await lab()
        for number in range(2):
            queued = client.post(
                "/api/test-runs/custom", json={"test_paths": ["example_voltage.VoltageTest"]}
            )
            assert queued.status_code == 201
        _as_runner(benches["a"])
        try:
            claimed = _claim(client).json()
            run_id = claimed["run"]["id"]
            cancelled = client.patch(f"/api/test-runs/{run_id}", json={"status": "Cancelled"})
            assert cancelled.status_code == 200, cancelled.text
            completed = client.post(
                f"/api/runners/runs/{run_id}/complete",
                headers={"Idempotency-Key": claimed["claim_id"]},
                json={"exit_code": 130},
            )
            assert completed.status_code == 200, completed.text
            assert completed.json()["status"] == "Cancelled"
            assert completed.json()["runner_exit_code"] == 130
            assert completed.json()["claim_acknowledged_at"] is not None
            next_claim = client.post(
                "/api/runners/claim-run",
                headers={"Idempotency-Key": "22222222-2222-4222-8222-222222222222"},
            )
            assert next_claim.status_code == 200, next_claim.text
            assert next_claim.json()["run"]["id"] != run_id
        finally:
            _clear()

    @pytest.mark.asyncio
    async def test_failed_execution_without_results_is_not_a_passed_run(self, client, lab):
        benches = await lab()
        queued = client.post(
            "/api/test-runs/custom",
            json={
                "test_paths": ["example_voltage.VoltageTest"],
                "name": "Unavailable selection",
            },
        )
        assert queued.status_code == 201
        _as_runner(benches["a"])
        try:
            claimed = _claim(client).json()
            response = client.post(
                f"/api/runners/runs/{claimed['run']['id']}/complete",
                headers={"Idempotency-Key": claimed["claim_id"]},
                json={"exit_code": 1},
            )
            assert response.status_code == 200
            stats = client.get("/api/test-runs/stats?suite=Unavailable%20selection").json()
            assert stats["passed_runs"] == 0
            assert stats["failed_runs"] == 1
            assert stats["in_progress_runs"] == 0
            assert stats["total_tests"] == 0
        finally:
            _clear()

    @pytest.mark.asyncio
    async def test_results_do_not_release_an_unacknowledged_claim(self, client, lab):
        benches = await lab()
        payload = {"test_paths": ["example_voltage.VoltageTest"]}
        client.post("/api/test-runs/custom", json=payload)
        client.post("/api/test-runs/custom", json=payload)
        _as_runner(benches["a"])
        try:
            claimed = _claim(client).json()
            run_id = claimed["run"]["id"]
            uploaded = client.post(
                "/api/results",
                json={
                    "test_run_id": run_id,
                    "results": [
                        {"test_class": "VoltageTest", "test_method": "test_idle", "passed": True}
                    ],
                },
            )
            assert uploaded.status_code == 201, uploaded.text
            assert client.get(f"/api/test-runs/{run_id}").json()["status"] == "Completed"
            second_key = {"Idempotency-Key": "22222222-2222-4222-8222-222222222222"}
            blocked = client.post("/api/runners/claim-run", headers=second_key)
            assert blocked.status_code == 409, blocked.text
            completed = client.post(
                f"/api/runners/runs/{run_id}/complete",
                headers={"Idempotency-Key": claimed["claim_id"]},
                json={"exit_code": 0},
            )
            assert completed.status_code == 200, completed.text
            next_claim = client.post("/api/runners/claim-run", headers=second_key)
            assert next_claim.status_code == 200, next_claim.text
            assert next_claim.json()["run"]["id"] != run_id
        finally:
            _clear()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("passed", [True, False])
    async def test_claimed_run_stats_wait_for_the_station_terminal_answer(self, client, lab, passed):
        stations = await lab()
        client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["example_voltage.VoltageTest"], "name": "Awaiting station"},
        )
        _as_runner(stations["a"])
        try:
            claimed = _claim(client).json()
            run_id = claimed["run"]["id"]
            uploaded = client.post(
                "/api/results",
                json={
                    "test_run_id": run_id,
                    "results": [
                        {"test_class": "VoltageTest", "test_method": "test_idle", "passed": passed}
                    ],
                },
            )
            assert uploaded.status_code == 201, uploaded.text
            stats = client.get("/api/test-runs/stats", params={"suite": "Awaiting station"}).json()
            assert stats["passed_runs"] == stats["failed_runs"] == 0
            assert stats["in_progress_runs"] == 1
            completed = client.post(
                f"/api/runners/runs/{run_id}/complete",
                headers={"Idempotency-Key": claimed["claim_id"]},
                json={"exit_code": 0 if passed else 1},
            )
            assert completed.status_code == 200, completed.text
            stats = client.get("/api/test-runs/stats", params={"suite": "Awaiting station"}).json()
            assert stats["passed_runs"] == int(passed)
            assert stats["failed_runs"] == int(not passed)
            assert stats["in_progress_runs"] == 0
        finally:
            _clear()

    @pytest.mark.asyncio
    async def test_a_nonzero_test_exit_still_completes_the_execution(self, client, lab):
        benches = await lab()
        client.post("/api/test-runs/custom", json={"test_paths": ["example_voltage.VoltageTest"]})

        _as_runner(benches["a"])
        try:
            claimed = _claim(client).json()
            run_id = claimed["run"]["id"]
            response = client.post(
                f"/api/runners/runs/{run_id}/complete",
                headers={"Idempotency-Key": claimed["claim_id"]},
                json={"exit_code": 1},
            )
        finally:
            _clear()

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "Completed"
        assert response.json()["runner_exit_code"] == 1
        assert response.json()["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_completion_is_idempotent_and_records_the_runner_answer_once(self, client, lab):
        benches = await lab()
        client.post("/api/test-runs/custom", json={"test_paths": ["example_voltage.VoltageTest"]})

        _as_runner(benches["a"])
        try:
            claimed = _claim(client).json()
            run_id = claimed["run"]["id"]
            headers = {"Idempotency-Key": claimed["claim_id"]}
            payload = {"exit_code": 1, "error": "executor crashed"}
            first = client.post(
                f"/api/runners/runs/{run_id}/complete", headers=headers, json=payload
            )
            second = client.post(
                f"/api/runners/runs/{run_id}/complete", headers=headers, json=payload
            )
            events = client.get(f"/api/test-runs/{run_id}/events").json()
        finally:
            _clear()

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["runner_error"] == "executor crashed"
        assert [event["title"] for event in events].count("Runner acknowledged completion") == 1

    @pytest.mark.asyncio
    async def test_completion_rejects_the_wrong_claim_key(self, client, lab):
        benches = await lab()
        client.post("/api/test-runs/custom", json={"test_paths": ["example_voltage.VoltageTest"]})

        _as_runner(benches["a"])
        try:
            claimed = _claim(client).json()
            response = client.post(
                f"/api/runners/runs/{claimed['run']['id']}/complete",
                headers={"Idempotency-Key": "22222222-2222-4222-8222-222222222222"},
                json={"exit_code": 0},
            )
        finally:
            _clear()

        assert response.status_code == 409


class TestRequestsAndExecutionEvidence:
    """Queued requests remain outside execution evidence until a station claims them."""

    @pytest.mark.asyncio
    async def test_queued_request_is_listed_separately(self, client, lab):
        await lab()
        created = client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["example_voltage.VoltageTest"], "name": "Ad-hoc"},
        ).json()["requests"][0]
        assert client.get("/api/test-runs?status=Pending").json()["runs"] == []
        assert client.get("/api/test-runs/stats").json()["total_runs"] == 2
        requests = client.get("/api/execution-requests").json()
        assert requests == [created]
        assert client.get(f"/api/execution-requests/{created['id']}").json() == created

    @pytest.mark.asyncio
    async def test_station_claim_creates_execution_and_request_link(self, client, lab):
        stations = await lab()
        request = client.post(
            "/api/test-runs/custom", json={"test_paths": ["example_voltage.VoltageTest"]}
        ).json()["requests"][0]
        _as_runner(stations["a"])
        try:
            first = _claim(client)
            second = _claim(client)
        finally:
            _clear()
        assert first.status_code == second.status_code == 200
        assert first.json()["run"]["id"] == second.json()["run"]["id"]
        linked = client.get(f"/api/execution-requests/{request['id']}").json()
        assert linked["state"] == "claimed"
        assert linked["run_id"] == first.json()["run"]["id"]
        assert client.get("/api/test-runs/stats").json()["total_runs"] == 3
        events = client.get(f"/api/test-runs/{linked['run_id']}/events").json()
        assert [event["title"] for event in events] == ["Run claimed"]
        assert events[0]["event_metadata"]["request_id"] == request["id"]

    @pytest.mark.asyncio
    async def test_station_cannot_read_another_stations_request(self, client, lab):
        stations = await lab()
        request = client.post(
            "/api/test-runs/custom", json={"test_paths": ["thermal.ThermalTest"]}
        ).json()["requests"][0]
        _as_runner(stations["a"])
        try:
            assert client.get("/api/execution-requests").json() == []
            assert client.get(f"/api/execution-requests/{request['id']}").status_code == 404
        finally:
            _clear()

    @pytest.mark.asyncio
    async def test_retained_placeholder_is_not_execution_evidence(self, client, lab, db_session):
        stations = await lab()
        placeholder = TestRun(
            name="Old queued request",
            test_case_list="a.B",
            selected_tests=["a.B"],
            status="Pending",
            runner_id=stations["a"].id,
            record_kind="legacy_request",
        )
        db_session.add(placeholder)
        await db_session.commit()
        assert client.get("/api/test-runs/stats").json()["total_runs"] == 2
        assert client.get("/api/test-runs?status=Pending").json()["runs"] == []
        assert client.get(f"/api/test-runs/{placeholder.id}").status_code == 404
        assert (
            "Old queued request" not in client.get("/api/test-runs/filter-options").json()["suites"]
        )
        retained = await db_session.scalar(
            select(TestRun.id)
            .where(TestRun.id == placeholder.id)
            .execution_options(include_legacy_requests=True)
        )
        assert retained == placeholder.id
