"""Notification rules per product.

Every existing notification channel keeps posting the runs of every product: the new
``all_products`` flag is true on each of them. ``product_notification_rules`` routes one
product's runs to one channel with its own run filter.
"""

import sqlalchemy as sa

from alembic import op

revision = "023_product_notification_rules"
down_revision = "022_product_access"
branch_labels = None
depends_on = None


def upgrade():
    """Add notification_channels.all_products, true for every channel, and the rule table."""
    op.add_column(
        "notification_channels",
        sa.Column("all_products", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "product_notification_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "channel_id",
            sa.Integer(),
            sa.ForeignKey("notification_channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_filter", sa.String(length=30), nullable=False, server_default="all"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("product_id", "channel_id", name="uq_product_notification_rule"),
    )
    op.create_index(
        "ix_product_notification_rules_product_id", "product_notification_rules", ["product_id"]
    )
    op.create_index(
        "ix_product_notification_rules_channel_id", "product_notification_rules", ["channel_id"]
    )


def downgrade():
    """Drop the rule table and notification_channels.all_products."""
    op.drop_index(
        "ix_product_notification_rules_channel_id", table_name="product_notification_rules"
    )
    op.drop_index(
        "ix_product_notification_rules_product_id", table_name="product_notification_rules"
    )
    op.drop_table("product_notification_rules")
    op.drop_column("notification_channels", "all_products")
