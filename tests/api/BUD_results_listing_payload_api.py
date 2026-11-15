"""
* @file     ${tests/api/BUD_results_listing_payload_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    A run's result listing carries every column the run detail draws but the method traceback.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests a station's failed result and two results recorded in order.
"""

from app.models import TestResult
from tests.api.results_listing_payload_api import ResultsListingPayloadApiBase


class ResultsListingPayloadApiTest(ResultsListingPayloadApiBase):

    def setUpClass(self):
        super().setUpClass()
        p, station, request = self.parameters, self.bud.bud_station_request, self.bud.bud_request
        self.bud.bud_start_app()
        self.bud.bud_add_test_station(with_run=False)
        run_id = station(p.POST, p.TEST_RUNS_PATH, json=p.RESULT_RUN).json().get("id")
        self.tc_upload = station(
            p.POST, p.RESULTS_PATH, json={"test_run_id": run_id, "results": [p.RESULT_FAILURE]}
        )
        self.tc_rows = request(p.GET, p.RESULTS_RUN_PATH.format(run_id)).json()
        stored = self.bud.bud_find_in_app(TestResult, test_run_id=run_id)
        result_id = stored[0].id if stored else None
        self.tc_stored_trace = stored[0].traceback if stored else None
        self.tc_detail = request(p.GET, p.RESULT_DETAIL_PATH.format(result_id)).json()
        ordered_run = station(p.POST, p.TEST_RUNS_PATH, json=p.RESULT_ORDERED_RUN).json().get("id")
        station(
            p.POST,
            p.RESULTS_PATH,
            json={
                "test_run_id": ordered_run,
                "results": [
                    {**p.RESULT_FAILURE, "test_method": method, "passed": True}
                    for method in p.RESULT_ORDER
                ],
            },
        )
        self.tc_order = [
            row.get("test_method")
            for row in request(p.GET, p.RESULTS_RUN_PATH.format(ordered_run)).json()
        ]
        self.tc_missing_run = request(
            p.GET, p.RESULTS_RUN_PATH.format(p.RESULT_MISSING_RUN)
        ).status_code

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ResultsListingPayloadApiTest().run()
