"""The audit prune command removes only events older than the retention it is given."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app import audit
from app.db.database import Base
from app.models import AuditEvent


def test_prune_keeps_events_inside_the_retention(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(audit, "async_session_maker", session_maker)

    async def _run():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with session_maker() as session:
            now = datetime.utcnow()
            session.add_all(
                [
                    AuditEvent(
                        actor_type="user", action="old", occurred_at=now - timedelta(days=40)
                    ),
                    AuditEvent(
                        actor_type="user", action="new", occurred_at=now - timedelta(days=5)
                    ),
                ]
            )
            await session.commit()
        removed = await audit.prune(30)
        async with session_maker() as session:
            left = [e.action for e in (await session.execute(select(AuditEvent))).scalars()]
        await engine.dispose()
        return removed, left

    removed, left = asyncio.run(_run())

    assert removed == 1
    assert left == ["new"]
