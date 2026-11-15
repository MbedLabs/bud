"""
* @file     ${tests/api/runs_lifecycle_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the test run lifecycle and the system settings endpoints.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of creating, reading, updating and deleting runs, and of the settings.
"""

from tests.bud_test_base import BudAppTestCase


class RunsLifecycleApiBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_LIFE_CHECK}")

    def bud_a_station_creates_a_run(self):
        self.check("create")

    def bud_creating_a_run_records_an_event(self):
        self.check("creation event")

    def bud_reading_runs_finds_them_and_their_events(self):
        self.check("read")

    def bud_the_run_list_filters_and_pages(self):
        self.check("list")

    def bud_latest_per_suite_returns_one_run_each(self):
        self.check("latest")

    def bud_a_station_records_the_final_counters(self):
        self.check("counters")

    def bud_completing_a_run_stamps_and_records_it(self):
        self.check("completion")

    def bud_updates_of_unknown_runs_and_statuses_are_refused(self):
        self.check("update refusals")

    def bud_deleting_a_run_takes_its_results_with_it(self):
        self.check("deletion")

    def bud_the_statistics_aggregate_the_filtered_runs(self):
        self.check("stats")

    def bud_the_filter_options_list_real_suites_and_stations(self):
        self.check("options")

    def bud_the_system_settings_are_written_and_read(self):
        self.check("settings")

    def bud_the_bloom_integration_settings_keep_their_token_safe(self):
        self.check("plm")

    def bud_the_settings_need_a_signed_in_person(self):
        self.check("signed out")
