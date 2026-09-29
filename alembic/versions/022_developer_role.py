"""developer role: users and groups can be developers; groups never carry admin

Revision ID: 022_developer_role
Revises: 021_access_requests
Create Date: 2026-09-29

"""

from alembic import op

revision = "022_developer_role"
down_revision = "021_access_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the developer role and turn groups that carried admin into developer groups."""
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'developer'")
    op.execute("UPDATE groups SET role = 'developer' WHERE role = 'admin'")


def downgrade() -> None:
    """Turn developers into viewers and rebuild the role type without developer."""
    op.execute("UPDATE groups SET role = 'viewer' WHERE role = 'developer'")
    op.execute("UPDATE users SET role = 'viewer' WHERE role = 'developer'")
    op.execute("ALTER TYPE userrole RENAME TO userrole_with_developer")
    op.execute("CREATE TYPE userrole AS ENUM ('admin', 'viewer')")
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE userrole USING role::text::userrole")
    op.execute("DROP TYPE userrole_with_developer")
