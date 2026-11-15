"""
* @file     ${tests/logic/BUD_image_release.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Release promotion moves only eligible aliases, keeps published digests and refuses
*           malformed references before docker is called.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests scripts/image_release.py with docker and the registry stood in by mocks.
"""

import subprocess
from unittest import mock

from tests.logic.image_release import ImageReleaseBase


class ImageReleaseTest(ImageReleaseBase):

    def setUpClass(self):
        super().setUpClass()
        p, attempt = self.parameters, self.bud.bud_attempt
        release = self.bud.bud_load_repository_module(p.RELEASE_MODULE, p.RELEASE_SCRIPT)
        eligible = release.eligible_aliases
        self.tc_older = eligible(p.RELEASE_OLDER_ALIASES, p.RELEASE_OLDER_REF, p.RELEASE_LATEST_TAG)
        self.tc_current = eligible(p.RELEASE_STABLE, p.RELEASE_CURRENT_REF, p.RELEASE_LATEST_TAG)
        self.tc_stale = eligible(
            p.RELEASE_LATEST, p.RELEASE_BRANCH_REF, p.RELEASE_LATEST_TAG, False
        )
        self.tc_prerelease = eligible(
            p.RELEASE_STABLE, p.RELEASE_PRERELEASE_REF, p.RELEASE_LATEST_TAG
        )
        execute = mock.Mock()
        error = attempt(
            lambda: release.promote(
                p.RELEASE_IMAGE,
                p.RELEASE_VERSION_ALIASES,
                lambda _: p.RELEASE_OTHER_DIGEST,
                execute,
            )
        )
        self.tc_conflict = (error, execute.called)
        execute = mock.Mock()
        attempt(
            lambda: release.promote(
                p.RELEASE_IMAGE, p.RELEASE_REPEATED_ALIASES, lambda _: p.RELEASE_DIGEST, execute
            )
        )
        self.tc_repeated = [call.args for call in execute.call_args_list]
        self.tc_mismatch = attempt(
            lambda: release.promote(
                p.RELEASE_IMAGE,
                p.RELEASE_STABLE_ALIASES,
                lambda _: p.RELEASE_OTHER_DIGEST,
                mock.Mock(),
            )
        )
        self.tc_malformed_digest = {}
        for reference in p.RELEASE_MALFORMED:
            docker = mock.Mock()
            with mock.patch.object(release.subprocess, "run", docker):
                outcome = attempt(lambda reference=reference: release.digest(reference))
            self.tc_malformed_digest[reference] = (outcome, docker.called)
        self.tc_well_formed_digest = {}
        for reference in p.RELEASE_WELL_FORMED:
            answer = subprocess.CompletedProcess([], 0, stdout=p.RELEASE_DIGEST + "\n", stderr="")
            docker = mock.Mock(return_value=answer)
            with mock.patch.object(release.subprocess, "run", docker):
                value = attempt(lambda reference=reference: release.digest(reference))
            command = docker.call_args.args[0] if docker.call_args else []
            self.tc_well_formed_digest[reference] = (value, command)
        self.tc_reference_checks = {
            reference: release.is_image_reference(reference)
            for reference in p.RELEASE_MALFORMED + p.RELEASE_WELL_FORMED
        }
        self.tc_malformed_promotions = {}
        for case, (image, aliases) in p.RELEASE_MALFORMED_PROMOTIONS.items():
            inspect, execute = mock.Mock(), mock.Mock()
            outcome = attempt(
                lambda image=image, aliases=aliases, inspect=inspect, execute=execute: release.promote(
                    image, aliases, inspect, execute
                )
            )
            self.tc_malformed_promotions[case] = (outcome, inspect.called, execute.called)

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ImageReleaseTest().run()
