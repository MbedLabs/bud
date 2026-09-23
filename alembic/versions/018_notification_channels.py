"""notification_channels and notification_deliveries: run-finished webhooks

Revision ID: 018_notification_channels
Revises: 017_report_branding
Create Date: 2026-09-23

"""

import sqlalchemy as sa

from alembic import op

revision = "018_notification_channels"
down_revision = "017_report_branding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the notification channel and delivery tables."""
    op.create_table(
        "notification_channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("url_encrypted", sa.Text(), nullable=False),
        sa.Column("url_prefix", sa.String(length=60), nullable=False),
        sa.Column("secret_encrypted", sa.Text(), nullable=True),
        sa.Column("run_filter", sa.String(length=30), nullable=False, server_default="all"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "test_run_id",
            sa.Integer(),
            sa.ForeignKey("test_runs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "channel_id",
            sa.Integer(),
            sa.ForeignKey("notification_channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("delivered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_notification_deliveries_test_run_id", "notification_deliveries", ["test_run_id"]
    )
    op.create_index(
        "ix_notification_deliveries_channel_id", "notification_deliveries", ["channel_id"]
    )


def downgrade() -> None:
    """Drop the notification tables."""
    op.drop_index("ix_notification_deliveries_channel_id", table_name="notification_deliveries")
    op.drop_index("ix_notification_deliveries_test_run_id", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
    op.drop_table("notification_channels")
