"""
* @file     ${tests/api/object_storage.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests S3 storage of run artifacts.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of the bucket, its mirror, cleanup and migration.
"""

from tests.bud_test_base import BudAppTestCase


class ObjectStorageBase(BudAppTestCase):

    def bud_upload_and_download_go_through_the_bucket(self):
        p, found = self.parameters, self.tc_round_trip
        self.print_variables(found)
        self.assertEqual(found["uploaded"], p.STATUS_CREATED, msg=p.MSG_S3_UPLOADED)
        self.assertEqual(found["keys"], found["expected keys"], msg=p.MSG_S3_KEYS)
        self.assertEqual(found["mirrored"], True, msg=p.MSG_S3_MIRRORED)
        self.assertEqual(found["downloaded"], p.STATUS_OK, msg=p.MSG_S3_DOWNLOADED)
        self.assertEqual(found["content"], p.S3_EVIDENCE, msg=p.MSG_S3_CONTENT)
        self.assertRegex(found["disposition"], p.ATTACHMENT_PATTERN, msg=p.MSG_S3_ATTACHMENT)
        self.assertEqual(found["policy"], p.SANDBOX_POLICY, msg=p.MSG_S3_SANDBOX)
        self.assertEqual(found["fallback"], (p.STATUS_OK, p.S3_EVIDENCE), msg=p.MSG_S3_FALLBACK)
        self.assertEqual(found["unreachable"], p.STATUS_UNAVAILABLE, msg=p.MSG_S3_UNREACHABLE)
        self.assertEqual(found["deleted"], p.STATUS_NO_CONTENT, msg=p.MSG_S3_DELETED)

    def bud_without_the_mirror_only_the_bucket_holds_it(self):
        p, found = self.parameters, self.tc_unmirrored
        self.print_variables(found)
        self.assertEqual(found["uploaded"], p.STATUS_CREATED, msg=p.MSG_S3_UPLOADED)
        self.assertEqual(found["mirrored"], False, msg=p.MSG_S3_NOT_MIRRORED)
        self.assertEqual(found["content"], p.S3_EVIDENCE, msg=p.MSG_S3_CONTENT)
        self.assertEqual(found["deleted"], p.STATUS_NO_CONTENT, msg=p.MSG_S3_DELETED)
        self.assertEqual(found["keys"], [], msg=p.MSG_S3_KEYS)

    def bud_refused_upload_leaves_nothing(self):
        p, found = self.parameters, self.tc_refused
        self.print_variables(found)
        self.assertEqual(found["status"], p.STATUS_UNAVAILABLE, msg=p.MSG_S3_REFUSED)
        self.assertEqual(found["files"], [], msg=p.MSG_S3_NOTHING_LEFT)

    def bud_stored_file_is_read_from_the_bucket_then_the_mirror(self):
        p = self.parameters
        self.assertEqual(
            self.tc_read_stored,
            [p.S3_LOCAL_BYTES, p.S3_BUCKET_BYTES, p.NONE_TYPE, p.NONE_TYPE],
            msg=p.MSG_S3_READ_STORED,
        )

    def bud_cleanup_reconciles_the_bucket(self):
        p, found = self.parameters, self.tc_cleanup
        self.print_variables(found)
        self.assertEqual(found["expired"], 1, msg=p.MSG_S3_EXPIRED)
        self.assertEqual(found["keys"], [p.S3_KEY.format(p.S3_KEPT)], msg=p.MSG_S3_KEYS)
        self.assertEqual(found["missing"], 1, msg=p.MSG_S3_MISSING)
        self.assertEqual(found["old left"], False, msg=p.MSG_S3_OLD_GONE)

    def bud_migration_copies_once_and_checks_sizes(self):
        self.assertEqual(
            self.tc_migrations, self.parameters.S3_MIGRATIONS, msg=self.parameters.MSG_S3_MIGRATIONS
        )

    def bud_migrate_command_exits_by_outcome(self):
        p = self.parameters
        self.assertEqual(self.tc_command_codes, p.S3_COMMAND_CODES, msg=p.MSG_S3_COMMAND_CODES)
        self.assertIn(p.S3_COMMAND_OUTPUT, self.tc_command_output, msg=p.MSG_S3_COMMAND_OUTPUT)

    def bud_readiness_names_the_storage(self):
        self.assertEqual(
            self.tc_readiness, self.parameters.S3_READINESS, msg=self.parameters.MSG_S3_READINESS
        )

    def bud_s3_needs_a_bucket(self):
        p = self.parameters
        self.print_variables({"refusal": self.tc_no_bucket})
        self.assertEqual(
            isinstance(self.tc_no_bucket, ValueError), True, msg=p.MSG_S3_BUCKET_REQUIRED
        )
        self.assertIn(p.S3_NEEDS_BUCKET, str(self.tc_no_bucket), msg=p.MSG_S3_BUCKET_TEXT)
        self.assertEqual(self.tc_prefix, p.S3_DEFAULT_PREFIX, msg=p.MSG_S3_PREFIX)
