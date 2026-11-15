"""
* @file     ${tests/logic/image_release.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the release promotion script.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of alias eligibility, promotion and references.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase

REFERENCE_CHECKS = [(reference, False) for reference in params.RELEASE_MALFORMED] + [
    (reference, True) for reference in params.RELEASE_WELL_FORMED
]


class ImageReleaseBase(BudAppTestCase):

    def bud_older_release_keeps_the_floating_tags(self):
        self.assertEqual(
            self.tc_older, self.parameters.RELEASE_OLDER_KEPT, msg=self.parameters.MSG_RELEASE_OLDER
        )

    def bud_current_release_promotes_stable(self):
        self.assertEqual(
            self.tc_current, self.parameters.RELEASE_STABLE, msg=self.parameters.MSG_RELEASE_CURRENT
        )

    def bud_stale_branch_does_not_promote_latest(self):
        self.assertEqual(self.tc_stale, [], msg=self.parameters.MSG_RELEASE_STALE_BRANCH)

    def bud_prerelease_does_not_promote_stable(self):
        self.assertEqual(self.tc_prerelease, [], msg=self.parameters.MSG_RELEASE_PRERELEASE)

    def bud_version_conflict_stops_before_any_alias_changes(self):
        p = self.parameters
        error, executed = self.tc_conflict
        self.print_variables({"error": error, "aliases changed": executed})
        self.assertEqual(type(error).__name__, p.RUNTIME_ERROR, msg=p.MSG_RELEASE_CONFLICT)
        self.assertIn(p.RELEASE_OVERWRITE_TEXT, str(error), msg=p.MSG_RELEASE_CONFLICT_TEXT)
        self.assertEqual(executed, False, msg=p.MSG_RELEASE_NOTHING_CHANGED)

    def bud_repeated_promotion_keeps_the_digest(self):
        p = self.parameters
        calls = self.tc_repeated
        self.print_variables({"docker calls": calls})
        self.assertEqual(len(calls), p.RELEASE_PROMOTIONS, msg=p.MSG_RELEASE_REPEATED)
        self.assertEqual(
            [call[-1] for call in calls],
            [p.RELEASE_IMAGE] * len(calls),
            msg=p.MSG_RELEASE_SAME_IMAGE,
        )

    def bud_digest_mismatch_after_promotion_fails(self):
        p = self.parameters
        self.print_variables({"error": self.tc_mismatch})
        self.assertEqual(
            type(self.tc_mismatch).__name__, p.RUNTIME_ERROR, msg=p.MSG_RELEASE_MISMATCH
        )
        self.assertIn(p.RELEASE_VERIFY_TEXT, str(self.tc_mismatch), msg=p.MSG_RELEASE_MISMATCH_TEXT)

    @parameterized(params.RELEASE_MALFORMED)
    def bud_digest_refuses_a_malformed_reference(self, reference):
        p = self.parameters
        outcome, docker_called = self.tc_malformed_digest[reference]
        self.print_variables({"reference": reference, "outcome": outcome})
        self.assertEqual(type(outcome).__name__, p.VALUE_ERROR, msg=p.MSG_RELEASE_REFUSED)
        self.assertIn(p.RELEASE_INVALID_TEXT, str(outcome), msg=p.MSG_RELEASE_REFUSED_TEXT)
        self.assertEqual(docker_called, False, msg=p.MSG_RELEASE_NO_DOCKER)

    @parameterized(params.RELEASE_WELL_FORMED)
    def bud_digest_inspects_a_registry_reference(self, reference):
        p = self.parameters
        value, command = self.tc_well_formed_digest[reference]
        self.print_variables({"digest": value, "docker command": command})
        self.assertEqual(value, p.RELEASE_DIGEST, msg=p.MSG_RELEASE_DIGEST)
        self.assertEqual(
            command[:5], p.RELEASE_DOCKER_INSPECT + [reference], msg=p.MSG_RELEASE_INSPECTED
        )

    @parameterized(REFERENCE_CHECKS)
    def bud_reference_check_matches_digest(self, reference, accepted):
        self.assertEqual(
            self.tc_reference_checks[reference], accepted, msg=self.parameters.MSG_RELEASE_CHECK
        )

    @parameterized(params.RELEASE_MALFORMED_PROMOTIONS)
    def bud_promotion_refuses_a_malformed_reference(self, case):
        p = self.parameters
        outcome, inspected, executed = self.tc_malformed_promotions[case]
        self.print_variables({"case": case, "outcome": outcome})
        self.assertEqual(type(outcome).__name__, p.VALUE_ERROR, msg=p.MSG_RELEASE_REFUSED)
        self.assertIn(p.RELEASE_INVALID_TEXT, str(outcome), msg=p.MSG_RELEASE_REFUSED_TEXT)
        self.assertEqual(inspected, False, msg=p.MSG_RELEASE_NOT_INSPECTED)
        self.assertEqual(executed, False, msg=p.MSG_RELEASE_NOT_EXECUTED)
