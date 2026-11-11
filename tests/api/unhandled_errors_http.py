"""
* @file     ${tests/api/unhandled_errors_http.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests what an unhandled or integrity error tells the user.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of error answers and their references.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class UnhandledErrorsHttpBase(BudAppTestCase):

    def bud_500_carries_a_reference_to_quote(self):
        p, found = self.parameters, self.tc_boom
        self.print_variables(found)
        self.assertEqual(found["status"], p.STATUS_SERVER_ERROR, msg=p.MSG_ERROR_500)
        self.assertTrue(
            bool(found["reference"]), msg=p.MSG_ERROR_REFERENCE, actual=found["reference"]
        )
        self.assertEqual(
            found["body reference"], found["reference"], msg=p.MSG_ERROR_BODY_REFERENCE
        )
        self.assertIn(str(found["reference"]), found["detail"], msg=p.MSG_ERROR_DETAIL_REFERENCE)

    def bud_500_quotes_the_supplied_id(self):
        p, found = self.parameters, self.tc_supplied
        self.print_variables(found)
        self.assertEqual(found["status"], p.STATUS_SERVER_ERROR, msg=p.MSG_ERROR_500)
        self.assertEqual(found["reference"], p.ERROR_SUPPLIED_ID, msg=p.MSG_ERROR_SUPPLIED_HEADER)
        self.assertEqual(
            found["body reference"], p.ERROR_SUPPLIED_ID, msg=p.MSG_ERROR_BODY_REFERENCE
        )
        self.assertIn(
            p.ERROR_QUOTE.format(p.ERROR_SUPPLIED_ID),
            found["detail"],
            msg=p.MSG_ERROR_DETAIL_REFERENCE,
        )
        self.assertEqual(
            found["events"], [(p.ERROR_SUPPLIED_ID, p.STATUS_SERVER_ERROR)], msg=p.MSG_ERROR_EVENT
        )

    def bud_500_quotes_the_generated_id(self):
        p, found = self.parameters, self.tc_generated
        self.print_variables(found)
        self.assertNotEqual(found["reference"], p.ERROR_NO_ID, msg=p.MSG_ERROR_REFERENCE)
        self.assertEqual(len(found["reference"]), p.ERROR_ID_LENGTH, msg=p.MSG_ERROR_GENERATED)
        self.assertEqual(
            found["body reference"], found["reference"], msg=p.MSG_ERROR_BODY_REFERENCE
        )
        self.assertIn(
            p.ERROR_QUOTE.format(found["reference"]),
            found["detail"],
            msg=p.MSG_ERROR_DETAIL_REFERENCE,
        )

    @parameterized(params.ERROR_LEAKS)
    def bud_500_does_not_leak_the_exception(self, text):
        self.assertNotIn(text, self.tc_boom["text"], msg=self.parameters.MSG_ERROR_NO_LEAK)

    def bud_lost_race_is_a_conflict(self):
        p, found = self.parameters, self.tc_conflict
        self.print_variables(found)
        self.assertEqual(found["status"], p.STATUS_CONFLICT, msg=p.MSG_ERROR_CONFLICT)
        self.assertEqual(
            found["body reference"], found["reference"], msg=p.MSG_ERROR_BODY_REFERENCE
        )
        self.assertIn(
            str(found["body reference"]), found["detail"], msg=p.MSG_ERROR_DETAIL_REFERENCE
        )
        self.assertIn(p.ERROR_ALREADY_EXISTS, found["detail"], msg=p.MSG_ERROR_ALREADY_EXISTS)

    @parameterized(params.ERROR_CONSTRAINT_LEAKS)
    def bud_conflict_does_not_leak_the_constraint(self, text):
        self.assertNotIn(
            text, self.tc_conflict["text"], msg=self.parameters.MSG_ERROR_NO_CONSTRAINT
        )

    def bud_missing_reference_is_a_conflict(self):
        p, found = self.parameters, self.tc_missing_reference
        self.assertEqual(found["status"], p.STATUS_CONFLICT, msg=p.MSG_ERROR_FK)
        self.assertNotIn(p.ERROR_STILL_REFERENCED, found["text"], msg=p.MSG_ERROR_NO_LEAK)

    def bud_failing_commit_is_a_conflict(self):
        p, found = self.parameters, self.tc_late
        self.print_variables(found)
        self.assertEqual(found["status"], p.STATUS_CONFLICT, msg=p.MSG_ERROR_LATE)
        self.assertEqual(
            found["body reference"], found["reference"], msg=p.MSG_ERROR_BODY_REFERENCE
        )
        self.assertNotIn(p.ERROR_CONSTRAINT, found["text"], msg=p.MSG_ERROR_NO_CONSTRAINT)

    def bud_every_route_commits_before_its_response(self):
        p = self.parameters
        self.assertTrue(
            self.tc_session_routes > 0,
            msg=p.MSG_ERROR_SESSION_ROUTES,
            actual=self.tc_session_routes,
        )
        self.assertEqual(self.tc_late_routes, [], msg=p.MSG_ERROR_COMMIT_FIRST)
