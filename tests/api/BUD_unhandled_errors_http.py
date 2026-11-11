"""
* @file     ${tests/api/BUD_unhandled_errors_http.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    An unhandled or integrity error still tells the user a reference they can report.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module serves routes that fail on purpose on the started app.
"""

from unittest import mock

import asyncpg
from fastapi import Depends
from fastapi.routing import APIRoute
from sqlalchemy.exc import IntegrityError

from app import main
from app.db import database
from app.db.database import get_db
from app.models import AuditEvent
from tests.api.unhandled_errors_http import UnhandledErrorsHttpBase


def session_dependencies(dependant):
    """Every dependency on get_db below a route's dependant."""
    for sub in dependant.dependencies:
        if sub.call is get_db:
            yield sub
        yield from session_dependencies(sub)


def api_routes(routes):
    """Every API route, those of included routers too."""
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        included = getattr(route, "original_router", None)
        if included is not None:
            yield from api_routes(included.routes)


class FailingCommitSession:
    """A session whose commit is refused with a unique violation."""

    def __init__(self, insert, duplicate):
        self.insert, self.duplicate = insert, duplicate

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def commit(self):
        """Refuse the commit."""
        raise IntegrityError(
            self.insert, {}, asyncpg.exceptions.UniqueViolationError(self.duplicate)
        )

    async def rollback(self):
        """Roll nothing back."""
        return None

    async def close(self):
        """Close nothing."""
        return None


class UnhandledErrorsHttpTest(UnhandledErrorsHttpBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.bud.bud_start_app(signed_in=False)
        self.bud.bud_add_route(p.ERROR_BOOM_PATH, self.boom)
        self.bud.bud_add_route(p.ERROR_CONFLICT_PATH, self.conflict)
        self.bud.bud_add_route(p.ERROR_FK_PATH, self.missing_reference)
        self.bud.bud_add_route(p.ERROR_LATE_PATH, self.late)
        self.tc_boom = self.answer(self.bud.bud_request(p.GET, p.ERROR_BOOM_PATH))
        self.tc_supplied = self.answer(
            self.bud.bud_request(
                p.GET, p.ERROR_BOOM_PATH, headers={p.REQUEST_ID_HEADER: p.ERROR_SUPPLIED_ID}
            )
        )
        self.tc_supplied["events"] = [
            (event.request_id, (event.details or {}).get("status"))
            for event in self.bud.bud_find_in_app(
                AuditEvent, action=p.API_REQUEST_ACTION, request_id=p.ERROR_SUPPLIED_ID
            )
        ]
        self.tc_generated = self.answer(self.bud.bud_request(p.GET, p.ERROR_BOOM_PATH))
        self.tc_conflict = self.answer(self.bud.bud_request(p.GET, p.ERROR_CONFLICT_PATH))
        self.tc_missing_reference = self.answer(self.bud.bud_request(p.GET, p.ERROR_FK_PATH))
        with mock.patch.object(
            database,
            "async_session_maker",
            lambda: FailingCommitSession(p.ERROR_INSERT, p.ERROR_DUPLICATE),
        ):
            self.tc_late = self.answer(
                self.bud.bud_request_without_overrides(p.GET, p.ERROR_LATE_PATH)
            )
        self.bud.bud_remove_routes()
        routes = list(api_routes(main.app.routes))
        self.tc_session_routes = sum(
            1 for route in routes for _ in session_dependencies(route.dependant)
        )
        self.tc_late_routes = sorted(
            {
                f"{sorted(route.methods)} {route.path}"
                for route in routes
                for dependency in session_dependencies(route.dependant)
                if dependency.scope != "function"
            }
        )

    @staticmethod
    def answer(response):
        """The parts of an error answer the steps check."""
        body = (
            response.json()
            if response.headers.get("content-type", "").startswith("application/json")
            else {}
        )
        return {
            "status": response.status_code,
            "reference": response.headers.get("x-request-id", ""),
            "body reference": body.get("request_id"),
            "detail": str(body.get("detail", "")),
            "text": response.text,
        }

    async def boom(self):
        """Fail with an unhandled error."""
        raise RuntimeError(self.parameters.ERROR_BOOM_TEXT)

    async def conflict(self):
        """Lose the race between checking for a row and writing it."""
        p = self.parameters
        raise IntegrityError(
            p.ERROR_INSERT, {}, asyncpg.exceptions.UniqueViolationError(p.ERROR_DUPLICATE)
        )

    async def missing_reference(self):
        """Delete a row another still references."""
        p = self.parameters
        raise IntegrityError(
            p.ERROR_DELETE,
            {},
            asyncpg.exceptions.ForeignKeyViolationError(p.ERROR_STILL_REFERENCED),
        )

    async def late(self, db=Depends(get_db, scope="function")):
        """Answer, leaving the session's commit to fail."""
        return {"ok": True}

    def tearDownClass(self):
        self.bud.bud_remove_routes()
        super().tearDownClass()


if __name__ == "__main__":
    UnhandledErrorsHttpTest().run()
