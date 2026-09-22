"""company_logo: instance customer logo for PDF reports

Revision ID: 017_report_branding
Revises: 016_key_station_name
Create Date: 2026-09-20

"""

import sqlalchemy as sa

from alembic import op

revision = "017_report_branding"
down_revision = "016_key_station_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the company_logo table."""
    op.create_table(
        "company_logo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("logo", sa.LargeBinary(), nullable=True),
        sa.Column("logo_content_type", sa.String(length=100), nullable=True),
        sa.Column("logo_filename", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    """Drop the company_logo table."""
    op.drop_table("company_logo")
