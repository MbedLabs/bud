"""
* @file     ${tests/api/station_naming.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests how Test Stations are named.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of named enrolment keys and renaming.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class StationNamingBase(BudAppTestCase):

    def bud_keys_are_minted(self):
        self.assertEqual(
            self.tc_minted,
            [self.parameters.STATUS_CREATED] * len(self.tc_minted),
            msg=self.parameters.MSG_KEY_MINTED,
        )

    def bud_chosen_name_wins(self):
        p = self.parameters
        self.print_variables({"status": self.tc_named.status_code, "body": self.tc_named.text})
        self.assertEqual(self.tc_named.status_code, p.STATUS_CREATED, msg=p.MSG_STATION_REGISTERED)
        self.assertEqual(
            self.tc_named.json().get("account"), p.STATION_NAMED, msg=p.MSG_STATION_NAME_WINS
        )

    def bud_unnamed_key_keeps_the_station_name(self):
        p = self.parameters
        self.print_variables({"status": self.tc_unnamed.status_code, "body": self.tc_unnamed.text})
        self.assertEqual(
            self.tc_unnamed.status_code, p.STATUS_CREATED, msg=p.MSG_STATION_REGISTERED
        )
        self.assertEqual(
            self.tc_unnamed.json().get("account"),
            p.STATION_REGISTRATION["username"],
            msg=p.MSG_STATION_OWN_NAME,
        )

    def bud_token_identifies_the_station_by_id(self):
        self.print_variables({"claims": self.tc_claims, "station id": self.tc_station_id})
        self.assertEqual(
            (self.tc_claims or {}).get("rid"),
            str(self.tc_station_id),
            msg=self.parameters.MSG_STATION_TOKEN_ID,
        )

    def bud_taken_name_is_refused(self):
        p = self.parameters
        self.print_variables({"status": self.tc_taken.status_code, "body": self.tc_taken.text})
        self.assertEqual(self.tc_taken.status_code, p.STATUS_CONFLICT, msg=p.MSG_STATION_NAME_TAKEN)
        self.assertIn(
            p.STATION_TAKEN_TEXT,
            str(self.tc_taken.json().get("detail")),
            msg=p.MSG_STATION_NAME_TAKEN_TEXT,
        )

    def bud_reserved_name_is_refused(self):
        p = self.parameters
        self.print_variables(
            {"status": self.tc_reserved.status_code, "body": self.tc_reserved.text}
        )
        self.assertEqual(
            self.tc_reserved.status_code, p.STATUS_CONFLICT, msg=p.MSG_STATION_NAME_RESERVED
        )
        self.assertIn(
            p.STATION_RESERVED_TEXT,
            str(self.tc_reserved.json().get("detail")),
            msg=p.MSG_STATION_NAME_RESERVED_TEXT,
        )

    @parameterized(params.STATION_BAD_NAMES)
    def bud_name_that_breaks_a_url_is_refused(self, name):
        self.assertEqual(
            self.tc_bad_names[name],
            self.parameters.STATUS_UNPROCESSABLE,
            msg=self.parameters.MSG_STATION_BAD_NAME,
        )

    def bud_administrator_renames_a_station(self):
        p = self.parameters
        self.print_variables({"status": self.tc_renamed.status_code, "body": self.tc_renamed.text})
        self.assertEqual(self.tc_renamed.status_code, p.STATUS_OK, msg=p.MSG_STATION_RENAMED)
        self.assertEqual(
            self.tc_renamed.json().get("account"), p.STATION_RENAMED, msg=p.MSG_STATION_NEW_NAME
        )
        self.assertEqual(self.tc_key_name, p.STATION_RENAMED, msg=p.MSG_STATION_KEY_RENAMED)

    def bud_renamed_station_keeps_its_token(self):
        p = self.parameters
        self.print_variables({"rename": self.tc_moved, "resolved": self.tc_resolved})
        self.assertEqual(self.tc_moved, p.STATUS_OK, msg=p.MSG_STATION_RENAMED)
        self.assertEqual(
            type(self.tc_resolved).__name__ != p.NONE_TYPE, True, msg=p.MSG_STATION_TOKEN_KEPT
        )
        self.assertEqual(
            getattr(self.tc_resolved, "account", None),
            p.STATION_MOVED,
            msg=p.MSG_STATION_TOKEN_NAME,
        )

    def bud_renaming_onto_a_taken_name_is_refused(self):
        self.assertEqual(
            self.tc_rename_taken,
            self.parameters.STATUS_CONFLICT,
            msg=self.parameters.MSG_STATION_RENAME_TAKEN,
        )

    def bud_renaming_an_unknown_station_is_not_found(self):
        self.assertEqual(
            self.tc_rename_unknown,
            self.parameters.STATUS_NOT_FOUND,
            msg=self.parameters.MSG_STATION_RENAME_UNKNOWN,
        )
