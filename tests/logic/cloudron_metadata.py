"""
* @file     ${tests/logic/cloudron_metadata.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the Cloudron package metadata.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Base class containing the bud methods of the manifest, description and changelog.
"""

import json
import re

from tests.bud_test_base import BudAppTestCase


class CloudronMetadataBase(BudAppTestCase):

    def bud_title_is_the_product_name(self):
        self.assertEqual(
            self.tc_manifest["title"],
            self.parameters.CLOUDRON_TITLE,
            msg=self.parameters.MSG_CLOUDRON_TITLE,
            abort_on_fail=False,
        )

    def bud_tagline_is_the_product_positioning(self):
        self.assertEqual(
            self.tc_manifest["tagline"],
            self.parameters.CLOUDRON_TAGLINE,
            msg=self.parameters.MSG_CLOUDRON_TAGLINE,
            abort_on_fail=False,
        )

    def bud_description_is_the_product_positioning(self):
        self.assertEqual(
            self.tc_description,
            self.parameters.CLOUDRON_DESCRIPTION_TEXT,
            msg=self.parameters.MSG_CLOUDRON_DESCRIPTION,
            abort_on_fail=False,
        )

    def bud_manifest_does_not_say_embedded(self):
        self.assertNotIn(
            self.parameters.CLOUDRON_EMBEDDED,
            json.dumps(self.tc_manifest).lower(),
            msg=self.parameters.MSG_CLOUDRON_MANIFEST_EMBEDDED,
            abort_on_fail=False,
        )

    def bud_description_does_not_say_embedded(self):
        self.assertNotIn(
            self.parameters.CLOUDRON_EMBEDDED,
            self.tc_description.lower(),
            msg=self.parameters.MSG_CLOUDRON_DESCRIPTION_EMBEDDED,
            abort_on_fail=False,
        )

    def bud_description_does_not_say_self_hosted(self):
        self.assertNotIn(
            self.parameters.CLOUDRON_SELF_HOSTED,
            self.tc_description.lower(),
            msg=self.parameters.MSG_CLOUDRON_SELF_HOSTED,
            abort_on_fail=False,
        )

    def bud_package_version_is_the_product_version(self):
        self.print_variables({"product version": self.tc_version})
        self.assertEqual(
            self.tc_manifest["version"],
            self.tc_version,
            msg=self.parameters.MSG_CLOUDRON_VERSION,
            abort_on_fail=False,
        )

    def bud_upstream_version_is_the_product_version(self):
        self.assertEqual(
            self.tc_manifest["upstreamVersion"],
            self.tc_version,
            msg=self.parameters.MSG_CLOUDRON_UPSTREAM,
            abort_on_fail=False,
        )

    def bud_changelog_has_the_product_version(self):
        self.assertIn(
            self.parameters.CLOUDRON_VERSION_SECTION.format(self.tc_version),
            self.tc_changelog,
            msg=self.parameters.MSG_CLOUDRON_SECTION,
            abort_on_fail=False,
        )

    def bud_changelog_opens_with_a_version(self):
        self.assertRegex(
            self.tc_changelog.splitlines()[0],
            self.parameters.CLOUDRON_VERSION_HEADER,
            msg=self.parameters.MSG_CLOUDRON_HEADER,
            abort_on_fail=True,
        )

    def bud_changelog_opens_with_the_newest_version(self):
        top = re.search(self.parameters.CLOUDRON_VERSION_HEADER, self.tc_changelog.splitlines()[0])
        newest = tuple(int(part) for part in top.group(1).split("."))
        version = tuple(int(part) for part in self.tc_version.split("."))
        self.assertTrue(
            newest >= version,
            msg=self.parameters.MSG_CLOUDRON_NEWEST,
            expected=f">= {version}",
            actual=newest,
            abort_on_fail=False,
        )
