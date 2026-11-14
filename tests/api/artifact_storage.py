"""
* @file     ${tests/api/artifact_storage.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the artifact quota, upload leases and cleanup.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of the upload policy.
"""

from tests.bud_test_base import BudAppTestCase


class ArtifactStorageBase(BudAppTestCase):

    def bud_run_quota_reserves_only_what_is_left(self):
        self.print_variables({"lease": self.tc_lease})
        self.assertEqual(
            getattr(self.tc_lease, "reserved_bytes", self.tc_lease),
            self.parameters.UPLOAD_REMAINING,
            msg=self.parameters.MSG_UPLOAD_REMAINING,
        )

    def bud_one_active_upload_per_person(self):
        self.print_variables({"second upload": self.tc_second_upload})
        self.assertEqual(
            type(self.tc_second_upload).__name__,
            self.parameters.HTTP_EXCEPTION,
            msg=self.parameters.MSG_UPLOAD_ONE_ACTIVE,
            abort_on_fail=True,
        )
        self.assertEqual(
            self.tc_second_upload.status_code,
            self.parameters.STATUS_TOO_MANY,
            msg=self.parameters.MSG_UPLOAD_TOO_MANY,
        )

    def bud_upload_start_rate_is_limited(self):
        self.print_variables({"third upload": self.tc_third_upload})
        self.assertEqual(
            type(self.tc_third_upload).__name__,
            self.parameters.HTTP_EXCEPTION,
            msg=self.parameters.MSG_UPLOAD_RATE,
            abort_on_fail=True,
        )
        self.assertEqual(
            self.tc_third_upload.status_code,
            self.parameters.STATUS_TOO_MANY,
            msg=self.parameters.MSG_UPLOAD_TOO_MANY,
        )
        self.assertIn(
            self.parameters.UPLOAD_RATE_TEXT,
            self.tc_third_upload.detail.lower(),
            msg=self.parameters.MSG_UPLOAD_RATE_TEXT,
        )

    def bud_cleanup_removes_expired_rows_and_old_orphans(self):
        p = self.parameters
        self.print_variables({"report": self.tc_report})
        self.assertEqual(
            self.tc_report.expired_artifacts, p.CLEANUP_REMOVED, msg=p.MSG_CLEANUP_EXPIRED
        )
        self.assertEqual(self.tc_report.orphan_files, p.CLEANUP_REMOVED, msg=p.MSG_CLEANUP_ORPHANS)
        self.assertEqual(self.tc_expired_file_left, False, msg=p.MSG_CLEANUP_EXPIRED_FILE)
        self.assertEqual(self.tc_orphan_left, False, msg=p.MSG_CLEANUP_ORPHAN_FILE)
        self.assertEqual(type(self.tc_lease_left).__name__, p.NONE_TYPE, msg=p.MSG_CLEANUP_LEASE)
