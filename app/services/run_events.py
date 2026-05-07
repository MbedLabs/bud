"""Helpers for recording system-visible test run events."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TestRunEvent


async def record_test_run_event(
    db: AsyncSession,
    *,
    test_run_id: int,
    stage: str,
    status: str,
    title: str,
    message: Optional[str] = None,
    event_metadata: Optional[dict[str, Any]] = None,
    sequence: Optional[int] = None,
) -> TestRunEvent:
    """Append a timeline event to a test run."""
    if sequence is None:
        current_sequence = await db.scalar(
            select(func.max(TestRunEvent.sequence)).where(TestRunEvent.test_run_id == test_run_id)
        )
        sequence = (current_sequence or 0) + 1

    event = TestRunEvent(
        test_run_id=test_run_id,
        sequence=sequence,
        stage=stage,
        status=status,
        title=title,
        message=message,
        event_metadata=event_metadata,
    )
    db.add(event)
    return event
