"""
* @file     ${tests/api/results_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the results a station uploads after a run.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of POST /api/results.
"""

from tests.bud_test_base import BudAppTestCase


class ResultsApiBase(BudAppTestCase):

    def bud_upload_keeps_assertions_and_counts_classes(self):
        p, found = self.parameters, self.tc_voltage
        self.print_variables({key: value for key, value in found.items() if key != "failing"})
        self.assertEqual(found["status"], p.STATUS_CREATED, msg=p.MSG_RESULTS_UPLOADED)
        self.assertEqual(found["count"], 2, msg=p.MSG_RESULTS_COUNT)
        self.assertEqual(found["rows"], 2, msg=p.MSG_RESULTS_ROWS)
        failing = found["failing"]
        self.assertEqual(failing.get("passed"), False, msg=p.MSG_RESULTS_FAILED_METHOD)
        self.assertIn(p.RESULTS_TRACE_WORD, failing.get("traceback") or "", msg=p.MSG_RESULTS_TRACE)
        self.assertEqual(len(failing.get("assertions") or []), 2, msg=p.MSG_RESULTS_ASSERTIONS)
        failed = next((a for a in failing.get("assertions") or [] if a.get("passed") is False), {})
        self.assertEqual(
            (failed.get("actual"), (failed.get("metadata") or {}).get("cell")),
            (p.RESULTS_FAILED_ACTUAL, p.RESULTS_FAILED_CELL),
            msg=p.MSG_RESULTS_FAILED_ASSERTION,
        )
        self.assertEqual(found["passing"], True, msg=p.MSG_RESULTS_PASSED_METHOD)
        self.assertEqual(found["counts"], p.RESULTS_VOLTAGE_COUNTS, msg=p.MSG_RESULTS_CLASS_COUNTS)
        self.assertIn(p.RESULTS_EVENT_TITLE, found["event titles"], msg=p.MSG_RESULTS_EVENT)
        self.assertEqual(
            found["timeline"], (p.STATUS_OK, p.RESULTS_EVENT_TITLE), msg=p.MSG_RESULTS_EVENTS_READ
        )

    def bud_two_classes_count_one_passed_and_one_failed(self):
        p, found = self.parameters, self.tc_mixed
        self.print_variables(found)
        self.assertEqual(found["status"], p.STATUS_CREATED, msg=p.MSG_RESULTS_UPLOADED)
        self.assertEqual(found["counts"], p.RESULTS_MIXED_COUNTS, msg=p.MSG_RESULTS_CLASS_COUNTS)

    def bud_detached_upload_creates_a_completed_run(self):
        p, found = self.parameters, self.tc_detached
        self.print_variables(found)
        self.assertEqual(found["status"], p.STATUS_CREATED, msg=p.MSG_RESULTS_UPLOADED)
        self.assertEqual(found["count"], 1, msg=p.MSG_RESULTS_COUNT)
        self.assertEqual(found["times in order"], True, msg=p.MSG_RESULTS_DETACHED_TIMES)

    def bud_detached_upload_keeps_the_software(self):
        p, found = self.parameters, self.tc_software
        self.print_variables(found)
        self.assertEqual(found["status"], p.STATUS_CREATED, msg=p.MSG_RESULTS_UPLOADED)
        expected = {**p.RESULTS_SOFTWARE}
        expected["test_case_list"] = expected.pop("test_suite_name")
        self.assertEqual(found["software"], expected, msg=p.MSG_RESULTS_SOFTWARE)
