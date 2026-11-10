"""
* @file     ${tests/sec/run_producer_http.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests that only stations write test run records.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of the run producer checks.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from app.models.user import UserRole
from tests.bud_test_base import BudAppTestCase

HUMAN_WRITES = [
    f"{role.value}, {operation}" for role in UserRole for operation in params.RUN_WRITE_OPERATIONS
]


class RunProducerHttpBase(BudAppTestCase):

    @parameterized(HUMAN_WRITES)
    def bud_person_cannot_write_a_run_record(self, case):
        found = self.tc_human[case]
        self.print_variables({"case": case, **found})
        self.assertEqual(
            found["status code"],
            self.parameters.STATUS_FORBIDDEN,
            msg=self.parameters.MSG_PRODUCER_HUMAN_REFUSED,
            abort_on_fail=False,
        )
        self.assertEqual(
            found["run status"],
            self.parameters.RUN_RUNNING,
            msg=self.parameters.MSG_PRODUCER_STATUS_KEPT,
            abort_on_fail=False,
        )
        self.assertEqual(
            found["total tests"],
            self.parameters.PRODUCER_UNTOUCHED_TOTAL,
            msg=self.parameters.MSG_PRODUCER_TOTAL_KEPT,
            abort_on_fail=False,
        )
        self.assertEqual(
            type(found["completed at"]).__name__,
            self.parameters.NONE_TYPE,
            msg=self.parameters.MSG_PRODUCER_NOT_COMPLETED,
            abort_on_fail=False,
        )
        self.assertEqual(
            found["runs"],
            self.parameters.PRODUCER_RUN_COUNT,
            msg=self.parameters.MSG_PRODUCER_NO_NEW_RUN,
            abort_on_fail=False,
        )
        self.assertEqual(
            found["run events"],
            self.parameters.PRODUCER_EVENT_COUNT,
            msg=self.parameters.MSG_PRODUCER_NO_EVENT,
            abort_on_fail=False,
        )

    def bud_station_creates_its_run(self):
        self.print_variables({"status": self.tc_created.status_code, "body": self.tc_created.text})
        self.assertEqual(
            self.tc_created.status_code,
            self.parameters.STATUS_CREATED,
            msg=self.parameters.MSG_PRODUCER_STATION_CREATES,
            abort_on_fail=True,
        )

    def bud_station_updates_its_run(self):
        self.print_variables({"status": self.tc_updated.status_code, "body": self.tc_updated.text})
        self.assertEqual(
            self.tc_updated.status_code,
            self.parameters.STATUS_OK,
            msg=self.parameters.MSG_PRODUCER_STATION_UPDATES,
            abort_on_fail=False,
        )

    def bud_run_keeps_what_the_station_reported(self):
        run = self.tc_station_run
        self.assertEqual(
            run.runner_id,
            self.tc_station_id,
            msg=self.parameters.MSG_PRODUCER_RUN_OWNER,
            abort_on_fail=False,
        )
        self.assertEqual(
            (run.total_tests, run.passed_tests, run.failed_tests),
            self.parameters.PRODUCER_COUNTS,
            msg=self.parameters.MSG_PRODUCER_RUN_COUNTS,
            abort_on_fail=False,
        )
        self.assertEqual(
            run.ref_test_software,
            self.parameters.PRODUCER_REF,
            msg=self.parameters.MSG_PRODUCER_RUN_REF,
            abort_on_fail=False,
        )
