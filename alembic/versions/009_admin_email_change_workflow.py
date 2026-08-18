"""locked baseline schema

Revision ID: 009_admin_email_change_workflow
Revises:
Create Date: 2026-07-31

Single locked baseline for the Bud schema.

This replaces the previous chain, whose base revision built the schema by calling
``Base.metadata.create_all()``. Because that base always produced whatever the
models currently described, every later revision found its columns already
present on a fresh install and had to be written defensively with
inspect-then-add guards - and the real ALTER path was therefore never exercised
by the fresh-install CI check.

The revision identifier is deliberately kept as the previous head
(``009_admin_email_change_workflow``) so that databases already migrated to that
head report the same identifier, are seen as up to date, and are left untouched.
No stamp or manual step is required for an existing deployment.

From here migrations are ordinary explicit DDL: a new revision alters this
baseline, so the empty-database CI check exercises the same statements a
deployed database will run.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "009_admin_email_change_workflow"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "runners",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("token", sa.String(length=500), nullable=False),
        sa.Column("socket_port", sa.Integer(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_heartbeat", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account"),
    )
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "teststations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("token", sa.String(length=500), nullable=False),
        sa.Column("socket_port", sa.Integer(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_heartbeat", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account"),
    )
    op.create_table(
        "upload_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("principal_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_upload_attempts_created_at"), "upload_attempts", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_upload_attempts_principal_key"), "upload_attempts", ["principal_key"], unique=False
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.Enum("admin", "viewer", name="userrole"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("session_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("invited_at", sa.DateTime(), nullable=True),
        sa.Column("invited_by_user_id", sa.Integer(), nullable=True),
        sa.Column("last_invite_sent_at", sa.DateTime(), nullable=True),
        sa.Column("invite_accepted_at", sa.DateTime(), nullable=True),
        sa.Column("password_set_at", sa.DateTime(), nullable=True),
        sa.Column("email_verified_at", sa.DateTime(), nullable=True),
        sa.Column("pending_email", sa.String(length=255), nullable=True),
        sa.Column("email_change_status", sa.String(length=32), nullable=True),
        sa.Column("email_change_requested_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_table(
        "test_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("test_case_list", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("url_test_software", sa.String(length=500), nullable=True),
        sa.Column("ref_test_software", sa.String(length=100), nullable=False),
        sa.Column("url_software_under_test", sa.String(length=500), nullable=True),
        sa.Column("ref_software_under_test", sa.String(length=100), nullable=True),
        sa.Column("total_tests", sa.Integer(), nullable=False),
        sa.Column("passed_tests", sa.Integer(), nullable=False),
        sa.Column("failed_tests", sa.Integer(), nullable=False),
        sa.Column("skipped_tests", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("runner_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.ForeignKeyConstraint(
            ["runner_id"],
            ["runners.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_test_runs_product_id"), "test_runs", ["product_id"], unique=False)
    op.create_index(op.f("ix_test_runs_runner_id"), "test_runs", ["runner_id"], unique=False)
    op.create_table(
        "user_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "purpose",
            sa.Enum(
                "invite",
                "email_verification",
                "password_reset",
                "refresh",
                "email_change",
                name="usertokenpurpose",
            ),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("target_email", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_tokens_expires_at"), "user_tokens", ["expires_at"], unique=False)
    op.create_index(op.f("ix_user_tokens_token_hash"), "user_tokens", ["token_hash"], unique=True)
    op.create_index(op.f("ix_user_tokens_used_at"), "user_tokens", ["used_at"], unique=False)
    op.create_index(op.f("ix_user_tokens_user_id"), "user_tokens", ["user_id"], unique=False)
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("test_case", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("test_run_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["test_run_id"],
            ["test_runs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "test_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("test_class", sa.String(length=255), nullable=False),
        sa.Column("test_method", sa.String(length=255), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("traceback", sa.Text(), nullable=True),
        sa.Column("assertions", sa.JSON(), nullable=True),
        sa.Column("test_metadata", sa.JSON(), nullable=True),
        sa.Column("work_package_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("test_run_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.ForeignKeyConstraint(
            ["test_run_id"],
            ["test_runs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_test_results_product_id"), "test_results", ["product_id"], unique=False
    )
    op.create_index(
        op.f("ix_test_results_test_run_id"), "test_results", ["test_run_id"], unique=False
    )
    op.create_index(
        op.f("ix_test_results_work_package_id"), "test_results", ["work_package_id"], unique=False
    )
    op.create_table(
        "test_run_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("test_run_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["test_run_id"],
            ["test_runs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_test_run_events_test_run_id"), "test_run_events", ["test_run_id"], unique=False
    )
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
        op.f("ix_upload_leases_expires_at"), "upload_leases", ["expires_at"], unique=False
    )
    op.create_index(
        op.f("ix_upload_leases_principal_key"), "upload_leases", ["principal_key"], unique=True
    )
    op.create_index(
        op.f("ix_upload_leases_test_run_id"), "upload_leases", ["test_run_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_upload_leases_test_run_id"), table_name="upload_leases")
    op.drop_index(op.f("ix_upload_leases_principal_key"), table_name="upload_leases")
    op.drop_index(op.f("ix_upload_leases_expires_at"), table_name="upload_leases")
    op.drop_table("upload_leases")
    op.drop_index(op.f("ix_test_run_events_test_run_id"), table_name="test_run_events")
    op.drop_table("test_run_events")
    op.drop_index(op.f("ix_test_results_work_package_id"), table_name="test_results")
    op.drop_index(op.f("ix_test_results_test_run_id"), table_name="test_results")
    op.drop_index(op.f("ix_test_results_product_id"), table_name="test_results")
    op.drop_table("test_results")
    op.drop_table("artifacts")
    op.drop_index(op.f("ix_user_tokens_user_id"), table_name="user_tokens")
    op.drop_index(op.f("ix_user_tokens_used_at"), table_name="user_tokens")
    op.drop_index(op.f("ix_user_tokens_token_hash"), table_name="user_tokens")
    op.drop_index(op.f("ix_user_tokens_expires_at"), table_name="user_tokens")
    op.drop_table("user_tokens")
    op.drop_index(op.f("ix_test_runs_runner_id"), table_name="test_runs")
    op.drop_index(op.f("ix_test_runs_product_id"), table_name="test_runs")
    op.drop_table("test_runs")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_upload_attempts_principal_key"), table_name="upload_attempts")
    op.drop_index(op.f("ix_upload_attempts_created_at"), table_name="upload_attempts")
    op.drop_table("upload_attempts")
    op.drop_table("teststations")
    op.drop_table("system_settings")
    op.drop_table("runners")
    op.drop_table("products")

    # Alembic's autogenerate drops tables but not the enum types they use, which
    # would make a re-upgrade fail with "type already exists".
    for enum_name in ("userrole", "usertokenpurpose"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
