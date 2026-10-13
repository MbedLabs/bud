"""Groups API: bundles of policies, the users they are given to, and access management's user list.

Admins and holders of access management use it. Someone who is not an Admin gives,
creates, edits and removes only groups whose policies they hold themselves; only an Admin
gives App Administration. A group holding station management accepts Admin or Developer
recipients. Default groups are read-only; duplicating one gives an editable
copy.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import require_permission
from app.core.access import (
    APP_ADMINISTRATION,
    effective_permissions,
    group_permissions,
    permission_set,
    user_groups,
)
from app.db.database import get_db
from app.models.access import AccessGroup, AccessGroupMember, Policy
from app.models.user import User, UserRole
from app.schemas.groups import (
    AccessGroupRef,
    AccessUserResponse,
    GroupCreate,
    GroupMemberAdd,
    GroupMemberResponse,
    GroupPolicyRef,
    GroupResponse,
    GroupUpdate,
)
from app.services.audit import record_audit_event

router = APIRouter()
access_router = APIRouter()

require_access_management = require_permission("access", "manage")


async def load_group(db: AsyncSession, group_id: int) -> AccessGroup:
    """The group with its policies and members; a missing group is a 404."""
    group = (
        await db.execute(
            select(AccessGroup)
            .options(selectinload(AccessGroup.policies), selectinload(AccessGroup.members))
            .where(AccessGroup.id == group_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


async def _response(db: AsyncSession, group: AccessGroup) -> GroupResponse:
    user_ids = [member.user_id for member in group.members]
    users = {
        user.id: user
        for user in (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars()
    }
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        is_default=group.is_default,
        system_key=group.system_key,
        policies=[
            GroupPolicyRef(id=policy.id, name=policy.name)
            for policy in sorted(group.policies, key=lambda policy: policy.name)
        ],
        permissions=sorted(group_permissions(group)),
        members=[
            GroupMemberResponse(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                profile_picture_url=user.profile_picture_url,
            )
            for user in sorted(users.values(), key=lambda user: user.full_name)
        ],
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


async def require_within_own_access(db: AsyncSession, actor: User, permissions: frozenset[str]):
    """Refuse someone who is not an Admin when the permissions exceed their own access."""
    if actor.role == UserRole.admin:
        return
    if not permissions <= await effective_permissions(db, actor):
        raise HTTPException(
            status_code=403, detail="You can only give access that you hold yourself"
        )


async def check_giveable(db: AsyncSession, actor: User, group: AccessGroup, user: User) -> None:
    """Validate the giver's authority and the recipient's base role."""
    if group.system_key == APP_ADMINISTRATION and actor.role != UserRole.admin:
        raise HTTPException(
            status_code=403, detail="Only an Admin gives Application Administrators"
        )
    permissions = group_permissions(group)
    await require_within_own_access(db, actor, permissions)
    if "stations.manage" in permissions and user.role not in (UserRole.admin, UserRole.developer):
        raise HTTPException(
            status_code=422,
            detail="Station management requires an Admin or Developer base role",
        )


async def give_group(db: AsyncSession, actor: User, group: AccessGroup, user: User) -> bool:
    """Add a missing group membership and report whether it was added."""
    await check_giveable(db, actor, group, user)
    exists = await db.get(AccessGroupMember, {"group_id": group.id, "user_id": user.id})
    if exists is not None:
        return False
    db.add(AccessGroupMember(group_id=group.id, user_id=user.id))
    await record_audit_event(
        db,
        "group.member_added",
        target_type="group",
        target_id=group.id,
        details={"user_id": user.id},
    )
    await db.flush()
    return True


async def _policies(db: AsyncSession, policy_ids: list[int]) -> list[Policy]:
    unique = list(dict.fromkeys(policy_ids))
    policies = list((await db.execute(select(Policy).where(Policy.id.in_(unique)))).scalars())
    if len(policies) != len(unique):
        raise HTTPException(status_code=422, detail="Unknown policy")
    return policies


def _policies_permissions(policies: list[Policy]) -> frozenset[str]:
    names: set[str] = set()
    for policy in policies:
        names |= permission_set(policy.permissions)
    return frozenset(names)


def _refuse_default(group: AccessGroup) -> None:
    if group.is_default:
        raise HTTPException(
            status_code=409, detail="Default groups cannot be changed; duplicate it instead"
        )


@router.get("", response_model=list[GroupResponse])
async def list_groups(
    db: AsyncSession = Depends(get_db, scope="function"),
    _actor: User = Depends(require_access_management),
):
    """Every group with its policies and members, defaults first."""
    groups = (
        await db.execute(
            select(AccessGroup)
            .options(selectinload(AccessGroup.policies), selectinload(AccessGroup.members))
            .order_by(AccessGroup.is_default.desc(), AccessGroup.name)
        )
    ).scalars()
    return [await _response(db, group) for group in groups]


@router.post("", response_model=GroupResponse, status_code=201)
async def create_group(
    data: GroupCreate,
    db: AsyncSession = Depends(get_db, scope="function"),
    actor: User = Depends(require_access_management),
):
    """Create a group from policies, with no members yet."""
    policies = await _policies(db, data.policy_ids)
    await require_within_own_access(db, actor, _policies_permissions(policies))
    group = AccessGroup(name=data.name, description=data.description, policies=policies)
    db.add(group)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="A group with this name already exists")
    await record_audit_event(
        db,
        "group.created",
        target_type="group",
        target_id=group.id,
        details={"name": group.name, "policy_ids": [policy.id for policy in policies]},
    )
    return await _response(db, await load_group(db, group.id))


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    _actor: User = Depends(require_access_management),
):
    """One group with its policies and members."""
    return await _response(db, await load_group(db, group_id))


@router.patch("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: int,
    data: GroupUpdate,
    db: AsyncSession = Depends(get_db, scope="function"),
    actor: User = Depends(require_access_management),
):
    """Rename a custom group, change its description or its policies."""
    group = await load_group(db, group_id)
    _refuse_default(group)
    await require_within_own_access(db, actor, group_permissions(group))
    if data.policy_ids is not None:
        policies = await _policies(db, data.policy_ids)
        await require_within_own_access(db, actor, _policies_permissions(policies))
        group.policies = policies
    if data.name is not None:
        group.name = data.name
    if "description" in data.model_fields_set:
        group.description = data.description
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="A group with this name already exists")
    await record_audit_event(
        db,
        "group.updated",
        target_type="group",
        target_id=group_id,
        details={"fields": sorted(data.model_fields_set)},
    )
    return await _response(db, await load_group(db, group_id))


@router.post("/{group_id}/duplicate", response_model=GroupResponse, status_code=201)
async def duplicate_group(
    group_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    actor: User = Depends(require_access_management),
):
    """Create an editable copy named ``<name> (copy)`` with the same policies and no members."""
    source = await load_group(db, group_id)
    await require_within_own_access(db, actor, group_permissions(source))
    copy = AccessGroup(
        name=f"{source.name} (copy)"[:100],
        description=source.description,
        policies=list(source.policies),
    )
    db.add(copy)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="A group with this name already exists")
    await record_audit_event(
        db,
        "group.created",
        target_type="group",
        target_id=copy.id,
        details={"name": copy.name, "duplicated_from": source.id},
    )
    return await _response(db, await load_group(db, copy.id))


@router.delete("/{group_id}", status_code=204)
async def delete_group(
    group_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    actor: User = Depends(require_access_management),
):
    """Delete a custom group; its members keep their base role and their other groups."""
    group = await load_group(db, group_id)
    _refuse_default(group)
    await require_within_own_access(db, actor, group_permissions(group))
    await record_audit_event(
        db, "group.deleted", target_type="group", target_id=group_id, details={"name": group.name}
    )
    await db.delete(group)
    await db.flush()


@router.post("/{group_id}/members", response_model=GroupResponse, status_code=201)
async def add_member(
    group_id: int,
    data: GroupMemberAdd,
    db: AsyncSession = Depends(get_db, scope="function"),
    actor: User = Depends(require_access_management),
):
    """Give a user the group."""
    group = await load_group(db, group_id)
    user = await db.get(User, data.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not await give_group(db, actor, group, user):
        raise HTTPException(status_code=409, detail="The user already has this group")
    return await _response(db, await load_group(db, group_id))


@router.delete("/{group_id}/members/{user_id}", response_model=GroupResponse)
async def remove_member(
    group_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    actor: User = Depends(require_access_management),
):
    """Take the group from a user."""
    group = await load_group(db, group_id)
    membership = await db.get(AccessGroupMember, {"group_id": group_id, "user_id": user_id})
    if membership is None:
        raise HTTPException(status_code=404, detail="The user does not have this group")
    if group.system_key == APP_ADMINISTRATION and actor.role != UserRole.admin:
        raise HTTPException(
            status_code=403, detail="Only an Admin gives Application Administrators"
        )
    await require_within_own_access(db, actor, group_permissions(group))
    await db.delete(membership)
    await record_audit_event(
        db,
        "group.member_removed",
        target_type="group",
        target_id=group_id,
        details={"user_id": user_id},
    )
    await db.flush()
    return await _response(db, await load_group(db, group_id))


@access_router.get("/users", response_model=list[AccessUserResponse])
async def list_access_users(
    db: AsyncSession = Depends(get_db, scope="function"),
    _actor: User = Depends(require_access_management),
):
    """Every user with their base role, their groups and their effective access."""
    users = (await db.execute(select(User).order_by(User.full_name))).scalars().all()
    rows = []
    for user in users:
        groups = await user_groups(db, user.id)
        rows.append(
            AccessUserResponse(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                is_active=user.is_active,
                groups=[AccessGroupRef(id=group.id, name=group.name) for group in groups],
                permissions=sorted(await effective_permissions(db, user)),
                profile_picture_url=user.profile_picture_url,
            )
        )
    return rows
