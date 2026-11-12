"""The Bud suites of tests/pg, as bud-runner run-tests -t tests.pg.SUITES runs them on PostgreSQL."""

import tests.config  # noqa: F401

SUITES = [
    "tests.pg.BUD_integrity_conflict_pg.IntegrityConflictPgTest",
    "tests.pg.BUD_refresh_flow_pg.RefreshFlowPgTest",
    "tests.pg.BUD_session_invalidation_pg.SessionInvalidationPgTest",
    "tests.pg.BUD_integration_real_auth_pg.IntegrationRealAuthPgTest",
    "tests.pg.BUD_execution_request_claims_pg.ExecutionRequestClaimsPgTest",
    "tests.pg.BUD_audit_request_indexes_pg.AuditRequestIndexesPgTest",
    "tests.pg.BUD_token_concurrency_pg.TokenConcurrencyPgTest",
    "tests.pg.BUD_group_overlap_pg.GroupOverlapPgTest",
    "tests.pg.BUD_email_change_pg.EmailChangePgTest",
    "tests.pg.BUD_cli_auth_migration_pg.CliAuthMigrationPgTest",
]
