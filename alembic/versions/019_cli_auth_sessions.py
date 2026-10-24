"""Browser-approved CLI authentication sessions."""

import sqlalchemy as sa

from alembic import op

revision = "019_cli_auth_sessions"
down_revision = "018_report_requests"
branch_labels = None
depends_on = None


def upgrade():
    """Add PKCE-bound authorization sessions without changing existing account data."""
    op.create_table(
        "cli_auth_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("client_name", sa.String(100), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("redirect_uri", sa.String(500), nullable=True),
        sa.Column("code_challenge", sa.String(128), nullable=False),
        sa.Column("state", sa.String(128), nullable=False),
        sa.Column("exchange_code_hash", sa.String(64), nullable=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("approved_session_version", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("mode IN ('callback', 'code')", name="ck_cli_auth_mode"),
    )
    op.create_index("ix_cli_auth_sessions_expires_at", "cli_auth_sessions", ["expires_at"])


def downgrade():
    """Drop the authorization sessions table with its rows and its expiry index."""
    op.drop_index("ix_cli_auth_sessions_expires_at", table_name="cli_auth_sessions")
    op.drop_table("cli_auth_sessions")
