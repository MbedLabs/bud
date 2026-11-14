"""
* @file     ${tests/sec/audit_labels_http.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the names the audit log gives the objects its events refer to.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of event labels and deleted marks.
"""

from tests.bud_test_base import BudAppTestCase


class AuditLabelsHttpBase(BudAppTestCase):

    def bud_administrator_reads_the_labelled_events(self):
        p = self.parameters
        self.assertEqual(self.tc_logins, [p.STATUS_OK, p.STATUS_OK], msg=p.MSG_LABELS_SIGNED_IN)
        self.assertEqual(self.tc_pages, [p.STATUS_OK, p.STATUS_OK], msg=p.MSG_LABELS_PAGE)

    def bud_events_name_their_targets_and_mark_deleted_ones(self):
        for (action, field), (found, expected) in self.tc_named.items():
            self.print_variables({"event": action, "field": field})
            self.assertEqual(found, expected, msg=self.parameters.MSG_LABELS_NAMED)

    def bud_deleted_run_keeps_its_id(self):
        self.assertEqual(
            self.tc_gone_id, self.tc_gone_expected, msg=self.parameters.MSG_LABELS_TARGET_ID
        )

    def bud_stored_event_keeps_its_target(self):
        self.assertEqual(
            self.tc_stored, self.tc_stored_expected, msg=self.parameters.MSG_LABELS_STORED
        )

    def bud_other_objects_are_named_and_odd_ids_are_not(self):
        self.print_variables({"labels": self.tc_odd})
        self.assertEqual(self.tc_odd, self.tc_odd_expected, msg=self.parameters.MSG_LABELS_ODD)
        self.assertEqual(
            self.tc_channel_created,
            self.parameters.LABELS_CHANNEL["name"],
            msg=self.parameters.MSG_LABELS_CHANNEL_CREATED,
        )
