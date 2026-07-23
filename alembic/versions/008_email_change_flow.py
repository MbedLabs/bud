"""add users.pending_email and the email_change token purpose

Revision ID: 008_email_change_flow
Revises: 007_user_session_version
Create Date: 2026-07-23

A verified email change stores the requested address in ``users.pending_email``
and issues a one-time ``email_change`` token to that address. The login email
only changes once the token is claimed.

``ALTER TYPE ... ADD VALUE`` cannot run inside a transaction block, so the enum
extension uses Alembic's ``autocommit_block()`` (the documented PostgreSQL
pattern). ``IF NOT EXISTS`` makes the fresh-database path a no-op.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "008_email_change_flow"
down_revision: Union[str, Sequence[str], None] = "007_user_session_version"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "pending_email" not in user_columns:
        op.add_column("users", sa.Column("pending_email", sa.String(length=255), nullable=True))

    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                sa.text("ALTER TYPE usertokenpurpose ADD VALUE IF NOT EXISTS 'email_change'")
            )


def downgrade() -> None:
    op.drop_column("users", "pending_email")
    # PostgreSQL cannot drop a single enum value; leaving 'email_change' in place
    # is harmless.
