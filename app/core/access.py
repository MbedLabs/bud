"""What a Bud user may do: the highest of their own role and the roles of their groups.

Viewer reads everything, Developer also queues custom runs and publishes a run to Bloom,
Administrator holds everything. Access is not scoped by products or stations.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.groups import Group, GroupMembership
from app.models.user import User, UserRole

ROLE_RANK = {UserRole.viewer: 0, UserRole.developer: 1, UserRole.admin: 2}


async def effective_role(db: AsyncSession, user: User) -> UserRole:
    """The highest of the user's own role and the roles of the groups they belong to."""
    if user.role == UserRole.admin:
        return UserRole.admin
    group_roles = (
        await db.execute(
            select(Group.role)
            .join(GroupMembership, GroupMembership.group_id == Group.id)
            .where(GroupMembership.user_id == user.id)
        )
    ).scalars()
    return max([user.role, *(UserRole(role) for role in group_roles)], key=ROLE_RANK.__getitem__)
