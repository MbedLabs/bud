"""carry an explicit test selection on a run

Revision ID: 011_custom_runs
Revises: 010_index_artifacts_by_run
Create Date: 2026-08-05

An ordinary run's `test_case_list` is a module path to a list the runner
declares in its own workspace - `Bud_Test_Suite.HIL_TEST_CASES` - which the
runner imports and resolves itself. A custom run is a selection made in Bud, so
the selection has to travel with the run rather than being named by something
that only exists on the bench.

`selected_tests` holds those test cases as importable `module.Class` paths, the
same form the runner's own loader takes. NULL means an ordinary run, and the
runner keeps resolving `test_case_list` as before - nothing about existing runs
changes.

`status` gets an index because claiming a run is a lookup by (runner, status)
and a runner polls on an interval: without it, every poll from every bench
scans the whole run history.
"""

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
