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
]
