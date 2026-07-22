"""add artifact upload controls

Revision ID: 005_artifact_upload_controls
Revises: 004_refresh_token_purpose
Create Date: 2026-07-22
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "005_artifact_upload_controls"
down_revision: Union[str, Sequence[str], None] = "004_refresh_token_purpose"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    artifact_columns = {column["name"] for column in inspector.get_columns("artifacts")}
    if "sha256" not in artifact_columns:
        op.add_column("artifacts", sa.Column("sha256", sa.String(length=64), nullable=True))

    tables = set(inspector.get_table_names())
    if "upload_attempts" not in tables:
        op.create_table(
            "upload_attempts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("principal_key", sa.String(length=128), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_upload_attempts_principal_key"),
            "upload_attempts",
            ["principal_key"],
            unique=False,
        )
        op.create_index(
            op.f("ix_upload_attempts_created_at"),
            "upload_attempts",
            ["created_at"],
            unique=False,
        )
    if "upload_leases" not in tables:
        op.create_table(
            "upload_leases",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("principal_key", sa.String(length=128), nullable=False),
            sa.Column("test_run_id", sa.Integer(), nullable=True),
            sa.Column("reserved_bytes", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["test_run_id"], ["test_runs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_upload_leases_principal_key"),
            "upload_leases",
            ["principal_key"],
            unique=True,
        )
        op.create_index(
            op.f("ix_upload_leases_test_run_id"),
            "upload_leases",
            ["test_run_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_upload_leases_expires_at"),
            "upload_leases",
            ["expires_at"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_upload_leases_expires_at"), table_name="upload_leases")
    op.drop_index(op.f("ix_upload_leases_test_run_id"), table_name="upload_leases")
    op.drop_index(op.f("ix_upload_leases_principal_key"), table_name="upload_leases")
    op.drop_table("upload_leases")
    op.drop_index(op.f("ix_upload_attempts_created_at"), table_name="upload_attempts")
    op.drop_index(op.f("ix_upload_attempts_principal_key"), table_name="upload_attempts")
    op.drop_table("upload_attempts")
    op.drop_column("artifacts", "sha256")
