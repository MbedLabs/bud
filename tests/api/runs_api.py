"""
* @file     ${tests/api/runs_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests creating and listing test runs.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of run creation, sorting and pagination.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class RunsApiBase(BudAppTestCase):

    def bud_created_run_keeps_its_software(self):
        p, found = self.parameters, self.tc_created
        self.print_variables(found)
        self.assertEqual(found["status"], p.STATUS_CREATED, msg=p.MSG_RUNS_CREATED)
        self.assertEqual(found["stored"], found["expected"], msg=p.MSG_RUNS_SOFTWARE)

    def bud_latest_run_per_suite(self):
        p, found = self.parameters, self.tc_latest
        self.print_variables(found)
        self.assertEqual(found["status"], p.STATUS_OK, msg=p.MSG_RUNS_LISTED)
        self.assertEqual(found["total"], 2, msg=p.MSG_RUNS_LATEST_TOTAL)
        self.assertEqual(found["ids"], found["expected"], msg=p.MSG_RUNS_LATEST_ORDER)

    @parameterized(params.RUNS_SORT_FIELDS)
    def bud_runs_sort_both_ways(self, field):
        p = self.parameters
        for status, ids, expected in self.tc_sorted[field]["directions"]:
            self.print_variables({"field": field, "ids": ids, "expected": expected})
            self.assertEqual(status, p.STATUS_OK, msg=p.MSG_RUNS_LISTED)
            self.assertEqual(ids, expected, msg=p.MSG_RUNS_SORTED)
        for status, total, ids, expected in self.tc_sorted[field]["filters"]:
            self.assertEqual(status, p.STATUS_OK, msg=p.MSG_RUNS_LISTED)
            self.assertEqual(total, 1, msg=p.MSG_RUNS_STATION_FILTER)
            self.assertEqual(ids, expected, msg=p.MSG_RUNS_STATION_FILTER)

    @parameterized(params.RUNS_PAGES)
    def bud_sorting_happens_before_pagination(self, offset):
        p = self.parameters
        status, total, names = self.tc_pages[offset]
        self.print_variables({"offset": offset, "names": names})
        self.assertEqual(status, p.STATUS_OK, msg=p.MSG_RUNS_LISTED)
        self.assertEqual(total, p.RUNS_MATCHES, msg=p.MSG_RUNS_PAGE_TOTAL)
        self.assertEqual(
            names,
            [f"Match {index:02d}" for index in range(offset, offset + p.RUNS_PAGE_SIZE)],
            msg=p.MSG_RUNS_PAGE,
        )

    def bud_display_sort_keeps_winners_and_stable_ties(self):
        p = self.parameters
        for status, total, ids, expected in self.tc_display["latest"]:
            self.print_variables({"ids": ids, "expected": expected})
            self.assertEqual(status, p.STATUS_OK, msg=p.MSG_RUNS_LISTED)
            self.assertEqual(total, 2, msg=p.MSG_RUNS_LATEST_TOTAL)
            self.assertEqual(ids, expected, msg=p.MSG_RUNS_DISPLAY_LATEST)
        for ids, expected in self.tc_display["ties"]:
            self.assertEqual(ids, expected, msg=p.MSG_RUNS_STABLE_TIES)

    def bud_invalid_sorting_is_refused(self):
        self.assertEqual(
            self.tc_invalid,
            [self.parameters.STATUS_UNPROCESSABLE] * len(self.parameters.RUNS_INVALID_SORTS),
            msg=self.parameters.MSG_RUNS_INVALID_SORT,
        )
