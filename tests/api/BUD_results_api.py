"""
* @file     ${tests/api/BUD_results_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    A station's uploaded results keep their assertions and count the run's test classes.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests uploads to a station's run and uploads that create their own run.
"""

from app.models import TestResult, TestRun, TestRunEvent
from tests.api.results_api import ResultsApiBase

SOFTWARE_FIELDS = (
    "test_case_list",
    "url_test_software",
    "ref_test_software",
    "url_software_under_test",
    "ref_software_under_test",
)


class ResultsApiTest(ResultsApiBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        run_id, response = self.upload_to_run(p.RESULTS_VOLTAGE_RUN, p.RESULTS_VOLTAGE)
        rows = {
            row.test_method: row for row in self.bud.bud_find_in_app(TestResult, test_run_id=run_id)
        }
        failing = rows.get(p.RESULTS_FAILING_METHOD)
        timeline = self.bud.bud_request(p.GET, p.RUN_EVENTS_PATH.format(run_id))
        first_title = (
            timeline.json()[0].get("title")
            if timeline.status_code == 200 and timeline.json()
            else None
        )
        self.tc_voltage = {
            "status": response.status_code,
            "count": response.json().get("count"),
            "rows": len(rows),
            "failing": {
                "passed": getattr(failing, "passed", None),
                "traceback": getattr(failing, "traceback", None),
                "assertions": getattr(failing, "assertions", None),
            },
            "passing": getattr(rows.get(p.RESULTS_PASSING_METHOD), "passed", None),
            "counts": self.counts(run_id),
            "event titles": [
                event.title for event in self.bud.bud_find_in_app(TestRunEvent, test_run_id=run_id)
            ],
            "timeline": (timeline.status_code, first_title),
        }
        run_id, response = self.upload_to_run(p.RESULTS_MIXED_RUN, p.RESULTS_MIXED)
        self.tc_mixed = {"status": response.status_code, "counts": self.counts(run_id)}
        response = self.upload({"results": p.RESULTS_DETACHED})
        run = self.stored_run(response.json().get("test_run_id"))
        self.tc_detached = {
            "status": response.status_code,
            "count": response.json().get("count"),
            "times in order": bool(
                run and run.started_at and run.completed_at and run.completed_at >= run.started_at
            ),
        }
        response = self.upload({**p.RESULTS_SOFTWARE, "results": p.RESULTS_SOFTWARE_RESULT})
        run = self.stored_run(response.json().get("test_run_id"))
        self.tc_software = {
            "status": response.status_code,
            "software": {field: getattr(run, field, None) for field in SOFTWARE_FIELDS},
        }

    def upload_to_run(self, run_fields, results):
        """Upload results to a running run of the test station on a fresh app."""
        self.bud.bud_start_app()
        station = self.bud.bud_add_test_station(with_run=False)
        run = self.bud.bud_add_to_app(
            TestRun(runner_id=station.id, status=self.parameters.RUN_RUNNING, **run_fields)
        )
        return run.id, self.bud.bud_station_request(
            self.parameters.POST,
            self.parameters.RESULTS_PATH,
            json={"test_run_id": run.id, "results": results},
        )

    def upload(self, payload):
        """Upload results without a run on a fresh app."""
        self.bud.bud_start_app()
        self.bud.bud_add_test_station(with_run=False)
        return self.bud.bud_station_request(
            self.parameters.POST, self.parameters.RESULTS_PATH, json=payload
        )

    def stored_run(self, run_id):
        """The stored run, or None."""
        found = self.bud.bud_find_in_app(TestRun, id=run_id)
        return found[0] if found else None

    def counts(self, run_id):
        """The run's total, passed and failed test counts."""
        run = self.stored_run(run_id)
        return (run.total_tests, run.passed_tests, run.failed_tests) if run else None

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ResultsApiTest().run()
