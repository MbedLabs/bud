"""Collect report requests and notify the current report publishers."""

import logging
from typing import Literal

import httpx
from pydantic import BaseModel, Field, TypeAdapter
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.access import has_permission
from app.core.config import settings
from app.models import ReportRequest, User
from app.services.audit import record_audit_event
from app.services.bloom_publish import BloomNotConfigured, bloom_credentials
from app.services.mail_service import MailConfigurationError, send_report_request_email

logger = logging.getLogger(__name__)


class RemoteRequest(BaseModel):
    """Validated request state from the configured Bloom publisher connection."""

    id: int = Field(gt=0)
    run_id: int = Field(gt=0)
    project_prefix: str = Field(min_length=1, max_length=50)
    requester_name: str = Field(max_length=255)
    requester_email: str = Field(max_length=255)
    status: Literal["pending", "delivered", "refused"]
    reason: str | None = None


async def mirror_page(
    db: AsyncSession, url: str, page: list[RemoteRequest], requested_ids: list[int] | None = None
) -> int:
    """Commit mailbox changes under a short database-only collection lock."""
    if db.bind.dialect.name == "postgresql":
        if not await db.scalar(text("SELECT pg_try_advisory_xact_lock(62521369)")):
            await db.rollback()
            return 0
    received = 0
    for item in page:
        row = await db.scalar(
            select(ReportRequest)
            .where(ReportRequest.bloom_url == url, ReportRequest.remote_id == item.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            row = ReportRequest(
                bloom_url=url,
                remote_id=item.id,
                run_id=item.run_id,
                project_prefix=item.project_prefix,
                requester_name=item.requester_name,
                requester_email=item.requester_email,
                status=item.status,
                reason=item.reason,
                notified_user_ids=[],
            )
            db.add(row)
            await db.flush()
            await record_audit_event(
                db,
                "report.requested",
                target_type="report_request",
                target_id=row.id,
                actor_type="service",
                details={"run_id": row.run_id},
            )
            received += 1
        elif row.status == "pending":
            row.status = item.status
            row.reason = item.reason
    if requested_ids is not None:
        missing = set(requested_ids) - {item.id for item in page}
        rows = (
            await db.scalars(
                select(ReportRequest)
                .where(
                    ReportRequest.bloom_url == url,
                    ReportRequest.remote_id.in_(missing),
                    ReportRequest.status == "pending",
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).all()
        for row in rows:
            row.status = "refused"
            row.reason = "The request is no longer available in Bloom."
            await record_audit_event(
                db,
                "report.refused",
                target_type="report_request",
                target_id=row.id,
                actor_type="service",
                details={"reason": row.reason},
            )
    await db.commit()
    return received


async def fetch_page(
    client: httpx.AsyncClient, url: str, token: str, params: dict
) -> list[RemoteRequest]:
    """A bounded and validated page from the configured publisher mailbox."""
    response = await client.get(
        f"{url}/api/bud/report-requests",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
    )
    response.raise_for_status()
    page = TypeAdapter(list[RemoteRequest]).validate_python(response.json())
    ids = [row.id for row in page]
    if len(page) > 100 or ids != sorted(set(ids)):
        raise ValueError("Invalid Bloom report-request page")
    return page


async def notify_publishers(db: AsyncSession, url: str) -> None:
    """Notify active publishers, checkpointing each recipient under a request lock."""
    request_ids = (
        await db.scalars(
            select(ReportRequest.id).where(
                ReportRequest.bloom_url == url, ReportRequest.status == "pending"
            )
        )
    ).all()
    if not request_ids:
        await db.commit()
        return
    users = (await db.scalars(select(User).where(User.is_active.is_(True)))).all()
    publishers = [
        (user.id, user.email, user.full_name)
        for user in users
        if await has_permission(db, user, "bloom_publish.execute")
    ]
    await db.commit()
    for request_id in request_ids:
        for user_id, email, name in publishers:
            row = await db.scalar(
                select(ReportRequest)
                .where(ReportRequest.id == request_id, ReportRequest.status == "pending")
                .with_for_update(skip_locked=True)
                .execution_options(populate_existing=True)
            )
            if row is None or user_id in row.notified_user_ids:
                await db.commit()
                continue
            try:
                await run_in_threadpool(
                    send_report_request_email,
                    to_email=email,
                    publisher_name=name,
                    requester_name=row.requester_name,
                    requester_email=row.requester_email,
                    project=row.project_prefix,
                    run_id=str(row.run_id),
                    review_link=f"{settings.APP_BASE_URL.rstrip('/')}/runs/{row.run_id}",
                )
            except MailConfigurationError:
                logger.warning("Report request %s publisher mail remains pending", row.id)
            else:
                row.notified_user_ids = [*row.notified_user_ids, user_id]
            await db.commit()


async def sync_report_requests(db: AsyncSession) -> int:
    """Collect new requests, refresh open states and retry unsent notifications."""
    try:
        url, token = await bloom_credentials(db)
    except BloomNotConfigured:
        return 0
    after_id = (
        await db.scalar(
            select(func.max(ReportRequest.remote_id)).where(ReportRequest.bloom_url == url)
        )
        or 0
    )
    await db.commit()
    received = 0
    async with httpx.AsyncClient(timeout=20) as client:
        while True:
            page = await fetch_page(client, url, token, {"after_id": after_id})
            if not page:
                break
            if any(item.id <= after_id for item in page):
                raise ValueError("Unordered Bloom report-request page")
            received += await mirror_page(db, url, page)
            after_id = page[-1].id
            if len(page) < 100:
                break
        pending_ids = list(
            (
                await db.scalars(
                    select(ReportRequest.remote_id)
                    .where(ReportRequest.bloom_url == url, ReportRequest.status == "pending")
                    .order_by(ReportRequest.remote_id)
                )
            ).all()
        )
        await db.commit()
        for start in range(0, len(pending_ids), 100):
            ids = pending_ids[start : start + 100]
            page = await fetch_page(client, url, token, {"request_ids": ids})
            if any(item.id not in ids for item in page):
                raise ValueError("Unexpected Bloom report-request state")
            await mirror_page(db, url, page, requested_ids=ids)
    await notify_publishers(db, url)
    return received
