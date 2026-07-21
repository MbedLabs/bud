"""add refresh purpose to user_tokens enum

Revision ID: 004_refresh_token_purpose
Revises: 003_sut_fields
Create Date: 2026-07-21

Refresh tokens are stored in the existing hashed, revocable ``user_tokens`` table
with ``purpose = 'refresh'``. On a fresh database the enum is created with this
value by ``create_all`` (revision 001); on an existing database it is added here.

``ALTER TYPE ... ADD VALUE`` cannot run inside a transaction block, so we use
Alembic's ``autocommit_block()`` (the documented pattern for PostgreSQL enum
extensions). ``IF NOT EXISTS`` makes the fresh-database path a no-op.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "004_refresh_token_purpose"
down_revision: Union[str, Sequence[str], None] = "003_sut_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(sa.text("ALTER TYPE usertokenpurpose ADD VALUE IF NOT EXISTS 'refresh'"))


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum value; leaving 'refresh' in place is
    # harmless (no rows reference it once the app stops issuing refresh tokens).
    pass
