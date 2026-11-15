"""
* @file     ${tests/logic/BUD_dockerfile.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The Dockerfile builds the UI in one stage on the build platform.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module tests the FROM lines of the repository's Dockerfile.
"""

from tests.logic.dockerfile import DockerfileBase


class DockerfileTest(DockerfileBase):

    def setUpClass(self):
        super().setUpClass()
        lines = self.bud.bud_read_repository_file(self.parameters.DOCKERFILE).splitlines()
        self.tc_ui_build_from = [
            line
            for line in lines
            if line.startswith(self.parameters.DOCKERFILE_FROM)
            and line.endswith(self.parameters.DOCKERFILE_UI_BUILD)
        ]

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    DockerfileTest().run()
