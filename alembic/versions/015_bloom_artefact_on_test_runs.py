"""record the Bloom artefact a run reached"""

import sqlalchemy as sa
from alembic import op

revision = "015_bloom_artefact_on_test_runs"
down_revision = "014_drop_teststations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("test_runs", sa.Column("bloom_artefact_id", sa.String(length=100), nullable=True))
    op.add_column(
        "test_runs", sa.Column("bloom_artefact_name", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "test_runs", sa.Column("bloom_artefact_url", sa.String(length=500), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("test_runs", "bloom_artefact_url")
    op.drop_column("test_runs", "bloom_artefact_name")
    op.drop_column("test_runs", "bloom_artefact_id")
