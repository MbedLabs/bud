"""initial_baseline

Revision ID: 001_initial_baseline
Revises:
Create Date: 2026-05-20

Initial baseline — schema is managed by SQLAlchemy create_tables().
Subsequent revisions migrate legacy startup schema changes from app/main.py.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
