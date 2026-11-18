"""
* @file     ${tests/logic/timestamp_text.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the times Bud writes for people.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of the UTC time text.
"""

from tests.bud_test_base import BudAppTestCase


class TimestampTextBase(BudAppTestCase):

    def bud_time_stops_at_seconds(self):
        self.print_variables({"time": self.parameters.TIMESTAMP_NAIVE, "text": self.naive})
        self.assertEqual(
            self.naive,
            self.parameters.TIMESTAMP_TEXT,
            msg=self.parameters.MSG_TIMESTAMP_SECONDS,
            abort_on_fail=False,
        )

    def bud_no_time_is_empty(self):
        self.print_variables({"text": self.none})
        self.assertEqual(
            self.none,
            self.parameters.TIMESTAMP_NONE_TEXT,
            msg=self.parameters.MSG_TIMESTAMP_NONE,
            abort_on_fail=False,
        )

    def bud_aware_time_is_converted_to_utc(self):
        self.print_variables({"time": self.parameters.TIMESTAMP_AWARE, "text": self.aware})
        self.assertEqual(
            self.aware,
            self.parameters.TIMESTAMP_TEXT,
            msg=self.parameters.MSG_TIMESTAMP_AWARE,
            abort_on_fail=False,
        )
