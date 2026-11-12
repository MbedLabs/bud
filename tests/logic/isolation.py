"""
* @file     ${tests/logic/isolation.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the isolation tests/config.py gives every suite.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the replaced credentials, the probes and the refusals.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class IsolationBase(BudAppTestCase):

    def bud_bootstrap_disables_dotenv(self):
        self.print_variables({"bootstrapped variables": self.tc_credentials})
        self.assertEqual(
            self.tc_credentials.get("dotenv"),
            self.parameters.ISOLATION_DOTENV_DISABLED,
            msg=self.parameters.MSG_ISOLATION_DOTENV,
        )

    def bud_bootstrap_replaces_inherited_credentials(self):
        for prefix in self.parameters.ISOLATION_PREFIXES:
            for key, expected in self.parameters.ISOLATION_REPLACED.items():
                self.assertEqual(
                    self.tc_credentials.get(prefix + key),
                    expected,
                    msg=f"{prefix}{key}: {self.parameters.MSG_ISOLATION_REPLACED}",
                )

    @parameterized(params.ISOLATION_PROBES)
    def bud_bootstrapped_process_answers_probe(self, case):
        self.print_variables({"case": case, "stderr": self.tc_probes[case][1][-600:]})
        self.assertEqual(
            self.tc_probes[case][0],
            self.parameters.ISOLATION_PROBES[case][2],
            msg=f"{case}: {self.parameters.MSG_ISOLATION_PROBE}",
        )

    @parameterized(params.ISOLATION_REFUSALS)
    def bud_bootstrap_refuses_unsafe_setting(self, case):
        returncode, stderr = self.tc_refusals[case]
        _, reason, hidden = self.parameters.ISOLATION_REFUSALS[case]
        self.print_variables({"case": case, "exit code": returncode, "stderr": stderr[-600:]})
        self.assertNotEqual(
            returncode,
            self.parameters.ISOLATION_STARTED,
            msg=f"{case}: {self.parameters.MSG_ISOLATION_REFUSED}",
        )
        if reason:
            self.assertIn(reason, stderr, msg=f"{case}: {self.parameters.MSG_ISOLATION_REASON}")
        for secret in hidden:
            self.assertNotIn(secret, stderr, msg=f"{case}: {self.parameters.MSG_ISOLATION_HIDDEN}")

    def bud_another_postgres_port_is_allowed(self):
        self.print_variables({"stderr": self.tc_other_postgres[1][-600:]})
        self.assertEqual(
            self.tc_other_postgres[0],
            self.parameters.ISOLATION_STARTED,
            msg=self.parameters.MSG_ISOLATION_ALLOWED,
        )
