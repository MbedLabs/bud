"""
* @file     ${tests/api/BUD_report_requests_http.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Report requests are collected durably, mailed to active publishers once, and decided against Bloom.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests each scenario on a fresh app database with Bloom served by a faked HTTP transport.
"""

from contextlib import contextmanager
from unittest import mock

import httpx
from sqlalchemy import select

from app.api import test_runs
from app.models import AuditEvent, ReportRequest, User, UserRole
from app.services import mail_service
from app.services import report_requests as report_service
from app.services.mail_service import MailDeliveryError
from tests.api.report_requests_http import ReportRequestsHttpBase

REAL_CLIENT = httpx.AsyncClient


def body_of(response):
    """The JSON answer, or an empty one."""
    try:
        return response.json() or {}
    except ValueError:
        return {}


@contextmanager
def bloom(handler):
    """Serve every outbound HTTP client through a faked transport."""
    transport = httpx.MockTransport(handler)
    with mock.patch.object(
        httpx, "AsyncClient", side_effect=lambda **kwargs: REAL_CLIENT(transport=transport)
    ):
        yield


def listing(current):
    """A Bloom answer listing one request to a first poll or a lookup by id, and nothing after."""

    def handler(request):
        first = (
            "request_ids" in request.url.params or int(request.url.params.get("after_id", "0")) < 1
        )
        return httpx.Response(200, json=[current] if first else [])

    return handler


class ReportRequestsHttpTest(ReportRequestsHttpBase):

    def setUpClass(self):
        super().setUpClass()
        self.tc_checks = {}
        for scenario in (self.collection, self.retry, self.checkpoints, self.paging, self.removed):
            self.bud.bud_start_app()
            self.bud.bud_delete_in_app(User)
            self.bud.bud_configure_bloom()
            self.bud.bud_await(scenario(self.bud.bud_open_session(on_app=True)))
        for scenario in (
            self.refusal,
            self.publication,
            self.mail,
            self.destination,
            self.delivered,
        ):
            self.bud.bud_start_app()
            self.bud.bud_configure_bloom()
            scenario()

    def remote(self, **changes):
        """One validated remote request."""
        return {**self.parameters.REPORT_REMOTE, **changes}

    def request_row(self, **values):
        """A pending stored report request."""
        p = self.parameters
        return ReportRequest(
            **{
                "bloom_url": p.BLOOM_REPORT_URL,
                "remote_id": 1,
                "run_id": p.REPORT_RUN_ID,
                "project_prefix": p.BLOOM_PUBLISH_PREFIX,
                "requester_name": "Reader",
                "requester_email": p.REPORT_REQUESTER,
                "status": "pending",
                "notified_user_ids": [],
                **values,
            }
        )

    @staticmethod
    def mailing(send):
        """Capture the publisher mails with send."""
        return mock.patch.object(report_service, "send_report_request_email", send)

    @staticmethod
    async def requests(db):
        """Every stored report request, read again."""
        db.expire_all()
        return (await db.scalars(select(ReportRequest))).all()

    async def collection(self, db):
        p = self.parameters
        for index, (role, active) in enumerate(p.REPORT_ROLES):
            db.add(
                User(
                    email=f"publisher-{index}@example.com",
                    full_name=f"Person {index}",
                    role=UserRole(role),
                    hashed_password="unused",
                    is_active=active,
                )
            )
        await db.commit()
        send = mock.MagicMock()
        with bloom(listing(self.remote())), self.mailing(send):
            first = await report_service.sync_report_requests(db)
            second = await report_service.sync_report_requests(db)
        rows = await self.requests(db)
        row = rows[0] if rows else self.request_row(requester_email=None, notified_user_ids=[])
        self.tc_checks["collection"] = {
            "the first collection stores one request": (first, 1),
            "the second collection stores none": (second, 0),
            "the active publishers are mailed": (
                {call.kwargs.get("to_email") for call in send.call_args_list},
                p.REPORT_NOTIFIED,
            ),
            "two mails are sent": (send.call_count, 2),
            "every mail links the run": (
                all(
                    str(call.kwargs.get("review_link")).endswith(p.REPORT_REVIEW_SUFFIX)
                    for call in send.call_args_list
                ),
                True,
            ),
            "one request is stored": (len(rows), 1),
            "the request names its reader": (row.requester_email, p.REPORT_REQUESTER),
            "two publishers are recorded as notified": (len(row.notified_user_ids or []), 2),
        }

    async def retry(self, db):
        db.add(
            User(
                email="publisher@example.com",
                full_name="Publisher",
                role=UserRole.admin,
                hashed_password="unused",
            )
        )
        await db.commit()
        current = self.remote()
        send = mock.MagicMock(side_effect=[MailDeliveryError("offline"), None])
        with bloom(listing(current)), self.mailing(send):
            await report_service.sync_report_requests(db)
            row = ((await self.requests(db)) or [self.request_row(status=None)])[0]
            after_failure = (row.status, bool(row.notified_user_ids))
            await report_service.sync_report_requests(db)
            row = ((await self.requests(db)) or [self.request_row()])[0]
            notified = len(row.notified_user_ids or [])
            current.update(status="delivered")
            await report_service.sync_report_requests(db)
            row = ((await self.requests(db)) or [self.request_row(status=None)])[0]
        self.tc_checks["retry"] = {
            "the request stays pending after the failed mail": (after_failure[0], "pending"),
            "nobody is recorded as notified after the failed mail": (after_failure[1], False),
            "the next collection notifies the publisher": (notified, 1),
            "Bloom's delivery closes the request": (row.status, "delivered"),
            "two mails are attempted": (send.call_count, 2),
        }

    async def checkpoints(self, db):
        for number in range(2):
            db.add(
                User(
                    email=f"checkpoint-{number}@example.com",
                    full_name="Publisher",
                    role=UserRole.admin,
                    hashed_password="unused",
                )
            )
        await db.commit()
        send = mock.MagicMock(side_effect=[None, RuntimeError("delivery interrupted")])
        raised = None
        with bloom(listing(self.remote())), self.mailing(send):
            try:
                await report_service.sync_report_requests(db)
            except RuntimeError as error:
                raised = str(error)
        first = send.call_args_list[0].kwargs.get("to_email") if send.call_args_list else None
        await db.rollback()
        retry = mock.MagicMock()
        with bloom(listing(self.remote())), self.mailing(retry):
            await report_service.sync_report_requests(db)
        again = retry.call_args.kwargs.get("to_email") if retry.call_args else first
        self.tc_checks["checkpoints"] = {
            "the interrupted delivery is raised": ("delivery interrupted" in str(raised), True),
            "the retry mails one publisher": (retry.call_count, 1),
            "the retry skips the publisher already mailed": (again != first, True),
        }

    async def paging(self, db):
        p = self.parameters
        seen = []

        def serve(request):
            after = int(request.url.params.get("after_id", "0"))
            seen.append(after)
            values = [
                self.remote(id=index, status="delivered")
                for index in range(after + 1, min(after + 100, 101) + 1)
            ]
            return httpx.Response(200, json=values)

        with bloom(serve):
            first = await report_service.sync_report_requests(db)
            second = await report_service.sync_report_requests(db)
        self.tc_checks["paging"] = {
            "the first collection pages through every request": (first, 101),
            "the second collection finds none": (second, 0),
            "the polls start after the highest stored id": (seen, p.REPORT_PAGES_SEEN),
        }

    async def removed(self, db):
        p = self.parameters
        db.add(self.request_row(remote_id=3))
        await db.commit()
        send = mock.MagicMock()
        with bloom(lambda request: httpx.Response(200, json=[])), self.mailing(send):
            await report_service.sync_report_requests(db)
        row = ((await self.requests(db)) or [self.request_row(status=None, reason="")])[0]
        self.tc_checks["removed"] = {
            "the request is refused": (row.status, "refused"),
            "the reason says it is gone from Bloom": (
                p.REPORT_NO_LONGER in (row.reason or ""),
                True,
            ),
            "nobody is mailed": (send.call_count, 0),
        }

    def person(self, role):
        """The signed-in tester with another base role."""
        p = self.parameters
        return User(
            id=p.TEST_ADMIN_ID,
            email=p.TEST_ADMIN_EMAIL,
            full_name=p.TEST_ADMIN_NAME,
            hashed_password="x",
            role=UserRole(role),
            is_active=True,
            session_version=1,
        )

    def stored(self, row_id):
        """The stored report request with an id."""
        return (
            self.bud.bud_find_in_app(ReportRequest, id=row_id) or [self.request_row(status=None)]
        )[0]

    def refusal(self):
        p = self.parameters
        row = self.bud.bud_add_to_app(self.request_row())
        path = p.REPORT_REFUSE_PATH.format(row.id)
        self.bud.bud_sign_in_as(self.person("viewer"))
        viewer_list = self.bud.bud_request(p.GET, p.REPORT_REQUESTS_PATH)
        viewer_refusal = self.bud.bud_request(p.POST, path, json={"reason": "No evidence"})
        self.bud.bud_sign_in_as(self.person("developer"))
        listed = body_of(self.bud.bud_request(p.GET, p.REPORT_REQUESTS_PATH))
        blank = self.bud.bud_request(p.POST, path, json={"reason": " "})

        def offline(request):
            raise httpx.ConnectError("offline", request=request)

        with bloom(offline):
            unreachable = self.bud.bud_request(p.POST, path, json={"reason": "Evidence incomplete"})
        after_offline = self.stored(row.id).status
        captured = []

        def accept(request):
            captured.append(request)
            return httpx.Response(200, json={"status": "refused"})

        with bloom(accept):
            accepted = self.bud.bud_request(p.POST, path, json={"reason": "Evidence incomplete"})
        self.tc_checks["refusal"] = {
            "a viewer cannot list requests": (viewer_list.status_code, p.STATUS_FORBIDDEN),
            "a viewer cannot refuse": (viewer_refusal.status_code, p.STATUS_FORBIDDEN),
            "a developer lists the request": (
                (listed if isinstance(listed, list) else [{}])[0].get("run_id"),
                p.REPORT_RUN_ID,
            ),
            "a blank reason is refused": (blank.status_code, p.STATUS_UNPROCESSABLE),
            "an unreachable Bloom is reported": (unreachable.status_code, p.STATUS_BAD_GATEWAY),
            "the request stays pending while Bloom is unreachable": (after_offline, "pending"),
            "the refusal succeeds once Bloom confirms": (accepted.status_code, p.STATUS_OK),
            "the request is refused": (self.stored(row.id).status, "refused"),
            "Bloom is told who refused": (
                p.REPORT_ACTOR in (captured[0].content if captured else b""),
                True,
            ),
        }

    def publication(self):
        p = self.parameters
        run = self.bud.bud_add_run_with_reports()
        for project, remote_id in ((p.BLOOM_PUBLISH_PREFIX, 1), ("ABC", 2)):
            self.bud.bud_add_to_app(
                self.request_row(remote_id=remote_id, run_id=run.id, project_prefix=project)
            )
        path = p.BLOOM_PUBLISH_PATH.format(run.id)
        with mock.patch.object(
            test_runs, "post_to_bloom", mock.AsyncMock(side_effect=httpx.ConnectError("offline"))
        ):
            failed = self.bud.bud_request(p.POST, path)
        after_failure = {row.status for row in self.bud.bud_find_in_app(ReportRequest)}
        answer = {"document_id": 7, "doc_id": "PRJ-RPT-001", "created": True}
        with mock.patch.object(test_runs, "post_to_bloom", mock.AsyncMock(return_value=answer)):
            published = self.bud.bud_request(p.POST, path)
        self.tc_checks["publication"] = {
            "a failed publication is reported": (failed.status_code, p.STATUS_BAD_GATEWAY),
            "every request stays pending after the failure": (after_failure, {"pending"}),
            "the publication succeeds": (published.status_code, p.STATUS_OK),
            "only the request of the run's project is delivered": (
                {row.project_prefix: row.status for row in self.bud.bud_find_in_app(ReportRequest)},
                {p.BLOOM_PUBLISH_PREFIX: "delivered", "ABC": "pending"},
            ),
        }

    def mail(self):
        p = self.parameters
        captured = []
        with mock.patch.object(
            mail_service, "send_email", lambda **values: captured.append(values)
        ):
            mail_service.send_report_request_email(
                to_email="publisher@example.com",
                publisher_name="Publisher",
                requester_name="<Reader>",
                requester_email=p.REPORT_REQUESTER,
                project=p.BLOOM_PUBLISH_PREFIX,
                run_id=str(p.REPORT_RUN_ID),
                review_link=p.REPORT_MAIL_LINK,
            )
        message = (captured or [{"html_body": "", "text_body": ""}])[0]
        html, text = message.get("html_body") or "", message.get("text_body") or ""
        self.tc_checks["mail"] = {
            "the HTML leaves no placeholder": ("${" in html, False),
            "the text leaves no placeholder": ("${" in text, False),
            "the HTML links the run": (f'href="{p.REPORT_MAIL_LINK}"' in html, True),
            "the HTML escapes the reader's name": ("&lt;Reader&gt;" in html, True),
            "the HTML holds no raw reader markup": ("<Reader>" in html, False),
        }

    def destination(self):
        p = self.parameters
        run = self.bud.bud_add_run_with_reports()
        row = self.bud.bud_add_to_app(
            self.request_row(remote_id=7, run_id=run.id, project_prefix="ABC")
        )
        path = p.REPORT_PUBLISH_PATH.format(row.id)
        publish = mock.AsyncMock()
        with mock.patch.object(test_runs, "post_to_bloom", publish):
            refused = self.bud.bud_request(p.POST, path)
        pending = self.stored(row.id)
        status_after_refusal = pending.status
        pending.project_prefix = p.BLOOM_PUBLISH_PREFIX
        self.bud.bud_add_to_app(pending)
        answer = {"document_id": 7, "doc_id": "PRJ-RPT-001", "created": True}
        with mock.patch.object(test_runs, "post_to_bloom", mock.AsyncMock(return_value=answer)):
            published = self.bud.bud_request(p.POST, path)
        self.tc_checks["destination"] = {
            "the publication is refused": (refused.status_code, p.STATUS_CONFLICT),
            "the refusal names the other project": (
                p.REPORT_DIFFERENT_PROJECT in str(body_of(refused).get("detail")),
                True,
            ),
            "nothing is posted to Bloom": (publish.await_count, 0),
            "the request stays pending": (status_after_refusal, "pending"),
            "the matching request is published": (published.status_code, p.STATUS_OK),
            "the request is delivered": (self.stored(row.id).status, "delivered"),
        }

    def delivered(self):
        p = self.parameters
        row = self.bud.bud_add_to_app(self.request_row(remote_id=8))
        answer = httpx.Response(409, json={"detail": "The report has already been delivered"})
        with bloom(lambda request: answer):
            response = self.bud.bud_request(
                p.POST, p.REPORT_REFUSE_PATH.format(row.id), json={"reason": "Too late"}
            )
        events = self.bud.bud_find_in_app(AuditEvent, action=p.REPORT_PUBLISHED_ACTION) or [
            AuditEvent(actor_type=None)
        ]
        self.tc_checks["delivered"] = {
            "the refusal answers": (response.status_code, p.STATUS_OK),
            "the answer says delivered": (body_of(response).get("status"), "delivered"),
            "the request is delivered": (self.stored(row.id).status, "delivered"),
            "the publication is audited as the service": (
                events[0].actor_type,
                p.REPORT_SERVICE_ACTOR,
            ),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ReportRequestsHttpTest().run()
