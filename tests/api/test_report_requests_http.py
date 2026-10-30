"""Durable report collection, publisher notification and decisions."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.core.config import settings
from app.models import AuditEvent, ReportRequest, User, UserRole
from app.services.mail_service import MailDeliveryError
from app.services.report_requests import sync_report_requests
from tests.api.test_bloom_publish_api import _configure_bloom, _run_with_reports


@pytest.fixture(autouse=True)
def encryption(monkeypatch):
    """Use a fresh integration key for the isolated request database."""
    monkeypatch.setattr(settings, "INTEGRATION_ENCRYPTION_KEY", Fernet.generate_key().decode())


def remote_row(**changes):
    """One validated remote request."""
    return {
        "id": 1,
        "run_id": 41,
        "project_prefix": "PRJ",
        "requester_name": "Reader",
        "requester_email": "reader@example.com",
        "status": "pending",
        "reason": None,
        **changes,
    }


def connection(handler):
    """A real HTTP client against the explicit fake integration transport."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_collection_is_durable_and_mail_only_reaches_active_publishers(db_session):
    await _configure_bloom(db_session)
    for i, role in enumerate([UserRole.admin, UserRole.developer, UserRole.viewer, UserRole.admin]):
        db_session.add(
            User(
                email=f"publisher-{i}@example.com",
                full_name=f"Person {i}",
                role=role,
                hashed_password="unused",
                is_active=i != 3,
            )
        )
    await db_session.commit()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=(
                [remote_row()]
                if "request_ids" in request.url.params
                or int(request.url.params.get("after_id", "0")) < 1
                else []
            ),
        )
    )
    factory = httpx.AsyncClient
    with (
        patch(
            "app.services.report_requests.httpx.AsyncClient",
            side_effect=lambda **kwargs: factory(transport=transport),
        ),
        patch("app.services.report_requests.send_report_request_email") as send,
    ):
        assert await sync_report_requests(db_session) == 1
        assert await sync_report_requests(db_session) == 0
    assert {call.kwargs["to_email"] for call in send.call_args_list} == {
        "publisher-0@example.com",
        "publisher-1@example.com",
    }
    assert send.call_count == 2
    assert all(call.kwargs["review_link"].endswith("/runs/41") for call in send.call_args_list)
    rows = (await db_session.scalars(select(ReportRequest))).all()
    assert len(rows) == 1
    assert rows[0].requester_email == "reader@example.com"
    assert len(rows[0].notified_user_ids) == 2


@pytest.mark.asyncio
async def test_failed_mail_retries_and_remote_terminal_state_is_reconciled(db_session):
    await _configure_bloom(db_session)
    db_session.add(
        User(
            email="publisher@example.com",
            full_name="Publisher",
            role=UserRole.admin,
            hashed_password="unused",
        )
    )
    await db_session.commit()
    current = remote_row()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=(
                [current]
                if "request_ids" in request.url.params
                or int(request.url.params.get("after_id", "0")) < 1
                else []
            ),
        )
    )
    factory = httpx.AsyncClient
    with (
        patch(
            "app.services.report_requests.httpx.AsyncClient",
            side_effect=lambda **kwargs: factory(transport=transport),
        ),
        patch(
            "app.services.report_requests.send_report_request_email",
            side_effect=[MailDeliveryError("offline"), None],
        ) as send,
    ):
        await sync_report_requests(db_session)
        row = (await db_session.scalars(select(ReportRequest))).one()
        assert row.status == "pending"
        assert not row.notified_user_ids
        await sync_report_requests(db_session)
        assert len(row.notified_user_ids) == 1
        current.update(status="delivered")
        await sync_report_requests(db_session)
        assert row.status == "delivered"
        assert send.call_count == 2


@pytest.mark.asyncio
async def test_refusal_requires_publisher_and_confirmed_remote_answer(
    client, db_session, test_user
):
    await _configure_bloom(db_session)
    row = ReportRequest(
        bloom_url="https://bloom.test",
        remote_id=1,
        run_id=41,
        project_prefix="PRJ",
        requester_name="Reader",
        requester_email="reader@example.com",
        status="pending",
        notified_user_ids=[],
    )
    db_session.add(row)
    await db_session.commit()
    path = f"/api/report-requests/{row.id}/refuse"
    test_user.role = UserRole.viewer
    assert client.get("/api/report-requests").status_code == 403
    assert client.post(path, json={"reason": "No evidence"}).status_code == 403
    test_user.role = UserRole.developer
    assert client.get("/api/report-requests").json()[0]["run_id"] == 41
    assert client.post(path, json={"reason": " "}).status_code == 422
    factory = httpx.AsyncClient

    def offline(request):
        raise httpx.ConnectError("offline", request=request)

    with patch(
        "app.api.report_requests.httpx.AsyncClient",
        side_effect=lambda **kwargs: factory(transport=httpx.MockTransport(offline)),
    ):
        assert client.post(path, json={"reason": "Evidence incomplete"}).status_code == 502
    await db_session.refresh(row)
    assert row.status == "pending"
    captured = []

    def accept(request):
        captured.append(request)
        return httpx.Response(200, json={"status": "refused"})

    with patch(
        "app.api.report_requests.httpx.AsyncClient",
        side_effect=lambda **kwargs: factory(transport=httpx.MockTransport(accept)),
    ):
        assert client.post(path, json={"reason": "Evidence incomplete"}).status_code == 200
    await db_session.refresh(row)
    assert row.status == "refused"
    assert b"Bud TMP user #1" in captured[0].content


@pytest.mark.asyncio
async def test_publish_closes_only_matching_requests_after_remote_success(
    client, db_session, tmp_path, monkeypatch
):
    from app.api import uploads

    monkeypatch.setattr(uploads, "_UPLOAD_ROOT", tmp_path.resolve())
    await _configure_bloom(db_session)
    run = await _run_with_reports(db_session, tmp_path)
    run_id = run.id
    for project in ["PRJ", "ABC"]:
        db_session.add(
            ReportRequest(
                bloom_url="https://bloom.test",
                remote_id=1 if project == "PRJ" else 2,
                run_id=run.id,
                project_prefix=project,
                requester_name="Reader",
                requester_email="reader@example.com",
                status="pending",
                notified_user_ids=[],
            )
        )
    await db_session.commit()
    with patch(
        "app.api.test_runs.post_to_bloom", new=AsyncMock(side_effect=httpx.ConnectError("offline"))
    ):
        assert client.post(f"/api/test-runs/{run_id}/publish-to-bloom").status_code == 502
    db_session.expire_all()
    assert {row.status for row in (await db_session.scalars(select(ReportRequest))).all()} == {
        "pending"
    }
    with patch(
        "app.api.test_runs.post_to_bloom",
        new=AsyncMock(return_value={"document_id": 7, "doc_id": "PRJ-RPT-001", "created": True}),
    ):
        assert client.post(f"/api/test-runs/{run_id}/publish-to-bloom").status_code == 200
    db_session.expire_all()
    states = {
        row.project_prefix: row.status
        for row in (await db_session.scalars(select(ReportRequest))).all()
    }
    assert states == {"PRJ": "delivered", "ABC": "pending"}


def test_publisher_mail_renders_the_real_run_url_and_escapes_reader_text(monkeypatch):
    """Rendered report email contains a resolved run link."""
    from app.services import mail_service

    captured = []
    monkeypatch.setattr(mail_service, "send_email", lambda **values: captured.append(values))
    mail_service.send_report_request_email(
        to_email="publisher@example.com",
        publisher_name="Publisher",
        requester_name="<Reader>",
        requester_email="reader@example.com",
        project="PRJ",
        run_id="41",
        review_link="http://localhost:3000/runs/41",
    )
    message = captured[0]
    assert "${" not in message["html_body"]
    assert "${" not in message["text_body"]
    assert 'href="http://localhost:3000/runs/41"' in message["html_body"]
    assert "&lt;Reader&gt;" in message["html_body"]
    assert "<Reader>" not in message["html_body"]


@pytest.mark.asyncio
async def test_completed_recipients_survive_a_later_unexpected_mail_failure(db_session):
    """Per-recipient notification checkpoints survive delivery failures."""
    await _configure_bloom(db_session)
    for number in range(2):
        db_session.add(
            User(
                email=f"checkpoint-{number}@example.com",
                full_name="Publisher",
                role=UserRole.admin,
                hashed_password="unused",
            )
        )
    await db_session.commit()
    factory = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json=(
                [remote_row()]
                if "request_ids" in request.url.params
                or int(request.url.params.get("after_id", "0")) < 1
                else []
            ),
        )
    )
    with (
        patch(
            "app.services.report_requests.httpx.AsyncClient",
            side_effect=lambda **kwargs: factory(transport=transport),
        ),
        patch(
            "app.services.report_requests.send_report_request_email",
            side_effect=[None, RuntimeError("delivery interrupted")],
        ) as send,
    ):
        with pytest.raises(RuntimeError, match="delivery interrupted"):
            await sync_report_requests(db_session)
    first = send.call_args_list[0].kwargs["to_email"]
    await db_session.rollback()
    with (
        patch(
            "app.services.report_requests.httpx.AsyncClient",
            side_effect=lambda **kwargs: factory(transport=transport),
        ),
        patch("app.services.report_requests.send_report_request_email") as retry,
    ):
        await sync_report_requests(db_session)
    assert retry.call_count == 1
    assert retry.call_args.kwargs["to_email"] != first


@pytest.mark.asyncio
async def test_collection_pages_new_requests_without_replaying_closed_history(db_session):
    """The durable highest ID bounds later polls; closed requests are not replayed."""
    await _configure_bloom(db_session)
    seen = []

    def serve(request):
        after = int(request.url.params.get("after_id", "0"))
        seen.append(after)
        values = [
            remote_row(id=index, status="delivered")
            for index in range(after + 1, min(after + 100, 101) + 1)
        ]
        return httpx.Response(200, json=values)

    factory = httpx.AsyncClient
    with patch(
        "app.services.report_requests.httpx.AsyncClient",
        side_effect=lambda **kwargs: factory(transport=httpx.MockTransport(serve)),
    ):
        assert await sync_report_requests(db_session) == 101
        assert await sync_report_requests(db_session) == 0
    assert seen == [0, 100, 101]


@pytest.mark.asyncio
async def test_request_fulfillment_rejects_a_different_destination_before_publication(
    client, db_session, tmp_path, monkeypatch
):
    from app.api import uploads

    monkeypatch.setattr(uploads, "_UPLOAD_ROOT", tmp_path.resolve())
    await _configure_bloom(db_session)
    run = await _run_with_reports(db_session, tmp_path)
    row = ReportRequest(
        bloom_url="https://bloom.test",
        remote_id=7,
        run_id=run.id,
        project_prefix="ABC",
        requester_name="Reader",
        requester_email="reader@example.com",
        status="pending",
        notified_user_ids=[],
    )
    db_session.add(row)
    await db_session.commit()
    with patch("app.api.test_runs.post_to_bloom", new=AsyncMock()) as publish:
        response = client.post(f"/api/report-requests/{row.id}/publish")
        assert response.status_code == 409
        assert "different Bloom project" in response.json()["detail"]
        publish.assert_not_awaited()
    await db_session.refresh(row)
    assert row.status == "pending"
    row.project_prefix = "PRJ"
    await db_session.commit()
    with patch(
        "app.api.test_runs.post_to_bloom",
        new=AsyncMock(return_value={"document_id": 7, "doc_id": "PRJ-RPT-001", "created": True}),
    ):
        assert client.post(f"/api/report-requests/{row.id}/publish").status_code == 200
    await db_session.refresh(row)
    assert row.status == "delivered"


@pytest.mark.asyncio
async def test_refusal_reconciles_an_already_delivered_remote_request(client, db_session):
    await _configure_bloom(db_session)
    row = ReportRequest(
        bloom_url="https://bloom.test",
        remote_id=8,
        run_id=41,
        project_prefix="PRJ",
        requester_name="Reader",
        requester_email="reader@example.com",
        status="pending",
        notified_user_ids=[],
    )
    db_session.add(row)
    await db_session.commit()
    factory = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            409, json={"detail": "The report has already been delivered"}
        )
    )
    with patch(
        "app.api.report_requests.httpx.AsyncClient",
        side_effect=lambda **kwargs: factory(transport=transport),
    ):
        response = client.post(f"/api/report-requests/{row.id}/refuse", json={"reason": "Too late"})
    assert response.status_code == 200
    assert response.json()["status"] == "delivered"
    await db_session.refresh(row)
    assert row.status == "delivered"
    event = await db_session.scalar(
        select(AuditEvent).where(AuditEvent.action == "report.published")
    )
    assert event.actor_type == "service"


@pytest.mark.asyncio
async def test_removed_remote_requests_close_the_local_inbox_without_another_email(db_session):
    await _configure_bloom(db_session)
    row = ReportRequest(
        bloom_url="https://bloom.test",
        remote_id=3,
        run_id=41,
        project_prefix="PRJ",
        requester_name="Reader",
        requester_email="reader@example.com",
        status="pending",
        notified_user_ids=[],
    )
    db_session.add(row)
    await db_session.commit()
    factory = httpx.AsyncClient
    with (
        patch(
            "app.services.report_requests.httpx.AsyncClient",
            side_effect=lambda **kwargs: factory(
                transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[]))
            ),
        ),
        patch("app.services.report_requests.send_report_request_email") as send,
    ):
        await sync_report_requests(db_session)
    await db_session.refresh(row)
    assert row.status == "refused"
    assert "no longer available" in row.reason
    send.assert_not_called()
