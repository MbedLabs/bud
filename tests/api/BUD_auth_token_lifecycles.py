"""
* @file     ${tests/api/BUD_auth_token_lifecycles.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Invitation, password reset and email change links work once, in their fragment, and only while valid.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests each flow on a fresh app database with the mail captured and the rate limits off.
"""

import re
from unittest import mock

from app.core.deps import limiter
from app.core.security import get_password_hash, verify_password
from app.models.user import User, UserRole
from app.models.user_token import UserToken, UserTokenPurpose
from app.services import mail_service
from tests.api.auth_token_lifecycles import AuthTokenLifecyclesBase


def body_of(response):
    """The JSON answer, or an empty one."""
    try:
        return response.json() or {}
    except ValueError:
        return {}


def type_name(value):
    """The type name of a value."""
    return type(value).__name__


class AuthTokenLifecyclesTest(AuthTokenLifecyclesBase):

    def setUpClass(self):
        super().setUpClass()
        self.mailbox = []
        patches = [
            mock.patch.object(limiter, "enabled", False),
            mock.patch.object(mail_service, "send_email", self.capture),
        ]
        for patch in patches:
            patch.start()
        self.tc_checks = {}
        for scenario in (
            self.invite_link,
            self.invite_info,
            self.accept,
            self.accept_twice,
            self.revoke,
            self.revoked_password,
            self.resend,
            self.reset,
            self.sign_out,
            self.reset_twice,
            self.weak_password,
            self.unknown_address,
            self.email_change,
            self.confirmation_address,
            self.cancelled_change,
            self.confirm_twice,
        ):
            self.bud.bud_start_app()
            self.mailbox.clear()
            scenario()
        for patch in patches:
            patch.stop()

    def capture(self, *, to_email, subject, text_body, html_body=None):
        """Keep one outbound message."""
        self.mailbox.append(
            {"to": to_email, "subject": subject, "text": text_body, "html": html_body or ""}
        )

    def token(self, text):
        """The token in the fragment of a link or message, or None."""
        match = re.search(self.parameters.LIFECYCLE_TOKEN, text or "")
        return match.group(1) if match else None

    def mailed_token(self):
        """The token of the latest message, or None."""
        latest = (self.mailbox or [{"text": "", "html": ""}])[-1]
        return self.token(latest["text"] + latest["html"])

    def invite(self, email, name):
        """Invite one person as the administrator."""
        p = self.parameters
        return self.bud.bud_request(
            p.POST, p.LIFECYCLE_INVITE_PATH, json={"email": email, "full_name": name}
        )

    def signed_out(self, path, body):
        """Post as a signed-out visitor."""
        return self.bud.bud_request_without_overrides(self.parameters.POST, path, json=body)

    def accept_invite(self, token, password=None):
        """Accept an invitation as a signed-out visitor."""
        p = self.parameters
        return self.signed_out(
            p.LIFECYCLE_ACCEPT_PATH,
            {"token": token, "password": password or p.LIFECYCLE_NEW_PASSWORD},
        )

    def account(self, email):
        """Store an active viewer with the test password."""
        return self.bud.bud_add_to_app(
            User(
                email=email,
                full_name="Person",
                hashed_password=get_password_hash(self.parameters.LIFECYCLE_PASSWORD),
                role=UserRole.viewer,
                is_active=True,
                session_version=1,
            )
        )

    def stored(self, **where):
        """The stored person matching the values, or an empty one."""
        return (self.bud.bud_find_in_app(User, **where) or [User(hashed_password="")])[0]

    def has_password(self, email, password):
        """Whether the stored person's password is the given one."""
        hashed = self.stored(email=email).hashed_password
        return bool(hashed) and verify_password(password, hashed)

    def refused(self, response):
        """The check row of a refused one-time link."""
        return (response.status_code, self.parameters.LIFECYCLE_REFUSED, "among")

    def forgot(self, email):
        """Ask for a password reset as a signed-out visitor."""
        return self.signed_out(self.parameters.LIFECYCLE_FORGOT_PATH, {"email": email})

    def reset_password(self, token, password):
        """Reset a password as a signed-out visitor."""
        return self.signed_out(
            self.parameters.LIFECYCLE_RESET_PATH, {"token": token, "new_password": password}
        )

    def change_email(self, user, new_email):
        """Start an email change as the administrator."""
        p = self.parameters
        return self.bud.bud_request(
            p.POST, p.LIFECYCLE_USER_PATH.format(user.id) + "/email", json={"new_email": new_email}
        )

    def confirm(self, token):
        """Confirm an email change as a signed-out visitor."""
        return self.signed_out(self.parameters.LIFECYCLE_CONFIRM_PATH, {"token": token})

    def invite_link(self):
        p = self.parameters
        response = self.invite("new@example.com", "New")
        link = str(body_of(response).get("invite_link"))
        self.tc_checks["invite link"] = {
            "the invitation is created": (response.status_code, p.STATUS_CREATED),
            "the link carries the token in its fragment": ("#token=" in link, True),
            "the link carries no token in its query": ("?token=" in link, False),
        }

    def invite_info(self):
        p = self.parameters
        token = self.token(body_of(self.invite("info@example.com", "Info")).get("invite_link"))
        info = self.signed_out(p.LIFECYCLE_INVITE_INFO_PATH, {"token": token})
        body = body_of(info)
        self.tc_checks["invite info"] = {
            "the link carries a token": (type_name(token), p.LIFECYCLE_STRING),
            "the invitation is described": (info.status_code, p.STATUS_OK),
            "the invitation is valid": (body.get("valid"), True),
            "the invitation names its address": (body.get("email"), "info@example.com"),
            "the invitation has not expired": (body.get("expired"), False),
        }

    def accept(self):
        p = self.parameters
        token = self.token(body_of(self.invite("accept@example.com", "Accept")).get("invite_link"))
        accepted = self.accept_invite(token)
        self.tc_checks["accept"] = {
            "the link carries a token": (type_name(token), p.LIFECYCLE_STRING),
            "the invitation is accepted": (accepted.status_code, p.STATUS_OK),
            "the chosen password is stored": (
                self.has_password("accept@example.com", p.LIFECYCLE_NEW_PASSWORD),
                True,
            ),
        }

    def accept_twice(self):
        p = self.parameters
        token = self.token(body_of(self.invite("once@example.com", "Once")).get("invite_link"))
        first = self.accept_invite(token)
        second = self.accept_invite(token, "yet-another-password")
        self.tc_checks["accept twice"] = {
            "the link carries a token": (type_name(token), p.LIFECYCLE_STRING),
            "the first acceptance succeeds": (first.status_code, p.STATUS_OK),
            "the second acceptance is refused": self.refused(second),
        }

    def revoke(self):
        p = self.parameters
        created = body_of(self.invite("revoked@example.com", "Revoked"))
        token = self.token(created.get("invite_link"))
        user_id = created.get("user", {}).get("id")
        revoked = self.bud.bud_request(
            p.POST, p.LIFECYCLE_USER_PATH.format(user_id) + "/revoke-invite"
        )
        accepted = self.accept_invite(token)
        self.tc_checks["revoke"] = {
            "the link carries a token": (type_name(token), p.LIFECYCLE_STRING),
            "the invitation is revoked": (revoked.status_code, p.STATUS_OK),
            "the revoked token is refused": self.refused(accepted),
        }

    def revoked_password(self):
        p = self.parameters
        created = body_of(self.invite("victim@example.com", "Victim"))
        token = self.token(created.get("invite_link"))
        user_id = created.get("user", {}).get("id")
        self.bud.bud_request(p.POST, p.LIFECYCLE_USER_PATH.format(user_id) + "/revoke-invite")
        self.accept_invite(token, "attacker-chosen-password")
        activated = self.bud.bud_request(
            p.PATCH, p.LIFECYCLE_USER_PATH.format(user_id), json={"is_active": True}
        )
        login = self.bud.bud_request_without_overrides(
            p.POST,
            p.LOGIN_PATH,
            json={"email": "victim@example.com", "password": "attacker-chosen-password"},
        )
        self.tc_checks["revoked password"] = {
            "the link carries a token": (type_name(token), p.LIFECYCLE_STRING),
            "the administrator activates the person": (activated.status_code, p.STATUS_OK),
            "the password sent with the revoked token signs nobody in": (
                login.status_code,
                p.STATUS_UNAUTHORIZED,
            ),
        }

    def resend(self):
        p = self.parameters
        created = body_of(self.invite("resend@example.com", "Resend"))
        first = self.token(created.get("invite_link"))
        resent = self.bud.bud_request(
            p.POST,
            p.LIFECYCLE_USER_PATH.format(created.get("user", {}).get("id")) + "/resend-invite",
        )
        second = self.token(body_of(resent).get("invite_link"))
        self.tc_checks["resend"] = {
            "the link carries a token": (type_name(first), p.LIFECYCLE_STRING),
            "the invitation is resent": (resent.status_code, p.STATUS_OK),
            "the new link carries a token": (type_name(second), p.LIFECYCLE_STRING),
            "the new token differs": (second != first, True),
        }

    def reset(self):
        p = self.parameters
        self.account("reset@example.com")
        self.forgot("reset@example.com")
        token = self.mailed_token()
        response = self.reset_password(token, p.LIFECYCLE_NEW_PASSWORD)
        self.tc_checks["reset"] = {
            "a token is mailed": (type_name(token), p.LIFECYCLE_STRING),
            "the password is reset": (response.status_code, p.STATUS_OK),
            "the new password is stored": (
                self.has_password("reset@example.com", p.LIFECYCLE_NEW_PASSWORD),
                True,
            ),
        }

    def sign_out(self):
        p = self.parameters
        before = self.account("signout@example.com").session_version
        self.forgot("signout@example.com")
        token = self.mailed_token()
        self.reset_password(token, p.LIFECYCLE_NEW_PASSWORD)
        after = self.stored(email="signout@example.com").session_version or 0
        self.tc_checks["sign out"] = {
            "a token is mailed": (type_name(token), p.LIFECYCLE_STRING),
            "the session version moves on": (after > before, True),
        }

    def reset_twice(self):
        p = self.parameters
        self.account("single@example.com")
        self.forgot("single@example.com")
        token = self.mailed_token()
        first = self.reset_password(token, p.LIFECYCLE_NEW_PASSWORD)
        second = self.reset_password(token, "a-third-long-password")
        self.tc_checks["reset twice"] = {
            "a token is mailed": (type_name(token), p.LIFECYCLE_STRING),
            "the first reset succeeds": (first.status_code, p.STATUS_OK),
            "the second reset is refused": self.refused(second),
        }

    def weak_password(self):
        p = self.parameters
        self.account("weak@example.com")
        self.forgot("weak@example.com")
        token = self.mailed_token()
        response = self.reset_password(token, "short")
        self.tc_checks["weak password"] = {
            "a token is mailed": (type_name(token), p.LIFECYCLE_STRING),
            "a short password is refused": (response.status_code, p.STATUS_UNPROCESSABLE),
        }

    def unknown_address(self):
        self.forgot("ghost@example.com")
        tokens = self.bud.bud_find_in_app(UserToken, purpose=UserTokenPurpose.password_reset)
        self.tc_checks["unknown address"] = {
            "no reset token is stored": (len(tokens), 0),
            "no mail is sent": (list(self.mailbox), []),
        }

    def email_change(self):
        p = self.parameters
        user = self.account("old@example.com")
        started = self.change_email(user, "new@example.com")
        pending = self.stored(id=user.id)
        token = self.mailed_token()
        confirmed = self.confirm(token)
        moved = self.stored(id=user.id)
        self.tc_checks["email change"] = {
            "the change is started": (started.status_code, p.STATUS_OK),
            "the login keeps the old address": (pending.email, "old@example.com"),
            "the new address waits": (pending.pending_email, "new@example.com"),
            "a token is mailed": (type_name(token), p.LIFECYCLE_STRING),
            "the new mailbox confirms": (confirmed.status_code, p.STATUS_OK),
            "the login moves to the new address": (moved.email, "new@example.com"),
            "nothing waits any more": (type_name(moved.pending_email), p.NONE_TYPE),
        }

    def confirmation_address(self):
        user = self.account("from@example.com")
        self.change_email(user, "to@example.com")
        self.tc_checks["confirmation address"] = {
            "the confirmation goes to the new address": (
                (self.mailbox or [{}])[-1].get("to"),
                "to@example.com",
            ),
        }

    def cancelled_change(self):
        p = self.parameters
        user = self.account("cancel@example.com")
        self.change_email(user, "never@example.com")
        token = self.mailed_token()
        cancelled = self.bud.bud_request(p.DELETE, p.LIFECYCLE_USER_PATH.format(user.id) + "/email")
        confirmed = self.confirm(token)
        self.tc_checks["cancelled change"] = {
            "a token is mailed": (type_name(token), p.LIFECYCLE_STRING),
            "the change is cancelled": (cancelled.status_code, p.STATUS_OK),
            "the cancelled token is refused": self.refused(confirmed),
            "the login keeps its address": (self.stored(id=user.id).email, "cancel@example.com"),
        }

    def confirm_twice(self):
        p = self.parameters
        user = self.account("reuse@example.com")
        self.change_email(user, "fresh@example.com")
        token = self.mailed_token()
        first = self.confirm(token)
        replay = self.confirm(token)
        self.tc_checks["confirm twice"] = {
            "a token is mailed": (type_name(token), p.LIFECYCLE_STRING),
            "the first confirmation succeeds": (first.status_code, p.STATUS_OK),
            "the replay is refused": self.refused(replay),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    AuthTokenLifecyclesTest().run()
