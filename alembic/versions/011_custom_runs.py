"""carry an explicit test selection on a run"""

from alembic import op
import sqlalchemy as sa

revision = "011_custom_runs"
down_revision = "010_index_artifacts_by_run"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("test_runs", sa.Column("selected_tests", sa.JSON(), nullable=True))
    op.execute("CREATE INDEX IF NOT EXISTS ix_test_runs_status ON test_runs (status)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_test_runs_status")
    op.drop_column("test_runs", "selected_tests")
