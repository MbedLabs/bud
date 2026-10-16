"""Publisher inbox and refusal of a Bloom reader's report request."""

from http import HTTPStatus

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_permission
from app.db import get_db
from app.models import ReportRequest, TestRun, User
from app.services.audit import record_audit_event
from app.services.bloom_publish import BloomNotConfigured, bloom_credentials

router = APIRouter()


class Refusal(BaseModel):
    """A publisher's explanation for refusing a report request."""

    reason: str = Field(min_length=1, max_length=2000)


@router.get("")
async def pending_requests(
    run_id: int | None = None,
    db: AsyncSession = Depends(get_db, scope="function"),
    _user: User = Depends(require_permission("bloom_publish", "execute")),
):
    """Pending requests for the current Bloom connection and optionally one run."""
    try:
        url, _token = await bloom_credentials(db)
    except BloomNotConfigured:
        return []
    query = select(ReportRequest, TestRun.name, TestRun.status).outerjoin(
        TestRun, TestRun.id == ReportRequest.run_id
    )
    query = query.where(ReportRequest.bloom_url == url, ReportRequest.status == "pending")
    if run_id is not None:
        query = query.where(ReportRequest.run_id == run_id)
    rows = (await db.execute(query.order_by(ReportRequest.id))).all()
    return [
        {
            "id": row.id,
            "run_id": row.run_id,
            "run_name": name or f"Run #{row.run_id}",
            "run_status": status,
            "project_prefix": row.project_prefix,
            "requester_name": row.requester_name,
            "requester_email": row.requester_email,
            "created_at": row.created_at,
        }
        for row, name, status in rows
    ]


@router.post(
    "/{request_id}/refuse",
    responses={
        404: {"description": HTTPStatus(404).phrase},
        409: {"description": HTTPStatus(409).phrase},
        422: {"description": HTTPStatus(422).phrase},
        502: {"description": HTTPStatus(502).phrase},
    },
)
async def refuse_request(
    request_id: int,
    data: Refusal,
    db: AsyncSession = Depends(get_db, scope="function"),
    user: User = Depends(require_permission("bloom_publish", "execute")),
):
    """Send a publisher's refusal to Bloom before closing the local request."""
    reason = data.reason.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="A refusal reason is required")
    try:
        url, token = await bloom_credentials(db)
    except BloomNotConfigured as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    row = await db.scalar(
        select(ReportRequest)
        .where(ReportRequest.id == request_id, ReportRequest.bloom_url == url)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="Request is already closed")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{url}/api/bud/report-requests/{row.remote_id}/refuse",
                headers={"Authorization": f"Bearer {token}"},
                json={"reason": reason, "publisher": f"{user.full_name} (Bud user #{user.id})"},
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 409:
            row.status = "delivered"
            await record_audit_event(
                db,
                "report.published",
                target_type="report_request",
                target_id=row.id,
                actor_type="service",
                details={"run_id": row.run_id, "source": "Bloom delivery reconciliation"},
            )
            await db.commit()
            return {"status": row.status}
        raise HTTPException(
            status_code=502,
            detail="Bloom rejected the refusal. Refresh the requests and check the connection.",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502, detail="Could not reach Bloom. The request remains open."
        ) from exc
    row.status = "refused"
    row.reason = reason
    await record_audit_event(
        db,
        "report.refused",
        target_type="report_request",
        target_id=row.id,
        details={"reason": reason, "run_id": row.run_id},
    )
    await db.commit()
    return {"status": row.status}


@router.post(
    "/{request_id}/publish",
    responses={
        404: {"description": HTTPStatus(404).phrase},
        409: {"description": HTTPStatus(409).phrase},
    },
)
async def publish_request(
    request_id: int,
    db: AsyncSession = Depends(get_db, scope="function"),
    user: User = Depends(require_permission("bloom_publish", "execute")),
):
    """Fulfill a pending request only by publishing into its Bloom project."""
    from app.api.test_runs import publish_report

    try:
        url, _token = await bloom_credentials(db)
    except BloomNotConfigured as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    row = await db.scalar(
        select(ReportRequest)
        .where(ReportRequest.id == request_id, ReportRequest.bloom_url == url)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="Request is already closed")
    return await publish_report(row.run_id, db, user, requested_project=row.project_prefix)
