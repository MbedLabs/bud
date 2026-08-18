"""Authorization policy for Bud test-run resources."""

from typing import Union

from fastapi import HTTPException

from app.models import Runner, TestRun
from app.models.user import User, UserRole

RunPrincipal = Union[User, Runner]


def require_mutating_user(user: User) -> None:
    """Keep Bud's Viewer role strictly read-only."""
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
            raise HTTPException(status_code=404, detail="Test run not found")
        return
    if mutate:
        require_mutating_user(principal)
