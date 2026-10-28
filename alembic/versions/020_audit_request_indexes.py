"""Indexes on the audit event outcome and client address."""

from alembic import op

revision = "020_audit_request_indexes"
down_revision = "019_cli_auth_sessions"
branch_labels = None
depends_on = None


def upgrade():
    """Add the outcome and client address indexes to audit_events, keeping every row."""
    op.create_index("ix_audit_events_outcome", "audit_events", ["outcome"])
    op.create_index("ix_audit_events_ip", "audit_events", ["ip"])


def downgrade():
    """Drop the outcome and client address indexes of audit_events, keeping every row."""
    op.drop_index("ix_audit_events_ip", table_name="audit_events")
    op.drop_index("ix_audit_events_outcome", table_name="audit_events")
