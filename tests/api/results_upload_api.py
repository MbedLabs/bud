"""
* @file     ${tests/api/results_upload_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests result submission as a Test Station drives it.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of uploading, run statistics and reading results.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class ResultsUploadApiBase(BudAppTestCase):

    def bud_uploads_against_an_existing_run(self):
        p, found = self.parameters, self.tc_existing
        self.print_variables(found)
        self.assertEqual(found["status"], p.STATUS_CREATED, msg=p.MSG_UPLOAD_EXISTING)
        self.assertEqual(found["answer"], (found["run id"], 1), msg=p.MSG_UPLOAD_ANSWER)

    def bud_results_without_a_run_create_one(self):
        p = self.parameters
        self.print_variables({"ad hoc": self.tc_adhoc, "product": self.tc_product})
        self.assertEqual(
            self.tc_adhoc[0], (p.STATUS_CREATED, p.STATUS_OK), msg=p.MSG_UPLOAD_CREATES_RUN
        )
        self.assertIn(p.UPLOAD_ADHOC, self.tc_adhoc[1], msg=p.MSG_UPLOAD_CREATES_RUN)
        self.assertEqual(self.tc_product[0], p.STATUS_CREATED, msg=p.MSG_UPLOAD_CREATES_RUN)
        self.assertIn(p.UPLOAD_PRODUCT, self.tc_product[1], msg=p.MSG_UPLOAD_PRODUCT_NAME)
        self.assertIn(p.UPLOAD_REGRESSION, self.tc_product[1], msg=p.MSG_UPLOAD_PRODUCT_NAME)

    def bud_what_an_upload_accepts(self):
        p, found = self.parameters, self.tc_accepts
        self.print_variables(found)
        self.assertEqual(found["missing run"], p.STATUS_NOT_FOUND, msg=p.MSG_UPLOAD_MISSING_RUN)
        self.assertEqual(found["failing"], p.STATUS_CREATED, msg=p.MSG_UPLOAD_FAILING)
        self.assertEqual(found["rich"], p.STATUS_CREATED, msg=p.MSG_UPLOAD_RICH)
        self.assertEqual(found["no results"], p.STATUS_UNPROCESSABLE, msg=p.MSG_UPLOAD_NO_RESULTS)

    def bud_run_counts_test_classes(self):
        p = self.parameters
        self.assertEqual(self.tc_mixed, p.UPLOAD_MIXED_COUNTS, msg=p.MSG_UPLOAD_CLASS_COUNTS)
        self.assertEqual(self.tc_robot, p.UPLOAD_ROBOT_COUNTS, msg=p.MSG_UPLOAD_SKIPPED)
        self.assertInTolerance(
            self.tc_duration, p.UPLOAD_TIMED_TOTAL, p.UPLOAD_TOLERANCE, msg=p.MSG_UPLOAD_DURATION
        )

    def bud_uploading_completes_the_run_and_records_an_event(self):
        p, found = self.parameters, self.tc_completion
        self.print_variables(found)
        self.assertEqual(found["statuses"], p.UPLOAD_STATUSES, msg=p.MSG_UPLOAD_COMPLETES)
        self.assertEqual(found["completed"], True, msg=p.MSG_UPLOAD_COMPLETES)
        self.assertGreater(found["events after"], found["events before"], msg=p.MSG_UPLOAD_EVENT)
        self.assertEqual(found["titled"], True, msg=p.MSG_UPLOAD_EVENT)

    def bud_reading_results(self):
        p, found = self.parameters, self.tc_reading
        self.print_variables(found)
        self.assertEqual(found["listed"], (p.STATUS_OK, 2), msg=p.MSG_UPLOAD_LISTED)
        self.assertEqual(found["list missing"], p.STATUS_NOT_FOUND, msg=p.MSG_UPLOAD_LIST_MISSING)
        self.assertEqual(
            found["detail"], (p.STATUS_OK, p.UPLOAD_RESULT["test_class"]), msg=p.MSG_UPLOAD_DETAIL
        )
        self.assertEqual(
            found["detail missing"], p.STATUS_NOT_FOUND, msg=p.MSG_UPLOAD_DETAIL_MISSING
        )

    @parameterized(params.UPLOAD_SIGNED_OUT_CALLS)
    def bud_signed_out_visitor_cannot_reach_results(self, method, path):
        self.assertEqual(
            self.tc_signed_out[(method, path)],
            self.parameters.STATUS_UNAUTHORIZED,
            msg=self.parameters.MSG_UPLOAD_SIGNED_OUT,
        )
