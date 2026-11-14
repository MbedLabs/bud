"""
* @file     ${tests/logic/audit_prune.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the audit prune command.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of the events removed and kept.
"""

from tests.bud_test_base import BudAppTestCase


class AuditPruneBase(BudAppTestCase):

    def bud_old_event_is_removed(self):
        self.print_variables({"removed": self.tc_removed})
        self.assertEqual(
            self.tc_removed,
            self.parameters.AUDIT_PRUNED,
            msg=self.parameters.MSG_AUDIT_PRUNED,
            abort_on_fail=False,
        )

    def bud_event_inside_the_retention_is_kept(self):
        self.print_variables({"left": self.tc_left})
        self.assertEqual(
            self.tc_left,
            self.parameters.AUDIT_LEFT,
            msg=self.parameters.MSG_AUDIT_LEFT,
            abort_on_fail=False,
        )
