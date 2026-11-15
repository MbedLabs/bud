"""
* @file     ${tests/api/BUD_custom_runs_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Chosen test cases are queued for the benches that ran them, claimed once and completed by their station.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests each scenario on a fresh app database with two benches, their runs and their results.
"""

from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import Runner, TestResult, TestRun
from app.models.user import User, UserRole
from tests.api.custom_runs_api import CustomRunsApiBase


def body_of(response):
    """The JSON answer, or an empty one."""
    try:
        return response.json() or {}
    except ValueError:
        return {}


def type_name(value):
    """The type name of a value."""
    return type(value).__name__


def result(test_class, method, source_file, run_id, when):
    """A passed result with its source file."""
    return TestResult(
        test_class=test_class,
        test_method=method,
        passed=True,
        duration_seconds=1.0,
        test_metadata={"test_case_file": source_file, "test_case_class": test_class},
        test_run_id=run_id,
        created_at=when,
    )


class CustomRunsApiTest(CustomRunsApiBase):

    def setUpClass(self):
        super().setUpClass()
        self.tc_checks = {}
        for name, scenario in (
            ("catalogue", self.catalogue),
            ("catalogue signed out", self.catalogue_signed_out),
            ("metadata", self.metadata),
            ("no evidence", self.no_evidence),
            ("assignment", self.assignment),
            ("pinning", self.pinning),
            ("unknown", self.unknown),
            ("bench queue", self.bench_queue),
            ("queue signed out", self.queue_signed_out),
            ("claim", self.claim_own),
            ("other queue", self.other_queue),
            ("retried claim", self.retried_claim),
            ("active claim", self.active_claim),
            ("oldest", self.oldest),
            ("person claim", self.person_claim),
            ("cancelled", self.cancelled),
            ("failed execution", self.failed_execution),
            ("results release", self.results_release),
            ("stats wait", self.stats_wait),
            ("nonzero exit", self.nonzero_exit),
            ("idempotent", self.idempotent),
            ("wrong key", self.wrong_key),
            ("listed apart", self.listed_apart),
            ("claim link", self.claim_link),
            ("foreign request", self.foreign_request),
            ("placeholder", self.placeholder),
        ):
            self.tc_checks[name] = scenario()

    def lab(self, signed_in=True):
        """A fresh app with two benches: a run of VoltageTest and BootTest on station-01 two hours
        ago, a run of ThermalTest and BootTest on station-02 an hour ago, and a LegacyTest without
        a source file."""
        self.bud.bud_start_app(signed_in=signed_in)
        self.admin = User(
            id=self.parameters.TEST_ADMIN_ID,
            email=self.parameters.TEST_ADMIN_EMAIL,
            full_name=self.parameters.TEST_ADMIN_NAME,
            hashed_password="x",
            role=UserRole.admin,
            is_active=True,
            session_version=1,
        )
        add = self.bud.bud_add_to_app
        bench_a = add(Runner(account="station-01", password_hash="x", token="t1", location="Lab A"))
        bench_b = add(Runner(account="station-02", password_hash="x", token="t2", location="Lab B"))
        now = datetime.utcnow()
        run_a = add(
            TestRun(
                name="Nightly",
                test_case_list="Bud_Suite.NIGHTLY",
                status="Completed",
                runner_id=bench_a.id,
                url_test_software=self.parameters.CUSTOM_REPOSITORY,
                ref_test_software=self.parameters.CUSTOM_REFERENCE,
                created_at=now - timedelta(hours=2),
            )
        )
        run_b = add(TestRun(name="Powertrain", test_case_list="Bud_Suite.POWERTRAIN", status="Completed", runner_id=bench_b.id, created_at=now - timedelta(hours=1)))
        for row in (
            result("VoltageTest", "test_idle", "/w/demo_voltage.py", run_a.id, now),
            result("VoltageTest", "test_load", "/w/demo_voltage.py", run_a.id, now),
            result("BootTest", "test_cold", "/w/boot_suite.py", run_a.id, now),
            result("ThermalTest", "test_soak", "/w/thermal.py", run_b.id, now),
            result("BootTest", "test_cold", "/w/boot_suite.py", run_b.id, now),
            TestResult(
                test_class="LegacyTest",
                test_method="test_old",
                passed=True,
                duration_seconds=1.0,
                test_metadata={"test_case_class": "LegacyTest"},
                test_run_id=run_a.id,
                created_at=now,
            ),
        ):
            add(row)
        return bench_a, bench_b

    def as_bench(self, bench):
        """Act as a bench."""
        self.bud.bud_sign_in_as(bench, as_person=False, as_uploader=True)

    def as_admin(self):
        """Act as the administrator again."""
        self.bud.bud_sign_in_as(self.admin, as_uploader=True)

    def queue(self, *paths, **extra):
        """Queue a custom run as the signed-in person."""
        p = self.parameters
        return self.bud.bud_request(p.POST, p.CUSTOM_PATH, json={"test_paths": list(paths), **extra})

    def requests_of(self, *paths, **extra):
        """The queued requests of one selection."""
        return body_of(self.queue(*paths, **extra)).get("requests") or [{}]

    def claim(self, key=None):
        """Claim the next run as the signed-in bench."""
        p = self.parameters
        return self.bud.bud_request(p.POST, p.CUSTOM_CLAIM_PATH, headers={"Idempotency-Key": key or p.CUSTOM_CLAIM_ID})

    def complete(self, run_id, key, payload):
        """Report a claimed run's terminal answer."""
        p = self.parameters
        return self.bud.bud_request(p.POST, p.CUSTOM_COMPLETE_PATH.format(run_id), headers={"Idempotency-Key": key or "missing"}, json=payload)

    def get(self, path, **kwargs):
        """Read one answer, an empty list kept as it is."""
        response = self.bud.bud_request(self.parameters.GET, path, **kwargs)
        try:
            data = response.json()
        except ValueError:
            return {}
        return {} if data is None else data

    def stats(self, suite=None):
        """The run statistics, for one suite when given."""
        return self.get(self.parameters.RUN_STATS_PATH, params={"suite": suite} if suite else None)

    def entries(self, **params):
        """The catalogue entries by path."""
        return {entry.get("test_path"): entry for entry in self.get(self.parameters.CUSTOM_CATALOG_PATH, params=params or None).get("entries", [])}

    def catalogue(self):
        p = self.parameters
        bench_a, _ = self.lab()
        listed = self.get(p.CUSTOM_CATALOG_PATH).get("entries", [])
        paths = [entry.get("test_path") for entry in listed]
        entries = self.entries()
        narrowed = set(self.entries(runner_account="station-02"))
        self.as_bench(bench_a)
        own = set(self.entries())
        return {
            "a case is listed once": (paths.count(p.CUSTOM_VOLTAGE), 1),
            "the voltage path is importable": (p.CUSTOM_VOLTAGE in paths, True),
            "the thermal path is importable": (p.CUSTOM_THERMAL in paths, True),
            "a case without source file is left out": (any(str(path).endswith("LegacyTest") for path in paths), False),
            "a shared case names both benches": (sorted(entries.get(p.CUSTOM_BOOT, {}).get("runner_accounts", [])), ["station-01", "station-02"]),
            "a case names its bench": (entries.get(p.CUSTOM_THERMAL, {}).get("runner_accounts"), ["station-02"]),
            "the methods of a case are counted": (entries.get(p.CUSTOM_VOLTAGE, {}).get("method_count"), 2),
            "a single method is counted": (entries.get(p.CUSTOM_THERMAL, {}).get("method_count"), 1),
            "the catalogue narrows to one bench": (narrowed, {p.CUSTOM_BOOT, p.CUSTOM_THERMAL}),
            "a bench sees only its own": (p.CUSTOM_THERMAL in own, False),
        }

    def catalogue_signed_out(self):
        p = self.parameters
        self.lab(signed_in=False)
        return {"the catalogue needs a signed-in entity": (self.bud.bud_request(p.GET, p.CUSTOM_CATALOG_PATH).status_code, p.STATUS_UNAUTHORIZED)}

    def metadata(self):
        p = self.parameters
        self.lab()
        queued = self.queue(p.CUSTOM_BOOT, runner_account="station-01")
        request = (body_of(queued).get("requests") or [{}])[0]
        source = request.get("source_metadata") or {}
        return {
            "the request is queued": (queued.status_code, p.STATUS_CREATED),
            "the request goes to the pinned station": (request.get("runner_account"), "station-01"),
            "the repository comes from the station": (source.get("url_test_software"), p.CUSTOM_REPOSITORY),
            "the reference comes from the station": (source.get("ref_test_software"), p.CUSTOM_REFERENCE),
        }

    def no_evidence(self):
        p = self.parameters
        self.lab()
        before = len(self.bud.bud_find_in_app(TestRun))
        response = self.queue(p.CUSTOM_VOLTAGE)
        body = body_of(response)
        request = (body.get("requests") or [{}])[0]
        return {
            "the request is queued": (response.status_code, p.STATUS_CREATED),
            "no run is stored": (len(self.bud.bud_find_in_app(TestRun)), before),
            "no run is answered": ("runs" in body, False),
            "the request waits": (request.get("state"), "queued"),
            "the request has no run": (type_name(request.get("run_id")), p.NONE_TYPE),
        }

    def assignment(self):
        p = self.parameters
        checks = {}
        self.lab()
        single = self.queue(p.CUSTOM_VOLTAGE, p.CUSTOM_BOOT)
        body = body_of(single)
        checks.update(
            {
                "a one-bench selection is queued": (single.status_code, p.STATUS_CREATED),
                "a one-bench selection makes one request": (len(body.get("requests", [])), 1),
                "the request waits": ((body.get("requests") or [{}])[0].get("state"), "queued"),
                "nothing is unassigned": (body.get("unassigned"), []),
                "the case that runs anywhere follows the bench-bound one": ((body.get("requests") or [{}])[0].get("runner_account"), "station-01"),
                "the request carries both cases": (sorted((body.get("requests") or [{}])[0].get("selected_tests") or []), [p.CUSTOM_BOOT, p.CUSTOM_VOLTAGE]),
            }
        )
        self.lab()
        split = body_of(self.queue(p.CUSTOM_VOLTAGE, p.CUSTOM_THERMAL)).get("requests", [])
        checks["a two-bench selection makes two requests"] = (len(split), 2)
        checks["each bench gets its request"] = (sorted(r.get("runner_account") for r in split), ["station-01", "station-02"])
        self.lab()
        checks["a case that runs anywhere goes to the latest bench"] = (self.requests_of(p.CUSTOM_BOOT)[0].get("runner_account"), "station-02")
        self.lab()
        run = self.requests_of(p.CUSTOM_VOLTAGE)[0]
        checks["the request carries the selection"] = (run.get("selected_tests"), [p.CUSTOM_VOLTAGE])
        checks["the request keeps the repository"] = ((run.get("source_metadata") or {}).get("url_test_software"), p.CUSTOM_REPOSITORY)
        checks["the request keeps the reference"] = ((run.get("source_metadata") or {}).get("ref_test_software"), p.CUSTOM_REFERENCE)
        self.lab()
        checks["a duplicate selection is queued once"] = (self.requests_of(p.CUSTOM_VOLTAGE, p.CUSTOM_VOLTAGE)[0].get("selected_tests"), [p.CUSTOM_VOLTAGE])
        return checks

    def pinning(self):
        p = self.parameters
        self.lab()
        pinned = body_of(self.queue(p.CUSTOM_BOOT, runner_account="station-02")).get("requests", [])
        self.lab()
        body = body_of(self.queue(p.CUSTOM_BOOT, p.CUSTOM_THERMAL, runner_account="station-01"))
        unassigned = body.get("unassigned") or [{}]
        return {
            "a pinned selection makes one request": (len(pinned), 1),
            "the request goes to the pinned bench": ((pinned or [{}])[0].get("runner_account"), "station-02"),
            "only the pinned bench gets a request": ([r.get("runner_account") for r in body.get("requests", [])], ["station-01"]),
            "the case it never ran is reported": ([item.get("test_path") for item in body.get("unassigned", [])], [p.CUSTOM_THERMAL]),
            "the report names where it ran": ("station-02" in str(unassigned[0].get("reason")), True),
        }

    def unknown(self):
        p = self.parameters
        self.lab()
        body = body_of(self.queue(p.CUSTOM_VOLTAGE, p.CUSTOM_GHOST))
        self.lab()
        nothing = self.queue(p.CUSTOM_GHOST)
        self.lab()
        bench = self.queue(p.CUSTOM_BOOT, runner_account="station-99")
        return {
            "the known case is queued": (len(body.get("requests", [])), 1),
            "the unknown case is reported": ((body.get("unassigned") or [{}])[0].get("test_path"), p.CUSTOM_GHOST),
            "nothing runnable is refused": (nothing.status_code, p.STATUS_UNPROCESSABLE),
            "the refusal names the case": (p.CUSTOM_GHOST in str(body_of(nothing).get("detail")), True),
            "an unknown bench is not found": (bench.status_code, p.STATUS_NOT_FOUND),
        }

    def bench_queue(self):
        p = self.parameters
        bench_a, _ = self.lab()
        self.as_bench(bench_a)
        self.bud.bud_forget_person()
        response = self.queue(p.CUSTOM_BOOT)
        return {
            "a bench cannot queue": (response.status_code, p.STATUS_FORBIDDEN),
            "the refusal asks for a person": (body_of(response).get("detail"), "User privileges required."),
        }

    def queue_signed_out(self):
        p = self.parameters
        self.lab(signed_in=False)
        return {
            "queueing needs a signed-in entity": (self.queue("a.B").status_code, p.STATUS_UNAUTHORIZED),
            "claiming needs a signed-in entity": (self.claim().status_code, p.STATUS_UNAUTHORIZED),
        }

    def claim_own(self):
        p = self.parameters
        bench_a, _ = self.lab()
        self.queue(p.CUSTOM_VOLTAGE)
        self.as_bench(bench_a)
        response = self.claim()
        body = body_of(response)
        return {
            "the bench claims": (response.status_code, p.STATUS_OK),
            "the claim keeps its key": (body.get("claim_id"), p.CUSTOM_CLAIM_ID),
            "the claim carries the selection": (body.get("selected_tests"), [p.CUSTOM_VOLTAGE]),
            "the run is running": ((body.get("run") or {}).get("status"), "Running"),
            "the run is started": (type_name((body.get("run") or {}).get("started_at")) != p.NONE_TYPE, True),
        }

    def other_queue(self):
        p = self.parameters
        bench_a, _ = self.lab()
        self.queue(p.CUSTOM_THERMAL)
        self.as_bench(bench_a)
        other = self.claim().status_code
        bench_a, _ = self.lab()
        self.as_bench(bench_a)
        return {
            "another bench's queue is invisible": (other, p.STATUS_NO_CONTENT),
            "an empty queue is no error": (self.claim().status_code, p.STATUS_NO_CONTENT),
        }

    def retried_claim(self):
        p = self.parameters
        bench_a, _ = self.lab()
        self.queue(p.CUSTOM_VOLTAGE)
        self.as_bench(bench_a)
        first, second = self.claim(), self.claim()
        return {
            "the first claim succeeds": (first.status_code, p.STATUS_OK),
            "the retried claim succeeds": (second.status_code, p.STATUS_OK),
            "the retried claim returns the same run": ((body_of(second).get("run") or {}).get("id"), (body_of(first).get("run") or {}).get("id")),
        }

    def active_claim(self):
        p = self.parameters
        bench_a, _ = self.lab()
        self.queue(p.CUSTOM_VOLTAGE, name="First")
        self.queue(p.CUSTOM_BOOT, name="Second")
        self.as_bench(bench_a)
        first, second = self.claim(), self.claim(p.CUSTOM_SECOND_CLAIM_ID)
        return {
            "the first claim succeeds": (first.status_code, p.STATUS_OK),
            "a second claim is a conflict": (second.status_code, p.STATUS_CONFLICT),
            "the conflict names the active claim": ("active claimed run" in str(body_of(second).get("detail")), True),
        }

    def oldest(self):
        p = self.parameters
        bench_a, _ = self.lab()
        first = self.requests_of(p.CUSTOM_VOLTAGE, name="First")[0]
        self.queue(p.CUSTOM_BOOT, name="Second")
        self.as_bench(bench_a)
        claimed = body_of(self.claim())
        self.as_admin()
        return {
            "the oldest request is claimed": ((claimed.get("run") or {}).get("name"), first.get("name")),
            "the request names its run": (self.get(f"{p.CUSTOM_REQUESTS_PATH}/{first.get('id')}").get("run_id"), (claimed.get("run") or {}).get("id")),
        }

    def person_claim(self):
        p = self.parameters
        self.lab()
        self.queue(p.CUSTOM_VOLTAGE)
        return {"a person cannot claim": (self.claim().status_code, p.STATUS_FORBIDDEN)}

    def cancelled(self):
        p = self.parameters
        bench_a, _ = self.lab()
        statuses = [self.queue(p.CUSTOM_VOLTAGE).status_code for _ in range(2)]
        self.as_bench(bench_a)
        claimed = body_of(self.claim())
        run_id = (claimed.get("run") or {}).get("id")
        cancelled = self.bud.bud_request(p.PATCH, f"{p.TEST_RUNS_PATH}/{run_id}", json={"status": "Cancelled"})
        completed = self.complete(run_id, claimed.get("claim_id"), {"exit_code": 130})
        answer = body_of(completed)
        next_claim = self.claim(p.CUSTOM_SECOND_CLAIM_ID)
        return {
            "both requests are queued": (statuses, [p.STATUS_CREATED] * 2),
            "the station cancels": (cancelled.status_code, p.STATUS_OK),
            "the cancellation is acknowledged": (completed.status_code, p.STATUS_OK),
            "the run stays cancelled": (answer.get("status"), "Cancelled"),
            "the exit code is recorded": (answer.get("runner_exit_code"), 130),
            "the acknowledgement is stamped": (type_name(answer.get("claim_acknowledged_at")) != p.NONE_TYPE, True),
            "the next request is claimed": (next_claim.status_code, p.STATUS_OK),
            "the next claim is another run": ((body_of(next_claim).get("run") or {}).get("id") != run_id, True),
        }

    def failed_execution(self):
        p = self.parameters
        bench_a, _ = self.lab()
        queued = self.queue(p.CUSTOM_VOLTAGE, name="Unavailable selection")
        self.as_bench(bench_a)
        claimed = body_of(self.claim())
        response = self.complete((claimed.get("run") or {}).get("id"), claimed.get("claim_id"), {"exit_code": 1})
        stats = self.stats("Unavailable selection")
        return {
            "the request is queued": (queued.status_code, p.STATUS_CREATED),
            "the completion is accepted": (response.status_code, p.STATUS_OK),
            "no run passed": (stats.get("passed_runs"), 0),
            "the run failed": (stats.get("failed_runs"), 1),
            "no run is in progress": (stats.get("in_progress_runs"), 0),
            "no test is counted": (stats.get("total_tests"), 0),
        }

    def upload(self, run_id, passed=True):
        """Upload one VoltageTest result to a run as the signed-in bench."""
        p = self.parameters
        return self.bud.bud_request(
            p.POST,
            "/api/results",
            json={"test_run_id": run_id, "results": [{"test_class": "VoltageTest", "test_method": "test_idle", "passed": passed}]},
        )

    def results_release(self):
        p = self.parameters
        bench_a, _ = self.lab()
        self.queue(p.CUSTOM_VOLTAGE)
        self.queue(p.CUSTOM_VOLTAGE)
        self.as_bench(bench_a)
        claimed = body_of(self.claim())
        run_id = (claimed.get("run") or {}).get("id")
        uploaded = self.upload(run_id)
        status = self.get(f"{p.TEST_RUNS_PATH}/{run_id}").get("status")
        blocked = self.claim(p.CUSTOM_SECOND_CLAIM_ID)
        completed = self.complete(run_id, claimed.get("claim_id"), {"exit_code": 0})
        next_claim = self.claim(p.CUSTOM_SECOND_CLAIM_ID)
        return {
            "the results are stored": (uploaded.status_code, p.STATUS_CREATED),
            "the run is completed": (status, "Completed"),
            "the claim still blocks": (blocked.status_code, p.STATUS_CONFLICT),
            "the completion is accepted": (completed.status_code, p.STATUS_OK),
            "the next request is claimed": (next_claim.status_code, p.STATUS_OK),
            "the next claim is another run": ((body_of(next_claim).get("run") or {}).get("id") != run_id, True),
        }

    def stats_wait(self):
        p = self.parameters
        checks = {}
        for passed in (True, False):
            bench_a, _ = self.lab()
            self.queue(p.CUSTOM_VOLTAGE, name="Awaiting station")
            self.as_bench(bench_a)
            claimed = body_of(self.claim())
            run_id = (claimed.get("run") or {}).get("id")
            uploaded = self.upload(run_id, passed)
            waiting = self.stats("Awaiting station")
            completed = self.complete(run_id, claimed.get("claim_id"), {"exit_code": 0 if passed else 1})
            done = self.stats("Awaiting station")
            label = "passing" if passed else "failing"
            checks.update(
                {
                    f"{label}: the results are stored": (uploaded.status_code, p.STATUS_CREATED),
                    f"{label}: nothing is decided before the answer": ((waiting.get("passed_runs"), waiting.get("failed_runs")), (0, 0)),
                    f"{label}: the run is in progress": (waiting.get("in_progress_runs"), 1),
                    f"{label}: the completion is accepted": (completed.status_code, p.STATUS_OK),
                    f"{label}: the passed count follows": (done.get("passed_runs"), int(passed)),
                    f"{label}: the failed count follows": (done.get("failed_runs"), int(not passed)),
                    f"{label}: nothing is in progress": (done.get("in_progress_runs"), 0),
                }
            )
        return checks

    def nonzero_exit(self):
        p = self.parameters
        bench_a, _ = self.lab()
        self.queue(p.CUSTOM_VOLTAGE)
        self.as_bench(bench_a)
        claimed = body_of(self.claim())
        response = self.complete((claimed.get("run") or {}).get("id"), claimed.get("claim_id"), {"exit_code": 1})
        answer = body_of(response)
        return {
            "the completion is accepted": (response.status_code, p.STATUS_OK),
            "the run is completed": (answer.get("status"), "Completed"),
            "the exit code is recorded": (answer.get("runner_exit_code"), 1),
            "the completion is stamped": (type_name(answer.get("completed_at")) != p.NONE_TYPE, True),
        }

    def idempotent(self):
        p = self.parameters
        bench_a, _ = self.lab()
        self.queue(p.CUSTOM_VOLTAGE)
        self.as_bench(bench_a)
        claimed = body_of(self.claim())
        run_id = (claimed.get("run") or {}).get("id")
        payload = {"exit_code": 1, "error": "executor crashed"}
        first = self.complete(run_id, claimed.get("claim_id"), payload)
        second = self.complete(run_id, claimed.get("claim_id"), payload)
        events = self.get(f"{p.TEST_RUNS_PATH}/{run_id}/events")
        titles = [event.get("title") for event in (events if isinstance(events, list) else [])]
        return {
            "the first completion is accepted": (first.status_code, p.STATUS_OK),
            "the second completion is accepted": (second.status_code, p.STATUS_OK),
            "the error is kept": (body_of(second).get("runner_error"), "executor crashed"),
            "the acknowledgement is recorded once": (titles.count("Runner acknowledged completion"), 1),
        }

    def wrong_key(self):
        p = self.parameters
        bench_a, _ = self.lab()
        self.queue(p.CUSTOM_VOLTAGE)
        self.as_bench(bench_a)
        claimed = body_of(self.claim())
        response = self.complete((claimed.get("run") or {}).get("id"), p.CUSTOM_SECOND_CLAIM_ID, {"exit_code": 0})
        return {"a completion with another key is a conflict": (response.status_code, p.STATUS_CONFLICT)}

    def listed_apart(self):
        p = self.parameters
        self.lab()
        created = self.requests_of(p.CUSTOM_VOLTAGE, name="Ad-hoc")[0]
        return {
            "no pending run is listed": (self.get(p.TEST_RUNS_PATH, params={"status": "Pending"}).get("runs"), []),
            "the statistics count the stored runs only": (self.stats().get("total_runs"), 2),
            "the request is listed apart": (self.get(p.CUSTOM_REQUESTS_PATH), [created]),
            "the request is read": (self.get(f"{p.CUSTOM_REQUESTS_PATH}/{created.get('id')}"), created),
        }

    def claim_link(self):
        p = self.parameters
        bench_a, _ = self.lab()
        request = self.requests_of(p.CUSTOM_VOLTAGE)[0]
        self.as_bench(bench_a)
        first, second = self.claim(), self.claim()
        self.as_admin()
        linked = self.get(f"{p.CUSTOM_REQUESTS_PATH}/{request.get('id')}")
        events = self.get(f"{p.TEST_RUNS_PATH}/{linked.get('run_id')}/events")
        events = events if isinstance(events, list) else []
        return {
            "both claims succeed": ((first.status_code, second.status_code), (p.STATUS_OK, p.STATUS_OK)),
            "both claims return one run": ((body_of(first).get("run") or {}).get("id"), (body_of(second).get("run") or {}).get("id")),
            "the request is claimed": (linked.get("state"), "claimed"),
            "the request names its run": (linked.get("run_id"), (body_of(first).get("run") or {}).get("id")),
            "the statistics count the claimed run": (self.stats().get("total_runs"), 3),
            "the run records its claim": ([event.get("title") for event in events], ["Run claimed"]),
            "the claim event names the request": (((events or [{}])[0].get("event_metadata") or {}).get("request_id"), request.get("id")),
        }

    def foreign_request(self):
        p = self.parameters
        bench_a, _ = self.lab()
        request = self.requests_of(p.CUSTOM_THERMAL)[0]
        self.as_bench(bench_a)
        return {
            "another bench's requests are not listed": (self.get(p.CUSTOM_REQUESTS_PATH), []),
            "another bench's request is not found": (
                self.bud.bud_request(p.GET, f"{p.CUSTOM_REQUESTS_PATH}/{request.get('id')}").status_code,
                p.STATUS_NOT_FOUND,
            ),
        }

    def placeholder(self):
        p = self.parameters
        bench_a, _ = self.lab()
        placeholder = self.bud.bud_add_to_app(
            TestRun(name="Old queued request", test_case_list="a.B", selected_tests=["a.B"], status="Pending", runner_id=bench_a.id, record_kind="legacy_request")
        )
        session = self.bud.bud_open_session(on_app=True)

        async def retained():
            return await session.scalar(
                select(TestRun.id).where(TestRun.id == placeholder.id).execution_options(include_legacy_requests=True)
            )

        options = self.get(p.RUN_FILTER_OPTIONS_PATH)
        return {
            "the statistics leave the placeholder out": (self.stats().get("total_runs"), 2),
            "no pending run is listed": (self.get(p.TEST_RUNS_PATH, params={"status": "Pending"}).get("runs"), []),
            "the placeholder is not found": (self.bud.bud_request(p.GET, f"{p.TEST_RUNS_PATH}/{placeholder.id}").status_code, p.STATUS_NOT_FOUND),
            "the placeholder is no suite option": ("Old queued request" in (options.get("suites") or []), False),
            "the placeholder is retained": (self.bud.bud_await(retained()), placeholder.id),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    CustomRunsApiTest().run()
