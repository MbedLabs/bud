"""groups, group_memberships, group_product_grants

Revision ID: 019_groups
Revises: 018_notification_channels
Create Date: 2026-09-24

"""

import sqlalchemy as sa

from alembic import op

revision = "019_groups"
down_revision = "018_notification_channels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the groups, their members and their product grants."""
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="viewer"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "group_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", "user_id", name="uq_group_membership"),
    )
    op.create_index("ix_group_memberships_user_id", "group_memberships", ["user_id"])
    op.create_table(
        "group_product_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", "product_id", name="uq_group_product_grant"),
    )


def downgrade() -> None:
    """Drop the product grants, the memberships and the groups."""
    op.drop_table("group_product_grants")
    op.drop_index("ix_group_memberships_user_id", table_name="group_memberships")
    op.drop_table("group_memberships")
    op.drop_table("groups")
