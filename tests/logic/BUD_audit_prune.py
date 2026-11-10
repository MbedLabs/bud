"""
* @file     ${tests/logic/BUD_audit_prune.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The audit prune command removes only events older than the retention it is given.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module tests one event older and one newer than a 30-day retention.
"""

from tests.logic.audit_prune import AuditPruneBase


class AuditPruneTest(AuditPruneBase):

    def setUpClass(self):
        super().setUpClass()
        self.bud.bud_add_audit_event(self.parameters.AUDIT_OLD_ACTION, self.parameters.AUDIT_OLD_AGE)
        self.bud.bud_add_audit_event(self.parameters.AUDIT_NEW_ACTION, self.parameters.AUDIT_NEW_AGE)
        self.tc_removed = self.bud.bud_prune_audit(self.parameters.AUDIT_RETENTION_DAYS)
        self.tc_left = self.bud.bud_audit_actions()

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    AuditPruneTest().run()
