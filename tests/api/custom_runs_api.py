"""
* @file     ${tests/api/custom_runs_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests choosing test cases in Bud and having the right bench run them.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the catalogue, the queue, the claims and the completions.
"""

from tests.bud_test_base import BudAppTestCase


class CustomRunsApiBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_CUSTOM_CHECK}")

    def bud_the_catalogue_lists_each_case_once_with_its_benches(self):
        self.check("catalogue")

    def bud_the_catalogue_needs_a_signed_in_entity(self):
        self.check("catalogue signed out")

    def bud_a_request_takes_its_metadata_from_the_assigned_station(self):
        self.check("metadata")

    def bud_a_request_creates_no_execution_evidence(self):
        self.check("no evidence")

    def bud_a_selection_is_queued_on_the_benches_that_ran_it(self):
        self.check("assignment")

    def bud_pinning_a_bench_keeps_everything_on_it(self):
        self.check("pinning")

    def bud_unknown_cases_and_benches_are_reported(self):
        self.check("unknown")

    def bud_a_bench_cannot_queue_work(self):
        self.check("bench queue")

    def bud_queueing_needs_a_signed_in_entity(self):
        self.check("queue signed out")

    def bud_a_bench_claims_its_own_queued_run(self):
        self.check("claim")

    def bud_a_bench_never_sees_another_benchs_queue(self):
        self.check("other queue")

    def bud_a_retried_claim_returns_the_original(self):
        self.check("retried claim")

    def bud_an_active_claim_blocks_a_second(self):
        self.check("active claim")

    def bud_the_oldest_queued_run_is_claimed_first(self):
        self.check("oldest")

    def bud_a_person_cannot_claim(self):
        self.check("person claim")

    def bud_a_cancelled_claim_is_acknowledged_and_the_next_taken(self):
        self.check("cancelled")

    def bud_a_failed_execution_without_results_is_failed(self):
        self.check("failed execution")

    def bud_results_do_not_release_an_unacknowledged_claim(self):
        self.check("results release")

    def bud_claimed_run_stats_wait_for_the_station(self):
        self.check("stats wait")

    def bud_a_nonzero_exit_completes_the_execution(self):
        self.check("nonzero exit")

    def bud_completion_is_idempotent(self):
        self.check("idempotent")

    def bud_completion_needs_the_claim_key(self):
        self.check("wrong key")

    def bud_a_queued_request_is_listed_apart(self):
        self.check("listed apart")

    def bud_a_claim_links_the_request_to_its_execution(self):
        self.check("claim link")

    def bud_a_station_cannot_read_another_stations_request(self):
        self.check("foreign request")

    def bud_a_retained_placeholder_is_no_evidence(self):
        self.check("placeholder")
