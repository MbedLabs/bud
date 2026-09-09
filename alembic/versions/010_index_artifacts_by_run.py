"""index artifacts by the run they belong to"""

from alembic import op

revision = "010_index_artifacts_by_run"
down_revision = "009_admin_email_change_workflow"
branch_labels = None
depends_on = None


_INDEXES = [
    ("ix_artifacts_test_run_id", "artifacts", "test_run_id"),
    ("ix_artifacts_created_at", "artifacts", "created_at"),
]


def upgrade() -> None:
    for name, table, columns in _INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")


def downgrade() -> None:
    for name, _table, _columns in reversed(_INDEXES):
        op.execute(f"DROP INDEX IF EXISTS {name}")
