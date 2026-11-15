"""
* @file     ${tests/api/runners_and_uploads_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests station heartbeats and artifact uploads, reads and deletions.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the ownership, the limits and the refusals.
"""

from tests.bud_test_base import BudAppTestCase


class RunnersAndUploadsApiBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_UPLOAD_CHECK}")

    def bud_a_heartbeat_touches_only_the_signed_in_station(self):
        self.check("heartbeat")

    def bud_a_station_cannot_read_another_stations_artifact(self):
        self.check("unowned")

    def bud_a_station_reads_its_own_artifact(self):
        self.check("owned")

    def bud_only_administrators_delete_artifacts(self):
        self.check("delete")

    def bud_a_station_cannot_upload_to_another_stations_run(self):
        self.check("foreign upload")

    def bud_a_station_uploads_to_its_own_run(self):
        self.check("own upload")

    def bud_an_upload_to_an_unknown_run_is_not_found(self):
        self.check("unknown run")

    def bud_an_oversized_upload_is_refused_without_a_partial_file(self):
        self.check("oversized")

    def bud_an_upload_at_the_file_limit_is_accepted(self):
        self.check("at limit")

    def bud_invalid_display_metadata_is_refused(self):
        self.check("long name")

    def bud_an_upload_that_would_eat_the_free_space_reserve_is_refused(self):
        self.check("free space")

    def bud_an_upload_uses_the_remaining_run_capacity(self):
        self.check("remaining")

    def bud_bytes_beyond_the_remaining_run_capacity_are_refused(self):
        self.check("beyond")

    def bud_a_viewer_cannot_upload(self):
        self.check("viewer")

    def bud_a_station_upload_needs_a_run(self):
        self.check("no run")

    def bud_an_administrator_cannot_upload(self):
        self.check("admin")

    def bud_every_station_upload_counts_against_the_run_quota(self):
        self.check("quota")
