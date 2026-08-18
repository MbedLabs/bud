"""Choosing test cases in Bud and having the right bench run them.

The catalogue is built from evidence: Bud does not read a bench's workspace, so
the only honest answer to "where can this run" is "where it has run". That makes
the interesting cases the ones about *placement* - a selection spanning two
benches, a test pinned to a bench that has never had it, a test Bud has never
seen at all - and about the claim being safe when two pollers race.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.api.auth import get_current_active_entity
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

    A location holds several benches and a test case can live on more than one,
    so the fixture has to have both or the placement rules are untested.
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
                _result("VoltageTest", "test_idle", "/w/BigPack_voltage.py", run_a.id, now),
                _result("VoltageTest", "test_load", "/w/BigPack_voltage.py", run_a.id, now),
                _result("BootTest", "test_cold", "/w/boot_suite.py", run_a.id, now),
                _result("ThermalTest", "test_soak", "/w/thermal.py", run_b.id, now),
                # Shared: the same class has run on both benches.
                _result("BootTest", "test_cold", "/w/boot_suite.py", run_b.id, now),
                # No source file, so no importable path: it cannot be selected.
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
    app.dependency_overrides.pop(get_current_active_entity, None)
    app.dependency_overrides.pop(get_uploader_entity, None)


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
        assert paths.count("BigPack_voltage.VoltageTest") == 1

    @pytest.mark.asyncio
    async def test_derives_the_importable_path_the_runner_takes(self, client, lab):
        await lab()

        paths = {entry["test_path"] for entry in client.get("/api/test-catalog").json()["entries"]}

        # The runner's loader splits on the last dot and imports the module, so
        # this is the form it can actually resolve - not the absolute file path
        # the bench reported, which means nothing off that machine.
        assert "BigPack_voltage.VoltageTest" in paths
        assert "thermal.ThermalTest" in paths

    @pytest.mark.asyncio
    async def test_omits_a_result_with_no_source_file(self, client, lab):
        await lab()

        paths = {entry["test_path"] for entry in client.get("/api/test-catalog").json()["entries"]}

        # A class name alone is not importable. Guessing a module for it would
        # queue a run that fails on the bench minutes later.
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

        # A test case carries several methods, and the count is what tells a
        # reader how much they are queueing.
        assert entries["BigPack_voltage.VoltageTest"]["method_count"] == 2
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

        # A station has no business enumerating what the rest of the lab runs,
        # and asking for someone else's does not change the answer.
        assert "thermal.ThermalTest" not in {entry["test_path"] for entry in entries}

    def test_requires_authentication(self, unauthenticated_client):
        assert unauthenticated_client.get("/api/test-catalog").status_code == 401


class TestQueueingACustomRun:
    @pytest.mark.asyncio
    async def test_queues_one_run_for_a_single_bench_selection(self, client, lab):
        await lab()

        response = client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["BigPack_voltage.VoltageTest", "boot_suite.BootTest"]},
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert len(body["runs"]) == 1
        assert body["runs"][0]["status"] == "Pending"
        assert body["unassigned"] == []

    @pytest.mark.asyncio
    async def test_splits_a_selection_that_spans_two_benches(self, client, lab):
        await lab()

        body = client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["BigPack_voltage.VoltageTest", "thermal.ThermalTest"]},
        ).json()

        # Voltage has only ever run on bench-01 and Thermal only on bench-02.
        # Refusing would be the unhelpful answer; this says what it did.
        assert len(body["runs"]) == 2
        assert sorted(run["runner_account"] for run in body["runs"]) == ["bench-01", "bench-02"]

    @pytest.mark.asyncio
    async def test_a_case_that_runs_anywhere_follows_the_ones_that_cannot(self, client, lab):
        await lab()

        body = client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["BigPack_voltage.VoltageTest", "boot_suite.BootTest"]},
        ).json()

        # Voltage has only ever run on bench-01, so it is forced there. Boot has
        # run on both - sending it to bench-02 because that is where it ran most
        # recently would split a selection that did not need splitting.
        assert len(body["runs"]) == 1
        assert body["runs"][0]["runner_account"] == "bench-01"
        assert sorted(body["runs"][0]["selected_tests"]) == [
            "BigPack_voltage.VoltageTest",
            "boot_suite.BootTest",
        ]

    @pytest.mark.asyncio
    async def test_a_case_that_runs_anywhere_falls_back_to_the_most_recent_bench(self, client, lab):
        await lab()

        body = client.post(
            "/api/test-runs/custom", json={"test_paths": ["boot_suite.BootTest"]}
        ).json()

        # Nothing forces a bench here, so the tiebreak applies: bench-02 ran it
        # last, and its workspace is the one most likely to still hold it.
        assert body["runs"][0]["runner_account"] == "bench-02"

    @pytest.mark.asyncio
    async def test_carries_the_selection_on_the_run(self, client, lab):
        await lab()

        run = client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["BigPack_voltage.VoltageTest"]},
        ).json()["runs"][0]

        # The bench cannot resolve this from `test_case_list`: an ordinary run
        # names a list that exists in the workspace, and this selection does not.
        assert run["selected_tests"] == ["BigPack_voltage.VoltageTest"]

    @pytest.mark.asyncio
    async def test_inherits_the_repository_of_the_run_that_produced_the_tests(self, client, lab):
        await lab()

        run = client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["BigPack_voltage.VoltageTest"]},
        ).json()["runs"][0]

        # Otherwise the bench runs whatever happens to be checked out, which is
        # not the code these tests last passed against.
        assert run["url_test_software"] == "https://git.test/tests.git"
        assert run["ref_test_software"] == "release-2026"

    @pytest.mark.asyncio
    async def test_pinning_a_bench_keeps_everything_on_it(self, client, lab):
        await lab()

        body = client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["boot_suite.BootTest"], "runner_account": "bench-02"},
        ).json()

        # BootTest has run on both, so pinning is the only way to say which.
        assert len(body["runs"]) == 1
        assert body["runs"][0]["runner_account"] == "bench-02"

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

        # Silently moving Thermal to bench-02 would defeat the point of pinning.
        assert [run["runner_account"] for run in body["runs"]] == ["bench-01"]
        assert [item["test_path"] for item in body["unassigned"]] == ["thermal.ThermalTest"]
        assert "bench-02" in body["unassigned"][0]["reason"]

    @pytest.mark.asyncio
    async def test_reports_a_test_bud_has_never_seen(self, client, lab):
        await lab()

        body = client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["BigPack_voltage.VoltageTest", "nowhere.GhostTest"]},
        ).json()

        assert len(body["runs"]) == 1
        assert body["unassigned"][0]["test_path"] == "nowhere.GhostTest"

    @pytest.mark.asyncio
    async def test_refuses_when_nothing_can_run(self, client, lab):
        await lab()

        response = client.post("/api/test-runs/custom", json={"test_paths": ["nowhere.GhostTest"]})

        # Creating an empty run would look like success and never execute.
        assert response.status_code == 422
        assert "nowhere.GhostTest" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_a_duplicate_selection_is_queued_once(self, client, lab):
        await lab()

        run = client.post(
            "/api/test-runs/custom",
            json={
                "test_paths": [
                    "BigPack_voltage.VoltageTest",
                    "BigPack_voltage.VoltageTest",
                ]
            },
        ).json()["runs"][0]

        assert run["selected_tests"] == ["BigPack_voltage.VoltageTest"]

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
        try:
            response = client.post(
                "/api/test-runs/custom", json={"test_paths": ["boot_suite.BootTest"]}
            )
        finally:
            _clear()

        assert response.status_code == 403

    def test_requires_authentication(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/test-runs/custom", json={"test_paths": ["a.B"]}
        )
        assert response.status_code == 401


class TestClaimingAQueuedRun:
    @pytest.mark.asyncio
    async def test_a_bench_takes_its_own_queued_run(self, client, lab):
        benches = await lab()
        client.post("/api/test-runs/custom", json={"test_paths": ["BigPack_voltage.VoltageTest"]})

        _as_runner(benches["a"])
        try:
            response = _claim(client)
        finally:
            _clear()

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["claim_id"] == "11111111-1111-4111-8111-111111111111"
        assert body["selected_tests"] == ["BigPack_voltage.VoltageTest"]
        assert body["run"]["status"] == "Running"

    @pytest.mark.asyncio
    async def test_claiming_marks_it_started(self, client, lab):
        benches = await lab()
        client.post("/api/test-runs/custom", json={"test_paths": ["BigPack_voltage.VoltageTest"]})

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

        # The run is queued for bench-02. bench-01 must not be handed it.
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_an_empty_queue_is_not_an_error(self, client, lab):
        benches = await lab()
        _as_runner(benches["a"])
        try:
            response = _claim(client)
        finally:
            _clear()

        # A station polls on an interval; "nothing for you" is the ordinary
        # answer and must not read as a failure in its logs.
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_a_retried_claim_returns_the_original_claim(self, client, lab):
        benches = await lab()
        client.post("/api/test-runs/custom", json={"test_paths": ["BigPack_voltage.VoltageTest"]})

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
            json={"test_paths": ["BigPack_voltage.VoltageTest"], "name": "First"},
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
            json={"test_paths": ["BigPack_voltage.VoltageTest"], "name": "First"},
        ).json()["runs"][0]
        client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["boot_suite.BootTest"], "name": "Second"},
        )

        _as_runner(benches["a"])
        try:
            claimed = _claim(client).json()
        finally:
            _clear()

        assert claimed["run"]["id"] == first["id"]

    @pytest.mark.asyncio
    async def test_a_user_cannot_claim_a_run(self, client, lab):
        await lab()
        client.post("/api/test-runs/custom", json={"test_paths": ["BigPack_voltage.VoltageTest"]})

        response = _claim(client)

        # Claiming means "I am about to execute this", which only a bench can
        # honestly say.
        assert response.status_code == 403

    def test_requires_authentication(self, unauthenticated_client):
        assert _claim(unauthenticated_client).status_code == 401


class TestCompletingAClaimedRun:
    @pytest.mark.asyncio
    async def test_a_nonzero_test_exit_still_completes_the_execution(self, client, lab):
        benches = await lab()
        client.post("/api/test-runs/custom", json={"test_paths": ["BigPack_voltage.VoltageTest"]})

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
        client.post("/api/test-runs/custom", json={"test_paths": ["BigPack_voltage.VoltageTest"]})

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
        client.post("/api/test-runs/custom", json={"test_paths": ["BigPack_voltage.VoltageTest"]})

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


class TestAQueuedRunInTheRestial:
    """A queued run has to behave like a run everywhere else in Bud."""

    @pytest.mark.asyncio
    async def test_appears_in_the_run_list(self, client, lab):
        await lab()
        client.post(
            "/api/test-runs/custom",
            json={"test_paths": ["BigPack_voltage.VoltageTest"], "name": "Ad-hoc"},
        )

        runs = client.get("/api/test-runs?status=Pending").json()["runs"]

        assert [run["name"] for run in runs] == ["Ad-hoc"]

    @pytest.mark.asyncio
    async def test_records_why_it_exists(self, client, lab):
        await lab()
        run = client.post(
            "/api/test-runs/custom", json={"test_paths": ["BigPack_voltage.VoltageTest"]}
        ).json()["runs"][0]

        events = client.get(f"/api/test-runs/{run['id']}/events").json()

        titles = [event["title"] for event in events]
        assert "Custom run queued" in titles
