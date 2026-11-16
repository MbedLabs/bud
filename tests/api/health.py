"""
* @file     ${tests/api/health.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the liveness and readiness probes.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of /api/health and /api/ready.
"""

from tests.bud_test_base import BudAppTestCase


class HealthBase(BudAppTestCase):

    def bud_health_answers(self):
        self.print_variables({"status": self.health.status_code, "body": self.health.text})
        self.assertEqual(
            self.health.status_code,
            self.parameters.STATUS_OK,
            msg=self.parameters.MSG_HEALTH_ANSWERS,
            abort_on_fail=True,
        )

    def bud_health_is_healthy(self):
        self.assertEqual(
            self.health.json()["status"],
            self.parameters.HEALTH_HEALTHY,
            msg=self.parameters.MSG_HEALTH_HEALTHY,
            abort_on_fail=False,
        )

    def bud_health_does_not_claim_the_database(self):
        self.assertNotEqual(
            self.health.json().get("database"),
            self.parameters.DATABASE_CONNECTED,
            msg=self.parameters.MSG_HEALTH_NO_DATABASE,
            abort_on_fail=False,
        )

    def bud_ready_answers(self):
        self.print_variables({"status": self.ready.status_code, "body": self.ready.text})
        self.assertEqual(
            self.ready.status_code,
            self.parameters.STATUS_OK,
            msg=self.parameters.MSG_READY_ANSWERS,
            abort_on_fail=True,
        )

    def bud_ready_is_ready(self):
        self.assertEqual(
            self.ready.json()["status"],
            self.parameters.HEALTH_READY,
            msg=self.parameters.MSG_READY_READY,
            abort_on_fail=False,
        )

    def bud_ready_reports_the_database_connected(self):
        self.assertEqual(
            self.ready.json()["database"],
            self.parameters.DATABASE_CONNECTED,
            msg=self.parameters.MSG_READY_DATABASE,
            abort_on_fail=False,
        )
