"""
* @file     ${tests/sec/BUD_cli_auth_sec.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    CLI sign-in accepts only loopback callbacks and matching proof keys, codes and accounts, and audits refusals.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests each scenario on a fresh signed-out app with code sign-in turned on.
"""

import base64
import hashlib
import json
from datetime import datetime, timedelta
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import text

from app.api.auth import get_current_active_entity
from app.core.config import settings
from app.core.deps import limiter
from app.core.security import create_access_token
from app.db import database as db_module
from app.models import AuditEvent, Runner, User, UserRole, UserToken, UserTokenPurpose
from app.services import cli_auth
from tests.sec.cli_auth_sec import CliAuthSecBase


def body_of(response):
    """The JSON answer, or an empty one."""
    try:
        return response.json() or {}
    except ValueError:
        return {}


def type_name(value):
    """The type name of a value."""
    return type(value).__name__


def challenge_of(verifier):
    """The S256 proof-key challenge of a verifier."""
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")


def code_for(challenge):
    """The XXXX-XXXX request code of a challenge, computed independently of the app."""
    letters = base64.b32encode(hashlib.sha256(challenge.encode()).digest()[:5]).decode()
    return f"{letters[:4]}-{letters[4:]}"


class CliAuthSecTest(CliAuthSecBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.challenge = challenge_of(p.CLI_VERIFIER)
        self.request_code = code_for(self.challenge)
        self.start_body = {**p.CLI_START, "code_challenge": self.challenge}
        patch = mock.patch.object(settings, "CLI_CODE_MODE_ENABLED", True)
        patch.start()
        self.tc_checks = {}
        self.callbacks()
        self.fields()
        self.confirmation()
        for failure in p.CLI_EXCHANGE_FAILURES:
            self.exchange_failure(failure)
        self.verifiers()
        self.refresh_rows()
        for condition in p.CLI_BAD_BINDINGS:
            self.binding(condition)
        self.station()
        for path in p.CLI_LIMITED_ROUTES:
            self.limited(path)
        self.deny()
        self.deny_bodies()
        self.mismatch()
        self.check_limits()
        self.approved_elsewhere()
        patch.stop()

    def fresh(self):
        """A fresh signed-out app."""
        self.bud.bud_start_app(signed_in=False)

    def account(self):
        """Store a viewer and return them with the headers of their token."""
        user = self.bud.bud_add_to_app(
            User(
                email="security-cli@example.com",
                full_name="CLI user",
                hashed_password="unused",
                role=UserRole.viewer,
                is_active=True,
                session_version=1,
            )
        )
        token = create_access_token({"sub": str(user.id), "type": "user", "ver": 1})
        return user, {"Authorization": f"Bearer {token}"}

    def post(self, path, **kwargs):
        """Post to the started app."""
        return self.bud.bud_request(self.parameters.POST, path, **kwargs)

    def start(self, **changes):
        """Start a CLI sign-in and return the session id."""
        return body_of(
            self.post(self.parameters.CLI_START_PATH, json={**self.start_body, **changes})
        ).get("session_id")

    def approve_body(self, session_id, code=None):
        """An approval body carrying the request code the client shows."""
        return {"session_id": session_id, "request_code": code or self.request_code}

    def events(self, action, outcome=None):
        """The audit events of an action, in order."""
        where = {"action": action, **({"outcome": outcome} if outcome else {})}
        return sorted(self.bud.bud_find_in_app(AuditEvent, **where), key=lambda event: event.id)

    def run_sql(self, statement, **values):
        """Run one statement on the started app's database."""
        session = self.bud.bud_open_session(on_app=True)

        async def run():
            result = await session.execute(text(statement), values)
            rows = result.scalars().all() if result.returns_rows else []
            await session.commit()
            return rows

        return self.bud.bud_await(run())

    def entity_status(self, token):
        """The status code get_current_active_entity refuses a token with, or the entity it returns."""
        session = self.bud.bud_open_session(on_app=True)

        async def resolve():
            try:
                return await get_current_active_entity(token=token, db=session)
            except HTTPException as error:
                return error.status_code

        return self.bud.bud_await(resolve())

    def callbacks(self):
        p = self.parameters
        self.fresh()
        checks = {}
        for uri in p.CLI_BAD_CALLBACKS:
            limiter.reset()
            response = self.post(
                p.CLI_START_PATH, json={**self.start_body, "mode": "callback", "redirect_uri": uri}
            )
            checks[f"{uri} is refused"] = (response.status_code, p.STATUS_UNPROCESSABLE)
        for host in p.CLI_LOOPBACK_HOSTS:
            limiter.reset()
            response = self.post(
                p.CLI_START_PATH,
                json={
                    **self.start_body,
                    "mode": "callback",
                    "redirect_uri": f"http://{host}:1234/callback",
                },
            )
            checks[f"{host} is accepted"] = (response.status_code, p.STATUS_OK)
        self.tc_checks["callbacks"] = checks

    def fields(self):
        p = self.parameters
        self.fresh()
        checks = {}
        for changes in p.CLI_BAD_FIELDS:
            limiter.reset()
            checks[f"{changes} is refused"] = (
                self.post(p.CLI_START_PATH, json={**self.start_body, **changes}).status_code,
                p.STATUS_UNPROCESSABLE,
            )
        self.tc_checks["fields"] = checks

    def confirmation(self):
        p = self.parameters
        self.fresh()
        user, headers = self.account()
        session_id = self.start()
        anonymous_read = self.bud.bud_request(p.GET, p.CLI_SESSION_PATH.format(session_id))
        anonymous_approval = self.post(p.CLI_APPROVE_PATH, json=self.approve_body(session_id))
        first = self.post(p.CLI_APPROVE_PATH, json=self.approve_body(session_id), headers=headers)
        second = self.post(p.CLI_APPROVE_PATH, json=self.approve_body(session_id), headers=headers)
        failures = self.events("auth.cli_approve", "failure")
        event = failures[0] if failures else AuditEvent(details={})
        later = self.bud.bud_request(p.GET, p.CLI_SESSION_PATH.format(session_id), headers=headers)
        self.tc_checks["confirmation"] = {
            "a signed-out read is refused": (anonymous_read.status_code, p.STATUS_UNAUTHORIZED),
            "a signed-out approval is refused": (
                anonymous_approval.status_code,
                p.STATUS_UNAUTHORIZED,
            ),
            "the person approves": (first.status_code, p.STATUS_OK),
            "a second approval is refused": (second.status_code, p.CLI_REFUSED, "among"),
            "the second answer carries no exchange code": (
                "exchange_code" in body_of(second),
                False,
            ),
            "one failed approval is audited": (len(failures), 1),
            "the audit says the request was not pending": (
                event.details,
                {"reason": "not_pending"},
            ),
            "the audit names the person": (event.actor_user_id, user.id),
            "the audit names the request": (event.target_id, session_id),
            "the audit leaves the exchange code out": (
                str(body_of(first).get("exchange_code")) in json.dumps(event.details),
                False,
            ),
            "the approved request is no longer readable": (
                later.status_code,
                p.CLI_REFUSED,
                "among",
            ),
        }

    def exchange_failure(self, failure):
        p = self.parameters
        self.fresh()
        user, headers = self.account()
        session_id = self.start()
        code = "not-approved"
        if failure != "pending":
            code = body_of(
                self.post(p.CLI_APPROVE_PATH, json=self.approve_body(session_id), headers=headers)
            ).get("exchange_code")
        if failure == "expired":
            self.run_sql(
                "UPDATE cli_auth_sessions SET expires_at = :expiry",
                expiry=datetime.utcnow() - timedelta(seconds=1),
            )
        if failure in ("disabled", "version"):
            stored = self.bud.bud_find_in_app(User, id=user.id)[0]
            if failure == "disabled":
                stored.is_active = False
            else:
                stored.session_version += 1
            self.bud.bud_add_to_app(stored)
        response = self.post(
            p.CLI_EXCHANGE_PATH,
            json={
                "session_id": session_id,
                "code": "wrong" if failure == "bad_code" else code,
                "code_verifier": "w" * 43 if failure == "bad_verifier" else p.CLI_VERIFIER,
            },
        )
        failures = self.events("auth.cli_exchange", "failure")
        event = failures[0] if failures else AuditEvent(details={})
        details = json.dumps(event.details)
        self.tc_checks[f"exchange {failure}"] = {
            "the exchange is refused": (response.status_code, p.CLI_REFUSED, "among"),
            "no access token is returned": ("access_token" in body_of(response), False),
            "no token is stored": (len(self.bud.bud_find_in_app(UserToken)), 0),
            "no successful exchange is audited": (
                len(self.events("auth.cli_exchange", "success")),
                0,
            ),
            "one failed exchange is audited": (len(failures), 1),
            "the audit names the reason": (
                event.details,
                {"reason": p.CLI_EXCHANGE_FAILURES[failure]},
            ),
            "the audit names no actor": (event.actor_type, "anonymous"),
            "the audit names the request": (event.target_id, session_id),
            "the audit leaves the code out": (str(code) in details, False),
            "the audit leaves the verifier out": (p.CLI_VERIFIER in details, False),
        }

    def verifiers(self):
        p = self.parameters
        self.fresh()
        self.tc_checks["verifiers"] = {
            f"a verifier of {len(verifier)} characters like {verifier[:3]} is refused": (
                self.post(
                    p.CLI_EXCHANGE_PATH,
                    json={
                        "session_id": p.CLI_UNKNOWN_SESSION,
                        "code": "code",
                        "code_verifier": verifier,
                    },
                ).status_code,
                p.STATUS_UNPROCESSABLE,
            )
            for verifier in p.CLI_BAD_VERIFIERS
        }

    def refresh_rows(self):
        p = self.parameters
        self.fresh()
        user, _ = self.account()
        checks = {}
        for refresh_id in p.CLI_BAD_REFRESH_IDS:
            token = create_access_token(
                {"sub": str(user.id), "type": "user", "ver": 1, "cli_refresh_id": refresh_id}
            )
            found = self.entity_status(token)
            checks[f"a refresh id of {refresh_id!r} is refused"] = (
                found if isinstance(found, int) else type_name(found),
                p.STATUS_UNAUTHORIZED,
            )
        self.tc_checks["refresh rows"] = checks

    def binding(self, condition):
        p = self.parameters
        self.fresh()
        user, _ = self.account()
        owner = user
        if condition == "wrong_user":
            owner = self.bud.bud_add_to_app(
                User(
                    email="other-cli@example.com",
                    full_name="Other",
                    hashed_password="unused",
                    role=UserRole.viewer,
                    is_active=True,
                )
            )
        row = self.bud.bud_add_to_app(
            UserToken(
                user_id=owner.id,
                purpose=(
                    UserTokenPurpose.invite
                    if condition == "wrong_purpose"
                    else UserTokenPurpose.refresh
                ),
                token_hash="a" * 64,
                expires_at=datetime.utcnow()
                + timedelta(minutes=-1 if condition == "expired" else 1),
                used_at=datetime.utcnow() if condition == "used" else None,
            )
        )
        token = create_access_token(
            {"sub": str(user.id), "type": "user", "ver": 1, "cli_refresh_id": row.id}
        )
        found = self.entity_status(token)
        self.tc_checks[f"binding {condition}"] = {
            "the token is refused": (
                found if isinstance(found, int) else type_name(found),
                p.STATUS_UNAUTHORIZED,
            )
        }

    def station(self):
        p = self.parameters
        self.fresh()
        session = self.bud.bud_open_session(on_app=True)

        async def resolve():
            runner = Runner(
                account=p.CLI_STATION, password_hash="unused", token="station-token", is_active=True
            )
            session.add(runner)
            await session.commit()
            token = create_access_token({"sub": runner.account, "type": "runner"})
            try:
                return await get_current_active_entity(token=token, db=session) is runner
            except HTTPException:
                return False

        self.tc_checks["station"] = {
            "the station token resolves to the station": (self.bud.bud_await(resolve()), True)
        }

    def limited(self, path):
        p = self.parameters
        self.fresh()
        body = {
            "start": self.start_body,
            "exchange": {
                "session_id": p.CLI_UNKNOWN_SESSION,
                "code": "invalid",
                "code_verifier": p.CLI_VERIFIER,
            },
            "refresh": {"refresh_token": "invalid"},
        }[path]
        statuses = [
            self.post(p.CLI_ROUTE_PATH.format(path), json=body).status_code for _ in range(31)
        ]
        self.tc_checks[f"limited {path}"] = {
            "the route answers too many requests": (p.STATUS_TOO_MANY in statuses, True),
            "the limiter stays enabled": (limiter.enabled, True),
        }

    def deny(self):
        p = self.parameters
        checks = {}
        station_token = create_access_token({"sub": p.CLI_STATION, "type": "runner"})
        for mode in ("callback", "code"):
            self.fresh()
            _, headers = self.account()
            changes = (
                {"mode": "callback", "redirect_uri": "http://127.0.0.1:1234/callback"}
                if mode == "callback"
                else {}
            )
            session_id = self.start(**changes)
            anonymous = self.post(p.CLI_DENY_PATH, json={"session_id": session_id})
            as_station = self.post(
                p.CLI_DENY_PATH,
                json={"session_id": session_id},
                headers={"Authorization": f"Bearer {station_token}"},
            )
            stored = self.run_sql("SELECT id FROM cli_auth_sessions")
            kept = self.bud.bud_request(
                p.GET, p.CLI_SESSION_PATH.format(session_id), headers=headers
            )
            checks[f"{mode}: a signed-out deny is refused"] = (
                anonymous.status_code,
                p.STATUS_UNAUTHORIZED,
            )
            checks[f"{mode}: a station deny is refused"] = (
                as_station.status_code,
                p.CLI_STATION_REFUSED,
                "among",
            )
            checks[f"{mode}: the request is kept"] = (stored, [str(session_id).replace("-", "")])
            checks[f"{mode}: the person still reads the request"] = (kept.status_code, p.STATUS_OK)
        self.tc_checks["deny"] = checks

    def deny_bodies(self):
        p = self.parameters
        self.fresh()
        _, headers = self.account()
        checks = {
            f"the body {body} is refused": (
                self.post(p.CLI_DENY_PATH, json=body, headers=headers).status_code,
                p.STATUS_UNPROCESSABLE,
            )
            for body in p.CLI_DENY_BODIES
        }
        self.fresh()
        _, headers = self.account()
        statuses = {
            self.post(
                p.CLI_DENY_PATH, json={"session_id": p.CLI_UNKNOWN_SESSION}, headers=headers
            ).status_code
            for _ in range(31)
        }
        checks["deny is answered every time without a rate limit"] = (
            statuses,
            {p.STATUS_BAD_REQUEST},
        )
        self.tc_checks["deny bodies"] = checks

    def mismatch(self):
        p = self.parameters
        self.fresh()
        user, headers = self.account()
        session_id = self.start()
        wrong = self.approve_body(session_id, p.CLI_WRONG_CODE)
        right = self.approve_body(session_id)
        unknown = self.approve_body(p.CLI_UNKNOWN_SESSION, p.CLI_WRONG_CODE)
        wrong_check = self.post(p.CLI_CHECK_PATH, json=wrong, headers=headers)
        wrong_approval = self.post(p.CLI_APPROVE_PATH, json=wrong, headers=headers)
        right_check = self.post(p.CLI_CHECK_PATH, json=right, headers=headers)
        unknown_check = self.post(p.CLI_CHECK_PATH, json=unknown, headers=headers)
        mismatches = [
            (event.outcome, event.actor_user_id, event.target_type, event.target_id, event.details)
            for event in self.events("auth.cli_code_mismatch")
        ]
        approval = self.post(p.CLI_APPROVE_PATH, json=right, headers=headers)
        self.tc_checks["mismatch"] = {
            "a wrong code is refused on check": (wrong_check.status_code, p.STATUS_BAD_REQUEST),
            "a wrong code is refused on approval": (
                wrong_approval.status_code,
                p.STATUS_BAD_REQUEST,
            ),
            "the right code passes the check": (right_check.status_code, p.STATUS_NO_CONTENT),
            "an unknown request is refused on check": (
                unknown_check.status_code,
                p.STATUS_BAD_REQUEST,
            ),
            "both mismatches are audited": (
                mismatches,
                [
                    (
                        "failure",
                        user.id,
                        "cli_auth_session",
                        session_id,
                        {"reason": "request_code_mismatch"},
                    )
                ]
                * 2,
            ),
            "the right code is approved": (approval.status_code, p.STATUS_OK),
        }

    def check_limits(self):
        p = self.parameters
        checks = {}
        for path, limit in p.CLI_CHECK_LIMITS.items():
            self.fresh()
            _, headers = self.account()
            body = self.approve_body(p.CLI_UNKNOWN_SESSION)
            statuses = [
                self.post(p.CLI_ROUTE_PATH.format(path), json=body, headers=headers).status_code
                for _ in range(limit + 1)
            ]
            checks[f"{path} answers within its limit"] = (
                set(statuses[:-1]),
                {p.STATUS_BAD_REQUEST},
            )
            checks[f"{path} refuses past its limit"] = (statuses[-1], p.STATUS_TOO_MANY)
        self.tc_checks["check limits"] = checks

    def approved_elsewhere(self):
        p = self.parameters
        self.fresh()
        user, headers = self.account()
        session_id = self.start()
        original = cli_auth.check_request_code

        async def approved_after_check(db, checked_id, typed):
            checked = await original(db, checked_id, typed)
            async with db_module.async_session_maker() as other:
                await other.execute(
                    text(
                        "UPDATE cli_auth_sessions SET user_id = :user_id, exchange_code_hash = 'approved-elsewhere' WHERE id = :id"
                    ),
                    {"user_id": user.id, "id": str(session_id).replace("-", "")},
                )
                await other.commit()
            return checked

        with mock.patch.object(cli_auth, "check_request_code", approved_after_check):
            refused = self.post(
                p.CLI_APPROVE_PATH, json=self.approve_body(session_id), headers=headers
            )
        failures = self.events("auth.cli_approve", "failure")
        self.tc_checks["approved elsewhere"] = {
            "the approval is refused": (refused.status_code, p.STATUS_BAD_REQUEST),
            "one failed approval is audited": (len(failures), 1),
            "the audit says the request was not pending": (
                (failures[0].details if failures else None),
                {"reason": "not_pending"},
            ),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    CliAuthSecTest().run()
