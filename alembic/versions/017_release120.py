"""Consolidated Bud 1.2.0 release schema: access policies and groups, station-owned executions, profile pictures."""

import hashlib
import json

import sqlalchemy as sa
from alembic import op

revision = "017_release120"
down_revision = "016_key_station_name"
branch_labels = None
depends_on = None

TABLE_STEPS = [
    ("company_logo", "_create_branding"),
    ("notification_channels", "_create_notifications"),
    ("groups", "_create_groups"),
    ("audit_events", "_create_audit"),
    ("access_requests", "_create_access_requests"),
]
SOURCE_TABLES = {
    "016_key_station_name": set(),
    "017_report_branding": {"company_logo"},
    "018_notification_channels": {
        "company_logo",
        "notification_channels",
        "notification_deliveries",
    },
    "019_groups": {
        "company_logo",
        "notification_channels",
        "notification_deliveries",
        "groups",
        "group_memberships",
        "group_product_grants",
    },
    "020_audit_events": {
        "company_logo",
        "notification_channels",
        "notification_deliveries",
        "groups",
        "group_memberships",
        "group_product_grants",
        "audit_events",
    },
    "021_access_requests": {
        "company_logo",
        "notification_channels",
        "notification_deliveries",
        "groups",
        "group_memberships",
        "group_product_grants",
        "audit_events",
        "access_requests",
    },
    "022_developer_role": {
        "company_logo",
        "notification_channels",
        "notification_deliveries",
        "groups",
        "group_memberships",
        "group_product_grants",
        "audit_events",
        "access_requests",
    },
}
SOURCE_SCHEMA_DIGESTS = {
    "016_key_station_name": "6ac0931ab3b7561a932f8d7fbcad6578c77cb27b2f0e8751068d8152530dbc81",
    "017_report_branding": "7b3fff485dc4c0af7672d02fa8e87ee78f17689a123bfd24b14ef70d8c9c1d12",
    "018_notification_channels": "72ba86b256de9bac43611bf4a8459ad9b2b461b40233210cff6663b6ab9832cc",
    "019_groups": "dcddf885f6afd1cc10ec7bdd0a9754eced2731ebf200db049094d627d5a85c28",
    "020_audit_events": "82a4307ec9498ab9bbb59f8de01e61e228c04471abbc9fbea411a32271f7603f",
    "021_access_requests": "db971a04a59dc45a72dae0669a00dd7cffdc7b12f9c8df7e13a39aabe7b8a73a",
    "022_developer_role": "ceaae327389807a5a551500a23b67eb77ede78eb3ae9c96bc4b3fa7f5e597647",
}
ACCESS_TABLES = {"policies", "access_groups", "access_group_policies", "access_group_members"}
POLICIES = (
    (
        "results",
        "Results",
        "See runs, results, artifacts, products and stations; export reports.",
        {
            "evidence": ["view"],
            "reports": ["export"],
            "products": ["view"],
            "stations": ["view"],
        },
    ),
    (
        "custom_runs",
        "Custom runs",
        "Queue a custom run on the Test Stations.",
        {"custom_runs": ["create"]},
    ),
    (
        "publish_to_bloom",
        "Reports publishing",
        "Publish a completed run's report to Bloom.",
        {"bloom_publish": ["execute"]},
    ),
    (
        "stations",
        "Stations",
        "Manage Test Stations: registration keys, enabling, editing and deleting stations.",
        {"stations": ["view", "manage"]},
    ),
    ("products", "Products", "Create and delete products.", {"products": ["view", "manage"]}),
    (
        "settings",
        "Settings and integrations",
        "Settings, the Bloom link, notification channels and the company logo.",
        {"settings": ["view", "edit"]},
    ),
    ("audit", "Audit log", "Read the audit log.", {"audit": ["view"]}),
    (
        "access_management",
        "Access management",
        "Decide access requests, give users their groups and edit groups.",
        {"access": ["manage"]},
    ),
)
GROUPS = (
    ("results_viewers", "Results Viewers", "See results.", ("results",)),
    (
        "test_operators",
        "Test Operators",
        "See results, queue custom runs and publish to Bloom.",
        ("results", "custom_runs", "publish_to_bloom"),
    ),
    (
        "station_managers",
        "Station Managers",
        "See results and manage Test Stations.",
        ("results", "stations"),
    ),
    (
        "access_managers",
        "Access Managers",
        "Station Managers plus access management.",
        ("results", "stations", "access_management"),
    ),
    (
        "app_administration",
        "Application Administrators",
        "Every grantable policy.",
        tuple(key for key, _name, _description, _permissions in POLICIES),
    ),
)
SOURCE_METADATA_KEYS = (
    "product_id",
    "url_test_software",
    "ref_test_software",
    "url_software_under_test",
    "ref_software_under_test",
)


def _create_branding() -> None:
    """Create the company_logo table."""
    op.create_table(
        "company_logo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("logo", sa.LargeBinary(), nullable=True),
        sa.Column("logo_content_type", sa.String(length=100), nullable=True),
        sa.Column("logo_filename", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def _create_notifications() -> None:
    """Create the notification channel and delivery tables."""
    op.create_table(
        "notification_channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("url_encrypted", sa.Text(), nullable=False),
        sa.Column("url_prefix", sa.String(length=60), nullable=False),
        sa.Column("secret_encrypted", sa.Text(), nullable=True),
        sa.Column("run_filter", sa.String(length=30), nullable=False, server_default="all"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "test_run_id",
            sa.Integer(),
            sa.ForeignKey("test_runs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "channel_id",
            sa.Integer(),
            sa.ForeignKey("notification_channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("delivered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_notification_deliveries_test_run_id",
        "notification_deliveries",
        ["test_run_id"],
    )
    op.create_index(
        "ix_notification_deliveries_channel_id",
        "notification_deliveries",
        ["channel_id"],
    )


def _create_groups() -> None:
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
            "group_id",
            sa.Integer(),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("group_id", "user_id", name="uq_group_membership"),
    )
    op.create_index("ix_group_memberships_user_id", "group_memberships", ["user_id"])
    op.create_table(
        "group_product_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
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


def _create_audit() -> None:
    """Create the audit_events table and its lookup indexes."""
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.String(length=100), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("details", sa.JSON(), nullable=True),
    )
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_target", "audit_events", ["target_type", "target_id"])
    op.create_index("ix_audit_events_product_id", "audit_events", ["product_id"])


def _create_access_requests() -> None:
    """Create the access_requests table."""
    op.create_table(
        "access_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("resource_type", sa.String(length=30), nullable=False),
        sa.Column("resource_ref", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("decided_by_user_id", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_access_requests_lookup",
        "access_requests",
        ["user_id", "resource_type", "resource_ref"],
    )
    op.create_index("ix_access_requests_status", "access_requests", ["status"])


def _signature(connection):
    """Hash the ordered schema shape excluding the migration ledger and revision value."""
    inspector = sa.inspect(connection)
    tables = []
    for name in sorted(inspector.get_table_names()):
        if name in {"alembic_version", "access_migration_state"}:
            continue
        tables.append(
            {
                "name": name,
                "columns": [
                    {
                        "name": c["name"],
                        "type": str(c["type"]),
                        "enum_values": getattr(c["type"], "enums", None),
                        "nullable": c["nullable"],
                        "default": str(c["default"]),
                    }
                    for c in inspector.get_columns(name)
                ],
                "pk": inspector.get_pk_constraint(name),
                "fk": sorted(inspector.get_foreign_keys(name), key=lambda item: str(item)),
                "unique": sorted(
                    inspector.get_unique_constraints(name), key=lambda item: str(item)
                ),
                "checks": sorted(inspector.get_check_constraints(name), key=lambda item: str(item)),
                "indexes": sorted(inspector.get_indexes(name), key=lambda item: str(item)),
            }
        )
    return hashlib.sha256(json.dumps(tables, sort_keys=True, default=str).encode()).hexdigest()


def _group_digest(connection):
    """Hash access-bearing policy and group data without names, profiles or credentials."""
    rows = [
        connection.execute(sa.text(query)).all()
        for query in (
            "SELECT id,system_key,is_default,permissions::text FROM policies ORDER BY id",
            "SELECT id,system_key,is_default FROM access_groups ORDER BY id",
            "SELECT group_id,policy_id FROM access_group_policies ORDER BY group_id,policy_id",
            "SELECT group_id,user_id FROM access_group_members ORDER BY group_id,user_id",
        )
    ]
    return hashlib.sha256(
        json.dumps([list(map(tuple, part)) for part in rows], sort_keys=True, default=str).encode()
    ).hexdigest()


def _create_access_schema():
    """Create policies, access groups as bundles of policies, and their members."""
    op.create_table(
        "policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("system_key", sa.String(length=40), nullable=True, unique=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "access_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("system_key", sa.String(length=40), nullable=True, unique=True),
        sa.Column("name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "access_group_policies",
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("access_groups.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("policy_id", sa.Integer(), sa.ForeignKey("policies.id"), primary_key=True),
    )
    op.create_table(
        "access_group_members",
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("access_groups.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_access_group_members_user_id", "access_group_members", ["user_id"])


def _seed_access(connection):
    """Ship the default policies and groups and give users of the old groups their match.

    A user in an old group that carried Developer is given Test Operators; a user only in
    old groups that carried Viewer is given Results Viewers. The old rows stay unused.
    """
    policy_ids = {}
    for key, name, description, permissions in POLICIES:
        policy_ids[key] = connection.scalar(
            sa.text(
                "INSERT INTO policies (system_key,name,description,permissions,is_default) "
                "VALUES (:key,:name,:description,CAST(:permissions AS JSON),true) RETURNING id"
            ),
            {
                "key": key,
                "name": name,
                "description": description,
                "permissions": json.dumps(permissions),
            },
        )
    group_ids = {}
    for key, name, description, keys in GROUPS:
        group_ids[key] = connection.scalar(
            sa.text(
                "INSERT INTO access_groups (system_key,name,description,is_default) "
                "VALUES (:key,:name,:description,true) RETURNING id"
            ),
            {"key": key, "name": name, "description": description},
        )
        for policy in keys:
            connection.execute(
                sa.text(
                    "INSERT INTO access_group_policies (group_id,policy_id) VALUES (:group,:policy)"
                ),
                {"group": group_ids[key], "policy": policy_ids[policy]},
            )
    rows = connection.execute(
        sa.text(
            "SELECT gm.user_id, MAX(CASE WHEN g.role = 'developer' THEN 1 ELSE 0 END) "
            "FROM group_memberships gm JOIN groups g ON g.id = gm.group_id "
            "GROUP BY gm.user_id ORDER BY gm.user_id"
        )
    ).all()
    for user_id, developer in rows:
        connection.execute(
            sa.text("INSERT INTO access_group_members (group_id,user_id) VALUES (:group,:user)"),
            {
                "group": group_ids["test_operators" if developer else "results_viewers"],
                "user": user_id,
            },
        )
    return [{"id": group_ids[key], "system_key": key} for key, *_rest in GROUPS]


def _preflight(connection, retained):
    """Validate the source revision, group roles, collisions and queue classification."""
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())
    if retained:
        row = (
            connection.execute(
                sa.text("SELECT * FROM access_migration_state WHERE revision=:revision"),
                {"revision": revision},
            )
            .mappings()
            .one_or_none()
        )
        if (
            row is None
            or row["format_version"] != 1
            or row["target_schema_digest"] != _signature(connection)
        ):
            raise RuntimeError("Retained release schema or ledger does not match")
    else:
        source_revision = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
        if source_revision not in SOURCE_TABLES:
            raise RuntimeError("Unsupported source revision")
        release_tables = set().union(*SOURCE_TABLES.values())
        if tables & release_tables != SOURCE_TABLES[source_revision]:
            raise RuntimeError("Source release table inventory does not match its revision")
        if _signature(connection) != SOURCE_SCHEMA_DIGESTS[source_revision]:
            raise RuntimeError("Source schema fingerprint does not match its revision")
        if "test_runs" in tables and "record_kind" in {
            c["name"] for c in inspector.get_columns("test_runs")
        }:
            raise RuntimeError("Release columns exist without a matching migration ledger")
        if tables & (ACCESS_TABLES | {"execution_requests"}):
            raise RuntimeError("Release tables exist without a matching migration ledger")
    if "groups" in tables:
        unknown = (
            connection.execute(
                sa.text(
                    "SELECT id FROM groups WHERE role NOT IN ('viewer','developer','admin') ORDER BY id"
                )
            )
            .scalars()
            .all()
        )
        if unknown:
            raise RuntimeError("Unsupported group roles at IDs " + str(unknown))
        names = connection.execute(
            sa.text(
                "SELECT lower(trim(name)),count(*) FROM groups GROUP BY lower(trim(name)) HAVING count(*)>1"
            )
        ).all()
        if names:
            raise RuntimeError("Duplicate normalized group names")
    return _queue_candidates(connection)


def _queue_candidates(connection):
    """Identify proven custom queue placeholders while refusing ambiguous selections."""
    inspector = sa.inspect(connection)
    records = (
        connection.execute(
            sa.text(
                "SELECT * FROM test_runs WHERE status='Pending' AND selected_tests IS NOT NULL ORDER BY id"
            )
        )
        .mappings()
        .all()
    )
    candidates = []
    ambiguous = []
    retained = "execution_requests" in inspector.get_table_names()
    for row in records:
        if retained and connection.scalar(
            sa.text("SELECT id FROM execution_requests WHERE legacy_queue_run_id=:id"),
            {"id": row["id"]},
        ):
            continue
        events = (
            connection.execute(
                sa.text("SELECT * FROM test_run_events WHERE test_run_id=:id"),
                {"id": row["id"]},
            )
            .mappings()
            .all()
        )
        evidence = connection.scalar(
            sa.text("SELECT count(*) FROM test_results WHERE test_run_id=:id"),
            {"id": row["id"]},
        ) + connection.scalar(
            sa.text("SELECT count(*) FROM artifacts WHERE test_run_id=:id"),
            {"id": row["id"]},
        )
        if row["claim_id"] or row["started_at"] or row["completed_at"] or evidence:
            continue
        queued = [
            e
            for e in events
            if e["stage"] == "execution"
            and e["status"] == "queued"
            and e["title"] == "Custom run queued"
        ]
        metadata = queued[0]["event_metadata"] if len(queued) == 1 else None
        tests = row["selected_tests"]
        station = connection.scalar(
            sa.text("SELECT account FROM runners WHERE id=:id"),
            {"id": row["runner_id"]},
        )
        if (
            not isinstance(tests, list)
            or not tests
            or not all(isinstance(p, str) and p.strip() for p in tests)
            or not isinstance(metadata, dict)
            or metadata.get("selected_tests") != tests
            or not isinstance(metadata.get("runner_account"), str)
            or len(events) != 1
            or row["runner_id"] is None
            or station is None
            or any(
                row[field]
                for field in (
                    "total_tests",
                    "passed_tests",
                    "failed_tests",
                    "skipped_tests",
                    "duration_seconds",
                )
            )
        ):
            ambiguous.append(row["id"])
        else:
            candidates.append((dict(row), station))
    if ambiguous:
        raise RuntimeError("Ambiguous queued execution IDs " + str(ambiguous))
    return candidates


def _create_request_schema():
    """Add the request table and retained execution classification."""
    op.add_column(
        "test_runs",
        sa.Column("record_kind", sa.String(20), nullable=False, server_default="execution"),
    )
    op.create_table(
        "execution_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "requested_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "runner_id",
            sa.Integer(),
            sa.ForeignKey("runners.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("runner_account", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("selected_tests", sa.JSON(), nullable=False),
        sa.Column(
            "source_run_id",
            sa.Integer(),
            sa.ForeignKey("test_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_metadata", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="queued"),
        sa.Column(
            "claimed_run_id",
            sa.Integer(),
            sa.ForeignKey("test_runs.id"),
            nullable=True,
            unique=True,
        ),
        sa.Column(
            "legacy_queue_run_id",
            sa.Integer(),
            sa.ForeignKey("test_runs.id"),
            nullable=True,
            unique=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("state IN ('queued','claimed')", name="ck_execution_request_state"),
        sa.CheckConstraint(
            "(state='queued' AND claimed_run_id IS NULL) OR (state='claimed' AND claimed_run_id IS NOT NULL)",
            name="ck_execution_request_claim_link",
        ),
    )
    op.create_index("ix_execution_requests_runner_id", "execution_requests", ["runner_id"])
    op.create_index("ix_execution_requests_state", "execution_requests", ["state"])


def _convert_queue(connection, candidates):
    """Retain original placeholders and create one request for each proven selection."""
    table = sa.table(
        "execution_requests",
        sa.column("runner_id"),
        sa.column("runner_account"),
        sa.column("name"),
        sa.column("selected_tests", sa.JSON()),
        sa.column("source_metadata", sa.JSON()),
        sa.column("state"),
        sa.column("legacy_queue_run_id"),
        sa.column("created_at"),
    )
    for row, station in candidates:
        connection.execute(
            table.insert().values(
                runner_id=row["runner_id"],
                runner_account=station,
                name=row["name"],
                selected_tests=row["selected_tests"],
                source_metadata={key: row[key] for key in SOURCE_METADATA_KEYS},
                state="queued",
                legacy_queue_run_id=row["id"],
                created_at=row["created_at"],
            )
        )
        connection.execute(
            sa.text("UPDATE test_runs SET record_kind='legacy_request' WHERE id=:id"),
            {"id": row["id"]},
        )


def upgrade():
    """Apply the frozen release delta and preserve existing identities and evidence."""
    connection = op.get_bind()
    tables = set(sa.inspect(connection).get_table_names())
    retained = "access_migration_state" in tables
    candidates = _preflight(connection, retained)
    if retained:
        _convert_queue(connection, candidates)
        return
    source_revision = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
    source_digest = _signature(connection)
    for table, function in TABLE_STEPS:
        if table not in tables:
            globals()[function]()
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'developer'")
    op.execute("UPDATE groups SET role='developer' WHERE role='admin'")
    _create_request_schema()
    _create_access_schema()
    op.add_column("users", sa.Column("profile_picture", sa.LargeBinary(), nullable=True))
    seed = _seed_access(connection)
    _convert_queue(connection, candidates)
    op.create_table(
        "access_migration_state",
        sa.Column("revision", sa.String(32), primary_key=True),
        sa.Column("format_version", sa.Integer(), nullable=False),
        sa.Column("source_revision", sa.String(32), nullable=False),
        sa.Column("source_schema_digest", sa.String(64), nullable=False),
        sa.Column("target_schema_digest", sa.String(64), nullable=False),
        sa.Column("seed_access_digest", sa.String(64), nullable=False),
        sa.Column("seed_manifest", sa.JSON(), nullable=False),
    )
    ledger = sa.table(
        "access_migration_state",
        sa.column("revision"),
        sa.column("format_version"),
        sa.column("source_revision"),
        sa.column("source_schema_digest"),
        sa.column("target_schema_digest"),
        sa.column("seed_access_digest"),
        sa.column("seed_manifest", sa.JSON()),
    )
    connection.execute(
        ledger.insert().values(
            revision=revision,
            format_version=1,
            source_revision=source_revision,
            source_schema_digest=source_digest,
            target_schema_digest=_signature(connection),
            seed_access_digest=_group_digest(connection),
            seed_manifest=seed,
        )
    )


def downgrade():
    """Refuse lossy rollback and retain release tables, enum values and data."""
    connection = op.get_bind()
    _preflight(connection, True)
    if connection.scalar(sa.text("SELECT count(*) FROM execution_requests")):
        raise RuntimeError("Cannot downgrade with execution requests")
    if connection.scalar(sa.text("SELECT count(*) FROM users WHERE role::text='developer'")):
        raise RuntimeError("Cannot downgrade with Developer accounts")
    stored = connection.scalar(
        sa.text("SELECT seed_access_digest FROM access_migration_state WHERE revision=:revision"),
        {"revision": revision},
    )
    if stored != _group_digest(connection):
        raise RuntimeError("Cannot downgrade after group access changed")
    if connection.scalar(
        sa.text(
            "SELECT count(*) FROM group_memberships gm JOIN groups g ON g.id=gm.group_id JOIN users u ON u.id=gm.user_id WHERE g.role='developer' AND u.role::text<>'admin'"
        )
    ):
        raise RuntimeError("Cannot downgrade with group-derived Developer access")
    if connection.scalar(
        sa.text(
            "SELECT count(*) FROM access_group_members m JOIN users u ON u.id=m.user_id "
            "JOIN access_group_policies gp ON gp.group_id=m.group_id "
            "JOIN policies p ON p.id=gp.policy_id "
            "WHERE u.role::text<>'admin' AND coalesce(p.system_key,'')<>'results'"
        )
    ):
        raise RuntimeError("Cannot downgrade with group-derived access beyond Results")
