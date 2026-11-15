"""
* @file     ${tests/logic/BUD_container_start.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The image starts as root only for preparation and hands every process to appuser.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module tests the repository's start.sh, supervisord.conf and Dockerfile.
"""

from tests.logic.container_start import ContainerStartBase


def stripped_lines(text):
    """The non-empty lines of a text, stripped."""
    return [line.strip() for line in text.splitlines() if line.strip()]


class ContainerStartTest(ContainerStartBase):

    def setUpClass(self):
        super().setUpClass()
        read = self.bud.bud_read_repository_file
        self.tc_start = read(self.parameters.START_SCRIPT)
        self.tc_start_lines = stripped_lines(self.tc_start)
        block_start = self.tc_start.index(self.parameters.START_CLOUDRON_BLOCK)
        block_end = self.tc_start.index(self.parameters.START_CLOUDRON_ELSE)
        self.tc_cloudron_block = self.tc_start[block_start:block_end]
        self.tc_supervisord_lines = stripped_lines(read(self.parameters.SUPERVISORD_CONF))
        self.tc_dockerfile = read(self.parameters.DOCKERFILE)

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ContainerStartTest().run()
