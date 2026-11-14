"""The Bud suites of tests/sec, as bud-runner run-tests -t tests.sec.SUITES runs them."""

import tests.config  # noqa: F401

SUITES = [
    "tests.sec.BUD_token_logging.TokenLoggingTest",
    "tests.sec.BUD_security.SecurityTest",
    "tests.sec.BUD_password_policy.PasswordPolicyTest",
    "tests.sec.BUD_route_auth_matrix.RouteAuthMatrixTest",
    "tests.sec.BUD_integration_settings_security.IntegrationSettingsSecurityTest",
    "tests.sec.BUD_nginx_security_headers.NginxSecurityHeadersTest",
    "tests.sec.BUD_run_producer_http.RunProducerHttpTest",
    "tests.sec.BUD_trusted_proxy_address.TrustedProxyAddressTest",
    "tests.sec.BUD_group_overlap_sec.GroupOverlapSecTest",
    "tests.sec.BUD_audit_log_http.AuditLogHttpTest",
    "tests.sec.BUD_audit_labels_http.AuditLabelsHttpTest",
    "tests.sec.BUD_runner_auth.RunnerAuthTest",
    "tests.sec.BUD_run_authorization.RunAuthorizationTest",
    "tests.sec.BUD_access_requests_http.AccessRequestsHttpTest",
    "tests.sec.BUD_cli_auth_sec.CliAuthSecTest",
    "tests.sec.BUD_api_request_audit.ApiRequestAuditTest",
]
