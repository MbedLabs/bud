"""
* @file     ${tests/api/BUD_runs_lifecycle_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Runs are created, read, listed, updated and deleted; settings are written, read and kept safe.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests each scenario on a fresh app database as the administrator and as the test station.
"""

from datetime import datetime, timedelta
from unittest import mock

from app.core.config import settings
from app.models import Runner, SystemSetting, TestResult, TestRun
from tests.api.runs_lifecycle_api import RunsLifecycleApiBase


def body_of(response):
    """The JSON answer, or an empty one."""
    try:
        return response.json() or {}
    except ValueError:
        return {}


def type_name(value):
    """The type name of a value."""
    return type(value).__name__


class RunsLifecycleApiTest(RunsLifecycleApiBase):

    def setUpClass(self):
        super().setUpClass()
        self.tc_checks = {}
        for scenario in (
            self.create,
            self.creation_event,
            self.read,
            self.listing,
            self.latest,
            self.counters,
            self.completion,
            self.update_refusals,
            self.deletion,
            self.stats,
            self.options,
            self.system_settings,
            self.plm,
            self.signed_out,
        ):
            scenario()

    def fresh(self):
        """A fresh app with the test station."""
        self.bud.bud_start_app()
        self.bud.bud_add_test_station(with_run=False)

    def get(self, path, **kwargs):
        """Read as the administrator."""
        return self.bud.bud_request(self.parameters.GET, path, **kwargs)

    def create_run(self, **changes):
        """Create a run as the test station and return the answer."""
        p = self.parameters
        return self.bud.bud_station_request(
            p.POST, p.TEST_RUNS_PATH, json={**p.LIFE_RUN, **changes}
        )

    def created_id(self, **changes):
        """Create a run as the test station and return its id."""
        return body_of(self.create_run(**changes)).get("id")

    def patch_run(self, run_id, body):
        """Update a run as the test station."""
        p = self.parameters
        return self.bud.bud_station_request(p.PATCH, f"{p.TEST_RUNS_PATH}/{run_id}", json=body)

    def events(self, run_id):
        """The events of a run."""
        return self.get(f"{self.parameters.TEST_RUNS_PATH}/{run_id}/events")

    def create(self):
        p = self.parameters
        self.fresh()
        response = self.create_run()
        self.tc_checks["create"] = {
            "the run is created": (response.status_code, p.STATUS_CREATED),
            "the run is named after its suite": (
                body_of(response).get("name"),
                p.LIFE_RUN["test_suite_name"],
            ),
            "the run is running": (body_of(response).get("status"), "Running"),
        }

    def creation_event(self):
        p = self.parameters
        self.fresh()
        events = self.events(self.created_id())
        self.tc_checks["creation event"] = {
            "the events are read": (events.status_code, p.STATUS_OK),
            "the creation is recorded": (len(body_of(events) or []) >= 1, True),
        }

    def read(self):
        p = self.parameters
        self.fresh()
        run_id = self.created_id()
        fetched = self.get(f"{p.TEST_RUNS_PATH}/{run_id}")
        self.tc_checks["read"] = {
            "the run is read": (fetched.status_code, p.STATUS_OK),
            "the run read is the one created": (body_of(fetched).get("id"), run_id),
            "an unknown run is not found": (
                self.get(f"{p.TEST_RUNS_PATH}/{p.LIFE_MISSING}").status_code,
                p.STATUS_NOT_FOUND,
            ),
            "the events of an unknown run are not found": (
                self.events(p.LIFE_MISSING).status_code,
                p.STATUS_NOT_FOUND,
            ),
        }

    def listing(self):
        p = self.parameters
        names = lambda body: {item.get("name") for item in body.get("runs", [])}
        self.fresh()
        self.create_run(test_suite_name="One")
        self.create_run(test_suite_name="Two")
        listed = body_of(self.get(p.TEST_RUNS_PATH))
        self.fresh()
        self.create_run(test_suite_name="Wanted")
        self.create_run(test_suite_name="Unwanted")
        wanted = body_of(self.get(p.TEST_RUNS_PATH, params={"suite": "Wanted"}))
        self.fresh()
        self.create_run()
        running = body_of(self.get(p.TEST_RUNS_PATH, params={"status": "Running"}))
        self.fresh()
        for index in range(3):
            self.create_run(test_suite_name=f"Suite{index}")
        page = body_of(self.get(p.TEST_RUNS_PATH, params={"limit": 2, "offset": 0}))
        self.tc_checks["list"] = {
            "the list counts both runs": ((listed.get("total") or 0) >= 2, True),
            "the list names both runs": (names(listed) >= {"One", "Two"}, True),
            "the suite filter keeps the wanted suite": (names(wanted), {"Wanted"}),
            "the status filter finds the new run": (bool(running.get("runs")), True),
            "the status filter keeps running runs only": (
                all(item.get("status") == "Running" for item in running.get("runs", [])),
                True,
            ),
            "the page holds at most two runs": (len(page.get("runs", [])) <= 2, True),
            "the page names its limit": (page.get("limit"), 2),
        }

    def latest(self):
        p = self.parameters
        self.fresh()
        now = datetime.utcnow()
        for name, age in (
            ("Repeated", timedelta(hours=2)),
            ("Repeated", timedelta()),
            ("Other", timedelta()),
        ):
            self.bud.bud_add_to_app(
                TestRun(name=name, test_case_list="c", status="Completed", created_at=now - age)
            )
        names = [
            item.get("name")
            for item in body_of(
                self.get(p.TEST_RUNS_PATH, params={"latest_per_suite": "true"})
            ).get("runs", [])
        ]
        self.tc_checks["latest"] = {
            "the repeated suite appears once": (names.count("Repeated"), 1),
            "the other suite appears": ("Other" in names, True),
        }

    def counters(self):
        p = self.parameters
        self.fresh()
        response = self.patch_run(self.created_id(), p.LIFE_FINAL_COUNTERS)
        body = body_of(response)
        self.tc_checks["counters"] = {
            "the update succeeds": (response.status_code, p.STATUS_OK),
            "the run is completed": (body.get("status"), "Completed"),
            "the passed count is stored": (
                body.get("passed_tests"),
                p.LIFE_FINAL_COUNTERS["passed_tests"],
            ),
            "the duration is stored": (
                body.get("duration_seconds"),
                p.LIFE_FINAL_COUNTERS["duration_seconds"],
            ),
        }

    def completion(self):
        p = self.parameters
        self.fresh()
        run_id = self.created_id()
        before = body_of(self.get(f"{p.TEST_RUNS_PATH}/{run_id}")).get("completed_at")
        events_before = len(body_of(self.events(run_id)) or [])
        self.patch_run(run_id, {"status": "Completed"})
        after = body_of(self.get(f"{p.TEST_RUNS_PATH}/{run_id}")).get("completed_at")
        events_after = len(body_of(self.events(run_id)) or [])
        self.tc_checks["completion"] = {
            "a running run has no completion time": (type_name(before), p.NONE_TYPE),
            "a completed run has a completion time": (type_name(after) != p.NONE_TYPE, True),
            "the status change is recorded as an event": (events_after > events_before, True),
        }

    def update_refusals(self):
        p = self.parameters
        self.fresh()
        unknown = self.patch_run(p.LIFE_MISSING, {"status": "Completed"})
        elsewhere = self.patch_run(self.created_id(), {"status": "Elsewhere"})
        self.tc_checks["update refusals"] = {
            "an unknown run is not found": (unknown.status_code, p.STATUS_NOT_FOUND),
            "an unknown status is refused": (elsewhere.status_code, p.STATUS_UNPROCESSABLE),
        }

    def deletion(self):
        p = self.parameters
        self.fresh()
        run_id = self.created_id()
        deleted = self.bud.bud_request(p.DELETE, f"{p.TEST_RUNS_PATH}/{run_id}")
        remaining = self.bud.bud_find_in_app(TestRun, id=run_id)
        unknown = self.bud.bud_request(p.DELETE, f"{p.TEST_RUNS_PATH}/{p.LIFE_MISSING}")
        self.fresh()
        run_id = self.created_id()
        self.bud.bud_add_to_app(
            TestResult(test_class="Smoke", test_method="test_x", passed=True, test_run_id=run_id)
        )
        with_results = self.bud.bud_request(p.DELETE, f"{p.TEST_RUNS_PATH}/{run_id}")
        orphans = self.bud.bud_find_in_app(TestResult, test_run_id=run_id)
        self.tc_checks["deletion"] = {
            "the run is deleted": (deleted.status_code, p.STATUS_NO_CONTENT),
            "the run is gone": (len(remaining), 0),
            "an unknown run is not found": (unknown.status_code, p.STATUS_NOT_FOUND),
            "a run with results is deleted": (with_results.status_code, p.STATUS_NO_CONTENT),
            "its results are gone": (len(orphans), 0),
        }

    def stats(self):
        p = self.parameters
        self.fresh()
        station = self.bud.bud_add_to_app(
            Runner(account="stats-station", password_hash="x", token="t")
        )
        now = datetime.utcnow()
        for name, passed, failed in (("Alpha", 10, 0), ("Beta", 6, 4)):
            self.bud.bud_add_to_app(
                TestRun(
                    name=name,
                    test_case_list="c",
                    status="Completed",
                    total_tests=10,
                    passed_tests=passed,
                    failed_tests=failed,
                    created_at=now,
                    runner_id=station.id,
                )
            )
        whole = body_of(self.get(p.RUN_STATS_PATH))
        self.fresh()
        self.bud.bud_add_to_app(
            TestRun(
                name="Only",
                test_case_list="c",
                status="Completed",
                total_tests=4,
                passed_tests=4,
                created_at=datetime.utcnow(),
            )
        )
        only = body_of(self.get(p.RUN_STATS_PATH, params={"suite": "Only"}))
        self.fresh()
        nobody = body_of(self.get(p.RUN_STATS_PATH, params={"runner_account": "nobody"}))
        self.tc_checks["stats"] = {
            "both runs are counted": ((whole.get("total_runs") or 0) >= 2, True),
            "their tests are counted": ((whole.get("total_tests") or 0) >= 20, True),
            "their passed tests are counted": ((whole.get("passed_tests") or 0) >= 16, True),
            "the pass rate is a percentage": (
                isinstance(whole.get("test_pass_rate"), (int, float))
                and 0 <= whole["test_pass_rate"] <= 100,
                True,
            ),
            "the suite filter counts its tests only": (only.get("total_tests"), 4),
            "an unknown station has no run": (nobody.get("total_runs"), 0),
            "an unknown station has a zero pass rate": (nobody.get("test_pass_rate"), 0.0),
        }

    def options(self):
        p = self.parameters
        self.fresh()
        station = self.bud.bud_add_to_app(
            Runner(account="opt-station", password_hash="x", token="t")
        )
        self.bud.bud_add_to_app(
            TestRun(
                name="Optioned",
                test_case_list="c",
                status="Completed",
                created_at=datetime.utcnow(),
                runner_id=station.id,
            )
        )
        options = body_of(self.get(p.RUN_FILTER_OPTIONS_PATH))
        self.tc_checks["options"] = {
            "the suite is offered": ("Optioned" in (options.get("suites") or []), True),
            "the station is offered": (
                "opt-station" in (options.get("runner_accounts") or []),
                True,
            ),
        }

    def system_settings(self):
        p = self.parameters
        self.fresh()
        listed = self.get(p.LIFE_SETTINGS_PATH)
        written = self.bud.bud_request(
            p.PUT, f"{p.LIFE_SETTINGS_PATH}/retention_days", json={"value": "30"}
        )
        read = self.get(f"{p.LIFE_SETTINGS_PATH}/retention_days")
        unknown = self.get(f"{p.LIFE_SETTINGS_PATH}/not-a-setting")
        self.bud.bud_request(p.PUT, f"{p.LIFE_SETTINGS_PATH}/mode", json={"value": "first"})
        self.bud.bud_request(p.PUT, f"{p.LIFE_SETTINGS_PATH}/mode", json={"value": "second"})
        stored = (
            self.bud.bud_find_in_app(SystemSetting, key="mode") or [SystemSetting(value=None)]
        )[0]
        self.tc_checks["settings"] = {
            "the settings are listed": (listed.status_code, p.STATUS_OK),
            "a setting is written": (written.status_code, p.STATUS_OK),
            "the setting is read": (read.status_code, p.STATUS_OK),
            "the setting holds its value": (body_of(read).get("value"), "30"),
            "an unknown setting is not found": (unknown.status_code, p.STATUS_NOT_FOUND),
            "a second write replaces the value": (stored.value, "second"),
        }

    def save_bloom(self, url, token):
        """Save the Bloom integration as the administrator."""
        p = self.parameters
        return self.bud.bud_request(
            p.POST, p.LIFE_PLM_PATH, json={"bloom_url": url, "bloom_token": token}
        )

    def plm(self):
        p = self.parameters
        self.fresh()
        with mock.patch.object(settings, "INTEGRATION_ENCRYPTION_KEY", ""):
            keyless = self.save_bloom(p.LIFE_BLOOM_URL, "blm_sync_x")
        unconfigured = self.get(p.LIFE_PLM_PATH)
        admin_token = self.save_bloom(p.LIFE_BLOOM_URL, "an-admin-token")
        stored = self.save_bloom(p.LIFE_BLOOM_URL + "/", "blm_sync_a-real-token")
        self.fresh()
        self.save_bloom(p.LIFE_BLOOM_URL, "blm_sync_super-secret")
        shown = body_of(self.get(p.LIFE_PLM_PATH))
        checks = {
            "a token without a key is refused": (keyless.status_code, p.STATUS_SERVICE_UNAVAILABLE),
            "the refusal names the missing key": (
                "ENCRYPTION_KEY" in str(body_of(keyless).get("detail")),
                True,
            ),
            "an unconfigured integration is read": (unconfigured.status_code, p.STATUS_OK),
            "an unconfigured integration has no address": (
                body_of(unconfigured).get("bloom_url"),
                "",
            ),
            "an unconfigured integration has no token": (
                body_of(unconfigured).get("has_bloom_token"),
                False,
            ),
            "an administrator token is refused": (admin_token.status_code, p.STATUS_UNPROCESSABLE),
            "the refusal names the service token prefix": (
                "blm_sync_" in str(body_of(admin_token).get("detail")),
                True,
            ),
            "a service token is stored": (stored.status_code, p.STATUS_OK),
            "the address is stored without its trailing slash": (
                body_of(stored).get("bloom_url"),
                p.LIFE_BLOOM_URL,
            ),
            "the integration says it holds a token": (body_of(stored).get("has_bloom_token"), True),
            "the token is never shown": ("blm_sync_super-secret" in str(shown), False),
            "the shown integration says it holds a token": (shown.get("has_bloom_token"), True),
        }
        for url in p.LIFE_BAD_URLS:
            self.fresh()
            checks[f"the address {url} is refused"] = (
                self.save_bloom(url, "blm_sync_t").status_code,
                p.STATUS_UNPROCESSABLE,
            )
        self.tc_checks["plm"] = checks

    def signed_out(self):
        p = self.parameters
        self.bud.bud_start_app(signed_in=False)
        self.tc_checks["signed out"] = {
            f"{method} {path} needs a signed-in person": (
                self.bud.bud_request(method, path, json={"value": "x"}).status_code,
                p.STATUS_UNAUTHORIZED,
            )
            for method, path in p.LIFE_SIGNED_OUT
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    RunsLifecycleApiTest().run()
