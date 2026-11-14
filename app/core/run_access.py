"""Authorization policy for Bud test-run resources."""

from typing import Union

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import holds_on_product, product_ids_with
from app.models import Runner, TestRun
from app.models.user import User, UserRole

RunPrincipal = Union[User, Runner]

TEST_RUN_NOT_FOUND = "Test run not found"


def require_mutating_user(user: User) -> None:
    """Let only users whose base role is Admin change runs, results and artifacts."""
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Administrator privileges required")


def require_run_access(
    principal: RunPrincipal,
    test_run: TestRun,
    *,
    mutate: bool = False,
) -> None:
    """Authorize a user or runner for a run without leaking cross-runner data."""
    if isinstance(principal, Runner):
        if test_run.runner_id != principal.id:
            raise HTTPException(status_code=404, detail=TEST_RUN_NOT_FOUND)
        return
    if mutate:
        require_mutating_user(principal)


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
        raise HTTPException(status_code=404, detail=TEST_RUN_NOT_FOUND)
    require_run_access(principal, test_run, mutate=mutate)
    await require_run_product(db, principal, test_run)
    return test_run


async def require_run_product(
    db: AsyncSession, principal: RunPrincipal, test_run: TestRun, permission: str = "evidence.view"
) -> None:
    """Answer 404 to a user who does not hold the permission on the run's product."""
    if isinstance(principal, User) and not await holds_on_product(
        db, principal, test_run.product_id, permission
    ):
        raise HTTPException(status_code=404, detail=TEST_RUN_NOT_FOUND)


async def readable_runs(
    db: AsyncSession, principal: RunPrincipal, permission: str = "evidence.view"
):
    """The condition limiting runs to the products where a user holds the permission, or None
    when no limit applies (a station, an administrator)."""
    if not isinstance(principal, User):
        return None
    ids = await product_ids_with(db, principal, permission)
    if ids is None:
        return None
    return TestRun.product_id.in_(sorted(ids))
