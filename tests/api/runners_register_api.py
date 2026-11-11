"""
* @file     ${tests/api/runners_register_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests Test Station registration with an enrolment key.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of POST /api/runners/register and station removal.
"""

from tests.bud_test_base import BudAppTestCase


class RunnersRegisterApiBase(BudAppTestCase):

    def bud_minted_keys_are_minted(self):
        self.assertEqual(
            self.tc_minted,
            [self.parameters.STATUS_CREATED] * len(self.tc_minted),
            msg=self.parameters.MSG_KEY_MINTED,
        )

    def bud_registration_needs_a_known_key(self):
        p = self.parameters
        self.assertEqual(self.tc_no_key, p.STATUS_UNPROCESSABLE, msg=p.MSG_REGISTER_NO_KEY)
        self.assertEqual(self.tc_unknown_key, p.STATUS_FORBIDDEN, msg=p.MSG_REGISTER_UNKNOWN_KEY)

    def bud_minted_key_registers_and_pins_the_station(self):
        p, found = self.parameters, self.tc_pinned
        self.print_variables(found)
        self.assertEqual(found["status"], p.STATUS_CREATED, msg=p.MSG_REGISTER_CREATED)
        self.assertEqual(
            found["account"], p.REGISTER_PAYLOAD["username"], msg=p.MSG_REGISTER_ACCOUNT
        )
        self.assertEqual(bool(found["token"]), True, msg=p.MSG_REGISTER_TOKEN)
        self.assertEqual(found["pinned"], (found["station id"], True), msg=p.MSG_REGISTER_PINNED)

    def bud_same_station_registers_again(self):
        p, found = self.parameters, self.tc_again
        self.assertEqual(found["first"], p.STATUS_CREATED, msg=p.MSG_REGISTER_CREATED)
        self.assertEqual(found["second"], (p.STATUS_CREATED, True), msg=p.MSG_REGISTER_AGAIN)

    def bud_wrong_password_is_refused(self):
        p, found = self.parameters, self.tc_wrong_password
        self.print_variables(found)
        self.assertEqual(found["first"], p.STATUS_CREATED, msg=p.MSG_REGISTER_CREATED)
        self.assertEqual(found["status"], p.STATUS_BAD_REQUEST, msg=p.MSG_REGISTER_WRONG_PASSWORD)
        self.assertIn(
            p.REGISTER_MISMATCH_TEXT, found["detail"].lower(), msg=p.MSG_REGISTER_MISMATCH
        )

    def bud_pinned_key_cannot_enrol_another_station(self):
        p, found = self.parameters, self.tc_other_station
        self.print_variables(found)
        self.assertEqual(found["first"], p.STATUS_CREATED, msg=p.MSG_REGISTER_CREATED)
        self.assertEqual(found["status"], p.STATUS_FORBIDDEN, msg=p.MSG_REGISTER_OTHER_STATION)
        self.assertIn(
            p.REGISTER_ANOTHER_STATION_TEXT, found["detail"], msg=p.MSG_REGISTER_OTHER_TEXT
        )

    def bud_second_key_cannot_displace_the_first(self):
        p, found = self.parameters, self.tc_displace
        self.print_variables(found)
        self.assertEqual(found["first"], p.STATUS_CREATED, msg=p.MSG_REGISTER_CREATED)
        self.assertEqual(found["status"], p.STATUS_CONFLICT, msg=p.MSG_REGISTER_DISPLACE)
        self.assertIn(p.REGISTER_HAS_KEY_TEXT, found["detail"], msg=p.MSG_REGISTER_DISPLACE_TEXT)

    def bud_key_adopts_a_station_without_one(self):
        p, found = self.parameters, self.tc_adopt
        self.print_variables(found)
        self.assertEqual(found["status"], p.STATUS_CREATED, msg=p.MSG_REGISTER_CREATED)
        self.assertEqual(found["pinned"], [found["legacy id"]], msg=p.MSG_REGISTER_ADOPT)

    def bud_who_may_delete_stations_and_manage_keys(self):
        p, found = self.parameters, self.tc_deletes
        self.print_variables(found)
        self.assertEqual(found["registered"], [p.STATUS_CREATED] * 3, msg=p.MSG_REGISTER_CREATED)
        self.assertEqual(found["key delete"], p.STATUS_UNAUTHORIZED, msg=p.MSG_REGISTER_KEY_DELETE)
        self.assertEqual(
            found["viewer delete"], p.STATUS_FORBIDDEN, msg=p.MSG_REGISTER_VIEWER_DELETE
        )
        self.assertEqual(
            found["viewer keys"], [p.STATUS_FORBIDDEN] * 3, msg=p.MSG_REGISTER_VIEWER_KEYS
        )
        self.assertEqual(
            found["admin delete"], p.STATUS_NO_CONTENT, msg=p.MSG_REGISTER_ADMIN_DELETE
        )
