"""startup_schema_migrations_to_alembic

Revision ID: 002_startup_schema
Revises: 001_initial_baseline
Create Date: 2026-05-20

Moves the legacy startup schema mutations (previously in app/main.py lifespan)
into Alembic revisions so production startup is predictable.

- migrate_user_columns: invite/password/email verification columns on users
- migrate_execution_columns: assertions, test_metadata, product_id on test_results
- migrate_user_roles_to_viewer: convert legacy 'user' role to 'viewer'
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_startup_schema"
down_revision: Union[str, Sequence[str], None] = "001_initial_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS invited_at TIMESTAMP NULL")
    )
    op.execute(
        sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS invited_by_user_id INTEGER NULL")
    )
    op.execute(
        sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_invite_sent_at TIMESTAMP NULL")
    )
    op.execute(
        sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS invite_accepted_at TIMESTAMP NULL")
    )
    op.execute(
        sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_set_at TIMESTAMP NULL")
    )
    op.execute(
        sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMP NULL")
    )

    op.execute(
        sa.text("ALTER TABLE test_results ADD COLUMN IF NOT EXISTS assertions JSON NULL")
    )
    op.execute(
        sa.text("ALTER TABLE test_results ADD COLUMN IF NOT EXISTS test_metadata JSON NULL")
    )
    op.execute(
        sa.text("ALTER TABLE test_results ADD COLUMN IF NOT EXISTS product_id INTEGER NULL")
    )

    op.execute(sa.text("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
                BEGIN
                    ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'viewer';
                EXCEPTION
                    WHEN duplicate_object THEN NULL;
                END;
            END IF;
        END
        $$;
    """))
    op.execute(sa.text("UPDATE users SET role = 'viewer' WHERE role::text = 'user'"))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS email_verified_at"))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS password_set_at"))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS invite_accepted_at"))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS last_invite_sent_at"))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS invited_by_user_id"))
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS invited_at"))
    op.execute(sa.text("ALTER TABLE test_results DROP COLUMN IF EXISTS product_id"))
    op.execute(sa.text("ALTER TABLE test_results DROP COLUMN IF EXISTS test_metadata"))
    op.execute(sa.text("ALTER TABLE test_results DROP COLUMN IF EXISTS assertions"))
