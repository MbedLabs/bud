"""
* @file     ${tests/api/BUD_cli_auth.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    CLI sign-in gives the approving person's own access, rotates and revokes it, and obeys the code mode switch.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests each scenario on a fresh signed-out app holding a viewer whose group gives settings.view.
"""

import base64
import hashlib
import json
import os
from datetime import datetime, timedelta
from unittest import mock
from urllib.parse import parse_qs, urlsplit

from app.core import config
from app.core.config import settings
from app.core.security import create_access_token, decode_access_token, get_password_hash
from app.models import AuditEvent, User, UserRole, UserToken, UserTokenPurpose
from app.models.access import AccessGroup, AccessGroupMember, Policy
from app.services import cli_auth, token_service
from tests.api.cli_auth import CliAuthBase


def body_of(response):
    """The JSON answer, or an empty one."""
    try:
        return response.json() or {}
    except ValueError:
        return {}


def challenge_of(verifier):
    """The S256 challenge of a verifier."""
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")


def code_for(challenge):
    """The XXXX-XXXX request code of a challenge, computed independently of the app."""
    letters = base64.b32encode(hashlib.sha256(challenge.encode()).digest()[:5]).decode()
    return f"{letters[:4]}-{letters[4:]}"


def moment(text, cut_zone=True):
    """The naive time a UTC timestamp names, or the first day of 2000 when it names none."""
    value = str(text or "")
    try:
        if cut_zone:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        return datetime.fromisoformat(value[:-1])
    except ValueError:
        return datetime(2000, 1, 1)


def code_mode(enabled):
    """Turn code sign-in on or off."""
    return mock.patch.object(settings, "CLI_CODE_MODE_ENABLED", enabled)


class CliAuthTest(CliAuthBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.verifier = p.CLI_VERIFIER
        self.challenge = challenge_of(self.verifier)
        self.request_code = code_for(self.challenge)
        patch = code_mode(True)
        patch.start()
        self.tc_checks = {}
        scenarios = [
            ("link", self.link),
            ("issue callback", lambda: self.issue("callback")),
            ("issue code", lambda: self.issue("code")),
            ("refresh", self.refresh),
            ("revoke all", self.revoke_all),
            ("browser refresh", self.browser_refresh),
            ("password change", self.password_change),
            ("session version", self.session_version),
            ("purge", self.purge),
            ("failed refresh", self.failed_refresh),
            ("deactivated refresh", self.deactivated_refresh),
            ("any refresh", self.any_refresh),
            ("request time", self.request_time),
            ("off start", self.off_start),
            ("off lookup", self.off_lookup),
            ("off exchange", self.off_exchange),
            ("off missing", self.off_missing),
            ("off callback", self.off_callback),
            ("deny callback", self.deny_callback),
            ("deny code", self.deny_code),
            ("deny off", self.deny_off),
            ("deny refused", self.deny_refused),
            ("check accepted", self.check_accepted),
            ("check refused", self.check_refused),
            ("check not pending", self.check_not_pending),
            ("check needs", self.check_needs),
            ("approve code", self.approve_code),
        ]
        for name, scenario in scenarios:
            self.fresh()
            checks = scenario()
            if self.helper_statuses:
                checks["every start and approval succeeds"] = (
                    set(self.helper_statuses),
                    {p.STATUS_OK},
                )
            self.tc_checks[name] = checks
        self.tc_checks["setting"] = self.setting()
        self.tc_checks["rfc vector"] = self.rfc_vector()
        patch.stop()

    def fresh(self, with_user=True):
        """A fresh signed-out app holding the viewer."""
        self.bud.bud_start_app(signed_in=False)
        self.helper_statuses = []
        if with_user:
            self.user = self.bud.bud_add_to_app(
                User(
                    email="cli-user@example.com",
                    full_name="CLI User",
                    hashed_password=get_password_hash(self.parameters.CLI_PASSWORD),
                    role=UserRole.viewer,
                    is_active=True,
                    session_version=1,
                )
            )
            policy = self.bud.bud_add_to_app(
                Policy(name="CLI settings view", permissions={"settings": ["view"]})
            )
            group = self.bud.bud_add_to_app(AccessGroup(name="CLI permission test"))
            self.bud.bud_run_sql(
                "INSERT INTO access_group_policies (group_id, policy_id) VALUES (:group_id, :policy_id)",
                group_id=group.id,
                policy_id=policy.id,
            )
            self.bud.bud_add_to_app(AccessGroupMember(group_id=group.id, user_id=self.user.id))

    def bearer(self, version=None):
        """The browser bearer header of the viewer."""
        token = create_access_token({"sub": str(self.user.id), "type": "user", "ver": version or 1})
        return {"Authorization": f"Bearer {token}"}

    def post(self, path, **kwargs):
        """Post to the started app."""
        return self.bud.bud_request(self.parameters.POST, path, **kwargs)

    def get(self, path, **kwargs):
        """Read from the started app."""
        return self.bud.bud_request(self.parameters.GET, path, **kwargs)

    def start(self, mode="code", **overrides):
        """Start an authorization and return its answer."""
        p = self.parameters
        data = {
            "client_name": "Terminal",
            "mode": mode,
            "code_challenge": self.challenge,
            "state": "client-state",
        }
        if mode == "callback":
            data["redirect_uri"] = p.CLI_CALLBACK
        response = self.post(p.CLI_START_PATH, json={**data, **overrides})
        self.helper_statuses.append(response.status_code)
        return body_of(response)

    def approve(self, pending, code=None):
        """Approve a pending client as the viewer and return the answer."""
        p = self.parameters
        response = self.post(
            p.CLI_APPROVE_PATH,
            json={
                "session_id": pending.get("session_id"),
                "request_code": code or self.request_code,
            },
            headers=self.bearer(),
        )
        self.helper_statuses.append(response.status_code)
        return body_of(response)

    def exchange(self, pending, code, verifier=None):
        """Present a one-time code and its verifier."""
        return self.post(
            self.parameters.CLI_EXCHANGE_PATH,
            json={
                "session_id": pending.get("session_id"),
                "code": code,
                "code_verifier": verifier or self.verifier,
            },
        )

    def tokens(self):
        """The tokens of a code-mode sign-in of the viewer."""
        pending = self.start()
        return body_of(self.exchange(pending, self.approve(pending).get("exchange_code")))

    def me(self, access_token):
        """The status of a profile read with an access token."""
        return self.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {access_token}"}
        ).status_code

    def session(self, session_id, headers=None):
        """Read a pending session as the viewer."""
        return self.get(
            self.parameters.CLI_SESSION_PATH.format(session_id), headers=headers or self.bearer()
        )

    def session_ids(self):
        """The stored session ids."""
        return set(self.bud.bud_run_sql("SELECT id FROM cli_auth_sessions"))

    def failures(self, action):
        """The failure events of an action, in order."""
        return sorted(
            self.bud.bud_find_in_app(AuditEvent, action=action, outcome="failure"),
            key=lambda e: e.id,
        )

    def expire(self, session_id=None):
        """Expire one stored session, or all of them."""
        expiry = datetime.utcnow() - timedelta(seconds=1)
        if session_id:
            self.bud.bud_run_sql(
                "UPDATE cli_auth_sessions SET expires_at = :expiry WHERE id = :id",
                expiry=expiry,
                id=session_id.replace("-", ""),
            )
        else:
            self.bud.bud_run_sql("UPDATE cli_auth_sessions SET expires_at = :expiry", expiry=expiry)

    def link(self):
        with mock.patch.object(settings, "APP_BASE_URL", "https://bud.example.test/api"):
            pending = self.start()
        return {
            "the link is the interface path": (
                pending.get("authorize_url"),
                f"/auth/cli?session_id={pending.get('session_id')}",
            )
        }

    def issue(self, mode):
        p = self.parameters
        pending = self.start(mode)
        link = urlsplit(pending.get("authorize_url", ""))
        expiry = moment(pending.get("expires_at"))
        metadata = self.session(pending.get("session_id"))
        approved = self.approve(pending)
        checks = {
            "the expiry is in UTC": (str(pending.get("expires_at")).endswith("Z"), True),
            "the link is the sign-in page": (link.path, "/auth/cli"),
            "the link names the session only": (
                parse_qs(link.query),
                {"session_id": [pending.get("session_id")]},
            ),
            "the request lives ten minutes": (
                timedelta(minutes=9) < expiry - datetime.utcnow() <= timedelta(minutes=10),
                True,
            ),
            "the request is read": (metadata.status_code, p.STATUS_OK),
            "the request names the client": (body_of(metadata).get("client_name"), "Terminal"),
            "the request is not consumed": (body_of(metadata).get("consumed"), False),
            "the request shows its fields only": (set(body_of(metadata)), p.CLI_SESSION_FIELDS),
        }
        if mode == "callback":
            callback = urlsplit(approved.get("redirect_to", ""))
            query = parse_qs(callback.query)
            code = (query.get("code") or [""])[0]
            checks["the callback is the loopback"] = (
                (callback.scheme, callback.netloc, callback.path),
                ("http", "127.0.0.1:41234", "/callback"),
            )
            checks["the callback carries the state"] = (query.get("state"), ["client-state"])
            checks["the callback keeps its query"] = (query.get("client"), ["terminal"])
        else:
            code = approved.get("exchange_code") or ""
            checks["the approval keeps the expiry"] = (
                approved.get("expires_at"),
                pending.get("expires_at"),
            )
        stored = self.bud.bud_run_sql(
            "SELECT exchange_code_hash FROM cli_auth_sessions WHERE id = :id",
            id=str(pending.get("session_id")).replace("-", ""),
        )
        result = self.exchange(pending, code)
        tokens = body_of(result)
        original = body_of(self.get("/api/auth/me", headers=self.bearer()))
        claims = decode_access_token(tokens.get("access_token", "")) or {}
        rows = (
            self.bud.bud_find_in_app(UserToken, id=claims.get("cli_refresh_id"))
            if isinstance(claims.get("cli_refresh_id"), int)
            else []
        )
        row = rows[0] if rows else UserToken()
        again = self.exchange(pending, code)
        events = (
            sorted(
                self.bud.bud_find_in_app(AuditEvent, action="auth.cli_exchange"), key=lambda e: e.id
            )
            + [AuditEvent(details={})] * 2
        )
        audit = json.dumps([event.details for event in events[:2]])
        checks.update(
            {
                "only the code's hash is stored": (
                    stored,
                    [hashlib.sha256(code.encode()).hexdigest()],
                ),
                "the exchange succeeds": (result.status_code, p.STATUS_OK),
                "the exchange answers the token fields": (set(tokens), p.CLI_TOKEN_FIELDS),
                "the token is a bearer": (tokens.get("token_type"), "bearer"),
                "the person is the approving viewer": (tokens.get("user"), original),
                "the role is kept": (original.get("role"), "viewer"),
                "the group permission is kept": (
                    "settings.view" in (original.get("permissions") or []),
                    True,
                ),
                "no extra permission is given": (
                    "settings.edit" in (original.get("permissions") or []),
                    False,
                ),
                "the token names the person": (
                    (claims.get("sub"), claims.get("type"), claims.get("ver")),
                    (str(self.user.id), "user", 1),
                ),
                "the token names its refresh row": (
                    isinstance(claims.get("cli_refresh_id"), int),
                    True,
                ),
                "the refresh row is a refresh token": (row.purpose, UserTokenPurpose.refresh),
                "the refresh row holds the token's hash": (
                    row.token_hash,
                    hashlib.sha256(tokens.get("refresh_token", "").encode()).hexdigest(),
                ),
                "no cookie is set": ("set-cookie" in result.headers, False),
                "the access token signs in": (self.me(tokens.get("access_token", "")), p.STATUS_OK),
                "the code works once": (again.status_code in (400, 401), True),
                "the exchanges are audited": (
                    [event.outcome for event in events[:2]],
                    ["success", "failure"],
                ),
                "the success names the viewer": (events[0].actor_user_id, self.user.id),
                "the failure names its reason": (
                    events[1].details,
                    {"reason": "expired_or_consumed"},
                ),
            }
        )
        for label, secret in (
            ("code", code),
            ("verifier", self.verifier),
            ("access token", tokens.get("access_token", "-")),
            ("refresh token", tokens.get("refresh_token", "-")),
        ):
            checks[f"the audit leaves the {label} out"] = (secret in audit, False)
        return checks

    def refresh(self):
        p = self.parameters
        tokens = self.tokens()
        rotated = self.post(p.CLI_REFRESH_PATH, json={"refresh_token": tokens.get("refresh_token")})
        replacement = body_of(rotated)
        return {
            "the refresh succeeds": (rotated.status_code, p.STATUS_OK),
            "the refresh token rotates": (
                replacement.get("refresh_token") != tokens.get("refresh_token"),
                True,
            ),
            "the access token rotates": (
                replacement.get("access_token") != tokens.get("access_token"),
                True,
            ),
            "the person is kept": (replacement.get("user"), tokens.get("user")),
            "the previous access token is retired": (
                self.me(tokens.get("access_token", "")),
                p.STATUS_UNAUTHORIZED,
            ),
            "the new access token signs in": (
                self.me(replacement.get("access_token", "")),
                p.STATUS_OK,
            ),
            "the previous refresh token is refused": (
                self.post(
                    p.CLI_REFRESH_PATH, json={"refresh_token": tokens.get("refresh_token")}
                ).status_code,
                p.STATUS_UNAUTHORIZED,
            ),
            "no cookie is set": ("set-cookie" in rotated.headers, False),
        }

    def revoke_all(self):
        p = self.parameters
        tokens = self.tokens()
        session = self.bud.bud_open_session(on_app=True)

        async def revoke():
            await token_service.invalidate_all_refresh_tokens(session, self.user.id)
            await session.commit()

        self.bud.bud_await(revoke())
        return {
            "the access token is refused": (
                self.me(tokens.get("access_token", "")),
                p.STATUS_UNAUTHORIZED,
            ),
            "the refresh token is refused": (
                self.post(
                    p.CLI_REFRESH_PATH, json={"refresh_token": tokens.get("refresh_token")}
                ).status_code,
                p.STATUS_UNAUTHORIZED,
            ),
            "the browser token still signs in": (
                self.get("/api/auth/me", headers=self.bearer()).status_code,
                p.STATUS_OK,
            ),
        }

    def browser_refresh(self):
        p = self.parameters
        login = self.bud.bud_log_in(self.user.email, p.CLI_PASSWORD)
        cookie = "bud_refresh_token=" in login.headers.get("set-cookie", "")
        response = self.post("/api/auth/refresh")
        return {
            "the login succeeds": (login.status_code, p.STATUS_OK),
            "the browser token names no refresh row": (
                "cli_refresh_id"
                in (decode_access_token(body_of(login).get("access_token", "")) or {}),
                False,
            ),
            "the browser keeps its refresh cookie": (cookie, True),
            "the cookie refresh succeeds": (response.status_code, p.STATUS_OK),
            "the cookie refresh answers no refresh token": (
                "refresh_token" in body_of(response),
                False,
            ),
            "the refreshed token names no refresh row": (
                "cli_refresh_id"
                in (decode_access_token(body_of(response).get("access_token", "")) or {}),
                False,
            ),
        }

    def password_change(self):
        p = self.parameters
        tokens = self.tokens()
        changed = self.bud.bud_request(
            p.PUT,
            "/api/auth/me/password",
            headers=self.bearer(),
            json={"current_password": p.CLI_PASSWORD, "new_password": p.CLI_NEW_PASSWORD},
        )
        return {
            "the password is changed": (changed.status_code, p.STATUS_OK),
            "the access token is refused": (
                self.me(tokens.get("access_token", "")),
                p.STATUS_UNAUTHORIZED,
            ),
            "the refresh token is refused": (
                self.post(
                    p.CLI_REFRESH_PATH, json={"refresh_token": tokens.get("refresh_token")}
                ).status_code,
                p.STATUS_UNAUTHORIZED,
            ),
        }

    def session_version(self):
        p = self.parameters
        tokens = self.tokens()
        stored = self.bud.bud_find_in_app(User, id=self.user.id)[0]
        stored.session_version += 1
        self.bud.bud_add_to_app(stored)
        return {
            "the access token is refused": (
                self.me(tokens.get("access_token", "")),
                p.STATUS_UNAUTHORIZED,
            )
        }

    def purge(self):
        p = self.parameters
        expired, exchanged, approved = self.start(), self.start(), self.start()
        result = self.exchange(exchanged, self.approve(exchanged).get("exchange_code"))
        self.approve(approved)
        self.expire(expired.get("session_id"))
        before = len(self.session_ids())
        fresh = self.start()
        return {
            "the exchange succeeds": (result.status_code, p.STATUS_OK),
            "three requests are stored": (before, 3),
            "only live requests are kept": (
                self.session_ids(),
                {
                    str(approved.get("session_id")).replace("-", ""),
                    str(fresh.get("session_id")).replace("-", ""),
                },
            ),
        }

    def failed_refresh(self):
        p = self.parameters
        tokens = self.tokens()
        first = self.post(p.CLI_REFRESH_PATH, json={"refresh_token": tokens.get("refresh_token")})
        replay = self.post(p.CLI_REFRESH_PATH, json={"refresh_token": tokens.get("refresh_token")})
        failures = self.failures("auth.cli_refresh")
        event = failures[0] if failures else AuditEvent(details={})
        return {
            "the refresh succeeds": (first.status_code, p.STATUS_OK),
            "the replay is refused": (replay.status_code, p.STATUS_UNAUTHORIZED),
            "the refusal is generic": (body_of(replay), {"detail": "Invalid or expired session"}),
            "one failure is audited": (len(failures), 1),
            "the failure names its reason": (event.details, {"reason": "invalid_token"}),
            "the failure names no actor": (event.actor_type, "anonymous"),
            "the failure leaves the token out": (
                str(tokens.get("refresh_token")) in json.dumps(event.details),
                False,
            ),
        }

    def deactivated_refresh(self):
        p = self.parameters
        tokens = self.tokens()
        stored = self.bud.bud_find_in_app(User, id=self.user.id)[0]
        stored.is_active = False
        self.bud.bud_add_to_app(stored)
        response = self.post(
            p.CLI_REFRESH_PATH, json={"refresh_token": tokens.get("refresh_token")}
        )
        failures = self.failures("auth.cli_refresh")
        rows = self.bud.bud_find_in_app(
            UserToken,
            token_hash=hashlib.sha256(str(tokens.get("refresh_token")).encode()).hexdigest(),
        )
        return {
            "the refresh is refused": (response.status_code, p.STATUS_UNAUTHORIZED),
            "one failure is audited": (len(failures), 1),
            "the failure names its reason": (
                (failures[0].details if failures else None),
                {"reason": "inactive_or_missing_user"},
            ),
            "the token is stored": (len(rows), 1),
            "the token is left unused": ((rows[0].used_at if rows else "missing") is None, True),
        }

    def any_refresh(self):
        p = self.parameters
        login = self.bud.bud_log_in(self.user.email, p.CLI_PASSWORD)
        browser = (
            (login.headers.get("set-cookie", "").split("bud_refresh_token=")[-1].split(";")[0])
            if "bud_refresh_token=" in login.headers.get("set-cookie", "")
            else ""
        )
        rotated = self.post(p.CLI_REFRESH_PATH, json={"refresh_token": browser})
        claims = decode_access_token(body_of(rotated).get("access_token", "")) or {}
        return {
            "the login succeeds": (login.status_code, p.STATUS_OK),
            "the browser token is rotated by the CLI": (rotated.status_code, p.STATUS_OK),
            "the new token names its refresh row": (
                isinstance(claims.get("cli_refresh_id"), int),
                True,
            ),
            "the browser cookie is consumed": (
                self.post("/api/auth/refresh").status_code,
                p.STATUS_UNAUTHORIZED,
            ),
        }

    def setting(self):
        names = ("BUD_CLI_CODE_MODE_ENABLED", "CLI_CODE_MODE_ENABLED")
        checks = {
            "the default is off": (
                config.Settings.model_fields["CLI_CODE_MODE_ENABLED"].default,
                False,
            )
        }
        with mock.patch.dict(os.environ):
            for name in names:
                os.environ.pop(name, None)
            checks["the built setting is off"] = (
                config.Settings(_env_file=None).CLI_CODE_MODE_ENABLED,
                False,
            )
            for name in names:
                os.environ[name] = "true"
                checks[f"{name} turns it on"] = (
                    config.Settings(_env_file=None).CLI_CODE_MODE_ENABLED,
                    True,
                )
                del os.environ[name]
        return checks

    def rfc_vector(self):
        p = self.parameters
        return {
            "the challenge matches the RFC 7636 vector": (
                challenge_of(p.CLI_RFC_VERIFIER),
                p.CLI_RFC_CHALLENGE,
            ),
            "the request code matches the shared vector": (
                cli_auth.request_code(p.CLI_RFC_CHALLENGE),
                p.CLI_RFC_CODE,
            ),
            "the letters match the vector": (
                base64.b32encode(
                    hashlib.sha256(p.CLI_RFC_CHALLENGE.encode()).digest()[:5]
                ).decode(),
                "BUUZWHVV",
            ),
        }

    def request_time(self):
        p = self.parameters
        checks = {}
        for mode in p.CLI_MODES:
            if checks:
                self.fresh()
            before = datetime.utcnow()
            pending = self.start(mode, code_challenge=p.CLI_RFC_CHALLENGE)
            metadata = body_of(self.session(pending.get("session_id")))
            created_text = str(metadata.get("created_at", "2000-01-01T00:00:00Z"))
            created = moment(created_text, cut_zone=False)
            expires = moment(metadata.get("expires_at"), cut_zone=False)
            checks[f"{mode}: the request code is not shown"] = ("request_code" in metadata, False)
            checks[f"{mode}: the time is in UTC"] = (created_text.endswith("Z"), True)
            checks[f"{mode}: the time is now"] = (
                before - timedelta(seconds=5)
                <= created
                <= datetime.utcnow() + timedelta(seconds=5),
                True,
            )
            checks[f"{mode}: the request lives ten minutes"] = (
                timedelta(minutes=9) < expires - created <= timedelta(minutes=10, seconds=5),
                True,
            )
        return checks

    def off_start(self):
        p = self.parameters
        with code_mode(False):
            response = self.post(
                p.CLI_START_PATH,
                json={
                    "client_name": "Terminal",
                    "mode": "code",
                    "code_challenge": self.challenge,
                    "state": "client-state",
                },
            )
        return {
            "start is refused": (response.status_code, p.STATUS_FORBIDDEN),
            "the refusal names the switch": (body_of(response), {"detail": p.CLI_CODE_OFF}),
            "nothing is stored": (self.session_ids(), set()),
        }

    def off_lookup(self):
        p = self.parameters
        checks = {}
        for approved in (False, True):
            if checks:
                self.fresh()
            pending = self.start()
            session_id = pending.get("session_id")
            if approved:
                self.approve(pending)
            with code_mode(False):
                lookup = self.session(session_id)
                refused = self.post(
                    p.CLI_APPROVE_PATH,
                    json={"session_id": session_id, "request_code": self.request_code},
                    headers=self.bearer(),
                )
            failures = self.failures("auth.cli_approve")
            event = failures[0] if failures else AuditEvent(details={})
            stored = self.bud.bud_run_sql(
                "SELECT user_id FROM cli_auth_sessions WHERE id = :id",
                id=str(session_id).replace("-", ""),
            )
            label = "approved" if approved else "pending"
            checks.update(
                {
                    f"{label}: the lookup is refused": (lookup.status_code, p.STATUS_FORBIDDEN),
                    f"{label}: the lookup names the switch": (
                        body_of(lookup),
                        {"detail": p.CLI_CODE_OFF},
                    ),
                    f"{label}: the approval is refused": (refused.status_code, p.STATUS_FORBIDDEN),
                    f"{label}: the approval names the switch": (
                        body_of(refused),
                        {"detail": p.CLI_CODE_OFF},
                    ),
                    f"{label}: one failure is audited": (len(failures), 1),
                    f"{label}: the failure names the switch": (
                        event.details,
                        {"reason": "code_mode_disabled"},
                    ),
                    f"{label}: the failure names the viewer": (event.actor_user_id, self.user.id),
                    f"{label}: the failure names the request": (event.target_id, session_id),
                    f"{label}: the request keeps its approver": (
                        stored,
                        [self.user.id if approved else None],
                    ),
                }
            )
        return checks

    def off_exchange(self):
        p = self.parameters
        pending = self.start()
        code = self.approve(pending).get("exchange_code")
        with code_mode(False):
            response = self.exchange(pending, code)
        failures = self.failures("auth.cli_exchange")
        event = failures[0] if failures else AuditEvent(details={})
        tokens = len(self.bud.bud_find_in_app(UserToken))
        later = self.exchange(pending, code)
        return {
            "the exchange is refused": (response.status_code, p.STATUS_BAD_REQUEST),
            "the refusal is generic": (body_of(response), {"detail": p.CLI_INVALID}),
            "one failure is audited": (len(failures), 1),
            "the failure names the switch": (event.details, {"reason": "code_mode_disabled"}),
            "the failure names no actor": (event.actor_type, "anonymous"),
            "the failure names the request": (event.target_id, pending.get("session_id")),
            "no token is stored": (tokens, 0),
            "the exchange works once code sign-in is back": (later.status_code, p.STATUS_OK),
        }

    def off_missing(self):
        p = self.parameters
        with code_mode(False):
            lookup = self.session(p.CLI_UNKNOWN_SESSION)
            refused = self.post(
                p.CLI_APPROVE_PATH,
                json={"session_id": p.CLI_UNKNOWN_SESSION, "request_code": self.request_code},
                headers=self.bearer(),
            )
        return {
            "the lookup is invalid": (lookup.status_code, p.STATUS_BAD_REQUEST),
            "the lookup refusal is generic": (body_of(lookup), {"detail": p.CLI_INVALID}),
            "the approval is invalid": (refused.status_code, p.STATUS_BAD_REQUEST),
        }

    def off_callback(self):
        p = self.parameters
        with code_mode(False):
            pending = self.start("callback")
            lookup = self.session(pending.get("session_id"))
            approved = self.approve(pending)
            code = (parse_qs(urlsplit(approved.get("redirect_to", "")).query).get("code") or [""])[
                0
            ]
            exchanged = self.exchange(pending, code)
        return {
            "the lookup works": (lookup.status_code, p.STATUS_OK),
            "the request is in callback mode": (body_of(lookup).get("mode"), "callback"),
            "the exchange works": (exchanged.status_code, p.STATUS_OK),
        }

    def deny(self, pending):
        """Deny a pending client as the viewer."""
        return self.post(
            self.parameters.CLI_DENY_PATH,
            json={"session_id": pending.get("session_id")},
            headers=self.bearer(),
        )

    def denied_and_gone(self, pending):
        """The checks that a denied request is audited and found nowhere."""
        p = self.parameters
        session_id = pending.get("session_id")
        events = self.bud.bud_find_in_app(AuditEvent, action="auth.cli_deny")
        return {
            "the request is deleted": (
                str(session_id).replace("-", "") in self.session_ids(),
                False,
            ),
            "the denial is audited": (
                [(e.outcome, e.actor_user_id, e.target_type, e.target_id) for e in events],
                [("success", self.user.id, "cli_auth_session", session_id)],
            ),
            "the lookup finds nothing": (
                self.session(session_id).status_code,
                p.STATUS_BAD_REQUEST,
            ),
            "the approval finds nothing": (
                self.post(
                    p.CLI_APPROVE_PATH,
                    json={"session_id": session_id, "request_code": self.request_code},
                    headers=self.bearer(),
                ).status_code,
                p.STATUS_BAD_REQUEST,
            ),
            "the exchange finds nothing": (
                self.exchange(pending, "any-code").status_code,
                p.STATUS_BAD_REQUEST,
            ),
        }

    def deny_callback(self):
        p = self.parameters
        pending = self.start("callback")
        response = self.deny(pending)
        target = urlsplit(body_of(response).get("redirect_to", ""))
        return {
            "the denial is answered": (response.status_code, p.STATUS_OK),
            "the answer is not stored": (response.headers.get("cache-control"), "no-store"),
            "the answer names the redirect only": (set(body_of(response)), {"redirect_to"}),
            "the redirect is the loopback": (
                (target.scheme, target.netloc, target.path),
                ("http", "127.0.0.1:41234", "/callback"),
            ),
            "the redirect says access was denied": (
                parse_qs(target.query),
                {"client": ["terminal"], "error": ["access_denied"], "state": ["client-state"]},
            ),
            **self.denied_and_gone(pending),
        }

    def deny_code(self):
        p = self.parameters
        pending = self.start()
        response = self.deny(pending)
        return {
            "the denial is answered": (response.status_code, p.STATUS_OK),
            "the answer is empty": (body_of(response), {}),
            **self.denied_and_gone(pending),
        }

    def deny_off(self):
        p = self.parameters
        pending = self.start()
        with code_mode(False):
            response = self.deny(pending)
            gone = self.denied_and_gone(pending)
        return {
            "the denial is answered": (response.status_code, p.STATUS_OK),
            "the answer is empty": (body_of(response), {}),
            **gone,
        }

    def deny_refused(self):
        p = self.parameters
        checks = {}
        for state in p.CLI_DENY_STATES:
            if checks:
                self.fresh()
            pending = self.start("callback")
            if state == "approved":
                self.approve(pending)
            if state == "denied":
                checks[f"{state}: the first denial is answered"] = (
                    self.deny(pending).status_code,
                    p.STATUS_OK,
                )
            if state == "expired":
                self.expire()
            if state == "unknown":
                pending = {"session_id": p.CLI_UNKNOWN_SESSION}
            response = self.deny(pending)
            failures = self.failures("auth.cli_deny")
            event = failures[0] if failures else AuditEvent(details={})
            checks[f"{state}: the denial is refused"] = (response.status_code, p.STATUS_BAD_REQUEST)
            checks[f"{state}: the refusal is generic"] = (
                body_of(response),
                {"detail": p.CLI_INVALID},
            )
            checks[f"{state}: one failure is audited"] = (len(failures), 1)
            checks[f"{state}: the failure says not pending"] = (
                event.details,
                {"reason": "not_pending"},
            )
            checks[f"{state}: the failure names the viewer"] = (event.actor_user_id, self.user.id)
            checks[f"{state}: the failure names the request"] = (
                event.target_id,
                pending.get("session_id"),
            )
            if state in ("approved", "expired"):
                checks[f"{state}: the request is kept"] = (
                    str(pending.get("session_id")).replace("-", "") in self.session_ids(),
                    True,
                )
        return checks

    def code_check(self, session_id, typed, headers=None):
        """Post one request code check."""
        return self.post(
            self.parameters.CLI_CHECK_PATH,
            json={"session_id": session_id, "request_code": typed},
            headers=self.bearer() if headers is None else headers,
        )

    def check_accepted(self):
        p = self.parameters
        checks = {}
        for typed in p.CLI_GOOD_TYPED:
            if checks:
                self.fresh()
            pending = self.start(code_challenge=p.CLI_RFC_CHALLENGE)
            response = self.code_check(pending.get("session_id"), typed)
            checks[f"{typed!r} passes"] = (response.status_code, p.STATUS_NO_CONTENT)
            checks[f"{typed!r}: the answer is not stored"] = (
                response.headers.get("Cache-Control"),
                "no-store",
            )
            checks[f"{typed!r}: the request stays readable"] = (
                self.session(pending.get("session_id")).status_code,
                p.STATUS_OK,
            )
        return checks

    def check_refused(self):
        p = self.parameters
        checks = {}
        for typed in p.CLI_BAD_TYPED:
            if checks:
                self.fresh()
            pending = self.start(code_challenge=p.CLI_RFC_CHALLENGE)
            response = self.code_check(pending.get("session_id"), typed)
            checks[f"{typed!r} is refused"] = (
                (response.status_code, body_of(response)),
                (p.STATUS_BAD_REQUEST, {"detail": p.CLI_INVALID}),
            )
            checks[f"{typed!r}: the request stays readable"] = (
                self.session(pending.get("session_id")).status_code,
                p.STATUS_OK,
            )
        return checks

    def check_not_pending(self):
        p = self.parameters
        expired, approved, consumed = self.start(), self.start(), self.start()
        self.approve(approved)
        code = self.approve(consumed).get("exchange_code")
        exchanged = self.exchange(consumed, code).status_code
        self.expire(expired.get("session_id"))
        checks = {"the consumed request is exchanged": (exchanged, p.STATUS_OK)}
        for label, session_id in (
            ("missing", p.CLI_UNKNOWN_SESSION),
            ("expired", expired.get("session_id")),
            ("approved", approved.get("session_id")),
            ("consumed", consumed.get("session_id")),
        ):
            response = self.code_check(session_id, self.request_code)
            checks[f"the {label} request is refused"] = (
                (response.status_code, body_of(response)),
                (p.STATUS_BAD_REQUEST, {"detail": p.CLI_INVALID}),
            )
        checks["no mismatch is audited"] = (self.failures("auth.cli_code_mismatch"), [])
        return checks

    def check_needs(self):
        p = self.parameters
        pending = self.start()
        unsigned = self.code_check(pending.get("session_id"), self.request_code, headers={})
        with code_mode(False):
            refused = self.code_check(pending.get("session_id"), self.request_code)
        return {
            "a signed-out check is refused": (unsigned.status_code, p.STATUS_UNAUTHORIZED),
            "a check with code sign-in off is refused": (
                (refused.status_code, body_of(refused)),
                (p.STATUS_FORBIDDEN, {"detail": p.CLI_CODE_OFF}),
            ),
        }

    def approve_code(self):
        p = self.parameters
        pending = self.start()
        session_id = pending.get("session_id")
        missing = self.post(
            p.CLI_APPROVE_PATH, json={"session_id": session_id}, headers=self.bearer()
        )
        wrong = self.post(
            p.CLI_APPROVE_PATH,
            json={"session_id": session_id, "request_code": "AAAA-AAAA"},
            headers=self.bearer(),
        )
        lookup = self.session(session_id)
        code = self.approve(pending).get("exchange_code")
        return {
            "an approval without a code is refused": (missing.status_code, p.STATUS_UNPROCESSABLE),
            "an approval with a wrong code is refused": (
                (wrong.status_code, body_of(wrong)),
                (p.STATUS_BAD_REQUEST, {"detail": p.CLI_INVALID}),
            ),
            "the request stays readable": (lookup.status_code, p.STATUS_OK),
            "the matching code is exchanged": (
                self.exchange(pending, code).status_code,
                p.STATUS_OK,
            ),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    CliAuthTest().run()
