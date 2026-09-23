"""Authorization policy for Bud test-run resources."""

from typing import Union

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import effective_role, in_scope, readable_products
from app.models import Runner, TestRun
from app.models.user import User, UserRole

RunPrincipal = Union[User, Runner]


async def require_mutating_user(db: AsyncSession, user: User) -> None:
    """Keep Bud's Viewer role strictly read-only; admin groups count as admin."""
    if await effective_role(db, user) != UserRole.admin:
        raise HTTPException(status_code=403, detail="Administrator privileges required")


async def require_run_access(
    db: AsyncSession,
    principal: RunPrincipal,
    test_run: TestRun,
    *,
    mutate: bool = False,
) -> None:
    """Authorize a user or runner for a run without leaking cross-runner data.

    A viewer limited to some products gets a 404 for a run outside them, the same
    answer as for a run that does not exist.
    """
    if isinstance(principal, Runner):
        if test_run.runner_id != principal.id:
            raise HTTPException(status_code=404, detail="Test run not found")
        return
    if mutate:
        await require_mutating_user(db, principal)
        return
    if not in_scope(await readable_products(db, principal), test_run.product_id):
        raise HTTPException(status_code=404, detail="Test run not found")
