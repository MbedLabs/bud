"""Station claims create exactly one execution under concurrent authenticated requests."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest

from tests.pg.conftest import unique_name
from tests.pg.test_integration_real_auth import _login, _station_headers


def _queue(client):
    human = {"Authorization": f"Bearer {_login(client)}"}
    station = _station_headers(client)
    module = unique_name("execution").replace(" ", "_")
    result = client.post(
        "/api/results",
        headers=station,
        json={
            "test_suite_name": module,
            "results": [
                {
                    "test_class": "Smoke",
                    "test_method": "test_boot",
                    "passed": True,
                    "metadata": {"test_case_file": f"{module}.py", "test_case_class": "Smoke"},
                }
            ],
        },
    )
    assert result.status_code == 201, result.text
    requests = []
    for number in range(2):
        queued = client.post(
            "/api/test-runs/custom",
            headers=human,
            json={"test_paths": [f"{module}.Smoke"], "name": f"{module} request {number}"},
        )
        assert queued.status_code == 201, queued.text
        requests.append(queued.json()["requests"][0])
    runs = client.get("/api/test-runs", headers=human).json()["runs"]
    assert not any(run["name"].startswith(f"{module} request") for run in runs)
    return human, station, requests


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_claims_commit_one_execution(client, same_key):
    human, station, requests = _queue(client)
    keys = [str(uuid4()), str(uuid4())]
    if same_key:
        keys[1] = keys[0]
    barrier = Barrier(2)

    def claim(key):
        barrier.wait(timeout=10)
        return client.post("/api/runners/claim-run", headers={**station, "Idempotency-Key": key})

    with ThreadPoolExecutor(max_workers=2) as workers:
        responses = list(workers.map(claim, keys))
    assert sorted(response.status_code for response in responses) == (
        [200, 200] if same_key else [200, 409]
    )
    claimed = [response.json() for response in responses if response.status_code == 200]
    assert len({body["run"]["id"] for body in claimed}) == 1
    run_id = claimed[0]["run"]["id"]
    claim_id = claimed[0]["claim_id"]
    first = client.get(f"/api/execution-requests/{requests[0]['id']}", headers=human).json()
    second = client.get(f"/api/execution-requests/{requests[1]['id']}", headers=human).json()
    assert (first["state"], first["run_id"]) == ("claimed", run_id)
    assert (second["state"], second["run_id"]) == ("queued", None)
    events = client.get(f"/api/test-runs/{run_id}/events", headers=human).json()
    assert [event["title"] for event in events] == ["Run claimed"]
    assert events[0]["event_metadata"]["request_id"] == first["id"]
    completed = client.post(
        f"/api/runners/runs/{run_id}/complete",
        headers={**station, "Idempotency-Key": claim_id},
        json={"exit_code": 0},
    )
    assert completed.status_code == 200, completed.text
    next_claim = client.post(
        "/api/runners/claim-run", headers={**station, "Idempotency-Key": str(uuid4())}
    )
    assert next_claim.status_code == 200, next_claim.text
    assert next_claim.json()["run"]["id"] != run_id
    linked = client.get(f"/api/execution-requests/{requests[1]['id']}", headers=human).json()
    assert linked["run_id"] == next_claim.json()["run"]["id"]


@pytest.mark.parametrize("same_answer", [True, False])
def test_concurrent_completion_records_one_terminal_answer(client, same_answer):
    human, station, requests = _queue(client)
    claim = client.post(
        "/api/runners/claim-run", headers={**station, "Idempotency-Key": str(uuid4())}
    )
    assert claim.status_code == 200, claim.text
    body = claim.json()
    run_id = body["run"]["id"]
    headers = {**station, "Idempotency-Key": body["claim_id"]}
    answers = [{"exit_code": 0}, {"exit_code": 0 if same_answer else 1}]
    barrier = Barrier(2)

    def complete(answer):
        barrier.wait(timeout=10)
        return client.post(f"/api/runners/runs/{run_id}/complete", headers=headers, json=answer)

    with ThreadPoolExecutor(max_workers=2) as workers:
        responses = list(workers.map(complete, answers))
    assert sorted(response.status_code for response in responses) == (
        [200, 200] if same_answer else [200, 409]
    )
    events = client.get(f"/api/test-runs/{run_id}/events", headers=human).json()
    assert [event["title"] for event in events].count("Runner acknowledged completion") == 1
    stored = client.get(f"/api/test-runs/{run_id}", headers=human).json()
    accepted = next(response.json() for response in responses if response.status_code == 200)
    assert stored["runner_exit_code"] == accepted["runner_exit_code"]
