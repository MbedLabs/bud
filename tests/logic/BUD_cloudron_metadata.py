"""
* @file     ${tests/logic/BUD_cloudron_metadata.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The Cloudron package carries the product positioning and the product version.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module tests the repository's Cloudron manifest, description and changelog.
"""

import json
import tomllib

from tests.logic.cloudron_metadata import CloudronMetadataBase


class CloudronMetadataTest(CloudronMetadataBase):

    def setUpClass(self):
        super().setUpClass()
        read = self.bud.bud_read_repository_file
        self.tc_manifest = json.loads(read(self.parameters.CLOUDRON_MANIFEST))
        self.tc_description = read(self.parameters.CLOUDRON_DESCRIPTION).strip()
        self.tc_changelog = read(self.parameters.CLOUDRON_CHANGELOG)
        self.tc_version = tomllib.loads(read(self.parameters.PYPROJECT))["project"]["version"]

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    CloudronMetadataTest().run()
