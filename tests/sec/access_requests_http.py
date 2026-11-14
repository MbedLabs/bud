"""
* @file     ${tests/sec/access_requests_http.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests asking the administrators for Publish to Bloom over HTTP.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the request, its mail, its decision and what it discloses.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class AccessRequestsHttpBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_ACCESS_CHECK}")

    def bud_a_request_mails_the_administrators_once_a_day(self):
        self.check("daily")

    def bud_an_administrator_decision_is_recorded_once(self):
        self.check("decision")

    def bud_an_anonymous_client_cannot_request(self):
        self.check("anonymous")

    def bud_only_known_resource_types_are_accepted(self):
        self.check("types")

    def bud_reviewers_see_each_requesters_picture_only(self):
        self.check("pictures")

    @parameterized(params.ACCESS_HOLDERS)
    def bud_a_holder_of_publish_to_bloom_is_refused_and_nobody_is_mailed(self, holder):
        self.check(holder)

    def bud_an_earlier_pending_request_does_not_answer_a_holder(self):
        self.check("earlier pending")

    def bud_the_requester_is_never_mailed_about_their_own_request(self):
        self.check("own request")

    def bud_stored_requests_of_earlier_types_stay_listed_named_and_decidable(self):
        self.check("earlier types")
