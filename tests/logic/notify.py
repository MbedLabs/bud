"""
* @file     ${tests/logic/notify.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the run-finished notifications.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the summary, the renderers, the filters and the delivery.
"""

from tests.bud_test_base import BudAppTestCase


class NotifyBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_NOTIFY_CHECK}")

    def bud_the_outcome_follows_the_counts(self):
        self.check("outcome")

    def bud_a_station_failure_without_results_reaches_failure_channels(self):
        self.check("station failure")

    def bud_claimed_runs_wait_for_the_station_answer(self):
        self.check("claim")

    def bud_the_failed_list_is_capped(self):
        self.check("failed line")

    def bud_every_format_carries_the_links_and_the_sync_failure(self):
        self.check("formats")

    def bud_each_renderer_has_its_shape(self):
        self.check("shapes")

    def bud_the_signature_is_hmac_sha256(self):
        self.check("signature")

    def bud_the_summary_describes_a_finished_run(self):
        self.check("summary")

    def bud_a_run_without_station_was_started_by_ci(self):
        self.check("ci")

    def bud_delivery_retries_and_records_each_attempt(self):
        self.check("retries")

    def bud_delivery_gives_up_after_three_attempts(self):
        self.check("gives up")

    def bud_a_finished_run_posts_once_per_channel(self):
        self.check("once")

    def bud_without_channel_nothing_is_sent(self):
        self.check("no channel")

    def bud_channels_filter_the_runs(self):
        self.check("filters")

    def bud_teams_connector_addresses_get_a_message_card(self):
        self.check("connector")

    def bud_teams_workflow_addresses_get_an_adaptive_card(self):
        self.check("workflow")

    def bud_the_discord_embed_has_a_timestamp(self):
        self.check("discord")

    def bud_teams_delivery_picks_the_card_from_the_address(self):
        self.check("teams delivery")

    def bud_a_redirect_is_not_a_delivery(self):
        self.check("redirect")
