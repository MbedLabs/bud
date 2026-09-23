"""What a Bud user may do: their role, refined by the groups they belong to.

A member of an admin group is an administrator. A viewer in no group reads every
product, as before groups existed. A viewer in one or more groups reads the products
those groups grant; a grant without a product covers every product. Runs without a
product are visible only to users who read every product.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.groups import Group, GroupMembership, GroupProductGrant
from app.models.user import User, UserRole

ProductScope = Optional[set[int]]


async def effective_role(db: AsyncSession, user: User) -> UserRole:
    """Admin when the user is one or belongs to an admin group, else viewer."""
    if user.role == UserRole.admin:
        return UserRole.admin
    admin_group = await db.scalar(
        select(GroupMembership.id)
        .join(Group, Group.id == GroupMembership.group_id)
        .where(GroupMembership.user_id == user.id, Group.role == UserRole.admin.value)
        .limit(1)
    )
    return UserRole.admin if admin_group is not None else user.role


async def readable_products(db: AsyncSession, user: User) -> ProductScope:
    """The product ids the user reads, or None for every product."""
    if await effective_role(db, user) == UserRole.admin:
        return None
    in_any_group = await db.scalar(
        select(GroupMembership.id).where(GroupMembership.user_id == user.id).limit(1)
    )
    if in_any_group is None:
        return None
    grants = (
        await db.execute(
            select(GroupProductGrant.product_id)
            .join(GroupMembership, GroupMembership.group_id == GroupProductGrant.group_id)
            .where(GroupMembership.user_id == user.id)
        )
    ).scalars()
    scope: set[int] = set()
    for product_id in grants:
        if product_id is None:
            return None
        scope.add(product_id)
    return scope


def in_scope(scope: ProductScope, product_id: Optional[int]) -> bool:
    """True when a product (or a run's product) is inside the scope."""
    return scope is None or (product_id is not None and product_id in scope)


def scope_condition(scope: ProductScope, column):
    """A WHERE term limiting a product column to the scope, or None for no limit."""
    if scope is None:
        return None
    return column.in_(sorted(scope))
