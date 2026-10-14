"""What a Bud user may do: their base role's allowance plus the policies of their groups.

The base role (Admin, Developer, Viewer) is the user's own and set at invitation. Admin
holds every permission. Viewer is allowed the Results policy; Developer is allowed Results,
Custom runs and Publish to Bloom. Groups are bundles of policies; a user can have several,
and a group only adds. Human access is not scoped by products or stations.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.access import AccessGroup, AccessGroupMember, Policy
from app.models.user import User, UserRole

PERMISSION_CATALOGUE: dict[str, tuple[str, ...]] = {
    "evidence": ("view",),
    "reports": ("export",),
    "products": ("view", "manage"),
    "stations": ("view", "manage"),
    "custom_runs": ("create",),
    "bloom_publish": ("execute",),
    "settings": ("view", "edit"),
    "audit": ("view",),
    "access": ("manage",),
}

ALL_PERMISSIONS: frozenset[str] = frozenset(
    f"{resource}.{action}"
    for resource, actions in PERMISSION_CATALOGUE.items()
    for action in actions
)


@dataclass(frozen=True)
class DefaultPolicy:
    """A shipped, read-only policy."""

    key: str
    name: str
    description: str
    permissions: dict[str, list[str]]


@dataclass(frozen=True)
class DefaultGroup:
    """A shipped, read-only group and the default policies it bundles."""

    key: str
    name: str
    description: str
    policies: tuple[str, ...]


DEFAULT_POLICIES: tuple[DefaultPolicy, ...] = (
    DefaultPolicy(
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
    DefaultPolicy(
        "custom_runs",
        "Custom runs",
        "Queue a custom run on the Test Stations.",
        {"custom_runs": ["create"]},
    ),
    DefaultPolicy(
        "publish_to_bloom",
        "Reports publishing",
        "Publish a completed run's report to Bloom.",
        {"bloom_publish": ["execute"]},
    ),
    DefaultPolicy(
        "stations",
        "Stations",
        "Manage Test Stations: registration keys, enabling, editing and deleting stations.",
        {"stations": ["view", "manage"]},
    ),
    DefaultPolicy(
        "products",
        "Products",
        "Create and delete products.",
        {"products": ["view", "manage"]},
    ),
    DefaultPolicy(
        "settings",
        "Settings and integrations",
        "Settings, the Bloom link, notification channels and the company logo.",
        {"settings": ["view", "edit"]},
    ),
    DefaultPolicy("audit", "Audit log", "Read the audit log.", {"audit": ["view"]}),
    DefaultPolicy(
        "access_management",
        "Access management",
        "Decide access requests, give users their groups and edit groups.",
        {"access": ["manage"]},
    ),
)

DEFAULT_GROUPS: tuple[DefaultGroup, ...] = (
    DefaultGroup("results_viewers", "Results Viewers", "See results.", ("results",)),
    DefaultGroup(
        "test_operators",
        "Test Operators",
        "See results, queue custom runs and publish to Bloom.",
        ("results", "custom_runs", "publish_to_bloom"),
    ),
    DefaultGroup(
        "station_managers",
        "Station Managers",
        "See results and manage Test Stations.",
        ("results", "stations"),
    ),
    DefaultGroup(
        "access_managers",
        "Access Managers",
        "Station Managers plus access management.",
        ("results", "stations", "access_management"),
    ),
    DefaultGroup(
        "app_administration",
        "Application Administrators",
        "Every grantable policy.",
        tuple(policy.key for policy in DEFAULT_POLICIES),
    ),
)

APP_ADMINISTRATION = "app_administration"

BASE_ROLE_POLICIES: dict[UserRole, tuple[str, ...]] = {
    UserRole.viewer: ("results",),
    UserRole.developer: ("results", "custom_runs", "publish_to_bloom"),
}

_DEFAULT_POLICY_BY_KEY = {policy.key: policy for policy in DEFAULT_POLICIES}


def permission_set(matrix: dict) -> frozenset[str]:
    """Flatten a ``{resource: [action, ...]}`` matrix into ``resource.action`` names."""
    return frozenset(
        f"{resource}.{action}" for resource, actions in (matrix or {}).items() for action in actions
    )


def base_role_permissions(role: UserRole) -> frozenset[str]:
    """What the base role allows on its own."""
    if role == UserRole.admin:
        return ALL_PERMISSIONS
    names: set[str] = set()
    for key in BASE_ROLE_POLICIES.get(role, ()):
        names |= permission_set(_DEFAULT_POLICY_BY_KEY[key].permissions)
    return frozenset(names)


def group_permissions(group: AccessGroup) -> frozenset[str]:
    """The union of the group's policies."""
    names: set[str] = set()
    for policy in group.policies:
        names |= permission_set(policy.permissions)
    return frozenset(names)


async def user_groups(db: AsyncSession, user_id: int) -> list[AccessGroup]:
    """The access groups the user has, with their policies loaded."""
    return list(
        (
            await db.execute(
                select(AccessGroup)
                .join(AccessGroupMember, AccessGroupMember.group_id == AccessGroup.id)
                .where(AccessGroupMember.user_id == user_id)
                .options(selectinload(AccessGroup.policies))
                .order_by(AccessGroup.name)
            )
        )
        .scalars()
        .all()
    )


async def effective_permissions(db: AsyncSession, user: User) -> frozenset[str]:
    """The base role's allowance plus every policy of every group the user has."""
    allowed = set(base_role_permissions(user.role))
    if user.role == UserRole.admin:
        return frozenset(allowed)
    for group in await user_groups(db, user.id):
        allowed |= group_permissions(group)
    return frozenset(allowed)


async def has_permission(db: AsyncSession, user: User, permission: str) -> bool:
    """Whether the user holds ``resource.action``."""
    return permission in await effective_permissions(db, user)


async def seed_default_access(db: AsyncSession) -> None:
    """Create the shipped policies and groups that are missing; existing rows are kept."""
    policies = {
        policy.system_key: policy
        for policy in (
            await db.execute(select(Policy).where(Policy.system_key.is_not(None)))
        ).scalars()
    }
    for default in DEFAULT_POLICIES:
        if default.key not in policies:
            policy = Policy(
                system_key=default.key,
                name=default.name,
                description=default.description,
                permissions=default.permissions,
                is_default=True,
            )
            db.add(policy)
            policies[default.key] = policy
    for policy in policies.values():
        if policy.system_key == "publish_to_bloom" and policy.name == "Publish to Bloom":
            policy.name = "Reports publishing"
    await db.flush()
    groups = (
        (await db.execute(select(AccessGroup).where(AccessGroup.system_key.is_not(None))))
        .scalars()
        .all()
    )
    for group in groups:
        if group.system_key == APP_ADMINISTRATION and group.name == "App Administration":
            group.name = "Application Administrators"
    existing = {group.system_key for group in groups}
    for default in DEFAULT_GROUPS:
        if default.key not in existing:
            db.add(
                AccessGroup(
                    system_key=default.key,
                    name=default.name,
                    description=default.description,
                    is_default=True,
                    policies=[policies[key] for key in default.policies],
                )
            )
    await db.flush()
