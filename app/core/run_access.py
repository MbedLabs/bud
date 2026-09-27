"""Authorization policy for Bud test-run resources."""

from typing import Union

from fastapi import HTTPException
from sqlalchemy import select
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


async def load_run(
    db: AsyncSession,
    principal: RunPrincipal,
    run_id: int,
    *,
    mutate: bool = False,
    options: tuple = (),
) -> TestRun:
    """The test run with the id after the run access check; a missing run is a 404."""
    test_run = (
        await db.execute(select(TestRun).where(TestRun.id == run_id).options(*options))
    ).scalar_one_or_none()
    if test_run is None:
        raise HTTPException(status_code=404, detail="Test run not found")
    await require_run_access(db, principal, test_run, mutate=mutate)
    return test_run
