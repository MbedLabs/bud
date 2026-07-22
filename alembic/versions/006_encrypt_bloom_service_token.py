"""remove plaintext Bloom integration tokens

Revision ID: 006_encrypt_bloom_service_token
Revises: 005_artifact_upload_controls
Create Date: 2026-07-22
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "006_encrypt_bloom_service_token"
down_revision: Union[str, Sequence[str], None] = "005_artifact_upload_controls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The legacy value is a now-revoked one-year Bloom admin JWT. Do not copy or
    # encrypt it: delete it and require a newly issued scoped credential.
    op.execute(sa.text("DELETE FROM system_settings WHERE key = 'bloom_token'"))


def downgrade() -> None:
    pass
