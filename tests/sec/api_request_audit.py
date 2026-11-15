"""
* @file     ${tests/sec/api_request_audit.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests that every HTTP request leaves one api.request audit event and repeated refusals are flagged.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     Base class containing the bud methods of the recorded actors, outcomes, flags and stored values.
"""

from tests.bud_test_base import BudAppTestCase


class ApiRequestAuditBase(BudAppTestCase):

    def check(self, scenario):
        """Assert every named check of one scenario: its found value against its expected one."""
        for name, (found, expected) in self.tc_checks[scenario].items():
            self.assertEqual(found, expected, msg=f"{name}: {self.parameters.MSG_AUDIT_HTTP_CHECK}")

    def bud_a_browser_session_is_recorded_as_a_web_user(self):
        self.check("web user")

    def bud_a_cli_token_is_recorded_as_a_cli_user(self):
        self.check("cli user")

    def bud_a_station_token_names_the_station_and_its_created_run(self):
        self.check("station")

    def bud_an_enrolment_key_names_its_station(self):
        self.check("enrolment key")

    def bud_a_created_object_and_its_path_parameters_are_recorded(self):
        self.check("created object")

    def bud_health_probes_are_recorded_as_anonymous(self):
        self.check("health")

    def bud_a_forged_token_is_denied_with_the_address(self):
        self.check("forged token")

    def bud_insufficient_permissions_are_denied(self):
        self.check("insufficient")

    def bud_a_deactivated_person_is_named_on_the_denied_request(self):
        self.check("deactivated person")

    def bud_a_deactivated_station_is_named_on_the_denied_request(self):
        self.check("deactivated station")

    def bud_a_not_found_answer_to_an_anonymous_caller_is_denied(self):
        self.check("anonymous not found")

    def bud_a_not_found_answer_to_a_person_or_station_is_a_failure(self):
        self.check("signed-in not found")

    def bud_a_wrong_enrolment_key_is_denied(self):
        self.check("wrong key")

    def bud_a_rate_limited_request_is_denied(self):
        self.check("rate limited")

    def bud_twenty_refusals_from_one_address_leave_one_flag(self):
        self.check("flag")

    def bud_refusals_outside_the_window_do_not_count(self):
        self.check("old refusals")

    def bud_no_secret_or_body_value_is_stored(self):
        self.check("secrets")

    def bud_a_failed_audit_write_keeps_the_response(self):
        self.check("failed write")

    def bud_an_actor_set_in_an_async_dependency_reaches_the_middleware(self):
        self.check("probe")

    def bud_the_audit_filters_select_by_actor_address_request_and_status(self):
        self.check("filters")

    def bud_created_ids_read_a_gzip_body_within_the_limit(self):
        self.check("created id")

    def bud_a_cors_preflight_is_answered_by_the_cors_layer_alone(self):
        self.check("preflight")

    def bud_a_refused_preflight_is_denied(self):
        self.check("refused preflight")

    def bud_a_foreign_origin_request_is_recorded_without_cors_permission(self):
        self.check("foreign origin")

    def bud_the_route_is_the_full_template_of_a_prefixed_route(self):
        self.check("route template")

    def bud_a_results_answer_names_its_run_and_an_id_wins(self):
        self.check("created ids")
