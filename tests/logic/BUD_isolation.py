"""
* @file     ${tests/logic/BUD_isolation.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Suites run with test-only credentials, no dotenv files, no outside SMTP and only the test database.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module bootstraps tests/config.py in new Python processes that inherit synthetic credentials.
"""

import json
import os
from pathlib import Path

from tests.logic.isolation import IsolationBase


class IsolationTest(IsolationBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.tc_credentials = self.parsed(self.bootstrap(p.ISOLATION_CREDENTIALS_PROBE).stdout, {})
        self.tc_probes = {}
        for case, (code, extra, expected) in p.ISOLATION_PROBES.items():
            done = self.bootstrap(code, extra)
            found = done.stdout.strip()
            if isinstance(expected, dict):
                found = self.parsed(found, found)
            self.tc_probes[case] = (found, done.stderr)
        self.tc_refusals = {}
        for case, (extra, _, _) in p.ISOLATION_REFUSALS.items():
            done = self.bootstrap("", extra)
            self.tc_refusals[case] = (done.returncode, done.stderr)
        done = self.bootstrap("", p.ISOLATION_OTHER_POSTGRES)
        self.tc_other_postgres = (done.returncode, done.stderr)

    @staticmethod
    def parsed(text, otherwise):
        """The JSON value of a probe's output, or otherwise when it holds none."""
        try:
            return json.loads(text)
        except ValueError:
            return otherwise

    def bootstrap(self, code, extra=None):
        """Run code after tests/config.py in a new process that inherits synthetic credentials."""
        p = self.parameters
        environment = {
            key: value for key, value in os.environ.items() if key in p.ISOLATION_KEPT_VARIABLES
        }
        for prefix in p.ISOLATION_PREFIXES:
            environment.update(
                {prefix + key: value for key, value in p.ISOLATION_INHERITED.items()}
            )
        environment.update(p.ISOLATION_FLAGS)
        environment["BUD_CONFIG_PATH"] = str(
            Path(__file__).resolve().parents[2] / p.ISOLATION_CONFIG
        )
        environment[p.ISOLATION_PROBE_FOLDER] = str(self.bud.bud_work_folder())
        environment.update(extra or {})
        return self.bud.bud_run_python(p.ISOLATION_PRELUDE + code, environment)

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    IsolationTest().run()
