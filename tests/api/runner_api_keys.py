"""
* @file     ${tests/api/runner_api_keys.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests Test Station enrolment keys.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of key authentication, minting and revoking.
"""

from tests.bud_test_base import BudAppTestCase


class RunnerApiKeysBase(BudAppTestCase):

    def bud_key_files_results_only_as_its_station(self):
        p, found = self.parameters, self.tc_impersonation
        self.print_variables(found)
        self.assertEqual(found["status"], p.STATUS_CREATED, msg=p.MSG_KEYS_FILED)
        self.assertEqual(len(found["owners"]), 1, msg=p.MSG_KEYS_ONE_RUN)
        self.assertEqual(found["owners"], [found["mine"]], msg=p.MSG_KEYS_OWN_STATION)

    def bud_keys_that_name_no_active_station_are_refused(self):
        p, found = self.parameters, self.tc_refused
        self.print_variables(found)
        self.assertEqual(found["unpinned"], p.STATUS_UNAUTHORIZED, msg=p.MSG_KEYS_UNPINNED)
        self.assertEqual(found["unknown"], p.STATUS_UNAUTHORIZED, msg=p.MSG_KEYS_UNKNOWN)
        self.assertEqual(found["unknown results"], 0, msg=p.MSG_KEYS_NO_RESULT)
        self.assertEqual(found["inactive"], p.STATUS_UNAUTHORIZED, msg=p.MSG_KEYS_INACTIVE)

    def bud_key_authenticates_its_own_station(self):
        p, found = self.parameters, self.tc_own
        self.print_variables(found)
        self.assertEqual(found["status"], p.STATUS_CREATED, msg=p.MSG_KEYS_FILED)
        self.assertEqual(found["owner"], found["mine"], msg=p.MSG_KEYS_OWN_STATION)

    def bud_removing_a_station_keeps_its_runs_and_revokes_its_keys(self):
        p, found = self.parameters, self.tc_removed
        self.print_variables(found)
        self.assertEqual(found["status"], p.STATUS_NO_CONTENT, msg=p.MSG_KEYS_REMOVED)
        self.assertEqual(found["stations"], 0, msg=p.MSG_KEYS_STATION_GONE)
        self.assertEqual(found["keys"], 0, msg=p.MSG_KEYS_REVOKED_WITH_STATION)
        self.assertEqual(found["run"], (True, p.NONE_TYPE), msg=p.MSG_KEYS_RUN_KEPT)

    def bud_minted_key_is_returned_once_and_never_listed(self):
        p, found = self.parameters, self.tc_minted
        self.print_variables(found)
        self.assertEqual(found["status"], p.STATUS_CREATED, msg=p.MSG_KEYS_MINTED)
        self.assertRegex(found["secret"], f"^{p.KEYS_PREFIX}", msg=p.MSG_KEYS_SECRET_PREFIX)
        self.assertEqual(type(found["station"]).__name__, p.NONE_TYPE, msg=p.MSG_KEYS_NO_STATION)
        self.assertEqual(found["listed status"], p.STATUS_OK, msg=p.MSG_KEYS_LISTED)
        self.assertEqual(len(found["rows"]), 1, msg=p.MSG_KEYS_ONE_LISTED, abort_on_fail=True)
        self.assertNotIn("api_key", found["rows"][0], msg=p.MSG_KEYS_NOT_LISTED)
        self.assertEqual(
            found["rows"][0].get("key_prefix"),
            found["secret"][: p.KEYS_PREFIX_LENGTH],
            msg=p.MSG_KEYS_PREFIX,
        )
        self.assertNotIn(found["secret"], found["listed text"], msg=p.MSG_KEYS_NOT_LISTED)
        self.assertEqual(len(found["hashes"]), 1, msg=p.MSG_KEYS_ONE_LISTED)
        self.assertNotIn(found["secret"], found["hashes"], msg=p.MSG_KEYS_HASHED)

    def bud_revoked_key_no_longer_authenticates(self):
        p, found = self.parameters, self.tc_revoked
        self.print_variables(found)
        self.assertEqual(found["accepted"], p.STATUS_CREATED, msg=p.MSG_KEYS_ACCEPTED)
        self.assertEqual(found["refused"], p.STATUS_UNAUTHORIZED, msg=p.MSG_KEYS_REVOKED)

    def bud_administrator_revokes_a_key(self):
        p, found = self.parameters, self.tc_admin_revoke
        self.print_variables(found)
        self.assertEqual(found["created"], p.STATUS_CREATED, msg=p.MSG_KEYS_MINTED)
        self.assertEqual(found["revoked"], p.STATUS_NO_CONTENT, msg=p.MSG_KEYS_REVOKE)
        self.assertEqual(found["listed"], [], msg=p.MSG_KEYS_EMPTY)
        self.assertEqual(found["stored"], 0, msg=p.MSG_KEYS_GONE)
        self.assertEqual(found["again"], p.STATUS_NOT_FOUND, msg=p.MSG_KEYS_REVOKE_AGAIN)
