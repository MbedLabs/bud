"""
* @file     ${tests/api/BUD_run_stats_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The run statistics count every matching run by time window, suite and Test Station.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests two suites on two Test Stations, one run older than 7 days and one pending.
"""

from datetime import datetime, timezone

from app.models import Runner, TestRun
from tests.api.run_stats_api import RunStatsApiBase


class RunStatsApiTest(RunStatsApiBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.bud.bud_start_app()
        stations = [
            self.bud.bud_add_to_app(
                Runner(account=account, password_hash=p.STATS_STATION_PASSWORD, token=f"t{index}")
            )
            for index, account in enumerate(p.STATS_STATIONS, start=1)
        ]
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for name, status, passed, failed, old, station in p.STATS_RUNS:
            self.bud.bud_add_to_app(
                TestRun(
                    name=name,
                    test_case_list=f"{name}.cases",
                    status=status,
                    total_tests=passed + failed,
                    passed_tests=passed,
                    failed_tests=failed,
                    skipped_tests=0,
                    created_at=now - p.STATS_OLD_AGE if old else now,
                    runner_id=stations[station].id,
                )
            )
        self.tc_stats = {
            case: self.bud.bud_request(p.GET, p.RUN_STATS_PATH, params=query)
            for case, (query, _) in p.STATS_CASES.items()
        }
        self.tc_options = self.bud.bud_request(p.GET, p.RUN_FILTER_OPTIONS_PATH)
        self.tc_literal = {
            path: self.bud.bud_request(p.GET, path).status_code for path in p.STATS_LITERAL_PATHS
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    RunStatsApiTest().run()
