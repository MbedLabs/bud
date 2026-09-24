"""access_requests: requests for access to a resource, and their decision

Revision ID: 021_access_requests
Revises: 020_audit_events
Create Date: 2026-09-24

"""

import sqlalchemy as sa

from alembic import op

revision = "021_access_requests"
down_revision = "020_audit_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the access_requests table."""
    op.create_table(
        "access_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("resource_type", sa.String(length=30), nullable=False),
        sa.Column("resource_ref", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("decided_by_user_id", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_access_requests_lookup",
        "access_requests",
        ["user_id", "resource_type", "resource_ref"],
    )
    op.create_index("ix_access_requests_status", "access_requests", ["status"])


def downgrade() -> None:
    """Drop the access_requests table."""
    op.drop_table("access_requests")
