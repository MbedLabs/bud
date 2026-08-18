"""index artifacts by the run they belong to

Revision ID: 010_index_artifacts_by_run
Revises: 009_admin_email_change_workflow
Create Date: 2026-08-05

`artifacts` carried only its primary key. Every read of the table is by the run
it belongs to - the new per-run listing, and the cascade that unlinks files when
a run is deleted - so both were sequential scans. Nothing has noticed yet
because nothing uploads artifacts through the runner, but the listing endpoint
is what makes them reachable, and the table grows one row per screenshot, trace
and capture once it is used.

`created_at` is indexed as well: the retention sweep at startup selects every
artifact older than the cutoff, which is otherwise a full scan on every boot.
"""

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
