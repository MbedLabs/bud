"""
* @file     ${tests/sec/audit_log_http.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the audit log over HTTP.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of recorded events and who reads them.
"""

from tests.bud_test_base import BudAppTestCase


class AuditLogHttpBase(BudAppTestCase):

    def bud_everyone_signs_in(self):
        self.assertEqual(
            self.tc_logins,
            [self.parameters.STATUS_OK] * len(self.tc_logins),
            msg=self.parameters.MSG_AUDIT_SIGNED_IN,
        )

    def bud_failed_login_is_recorded(self):
        p, found = self.parameters, self.tc_failed
        self.print_variables(found)
        self.assertEqual(found["status"], p.STATUS_UNAUTHORIZED, msg=p.MSG_AUDIT_LOGIN_REFUSED)
        self.assertEqual(len(found["events"]), 1, msg=p.MSG_AUDIT_ONE_EVENT, abort_on_fail=True)
        event = found["events"][0]
        self.assertEqual(event.outcome, p.AUDIT_FAILURE, msg=p.MSG_AUDIT_OUTCOME)
        self.assertEqual(event.actor_type, p.AUDIT_ANONYMOUS, msg=p.MSG_AUDIT_ANONYMOUS)
        self.assertEqual(event.target_id, found["user id"], msg=p.MSG_AUDIT_TARGET)
        self.assertEqual(event.request_id, found["request id"], msg=p.MSG_AUDIT_REQUEST_ID)
        self.assertEqual(event.user_agent, p.AUDIT_USER_AGENT, msg=p.MSG_AUDIT_USER_AGENT)
        self.assertNotIn(p.AUDIT_WRONG_PASSWORD, found["details"], msg=p.MSG_AUDIT_NO_PASSWORD)

    def bud_deactivation_records_the_admin(self):
        p, found = self.parameters, self.tc_deactivated
        self.print_variables({key: value for key, value in found.items() if key != "events"})
        self.assertEqual(found["status"], p.STATUS_OK, msg=p.MSG_AUDIT_DEACTIVATED)
        self.assertEqual(len(found["events"]), 1, msg=p.MSG_AUDIT_ONE_EVENT, abort_on_fail=True)
        event = found["events"][0]
        self.assertEqual(event.actor_type, p.AUDIT_USER_ACTOR, msg=p.MSG_AUDIT_ACTOR_USER)
        self.assertEqual(event.actor_user_id, found["admin id"], msg=p.MSG_AUDIT_ACTOR_ADMIN)
        self.assertEqual(event.target_id, found["member id"], msg=p.MSG_AUDIT_TARGET)

    def bud_enrolment_key_is_recorded_without_the_key(self):
        p, found = self.parameters, self.tc_key
        self.print_variables({"statuses": found["statuses"], "minted details": found["details"]})
        self.assertEqual(
            found["statuses"], (p.STATUS_CREATED, p.STATUS_NO_CONTENT), msg=p.MSG_AUDIT_KEY_STATUSES
        )
        self.assertEqual(len(found["minted"]), 1, msg=p.MSG_AUDIT_ONE_EVENT, abort_on_fail=True)
        self.assertEqual(len(found["revoked"]), 1, msg=p.MSG_AUDIT_ONE_EVENT, abort_on_fail=True)
        self.assertEqual(
            found["minted"][0].details.get("label"), p.AUDIT_KEY_LABEL, msg=p.MSG_AUDIT_KEY_LABEL
        )
        self.assertNotIn(found["key"], found["details"], msg=p.MSG_AUDIT_NO_KEY)
        self.assertEqual(found["revoked"][0].target_id, found["key id"], msg=p.MSG_AUDIT_TARGET)

    def bud_only_administrators_read_the_audit_log(self):
        p, found = self.parameters, self.tc_readers
        self.print_variables(found)
        self.assertEqual(found["refused"], p.STATUS_FORBIDDEN, msg=p.MSG_AUDIT_MEMBER_REFUSED)
        self.assertEqual(found["page"], p.STATUS_OK, msg=p.MSG_AUDIT_ADMIN_READS)
        self.assertEqual(found["total"], p.AUDIT_PAGE_TOTAL, msg=p.MSG_AUDIT_TOTAL)
        self.assertEqual(found["actions"], {p.AUDIT_LOGIN_ACTION}, msg=p.MSG_AUDIT_ACTIONS)
        self.assertEqual(found["first actor"], p.AUDIT_ADMIN_NAME, msg=p.MSG_AUDIT_ACTOR_NAME)

    def bud_no_endpoint_changes_an_audit_event(self):
        self.assertEqual(
            self.tc_audit_methods,
            self.parameters.AUDIT_READ_METHODS,
            msg=self.parameters.MSG_AUDIT_READ_ONLY,
        )

    def bud_pictures_follow_their_accounts(self):
        p, found = self.parameters, self.tc_pictures
        self.print_variables({key: value for key, value in found.items() if key != "rounds"})
        self.assertEqual(found["saved"], [p.STATUS_OK, p.STATUS_OK], msg=p.MSG_AUDIT_PICTURE_SAVED)
        self.assertNotEqual(
            found["admin picture"], found["member picture"], msg=p.MSG_AUDIT_PICTURES_DIFFER
        )
        self.assertEqual(
            found["signed out"],
            [p.STATUS_UNAUTHORIZED] * len(p.AUDIT_GUARDED_PATHS),
            msg=p.MSG_AUDIT_SIGNED_OUT,
        )
        self.assertEqual(
            found["member"],
            [p.STATUS_FORBIDDEN] * len(p.AUDIT_GUARDED_PATHS),
            msg=p.MSG_AUDIT_MEMBER_PAGE,
        )
        for round_found in found["rounds"]:
            self.print_variables(round_found)
            self.assertEqual(round_found["changed"], p.STATUS_OK, msg=p.MSG_AUDIT_PICTURE_SAVED)
            self.assertEqual(round_found["page"], p.STATUS_OK, msg=p.MSG_AUDIT_PAGE)
            self.assertEqual(
                round_found["actors"], round_found["expected"], msg=p.MSG_AUDIT_ACTOR_PICTURE
            )
            self.assertEqual(round_found["listed"], p.STATUS_OK, msg=p.MSG_AUDIT_PAGE)
            self.assertEqual(
                round_found["users"], round_found["expected"], msg=p.MSG_AUDIT_USER_PICTURE
            )
