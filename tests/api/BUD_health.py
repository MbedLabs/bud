"""
* @file     ${tests/api/BUD_health.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The liveness probe claims no database; the readiness probe checks it.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module tests both probes on the whole app.
"""

from tests.api.health import HealthBase


class HealthTest(HealthBase):

    def setUpClass(self):
        super().setUpClass()
        self.bud.bud_start_app()
        self.tc_health = self.bud.bud_request(self.parameters.GET, self.parameters.HEALTH_PATH)
        self.tc_ready = self.bud.bud_request(self.parameters.GET, self.parameters.READY_PATH)

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    HealthTest().run()
