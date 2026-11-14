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
        self.print_variables({"time": self.parameters.TIMESTAMP_NAIVE, "text": self.tc_naive})
        self.assertEqual(
            self.tc_naive,
            self.parameters.TIMESTAMP_TEXT,
            msg=self.parameters.MSG_TIMESTAMP_SECONDS,
            abort_on_fail=False,
        )

    def bud_no_time_is_empty(self):
        self.print_variables({"text": self.tc_none})
        self.assertEqual(
            self.tc_none,
            self.parameters.TIMESTAMP_NONE_TEXT,
            msg=self.parameters.MSG_TIMESTAMP_NONE,
            abort_on_fail=False,
        )

    def bud_aware_time_is_converted_to_utc(self):
        self.print_variables({"time": self.parameters.TIMESTAMP_AWARE, "text": self.tc_aware})
        self.assertEqual(
            self.tc_aware,
            self.parameters.TIMESTAMP_TEXT,
            msg=self.parameters.MSG_TIMESTAMP_AWARE,
            abort_on_fail=False,
        )
