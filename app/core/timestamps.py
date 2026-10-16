"""Timestamps as people read them in Bud: UTC, to the second."""

from datetime import datetime, timezone
from typing import Optional


def second_utc(value: Optional[datetime]) -> str:
    """The time as ``YYYY-MM-DD HH:MM:SS UTC``; empty when None. A naive time is taken as UTC."""
    if value is None:
        return ""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%d %H:%M:%S UTC")
