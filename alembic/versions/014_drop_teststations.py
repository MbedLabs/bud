"""drop the unused teststations table"""

from alembic import op
import sqlalchemy as sa

revision = "014_drop_teststations"
down_revision = "013_runner_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("teststations")


def downgrade() -> None:
    op.create_table(
        "teststations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("token", sa.String(length=500), nullable=False),
        sa.Column("socket_port", sa.Integer(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_heartbeat", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("account"),
    )
