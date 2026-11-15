"""
* @file     ${tests/api/BUD_auth_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    People sign in, refresh, sign out, edit their profile, change their password and email with real credentials.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests each scenario on a fresh signed-out app with the mail captured and the rate limits off.
"""

import re
from unittest import mock

from app.core.deps import limiter
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.user_token import UserToken, UserTokenPurpose
from app.services import mail_service
from tests.api.auth_api import AuthApiBase


def body_of(response):
    """The JSON answer, or an empty one."""
    try:
        return response.json() or {}
    except ValueError:
        return {}


def type_name(value):
    """The type name of a value."""
    return type(value).__name__


class AuthApiTest(AuthApiBase):

    def setUpClass(self):
        super().setUpClass()
        self.sent = []
        patches = [
            mock.patch.object(limiter, "enabled", False),
            mock.patch.object(mail_service, "send_email", lambda **mail: self.sent.append(mail)),
        ]
        for patch in patches:
            patch.start()
        self.tc_checks = {}
        for scenario in (
            self.login,
            self.login_refusals,
            self.refresh,
            self.logout,
            self.profile,
            self.admin_email_change,
            self.email_change_request,
            self.password_change,
            self.password_reset,
            self.bogus_tokens,
        ):
            scenario()
        for patch in patches:
            patch.stop()

    def fresh(self):
        """A fresh signed-out app with no captured mail."""
        self.bud.bud_start_app(signed_in=False)
        self.sent.clear()

    def account(self, email=None, role="viewer", is_active=True):
        """Store a person with the test password."""
        return self.bud.bud_add_to_app(
            User(
                email=email or self.parameters.AUTH_PERSON,
                full_name="Person",
                hashed_password=get_password_hash(self.parameters.AUTH_PASSWORD),
                role=UserRole(role),
                is_active=is_active,
                session_version=1,
            )
        )

    def log_in(self, email=None, password=None):
        """Sign in and return the answer."""
        p = self.parameters
        return self.bud.bud_log_in(email or p.AUTH_PERSON, password or p.AUTH_PASSWORD)

    @staticmethod
    def bearer(login):
        """The headers that carry a login's access token."""
        return {"Authorization": f"Bearer {body_of(login).get('access_token')}"}

    def cookie(self, response):
        """The refresh token a response sets, or None."""
        match = re.search(
            self.parameters.AUTH_REFRESH_COOKIE, response.headers.get("set-cookie", "")
        )
        return match.group(1) if match else None

    def post(self, path, **kwargs):
        """Post to the started app."""
        return self.bud.bud_request(self.parameters.POST, path, **kwargs)

    def stored(self, user):
        """The stored state of a person."""
        return (self.bud.bud_find_in_app(User, id=user.id) or [User()])[0]

    def refused(self, response, answers=None):
        """The check row of a refused request."""
        return (response.status_code, answers or self.parameters.AUTH_REFUSED, "among")

    def login(self):
        p = self.parameters
        self.fresh()
        self.account()
        response = self.log_in()
        body = body_of(response)
        cookies = response.headers.get("set-cookie", "")
        self.tc_checks["login"] = {
            "the login succeeds": (response.status_code, p.STATUS_OK),
            "an access token is returned": (bool(body.get("access_token")), True),
            "the person is returned": ((body.get("user") or {}).get("email"), p.AUTH_PERSON),
            "the password hash stays out": ("hashed_password" in (body.get("user") or {}), False),
            "a refresh cookie is set": (f"{p.AUTH_REFRESH_NAME}=" in cookies, True),
            "the refresh cookie is HTTP only": ("HttpOnly" in cookies, True),
        }

    def login_refusals(self):
        p = self.parameters
        self.fresh()
        self.account()
        self.account("off@example.com", is_active=False)
        wrong = self.log_in(password="wrong-password")
        unknown = self.log_in("nobody@example.com")
        wrong_short = self.log_in(password="nope")
        ghost = self.log_in("ghost@example.com", "nope")
        off = self.log_in("off@example.com")
        self.tc_checks["login refusals"] = {
            "a wrong password is refused": (wrong.status_code, p.STATUS_UNAUTHORIZED),
            "an unknown address is refused": (unknown.status_code, p.STATUS_UNAUTHORIZED),
            "both refusals share their status": (wrong_short.status_code, ghost.status_code),
            "both refusals share their detail": (
                body_of(wrong_short).get("detail"),
                body_of(ghost).get("detail"),
            ),
            "a deactivated account is refused": (off.status_code, p.STATUS_FORBIDDEN),
        }

    def refresh(self):
        p = self.parameters
        self.fresh()
        self.account()
        login = self.log_in()
        exchanged = self.post(
            p.AUTH_REFRESH_PATH, cookies={p.AUTH_REFRESH_NAME: self.cookie(login)}
        )
        self.fresh()
        self.account()
        login = self.log_in()
        first = self.cookie(login)
        rotation = self.post(p.AUTH_REFRESH_PATH, cookies={p.AUTH_REFRESH_NAME: first})
        self.bud.bud_clear_cookies()
        replay = self.post(p.AUTH_REFRESH_PATH, cookies={p.AUTH_REFRESH_NAME: first})
        self.fresh()
        missing = self.post(p.AUTH_REFRESH_PATH)
        forged = self.post(p.AUTH_REFRESH_PATH, cookies={p.AUTH_REFRESH_NAME: "not-a-real-token"})
        self.tc_checks["refresh"] = {
            "the login succeeds": (login.status_code, p.STATUS_OK),
            "the cookie is exchanged": (exchanged.status_code, p.STATUS_OK),
            "a new access token is returned": (bool(body_of(exchanged).get("access_token")), True),
            "the login sets a refresh token": (bool(first), True),
            "the rotation succeeds": (rotation.status_code, p.STATUS_OK),
            "the token rotates": (self.cookie(rotation) != first, True),
            "the rotated-away token is refused": (replay.status_code, p.STATUS_UNAUTHORIZED),
            "a refresh without a cookie is refused": (missing.status_code, p.STATUS_UNAUTHORIZED),
            "a forged cookie is refused": (forged.status_code, p.STATUS_UNAUTHORIZED),
        }

    def logout(self):
        p = self.parameters
        self.fresh()
        self.account()
        token = self.cookie(self.log_in())
        logout = self.post(p.AUTH_LOGOUT_PATH, cookies={p.AUTH_REFRESH_NAME: token})
        self.bud.bud_clear_cookies()
        reused = self.post(p.AUTH_REFRESH_PATH, cookies={p.AUTH_REFRESH_NAME: token})
        self.fresh()
        anonymous = self.post(p.AUTH_LOGOUT_PATH)
        self.tc_checks["logout"] = {
            "the login sets a refresh token": (bool(token), True),
            "the logout succeeds": (logout.status_code, p.STATUS_OK),
            "the revoked token is refused": (reused.status_code, p.STATUS_UNAUTHORIZED),
            "a logout without a session succeeds": (anonymous.status_code, p.STATUS_OK),
        }

    def profile(self):
        p = self.parameters
        self.fresh()
        anonymous = self.bud.bud_request(p.GET, p.AUTH_ME_PATH)
        self.account()
        headers = self.bearer(self.log_in())
        me = self.bud.bud_request(p.GET, p.AUTH_ME_PATH, headers=headers)
        renamed = self.bud.bud_request(
            p.PUT, p.AUTH_ME_PATH, json={"full_name": "Renamed"}, headers=headers
        )
        self.tc_checks["profile"] = {
            "the profile needs a token": (anonymous.status_code, p.STATUS_UNAUTHORIZED),
            "the profile is read": (me.status_code, p.STATUS_OK),
            "the profile is the signed-in person": (body_of(me).get("email"), p.AUTH_PERSON),
            "the name is changed": (renamed.status_code, p.STATUS_OK),
            "the new name is returned": (body_of(renamed).get("full_name"), "Renamed"),
        }

    def mailed_token(self, index):
        """The token in one captured mail, or None."""
        mail = self.sent[index] if len(self.sent) > index else {"text_body": ""}
        match = re.search(self.parameters.AUTH_MAILED_TOKEN, mail.get("text_body") or "")
        return match.group(1) if match else None

    def admin_email_change(self):
        p = self.parameters
        self.fresh()
        admin = self.account("admin-before@example.com", role="admin")
        headers = self.bearer(self.log_in(admin.email))
        response = self.post(
            p.AUTH_ME_EMAIL_PATH,
            json={"current_password": p.AUTH_PASSWORD, "new_email": "admin-after@example.com"},
            headers=headers,
        )
        requested = self.stored(admin)
        tokens = self.bud.bud_find_in_app(
            UserToken, user_id=admin.id, purpose=UserTokenPurpose.email_change
        )
        token = tokens[0] if tokens else UserToken()
        first_mail = self.sent[0] if self.sent else {}
        current = self.post(p.AUTH_CONFIRM_PATH, json={"token": self.mailed_token(0)})
        authorized = self.stored(admin)
        mails_after_authorization = len(self.sent)
        second_mail = self.sent[1] if len(self.sent) > 1 else {}
        new = self.post(p.AUTH_CONFIRM_PATH, json={"token": self.mailed_token(1)})
        moved = self.stored(admin)
        self.tc_checks["admin email change"] = {
            "the change is requested": (response.status_code, p.STATUS_OK),
            "the answer points at the current mailbox": (
                "current email" in str(body_of(response).get("message")).lower(),
                True,
            ),
            "the login keeps the old address": (requested.email, "admin-before@example.com"),
            "the new address waits": (requested.pending_email, "admin-after@example.com"),
            "the change waits for the current mailbox": (
                requested.email_change_status,
                "awaiting_current_confirmation",
            ),
            "one change token is stored": (len(tokens), 1),
            "the administrator issued the token": (token.created_by_user_id, admin.id),
            "the token targets the new address": (token.target_email, "admin-after@example.com"),
            "a mail is sent": (bool(self.sent), True),
            "the first mail goes to the current address": (
                first_mail.get("to_email"),
                "admin-before@example.com",
            ),
            "the first mail asks for authorization": (
                "authorize" in str(first_mail.get("subject")).lower(),
                True,
            ),
            "the first mail carries a token": (type_name(self.mailed_token(0)), "str"),
            "the current mailbox confirms": (current.status_code, p.STATUS_OK),
            "the answer points at the new mailbox": (
                "new email" in str(body_of(current).get("message")).lower(),
                True,
            ),
            "the login still keeps the old address": (authorized.email, "admin-before@example.com"),
            "the new address still waits": (authorized.pending_email, "admin-after@example.com"),
            "the change waits for the new mailbox": (
                authorized.email_change_status,
                "awaiting_confirmation",
            ),
            "a second mail is sent": (mails_after_authorization, 2),
            "the second mail goes to the new address": (
                second_mail.get("to_email"),
                "admin-after@example.com",
            ),
            "the second mail carries a token": (type_name(self.mailed_token(1)), "str"),
            "the new mailbox confirms": (new.status_code, p.STATUS_OK),
            "the login moves to the new address": (moved.email, "admin-after@example.com"),
            "nothing waits any more": (type_name(moved.pending_email), p.NONE_TYPE),
            "no change status is left": (type_name(moved.email_change_status), p.NONE_TYPE),
            "the move signs the sessions out": (moved.session_version, 2),
        }

    def email_change_request(self):
        p = self.parameters
        self.fresh()
        viewer = self.account("viewer-before@example.com")
        headers = self.bearer(self.log_in(viewer.email))
        response = self.post(
            p.AUTH_ME_EMAIL_PATH,
            json={"current_password": p.AUTH_PASSWORD, "new_email": "viewer-after@example.com"},
            headers=headers,
        )
        self.tc_checks["email change request"] = {
            "the change is requested": (response.status_code, p.STATUS_OK),
            "the change waits for approval": (self.stored(viewer).email_change_status, "requested"),
            "no mail is sent": (list(self.sent), []),
        }

    def password_change(self):
        p = self.parameters
        self.fresh()
        user = self.account()
        headers = self.bearer(self.log_in())
        wrong = self.bud.bud_request(
            p.PUT,
            p.AUTH_ME_PASSWORD_PATH,
            json={"current_password": "not-it", "new_password": "another-long-password"},
            headers=headers,
        )
        short = self.bud.bud_request(
            p.PUT,
            p.AUTH_ME_PASSWORD_PATH,
            json={"current_password": p.AUTH_PASSWORD, "new_password": "short"},
            headers=headers,
        )
        changed = self.bud.bud_request(
            p.PUT,
            p.AUTH_ME_PASSWORD_PATH,
            json={"current_password": p.AUTH_PASSWORD, "new_password": "a-brand-new-long-password"},
            headers=headers,
        )
        stale = self.bud.bud_request(p.GET, p.AUTH_ME_PATH, headers=headers)
        self.tc_checks["password change"] = {
            "a wrong current password is refused": self.refused(wrong, p.AUTH_WRONG_PASSWORD),
            "a short new password is refused": (short.status_code, p.STATUS_UNPROCESSABLE),
            "the password is changed": (changed.status_code, p.STATUS_OK),
            "the session version moves on": ((self.stored(user).session_version or 0) > 1, True),
            "the old token is refused": (stale.status_code, p.STATUS_UNAUTHORIZED),
        }

    def password_reset(self):
        p = self.parameters
        self.fresh()
        self.account()
        known = self.post(p.AUTH_FORGOT_PATH, json={"email": p.AUTH_PERSON})
        unknown = self.post(p.AUTH_FORGOT_PATH, json={"email": "ghost@example.com"})
        tokens = self.bud.bud_find_in_app(UserToken, purpose=UserTokenPurpose.password_reset)
        bogus = self.post(
            p.AUTH_RESET_PATH, json={"token": "nonsense", "new_password": "a-long-enough-password"}
        )
        self.tc_checks["password reset"] = {
            "both answers share their status": (known.status_code, unknown.status_code),
            "both answers share their body": (body_of(known), body_of(unknown)),
            "one reset token is issued for the real account": (len(tokens), 1),
            "a bogus reset token is refused": self.refused(bogus),
        }

    def bogus_tokens(self):
        p = self.parameters
        self.fresh()
        info = self.post(p.AUTH_INVITE_INFO_PATH, json={"token": "nope"})
        accept = self.post(
            p.AUTH_ACCEPT_PATH, json={"token": "nope", "password": "a-long-enough-password"}
        )
        verify = self.post(p.AUTH_VERIFY_PATH, json={"token": "nope"})
        confirm = self.post(p.AUTH_CONFIRM_PATH, json={"token": "nope"})
        checks = {"an unknown invitation is answered": self.refused(info, p.AUTH_INFO_ANSWERS)}
        if info.status_code == p.STATUS_OK:
            checks["an unknown invitation is invalid"] = (body_of(info).get("valid"), False)
        checks.update(
            {
                "an unknown invitation is not accepted": self.refused(accept),
                "a bogus verification is refused": self.refused(verify),
                "a bogus email confirmation is refused": self.refused(confirm),
            }
        )
        self.tc_checks["bogus tokens"] = checks

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    AuthApiTest().run()
