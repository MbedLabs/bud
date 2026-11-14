"""
* @file     ${tests/api/run_artifacts_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests the files a run left behind and the types it may upload.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     Base class containing the bud methods of a run's artifact listing and the allowlist.
"""

from budtestlibrary import parameterized

import tests.parameters as params
from tests.bud_test_base import BudAppTestCase


class RunArtifactsApiBase(BudAppTestCase):

    def bud_run_lists_its_files(self):
        p = self.parameters
        self.print_variables({"status": self.tc_listing.status_code, "names": self.tc_names})
        self.assertEqual(self.tc_listing.status_code, p.STATUS_OK, msg=p.MSG_ARTIFACT_LISTED)
        self.assertEqual(self.tc_names, p.ARTIFACT_LISTED, msg=p.MSG_ARTIFACT_LISTED)

    def bud_files_are_listed_oldest_first(self):
        stamps = [item.get("created_at") for item in self.tc_items]
        self.assertEqual(stamps, sorted(stamps), msg=self.parameters.MSG_ARTIFACT_ORDER)

    def bud_other_runs_and_unattached_files_are_not_listed(self):
        p = self.parameters
        self.assertNotIn(p.ARTIFACT_OTHER_RUN, self.tc_names, msg=p.MSG_ARTIFACT_OTHER_RUN)
        self.assertEqual(self.tc_other_status, p.STATUS_OK, msg=p.MSG_ARTIFACT_OTHER_LISTS)
        self.assertNotIn(p.ARTIFACT_UNATTACHED, self.tc_names, msg=p.MSG_ARTIFACT_UNATTACHED)

    @parameterized(params.ARTIFACT_PANEL_FIELDS)
    def bud_listing_carries_what_the_panel_renders(self, field):
        self.assertIn(field, self.tc_first, msg=self.parameters.MSG_ARTIFACT_PANEL_FIELD)

    def bud_listed_file_names_its_run_and_hides_its_storage(self):
        p = self.parameters
        self.assertEqual(
            self.tc_first.get("test_run_id"), self.tc_run_id, msg=p.MSG_ARTIFACT_RUN_ID
        )
        self.assertNotIn(p.ARTIFACT_STORAGE_FIELD, self.tc_first, msg=p.MSG_ARTIFACT_NO_STORAGE)

    def bud_empty_unknown_and_signed_out(self):
        p = self.parameters
        self.assertEqual(self.tc_empty, (p.STATUS_OK, []), msg=p.MSG_ARTIFACT_EMPTY)
        self.assertEqual(self.tc_missing, p.STATUS_NOT_FOUND, msg=p.MSG_ARTIFACT_MISSING_RUN)
        self.assertEqual(self.tc_signed_out, p.STATUS_UNAUTHORIZED, msg=p.MSG_ARTIFACT_SIGNED_OUT)

    @parameterized(params.ARTIFACT_ALLOWED_TYPES)
    def bud_type_a_run_produces_is_accepted(self, content_type):
        self.assertIn(content_type, self.tc_allowed, msg=self.parameters.MSG_ARTIFACT_ALLOWED)

    def bud_html_is_accepted_only_as_a_sandboxed_download(self):
        p = self.parameters
        self.assertIn(p.ARTIFACT_HTML, self.tc_allowed, msg=p.MSG_ARTIFACT_HTML)
        self.assertEqual(self.tc_download_policy, p.SANDBOX_POLICY, msg=p.MSG_ARTIFACT_HTML_SANDBOX)
        self.assertNotIn(p.ARTIFACT_SCRIPT, self.tc_allowed, msg=p.MSG_ARTIFACT_NO_SCRIPT)

    def bud_allowed_upload_is_accepted(self):
        p = self.parameters
        self.print_variables({"upload": self.tc_capture.text, "listed": self.tc_capture_listed})
        self.assertEqual(self.tc_capture.status_code, p.STATUS_CREATED, msg=p.MSG_ARTIFACT_CAPTURE)
        self.assertEqual(
            self.tc_capture_listed, p.ARTIFACT_CAPTURE[0], msg=p.MSG_ARTIFACT_CAPTURE_LISTED
        )

    def bud_refused_upload_names_the_allowed_types(self):
        p = self.parameters
        detail = str(self.tc_refused.json().get("detail"))
        self.print_variables({"status": self.tc_refused.status_code, "detail": detail})
        self.assertEqual(
            self.tc_refused.status_code, p.STATUS_UNSUPPORTED_MEDIA, msg=p.MSG_ARTIFACT_REFUSED
        )
        self.assertIn(p.ARTIFACT_SCRIPT, detail, msg=p.MSG_ARTIFACT_REFUSED_TYPE)
        self.assertIn(p.ARTIFACT_PLAIN, detail, msg=p.MSG_ARTIFACT_REFUSED_ALLOWED)
