"""Durable report-request workflow."""

import sqlalchemy as sa

from alembic import op

revision = "018_report_requests"
down_revision = "017_release120"
branch_labels = None
depends_on = None


def upgrade():
    """Add report-request storage without changing existing evidence or identities."""
    op.create_table(
        "report_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bloom_url", sa.String(500), nullable=False),
        sa.Column("remote_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("project_prefix", sa.String(50), nullable=False),
        sa.Column("requester_name", sa.String(255), nullable=False),
        sa.Column("requester_email", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("notified_user_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("bloom_url", "remote_id"),
    )
    op.create_index("ix_report_requests_run_id", "report_requests", ["run_id"])
    op.create_index("ix_report_requests_status", "report_requests", ["status"])


def downgrade():
    """Remove empty request storage; retain populated workflow history."""
    if op.get_bind().execute(sa.text("SELECT 1 FROM report_requests LIMIT 1")).first():
        raise RuntimeError("Report requests exist; preserve them before downgrading")
    op.drop_table("report_requests")
