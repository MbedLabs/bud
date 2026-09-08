"""give every Test Station its own enrolment key"""

from alembic import op
import sqlalchemy as sa

revision = "013_runner_api_keys"
down_revision = "012_claim_acknowledgements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runner_api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("key_hash", sa.String(length=255), nullable=False),
        sa.Column("key_prefix", sa.String(length=12), nullable=False),
        sa.Column("runner_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["runner_id"], ["runners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_runner_api_keys_key_hash", "runner_api_keys", ["key_hash"], unique=True)
    op.create_index("ix_runner_api_keys_runner_id", "runner_api_keys", ["runner_id"])


def downgrade() -> None:
    op.drop_index("ix_runner_api_keys_runner_id", table_name="runner_api_keys")
    op.drop_index("ix_runner_api_keys_key_hash", table_name="runner_api_keys")
    op.drop_table("runner_api_keys")
