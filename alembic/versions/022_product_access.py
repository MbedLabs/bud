"""Access per product: the groups a user holds on each product.

Every user keeps, on every existing product, the groups that give product-scoped
permissions today; a viewer also gets Results Viewers and a developer Test Operators,
which their base role gave them before. Administrators need no row.
"""

import json
from datetime import datetime, timezone

import sqlalchemy as sa

from alembic import op

revision = "022_product_access"
down_revision = "021_product_status"
branch_labels = None
depends_on = None

PRODUCT_RESOURCES = {"evidence", "reports", "custom_runs", "bloom_publish"}
BASE_ROLE_GROUPS = {"viewer": "results_viewers", "developer": "test_operators"}


def _product_scoped(permissions) -> bool:
    """Whether a policy's permissions hold any product-scoped permission."""
    matrix = json.loads(permissions) if isinstance(permissions, str) else (permissions or {})
    return any(
        resource in PRODUCT_RESOURCES or (resource == "products" and "manage" in actions)
        for resource, actions in matrix.items()
    )


def upgrade():
    """Create product_access and give every user their current access on every product."""
    op.create_table(
        "product_access",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("access_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "product_id", "user_id", "group_id", name="uq_product_access_product_user_group"
        ),
    )
    op.create_index("ix_product_access_product_id", "product_access", ["product_id"])
    op.create_index("ix_product_access_user_id", "product_access", ["user_id"])
    op.create_index("ix_product_access_group_id", "product_access", ["group_id"])

    connection = op.get_bind()
    products = [row[0] for row in connection.execute(sa.text("SELECT id FROM products"))]
    if not products:
        return
    scoped_groups = {
        row[0]
        for row in connection.execute(
            sa.text(
                "SELECT agp.group_id, p.permissions FROM access_group_policies agp "
                "JOIN policies p ON p.id = agp.policy_id"
            )
        )
        if _product_scoped(row[1])
    }
    group_by_key = {
        row[1]: row[0]
        for row in connection.execute(
            sa.text("SELECT id, system_key FROM access_groups WHERE system_key IS NOT NULL")
        )
    }
    pairs = {
        (row[0], row[1])
        for row in connection.execute(sa.text("SELECT user_id, group_id FROM access_group_members"))
        if row[1] in scoped_groups
    }
    for user_id, role in connection.execute(sa.text("SELECT id, role FROM users")):
        key = BASE_ROLE_GROUPS.get(str(role).lower().rsplit(".", 1)[-1])
        if key and key in group_by_key:
            pairs.add((user_id, group_by_key[key]))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = [
        {"product_id": product_id, "user_id": user_id, "group_id": group_id, "created_at": now}
        for product_id in products
        for user_id, group_id in sorted(pairs)
    ]
    if rows:
        connection.execute(
            sa.text(
                "INSERT INTO product_access (product_id, user_id, group_id, created_at) "
                "VALUES (:product_id, :user_id, :group_id, :created_at)"
            ),
            rows,
        )


def downgrade():
    """Drop product_access."""
    op.drop_index("ix_product_access_group_id", table_name="product_access")
    op.drop_index("ix_product_access_user_id", table_name="product_access")
    op.drop_index("ix_product_access_product_id", table_name="product_access")
    op.drop_table("product_access")
