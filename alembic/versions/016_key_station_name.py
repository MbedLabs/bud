"""reserve a station name on an enrolment key"""

import sqlalchemy as sa
from alembic import op

revision = "016_key_station_name"
down_revision = "015_bloom_artefact_on_test_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "runner_api_keys", sa.Column("station_name", sa.String(length=100), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("runner_api_keys", "station_name")
