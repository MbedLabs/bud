"""make runner claims idempotent and acknowledge their terminal answer

Revision ID: 012_claim_acknowledgements
Revises: 011_custom_runs
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "012_claim_acknowledgements"
down_revision = "011_custom_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("test_runs", sa.Column("claim_id", sa.String(length=36), nullable=True))
    op.add_column("test_runs", sa.Column("claim_acknowledged_at", sa.DateTime(), nullable=True))
    op.add_column("test_runs", sa.Column("runner_exit_code", sa.Integer(), nullable=True))
    op.add_column("test_runs", sa.Column("runner_error", sa.Text(), nullable=True))
    op.create_index("ix_test_runs_claim_id", "test_runs", ["claim_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_test_runs_claim_id", table_name="test_runs")
    op.drop_column("test_runs", "runner_error")
    op.drop_column("test_runs", "runner_exit_code")
    op.drop_column("test_runs", "claim_acknowledged_at")
    op.drop_column("test_runs", "claim_id")
