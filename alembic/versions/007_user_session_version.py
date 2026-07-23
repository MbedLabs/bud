"""add users.session_version for token invalidation

Revision ID: 007_user_session_version
Revises: 006_encrypt_bloom_service_token
Create Date: 2026-07-23
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "007_user_session_version"
down_revision: Union[str, Sequence[str], None] = "006_encrypt_bloom_service_token"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "session_version" not in user_columns:
        # server_default backfills every existing row to 1 so their currently
        # valid tokens (which will be re-minted with ver=1 on next login) line up.
        op.add_column(
            "users",
            sa.Column("session_version", sa.Integer(), nullable=False, server_default="1"),
        )


def downgrade() -> None:
    op.drop_column("users", "session_version")
