"""
* @file     ${tests/api/report_requests_http.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests collecting Bloom readers' report requests, notifying publishers and deciding them.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the collection, the mail, the refusal and the publication.
"""

from tests.bud_test_base import BudAppTestCase


class ReportRequestsHttpBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_REPORT_CHECK}")

    def bud_collection_is_durable_and_mails_only_active_publishers(self):
        self.check("collection")

    def bud_failed_mail_retries_and_the_remote_state_is_reconciled(self):
        self.check("retry")

    def bud_refusal_needs_a_publisher_and_a_confirmed_remote_answer(self):
        self.check("refusal")

    def bud_publishing_closes_only_matching_requests_after_remote_success(self):
        self.check("publication")

    def bud_publisher_mail_renders_the_run_link_and_escapes_reader_text(self):
        self.check("mail")

    def bud_notified_recipients_survive_a_later_mail_failure(self):
        self.check("checkpoints")

    def bud_collection_pages_new_requests_without_replaying_closed_ones(self):
        self.check("paging")

    def bud_a_request_for_another_project_is_refused_before_publication(self):
        self.check("destination")

    def bud_refusal_reconciles_a_request_bloom_already_delivered(self):
        self.check("delivered")

    def bud_requests_removed_in_bloom_close_without_another_mail(self):
        self.check("removed")
