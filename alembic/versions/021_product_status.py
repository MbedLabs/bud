"""Status of a product: Active or Archived."""

import sqlalchemy as sa

from alembic import op

revision = "021_product_status"
down_revision = "020_audit_request_indexes"
branch_labels = None
depends_on = None


def upgrade():
    """Add the status column to products; every existing product becomes Active."""
    op.add_column(
        "products",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="Active"),
    )


def downgrade():
    """Drop the status column of products, keeping every row."""
    op.drop_column("products", "status")
