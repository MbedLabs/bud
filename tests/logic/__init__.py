"""The Bud suites of tests/logic, as bud-runner run-tests -t tests.logic.SUITES runs them."""

import tests.config  # noqa: F401

SUITES = [
    "tests.logic.BUD_dockerfile.DockerfileTest",
    "tests.logic.BUD_timestamp_text.TimestampTextTest",
    "tests.logic.BUD_cloudron_metadata.CloudronMetadataTest",
    "tests.logic.BUD_audit_prune.AuditPruneTest",
    "tests.logic.BUD_response_timestamps.ResponseTimestampsTest",
    "tests.logic.BUD_container_start.ContainerStartTest",
    "tests.logic.BUD_access_token_format.AccessTokenFormatTest",
    "tests.logic.BUD_company_logo.CompanyLogoTest",
]
