"""add software-under-test repository fields to test runs

Revision ID: 003_add_software_under_test_fields
Revises: 002_startup_schema
Create Date: 2026-06-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_add_software_under_test_fields"
down_revision: Union[str, Sequence[str], None] = "002_startup_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text("ALTER TABLE test_runs ADD COLUMN IF NOT EXISTS url_software_under_test VARCHAR(500) NULL")
    )
    op.execute(
        sa.text("ALTER TABLE test_runs ADD COLUMN IF NOT EXISTS ref_software_under_test VARCHAR(100) NULL")
    )


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE test_runs DROP COLUMN IF EXISTS ref_software_under_test"))
    op.execute(sa.text("ALTER TABLE test_runs DROP COLUMN IF EXISTS url_software_under_test"))
