"""Application policies per user: the app-level access a user holds, as in Bloom.

Every user keeps the app-level access their app-wide groups give today: each policy of those
groups that holds an app-level permission becomes one of the user's application policies.
"""

import json

import sqlalchemy as sa

from alembic import op

revision = "024_user_application_policies"
down_revision = "023_product_notification_rules"
branch_labels = None
depends_on = None

PRODUCT_RESOURCES = {"evidence", "reports", "custom_runs", "bloom_publish"}


def _app_level(permissions) -> bool:
    """Whether a policy's permissions hold any app-level permission."""
    matrix = json.loads(permissions) if isinstance(permissions, str) else (permissions or {})
    return any(
        resource not in PRODUCT_RESOURCES and actions for resource, actions in matrix.items()
    )


def upgrade():
    """Create user_application_policies and copy the app-level policies of app-wide groups."""
    op.create_table(
        "user_application_policies",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "policy_id",
            sa.Integer(),
            sa.ForeignKey("policies.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    connection = op.get_bind()
    app_policies = {
        row[0]
        for row in connection.execute(sa.text("SELECT id, permissions FROM policies"))
        if _app_level(row[1])
    }
    rows = sorted(
        {
            (row[0], row[1])
            for row in connection.execute(
                sa.text(
                    "SELECT m.user_id, agp.policy_id FROM access_group_members m "
                    "JOIN access_group_policies agp ON agp.group_id = m.group_id"
                )
            )
            if row[1] in app_policies
        }
    )
    if rows:
        connection.execute(
            sa.text(
                "INSERT INTO user_application_policies (user_id, policy_id) "
                "VALUES (:user_id, :policy_id)"
            ),
            [{"user_id": user_id, "policy_id": policy_id} for user_id, policy_id in rows],
        )


def downgrade():
    """Drop user_application_policies."""
    op.drop_table("user_application_policies")
