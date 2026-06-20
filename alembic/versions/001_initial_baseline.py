"""initial_baseline

Revision ID: 001_initial_baseline
Revises:
Create Date: 2026-05-20

Initial baseline — schema is managed by SQLAlchemy create_tables().
Subsequent revisions migrate legacy startup schema changes from app/main.py.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "001_initial_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    import app.models  # noqa: F401
    from app.db.database import Base

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    pass
