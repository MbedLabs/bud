"""
* @file     ${tests/api/groups_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests base roles, policies and groups as bundles of policies over HTTP.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the defaults, the custom groups and policies, who gives what and the seeding.
"""

from tests.bud_test_base import BudAppTestCase


class GroupsApiBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_GROUPS_CHECK}")

    def bud_default_groups_and_policies_ship_read_only(self):
        self.check("defaults")

    def bud_custom_groups_bundle_policies(self):
        self.check("custom groups")

    def bud_the_group_contract_refuses_unknown_inputs(self):
        self.check("contract")

    def bud_an_administrator_edits_policies_against_the_catalogue(self):
        self.check("policies")

    def bud_the_base_role_plus_every_group_decides(self):
        self.check("base role")

    def bud_station_groups_take_administrators_and_developers_only(self):
        self.check("recipients")

    def bud_access_managers_give_only_what_they_hold(self):
        self.check("managers")

    def bud_groups_hide_nothing(self):
        self.check("hide nothing")

    def bud_each_role_and_group_reaches_its_routes(self):
        self.check("route map")

    def bud_publish_to_bloom_is_requested_and_granted_with_a_group(self):
        self.check("grant")

    def bud_administrators_are_told_of_requests(self):
        self.check("admins told")

    def bud_seeding_keeps_existing_rows(self):
        self.check("seed rows")

    def bud_a_custom_policy_grants_what_only_administrators_held(self):
        self.check("custom policy")

    def bud_seeding_renames_administration_and_keeps_its_members(self):
        self.check("seed administration")

    def bud_access_rosters_return_the_account_picture(self):
        self.check("pictures")

    def bud_seeding_renames_reports_publishing_and_keeps_its_links(self):
        self.check("seed publishing")
