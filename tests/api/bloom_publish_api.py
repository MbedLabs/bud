"""
* @file     ${tests/api/bloom_publish_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests publishing a run's reports to Bloom on request.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of what is published, how, and when it is refused.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class BloomPublishApiBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(
                found, expected, msg=f"{name}: {self.parameters.MSG_BLOOM_PUBLISH_CHECK}"
            )

    def bud_only_the_reports_are_published(self):
        self.check("chosen")

    def bud_the_endpoint_sends_the_reports_and_records_the_outcome(self):
        self.check("sent")

    def bud_the_files_travel_as_their_bytes(self):
        self.check("bytes")

    def bud_publishing_is_refused_while_bloom_is_not_configured(self):
        self.check("not configured")

    def bud_an_unfinished_run_without_reports_is_refused(self):
        self.check("unfinished")

    def bud_a_completed_legacy_run_gets_its_reports(self):
        self.check("legacy")

    @parameterized(params.BLOOM_PUBLISH_IDENTIFIERS)
    def bud_a_run_without_one_bloom_project_is_refused(self, case):
        self.check(case)

    def bud_a_refusal_from_bloom_is_reported(self):
        self.check("bloom refusal")

    def bud_an_unreachable_bloom_is_reported(self):
        self.check("unreachable")

    def bud_a_missing_run_is_not_found(self):
        self.check("missing run")

    def bud_finishing_a_run_publishes_nothing(self):
        self.check("finished")
