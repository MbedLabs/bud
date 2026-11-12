"""
* @file     ${tests/pg/BUD_execution_request_claims_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Concurrent station claims create one execution and concurrent completions record one answer.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module sends the two concurrent requests from two threads on the live app.
"""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from tests.pg.execution_request_claims_pg import ExecutionRequestClaimsPgBase


def body_of(response):
    """The JSON answer, or an empty one."""
    try:
        return response.json() or {}
    except ValueError:
        return {}


class ExecutionRequestClaimsPgTest(ExecutionRequestClaimsPgBase):

    def setUpClass(self):
        super().setUpClass()
        self.client = self.bud.bud_start_live_app()
        self.tc_checks = {
            "claims same key": self.claims(True),
            "claims two keys": self.claims(False),
            "completions same answer": self.completions(True),
            "completions two answers": self.completions(False),
        }

    def queue(self):
        """A station that ran a suite, and two queued requests for it; with the checks of the setup."""
        p = self.parameters
        login, human = self.bud.bud_live_bearer()
        steps, station = self.bud.bud_live_station()
        module = self.bud.bud_unique("execution").replace("-", "_")
        result = self.client.post(
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
        requests, statuses = [], []
        for number in range(2):
            queued = self.client.post(
                p.CUSTOM_PATH, headers=human, json={"test_paths": [f"{module}.Smoke"], "name": f"{module} request {number}"}
            )
            statuses.append(queued.status_code)
            requests.append((body_of(queued).get("requests") or [{}])[0])
        runs = body_of(self.client.get(p.TEST_RUNS_PATH, headers=human)).get("runs", [])
        checks = {
            "the administrator signs in": (login, p.STATUS_OK),
            "the station is enrolled": (steps, p.PG_ENROLMENT),
            "the station's results are stored": (result.status_code, p.STATUS_CREATED),
            "both requests are queued": (statuses, [p.STATUS_CREATED] * 2),
            "no queued request is a run": (any(str(run.get("name")).startswith(f"{module} request") for run in runs), False),
        }
        return human, station, requests, checks

    @staticmethod
    def together(call, arguments):
        """Run call on two arguments from two threads released together."""
        barrier = Barrier(2)

        def released(argument):
            barrier.wait(timeout=10)
            return call(argument)

        with ThreadPoolExecutor(max_workers=2) as workers:
            return list(workers.map(released, arguments))

    def claims(self, same_key):
        p = self.parameters
        human, station, requests, checks = self.queue()
        keys = [str(uuid4()), str(uuid4())]
        if same_key:
            keys[1] = keys[0]
        responses = self.together(lambda key: self.client.post(p.CUSTOM_CLAIM_PATH, headers={**station, "Idempotency-Key": key}), keys)
        claimed = [body_of(r) for r in responses if r.status_code == 200] or [{}]
        run_id = (claimed[0].get("run") or {}).get("id")
        first = body_of(self.client.get(f"{p.CUSTOM_REQUESTS_PATH}/{requests[0].get('id')}", headers=human))
        second = body_of(self.client.get(f"{p.CUSTOM_REQUESTS_PATH}/{requests[1].get('id')}", headers=human))
        events = self.client.get(f"{p.TEST_RUNS_PATH}/{run_id}/events", headers=human)
        events = body_of(events) if isinstance(body_of(events), list) else []
        completed = self.client.post(p.CUSTOM_COMPLETE_PATH.format(run_id), headers={**station, "Idempotency-Key": claimed[0].get("claim_id") or "missing"}, json={"exit_code": 0})
        next_claim = self.client.post(p.CUSTOM_CLAIM_PATH, headers={**station, "Idempotency-Key": str(uuid4())})
        linked = body_of(self.client.get(f"{p.CUSTOM_REQUESTS_PATH}/{requests[1].get('id')}", headers=human))
        checks.update(
            {
                "the claims answer as expected": (sorted(r.status_code for r in responses), [200, 200] if same_key else [200, 409]),
                "one execution is claimed": (len({(body.get("run") or {}).get("id") for body in claimed}), 1),
                "the first request is claimed": ((first.get("state"), first.get("run_id")), ("claimed", run_id)),
                "the second request waits": ((second.get("state"), second.get("run_id")), ("queued", None)),
                "the run records one claim": ([event.get("title") for event in events], ["Run claimed"]),
                "the claim names its request": (((events or [{}])[0].get("event_metadata") or {}).get("request_id"), first.get("id")),
                "the execution is completed": (completed.status_code, p.STATUS_OK),
                "the next request is claimed": (next_claim.status_code, p.STATUS_OK),
                "the next claim is another run": ((body_of(next_claim).get("run") or {}).get("id") != run_id, True),
                "the second request names its run": (linked.get("run_id"), (body_of(next_claim).get("run") or {}).get("id")),
            }
        )
        return checks

    def completions(self, same_answer):
        p = self.parameters
        human, station, _, checks = self.queue()
        claim = self.client.post(p.CUSTOM_CLAIM_PATH, headers={**station, "Idempotency-Key": str(uuid4())})
        body = body_of(claim)
        run_id = (body.get("run") or {}).get("id")
        headers = {**station, "Idempotency-Key": body.get("claim_id") or "missing"}
        answers = [{"exit_code": 0}, {"exit_code": 0 if same_answer else 1}]
        responses = self.together(lambda answer: self.client.post(p.CUSTOM_COMPLETE_PATH.format(run_id), headers=headers, json=answer), answers)
        events = self.client.get(f"{p.TEST_RUNS_PATH}/{run_id}/events", headers=human)
        titles = [event.get("title") for event in (body_of(events) if isinstance(body_of(events), list) else [])]
        stored = body_of(self.client.get(f"{p.TEST_RUNS_PATH}/{run_id}", headers=human))
        accepted = next((body_of(r) for r in responses if r.status_code == 200), {})
        checks.update(
            {
                "the run is claimed": (claim.status_code, p.STATUS_OK),
                "the completions answer as expected": (sorted(r.status_code for r in responses), [200, 200] if same_answer else [200, 409]),
                "one acknowledgement is recorded": (titles.count("Runner acknowledged completion"), 1),
                "the stored answer is the accepted one": (stored.get("runner_exit_code"), accepted.get("runner_exit_code")),
            }
        )
        return checks

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ExecutionRequestClaimsPgTest().run()
