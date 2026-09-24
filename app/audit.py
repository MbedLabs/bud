"""Audit maintenance: ``python -m app.audit prune --older-than-days N``.

The running application never deletes an audit event. Retention is the operator's
choice: this command removes events older than the given number of days, and is
run by hand or from the operator's scheduler.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta

from sqlalchemy import delete

from app.db.database import async_session_maker
from app.models.audit import AuditEvent


async def prune(older_than_days: int) -> int:
    """Delete the events older than the given number of days; returns how many."""
    cutoff = datetime.utcnow() - timedelta(days=older_than_days)
    async with async_session_maker() as session:
        result = await session.execute(delete(AuditEvent).where(AuditEvent.occurred_at < cutoff))
        await session.commit()
        return result.rowcount or 0


def main(argv: list[str] | None = None) -> int:
    """Parse the command line and run the requested maintenance."""
    parser = argparse.ArgumentParser(prog="python -m app.audit")
    commands = parser.add_subparsers(dest="command", required=True)
    prune_parser = commands.add_parser("prune", help="delete events older than N days")
    prune_parser.add_argument("--older-than-days", type=int, required=True)
    args = parser.parse_args(argv)
    if args.older_than_days < 1:
        parser.error("--older-than-days must be at least 1")
    removed = asyncio.run(prune(args.older_than_days))
    print(f"removed {removed} audit events older than {args.older_than_days} days")
    return 0


if __name__ == "__main__":
    sys.exit(main())
