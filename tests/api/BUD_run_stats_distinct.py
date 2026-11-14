"""
* @file     ${tests/api/BUD_run_stats_distinct.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The run statistics count each test once by its latest run, and every test execution.
* @author   Amine El Omari
* @date     2026-11-07
* @version  1.0.0
* @note     This module tests one suite run several times and another suite on one Test Station.
"""

from tests.api.run_stats_distinct import RunStatsDistinctBase


class RunStatsDistinctTest(RunStatsDistinctBase):

    def setUpClass(self):
        super().setUpClass()
        station_id = self.bud.bud_add_station(self.parameters.STATION_ACCOUNT)
        for index in range(self.parameters.RUN_COUNT - 1):
            self.bud.bud_add_run(
                self.parameters.SUITE,
                station_id,
                self.parameters.FIRST_RUN_AT + index * self.parameters.RUN_SPACING,
                self.parameters.TEST_CLASSES,
                self.parameters.EARLIER_OUTCOMES,
            )
        self.bud.bud_add_run(
            self.parameters.SUITE,
            station_id,
            self.parameters.FIRST_RUN_AT
            + (self.parameters.RUN_COUNT - 2) * self.parameters.RUN_SPACING,
            self.parameters.TEST_CLASSES,
            self.parameters.LATEST_OUTCOMES,
        )
        self.bud.bud_add_run(
            self.parameters.OTHER_SUITE,
            station_id,
            self.parameters.FIRST_RUN_AT,
            self.parameters.OTHER_SUITE_CLASSES,
            [self.parameters.PASSED] * len(self.parameters.OTHER_SUITE_CLASSES),
        )
        self.bud.bud_start_api()
        self.tc_suite_stats = self.bud.bud_get_stats(suite=self.parameters.SUITE)
        self.tc_all_stats = self.bud.bud_get_stats()

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    RunStatsDistinctTest().run()
