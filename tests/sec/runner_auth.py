"""
* @file     ${tests/sec/runner_auth.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests how Test Stations and uploaders authenticate.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of station tokens, heartbeats and token types.
"""

from tests.bud_test_base import BudAppTestCase


class RunnerAuthBase(BudAppTestCase):

    def bud_expired_station_claims_are_read_without_the_check(self):
        p, found = self.parameters, self.tc_ignore_exp
        self.print_variables(found)
        self.assertEqual(found["checked"], p.NONE_TYPE, msg=p.MSG_RUNNER_EXPIRED_REFUSED)
        self.assertEqual(found["claims"], found["expected"], msg=p.MSG_RUNNER_EXPIRED_CLAIMS)

    def bud_expired_station_token_needs_a_recent_heartbeat(self):
        p, found = self.parameters, self.tc_heartbeat
        self.print_variables(found)
        self.assertEqual(found["stale"], p.NONE_TYPE, msg=p.MSG_RUNNER_NO_HEARTBEAT)
        self.assertEqual(found["live"], found["live account"], msg=p.MSG_RUNNER_HEARTBEAT)

    def bud_uploader_is_the_station(self):
        p, found = self.parameters, self.tc_uploader
        self.print_variables(found)
        self.assertEqual(
            found["jwt"], ("Runner", found["jwt account"]), msg=p.MSG_RUNNER_UPLOADER_JWT
        )
        self.assertEqual(
            found["key"], ("Runner", found["key account"]), msg=p.MSG_RUNNER_UPLOADER_KEY
        )
        self.assertEqual(found["unpinned"], p.STATUS_UNAUTHORIZED, msg=p.MSG_RUNNER_UNPINNED_KEY)

    def bud_rotated_token_replaces_the_previous_one(self):
        p = self.parameters
        self.print_variables({"previous, current": self.tc_rotated})
        self.assertEqual(self.tc_rotated, (p.NONE_TYPE, "Runner"), msg=p.MSG_RUNNER_ROTATED)

    def bud_heartbeat_counts_only_within_the_timeout(self):
        self.assertEqual(
            self.tc_timeout, (False, True), msg=self.parameters.MSG_RUNNER_HEARTBEAT_TIMEOUT
        )

    def bud_tokens_of_unknown_or_no_type_are_refused(self):
        p, found = self.parameters, self.tc_types
        self.print_variables(found)
        self.assertEqual(found["entity"], p.STATUS_UNAUTHORIZED, msg=p.MSG_RUNNER_ODD_TYPE)
        self.assertEqual(found["uploader"], p.STATUS_UNAUTHORIZED, msg=p.MSG_RUNNER_ODD_TYPE)
        self.assertEqual(found["untyped"], p.STATUS_UNAUTHORIZED, msg=p.MSG_RUNNER_NO_TYPE)

    def bud_stale_user_token_cannot_upload(self):
        p, found = self.parameters, self.tc_stale_user
        self.print_variables(found)
        self.assertEqual(found["status"], p.STATUS_UNAUTHORIZED, msg=p.MSG_RUNNER_STALE_USER)
        self.assertIn(p.RUNNER_AUTH_REQUIRED, found["detail"], msg=p.MSG_RUNNER_STALE_TEXT)
