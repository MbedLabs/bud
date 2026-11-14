"""
* @file     ${tests/logic/BUD_timestamp_text.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Times Bud writes for people are in UTC, to the second.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module tests second_utc with a plain time, no time and a time with an offset.
"""

from app.core import timestamps
from tests.logic.timestamp_text import TimestampTextBase


class TimestampTextTest(TimestampTextBase):

    def setUpClass(self):
        super().setUpClass()
        self.tc_naive = timestamps.second_utc(self.parameters.TIMESTAMP_NAIVE)
        self.tc_none = timestamps.second_utc(None)
        self.tc_aware = timestamps.second_utc(self.parameters.TIMESTAMP_AWARE)

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    TimestampTextTest().run()
