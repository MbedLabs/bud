"""
* @file     ${tests/logic/BUD_e2e_image_smoke_script.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The smoke script passes the administrator name whole and uploads evidence as the station.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module runs scripts/e2e_image_smoke.sh with docker and curl stood in by scripts.
"""

import json
import tomllib

from tests.logic.e2e_image_smoke_script import E2eImageSmokeScriptBase


class E2eImageSmokeScriptTest(E2eImageSmokeScriptBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        folder = self.bud.bud_work_folder()
        self.executable(folder / "docker", p.SMOKE_RECORDING_DOCKER)
        log = folder / p.SMOKE_ARGV_LOG
        self.bud.bud_run_repository_script(
            p.SMOKE_SCRIPT, [p.SMOKE_IMAGE], folder, {p.SMOKE_ARGV_SETTING: str(log)}
        )
        calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        self.tc_app_run = next(
            (
                call
                for call in calls
                if call[:3] == p.SMOKE_RUN_PREFIX and call[3].startswith(p.SMOKE_APP_NAME)
            ),
            [],
        )
        folder = self.bud.bud_work_folder()
        self.executable(folder / "docker", p.SMOKE_DOCKER)
        self.executable(folder / "curl", p.SMOKE_CURL)
        version = tomllib.loads(self.bud.bud_read_repository_file(p.PYPROJECT))["project"][
            "version"
        ]
        (folder / p.SMOKE_VERSION_FILE).write_text(version)
        self.tc_smoke = self.bud.bud_run_repository_script(p.SMOKE_SCRIPT, [p.SMOKE_IMAGE], folder)

    @staticmethod
    def executable(path, text):
        """Write a stand-in command and make it executable."""
        path.write_text(text)
        path.chmod(0o755)

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    E2eImageSmokeScriptTest().run()
