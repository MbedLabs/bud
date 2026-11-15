"""
* @file     ${tests/api/BUD_results_upload_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    A Test Station submits results to its runs or new ones, and the run counts its test classes.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests station uploads on one started app and signed-out calls on another.
"""

from app.models import Product, TestResult
from tests.api.results_upload_api import ResultsUploadApiBase


class ResultsUploadApiTest(ResultsUploadApiBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.bud.bud_start_app()
        self.bud.bud_add_test_station(with_run=False)
        run_id = self.open_run(p.UPLOAD_NIGHTLY)
        response = self.upload({"test_run_id": run_id, "results": [p.UPLOAD_RESULT]})
        self.tc_existing = {
            "status": response.status_code,
            "answer": (response.json().get("test_run_id"), response.json().get("count")),
            "run id": run_id,
        }
        response = self.upload({"test_suite_name": p.UPLOAD_ADHOC, "results": [p.UPLOAD_RESULT]})
        run = self.read_run(response.json().get("test_run_id"))
        self.tc_adhoc = ((response.status_code, run[0]), run[1].get("name", ""))
        product = self.bud.bud_add_to_app(Product(name=p.UPLOAD_PRODUCT))
        response = self.upload(
            {
                "product_id": product.id,
                "test_suite_name": p.UPLOAD_REGRESSION,
                "results": [p.UPLOAD_RESULT],
            }
        )
        self.tc_product = (
            response.status_code,
            self.read_run(response.json().get("test_run_id"))[1].get("name", ""),
        )
        self.tc_accepts = {
            "missing run": self.upload(
                {"test_run_id": p.UPLOAD_MISSING, "results": [p.UPLOAD_RESULT]}
            ).status_code,
            "failing": self.upload(
                {
                    "test_suite_name": "Failures",
                    "results": [{**p.UPLOAD_RESULT, **p.UPLOAD_FAILING}],
                }
            ).status_code,
            "rich": self.upload(
                {"test_suite_name": "Rich", "results": [{**p.UPLOAD_RESULT, **p.UPLOAD_RICH}]}
            ).status_code,
            "no results": self.upload({"test_suite_name": "x"}).status_code,
        }
        mixed = self.read_run(self.upload_rows("Mixed", p.UPLOAD_MIXED))[1]
        self.tc_mixed = (
            mixed.get("total_tests"),
            mixed.get("passed_tests"),
            mixed.get("failed_tests"),
        )
        robot = self.read_run(self.upload_rows("Robot", p.UPLOAD_ROBOT))[1]
        self.tc_robot = tuple(
            robot.get(key)
            for key in ("total_tests", "passed_tests", "failed_tests", "skipped_tests")
        )
        self.tc_duration = self.read_run(self.upload_rows("Timed", p.UPLOAD_TIMED))[1].get(
            "duration_seconds"
        )
        self.tc_completion = self.completion()
        listed_run = self.upload_rows("Listed", [("C", "a", True, {}), ("C", "b", True, {})])
        listed = self.bud.bud_request(p.GET, p.RESULTS_RUN_PATH.format(listed_run))
        single_run = (
            self.upload({"test_suite_name": "Single", "results": [p.UPLOAD_RESULT]})
            .json()
            .get("test_run_id")
        )
        stored = self.bud.bud_find_in_app(TestResult, test_run_id=single_run)
        detail = self.bud.bud_request(
            p.GET, p.RESULT_DETAIL_PATH.format(stored[0].id if stored else 0)
        )
        self.tc_reading = {
            "listed": (
                listed.status_code,
                len(listed.json()) if listed.status_code == 200 else None,
            ),
            "list missing": self.bud.bud_request(
                p.GET, p.RESULTS_RUN_PATH.format(p.UPLOAD_MISSING)
            ).status_code,
            "detail": (detail.status_code, detail.json().get("test_class")),
            "detail missing": self.bud.bud_request(
                p.GET, p.RESULT_DETAIL_PATH.format(p.UPLOAD_MISSING)
            ).status_code,
        }
        self.bud.bud_start_app(signed_in=False)
        self.tc_signed_out = {
            (method, path): self.bud.bud_request(method, path, json={"results": []}).status_code
            for method, path in p.UPLOAD_SIGNED_OUT_CALLS
        }

    def upload(self, payload):
        """Submit results as the test station."""
        return self.bud.bud_station_request(
            self.parameters.POST, self.parameters.RESULTS_PATH, json=payload
        )

    def upload_rows(self, suite, rows):
        """Submit results built from (class, method, passed, extra) rows; return the run id."""
        results = [
            {
                **self.parameters.UPLOAD_RESULT,
                "test_class": test_class,
                "test_method": method,
                "passed": passed,
                **extra,
            }
            for test_class, method, passed, extra in rows
        ]
        return self.upload({"test_suite_name": suite, "results": results}).json().get("test_run_id")

    def open_run(self, payload):
        """Open a run as the test station and return its id."""
        return (
            self.bud.bud_station_request(
                self.parameters.POST, self.parameters.TEST_RUNS_PATH, json=payload
            )
            .json()
            .get("id")
        )

    def read_run(self, run_id):
        """Read a run: its status code and body."""
        response = self.bud.bud_request(
            self.parameters.GET, self.parameters.TEST_RUN_PATH.format(run_id)
        )
        return response.status_code, response.json() if response.status_code == 200 else {}

    def completion(self):
        """A run before and after its upload, with its timeline."""
        p = self.parameters
        run_id = self.open_run({"test_suite_name": "ToComplete", "test_case_list": "C"})
        before = self.read_run(run_id)[1].get("status")
        events_before = len(self.bud.bud_request(p.GET, p.RUN_EVENTS_PATH.format(run_id)).json())
        self.upload({"test_run_id": run_id, "results": [p.UPLOAD_RESULT]})
        after = self.read_run(run_id)[1]
        events = self.bud.bud_request(p.GET, p.RUN_EVENTS_PATH.format(run_id)).json()
        return {
            "statuses": (before, after.get("status")),
            "completed": after.get("completed_at") is not None,
            "events before": events_before,
            "events after": len(events),
            "titled": any(p.RESULTS_EVENT_TITLE in event.get("title", "") for event in events),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ResultsUploadApiTest().run()
