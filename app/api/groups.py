"""Groups API (admin only): groups, their members and their product grants."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import require_role
from app.db.database import get_db
from app.models import Product
from app.models.groups import Group, GroupMembership, GroupProductGrant
from app.models.user import User, UserRole
from app.schemas.groups import (
    GroupCreate,
    GroupGrantAdd,
    GroupGrantResponse,
    GroupMemberAdd,
    GroupMemberResponse,
    GroupResponse,
    GroupUpdate,
)
from app.services.audit import record_audit_event

router = APIRouter()

require_admin = require_role(UserRole.admin)


async def _load(db: AsyncSession, group_id: int) -> Group:
    group = (
        await db.execute(
            select(Group)
            .options(selectinload(Group.members), selectinload(Group.grants))
            .where(Group.id == group_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


async def _response(db: AsyncSession, group: Group) -> GroupResponse:
    user_ids = [m.user_id for m in group.members]
    users = {
        u.id: u for u in (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars()
    }
    product_ids = [g.product_id for g in group.grants if g.product_id is not None]
    products = {
        p.id: p.name
        for p in (await db.execute(select(Product).where(Product.id.in_(product_ids)))).scalars()
    }
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        role=group.role,
        members=[
            GroupMemberResponse(
                user_id=m.user_id,
                email=users[m.user_id].email,
                full_name=users[m.user_id].full_name,
            )
            for m in group.members
            if m.user_id in users
        ],
        grants=[
            GroupGrantResponse(
                id=g.id, product_id=g.product_id, product_name=products.get(g.product_id)
            )
            for g in group.grants
        ],
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


@router.get("", response_model=list[GroupResponse])
async def list_groups(
    db: AsyncSession = Depends(get_db, scope="function"), _admin: User = Depends(require_admin)
):
    """Every group with its members and product grants."""
    groups = (
        await db.execute(
            select(Group)
            .options(selectinload(Group.members), selectinload(Group.grants))
            .order_by(Group.name)
        )
    ).scalars()
    return [await _response(db, g) for g in groups]


@router.post("", response_model=GroupResponse, status_code=201)
async def create_group(
    data: GroupCreate,
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_admin),
):
    """Create a group with a role and no members or grants yet."""
    group = Group(name=data.name.strip(), description=data.description, role=data.role)
    db.add(group)
    try:
        await db.flush()
        await record_audit_event(
            db,
            "group.created",
            target_type="group",
            target_id=group.id,
            details={"name": group.name, "role": group.role},
        )
    except IntegrityError:
        raise HTTPException(status_code=400, detail="A group with this name already exists")
    return await _response(db, await _load(db, group.id))


@router.patch("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: int,
    data: GroupUpdate,
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_admin),
):
    """Rename a group, change its description or its role."""
    group = await _load(db, group_id)
    if data.name is not None:
        group.name = data.name.strip()
    if "description" in data.model_fields_set:
        group.description = data.description
    if data.role is not None:
        group.role = data.role
    try:
        await db.flush()
        await record_audit_event(
            db,
            "group.updated",
            target_type="group",
            target_id=group_id,
            details={"fields": sorted(data.model_fields_set)},
        )
    except IntegrityError:
        raise HTTPException(status_code=400, detail="A group with this name already exists")
    return await _response(db, await _load(db, group_id))


@router.delete("/{group_id}", status_code=204)
async def delete_group(
    group_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_admin),
):
    """Delete a group; its members keep only their own role."""
    await record_audit_event(
        db,
        "group.deleted",
        target_type="group",
        target_id=group_id,
    )
    await db.delete(await _load(db, group_id))
    await db.flush()


@router.post("/{group_id}/members", response_model=GroupResponse, status_code=201)
async def add_member(
    group_id: int,
    data: GroupMemberAdd,
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_admin),
):
    """Add a user to a group."""
    await _load(db, group_id)
    if await db.get(User, data.user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")
    exists = await db.scalar(
        select(GroupMembership.id).where(
            GroupMembership.group_id == group_id, GroupMembership.user_id == data.user_id
        )
    )
    if exists is not None:
        raise HTTPException(status_code=400, detail="The user is already in this group")
    db.add(GroupMembership(group_id=group_id, user_id=data.user_id))
    await record_audit_event(
        db,
        "group.member_added",
        target_type="group",
        target_id=group_id,
        details={"user_id": data.user_id},
    )
    await db.flush()
    return await _response(db, await _load(db, group_id))


@router.delete("/{group_id}/members/{user_id}", response_model=GroupResponse)
async def remove_member(
    group_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_admin),
):
    """Remove a user from a group."""
    membership = (
        await db.execute(
            select(GroupMembership).where(
                GroupMembership.group_id == group_id, GroupMembership.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=404, detail="The user is not in this group")
    await db.delete(membership)
    await record_audit_event(
        db,
        "group.member_removed",
        target_type="group",
        target_id=group_id,
        details={"user_id": membership.user_id},
    )
    await db.flush()
    return await _response(db, await _load(db, group_id))


@router.post("/{group_id}/grants", response_model=GroupResponse, status_code=201)
async def add_grant(
    group_id: int,
    data: GroupGrantAdd,
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_admin),
):
    """Grant a group one product, or every product when no product is given."""
    await _load(db, group_id)
    if data.product_id is not None and await db.get(Product, data.product_id) is None:
        raise HTTPException(status_code=404, detail="Product not found")
    exists = await db.scalar(
        select(GroupProductGrant.id).where(
            GroupProductGrant.group_id == group_id,
            (
                GroupProductGrant.product_id.is_(None)
                if data.product_id is None
                else GroupProductGrant.product_id == data.product_id
            ),
        )
    )
    if exists is not None:
        raise HTTPException(status_code=400, detail="The group already has this grant")
    db.add(GroupProductGrant(group_id=group_id, product_id=data.product_id))
    await record_audit_event(
        db,
        "group.grant_added",
        target_type="group",
        target_id=group_id,
        product_id=data.product_id,
        details={"all_products": data.product_id is None},
    )
    await db.flush()
    return await _response(db, await _load(db, group_id))


@router.delete("/{group_id}/grants/{grant_id}", response_model=GroupResponse)
async def remove_grant(
    group_id: int,
    grant_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    _admin: User = Depends(require_admin),
):
    """Revoke one product grant of a group."""
    grant = await db.get(GroupProductGrant, grant_id)
    if grant is None or grant.group_id != group_id:
        raise HTTPException(status_code=404, detail="Grant not found")
    await db.delete(grant)
    await record_audit_event(
        db,
        "group.grant_removed",
        target_type="group",
        target_id=group_id,
        product_id=grant.product_id,
        details={"all_products": grant.product_id is None},
    )
    await db.flush()
    return await _response(db, await _load(db, group_id))
