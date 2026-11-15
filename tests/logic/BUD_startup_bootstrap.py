"""
* @file     ${tests/logic/BUD_startup_bootstrap.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The app's start runs the legacy data repair and the admin seed only when their settings ask.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests the lifespan on a started app's database with each step stood in by a
*           recorder, for the four flag pairs.
"""

from unittest import mock

from app import main
from tests.logic.startup_bootstrap import StartupBootstrapBase


class StartupBootstrapTest(StartupBootstrapBase):

    def setUpClass(self):
        super().setUpClass()
        self.bud.bud_start_app()
        self.tc_steps = {
            case: self.start(repair, seed)
            for case, (repair, seed, _) in self.parameters.STARTUP_CASES.items()
        }

    def start(self, repair, seed):
        """Run the app's lifespan with the two settings and return the steps it ran."""
        steps = []

        def recorder(name):
            async def record():
                steps.append(name)

            return record

        first, *module_steps = self.parameters.STARTUP_STEPS
        with (
            mock.patch.multiple(
                main.app_settings, RUN_STARTUP_DATA_REPAIR=repair, AUTO_SEED_ADMIN=seed
            ),
            mock.patch.object(main.db, first, recorder(first)),
            mock.patch.multiple(main, **{name: recorder(name) for name in module_steps}),
        ):
            self.bud.bud_await(self.lifespan())
        return steps

    @staticmethod
    async def lifespan():
        """Enter and leave the app's lifespan."""
        async with main.lifespan(main.app):
            pass

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    StartupBootstrapTest().run()
