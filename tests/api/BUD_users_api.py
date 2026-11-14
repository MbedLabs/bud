"""
* @file     ${tests/api/BUD_users_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Administrators list, create, invite, change and delete users; the new mailbox confirms a change.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests each scenario on a freshly started app with outgoing mail captured.
"""

from unittest import mock

from app.api import auth, users
from app.models.user import User, UserRole
from app.models.user_token import UserToken, UserTokenPurpose
from app.services import mail_service
from tests.api.users_api import UsersApiBase


class UsersApiTest(UsersApiBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.sent = []
        self.mail = [
            mock.patch.object(module, "send_email", self.capture)
            for module in (mail_service, users, auth)
            if hasattr(module, "send_email")
        ]
        for patch in self.mail:
            patch.start()
        self.tc_checks = {
            "list and create": self.list_and_create(),
            "invitations": self.invitations(),
            "email change": self.email_change(),
            "update and delete": self.update_and_delete(),
        }
        self.bud.bud_start_app(signed_in=False)
        self.tc_signed_out = {
            (method, path): self.bud.bud_request(method, path, json={}).status_code
            for method, path in p.USERS_SIGNED_OUT_CALLS
        }

    def capture(self, *, to_email, subject, text_body, html_body=None):
        """Record an outgoing email in place of sending it."""
        self.sent.append({"to": to_email, "subject": subject})

    def call(self, method, path, **kwargs):
        """Send one request as the administrator."""
        return self.bud.bud_request(method, path, **kwargs)

    def user(self, email, **overrides):
        """Store a user."""
        return self.bud.bud_add_to_app(
            User(
                email=email,
                full_name=overrides.pop("full_name", "Someone"),
                hashed_password="hashed",
                role=overrides.pop("role", UserRole.viewer),
                is_active=True,
                session_version=1,
            )
        )

    def list_and_create(self):
        """List two users, create one, a duplicate and one with a short password."""
        p = self.parameters
        self.bud.bud_start_app()
        self.user("one@example.com")
        self.user("two@example.com")
        listed = self.call(p.GET, p.USERS_PATH)
        created = self.call(p.POST, p.USERS_PATH, json=p.USERS_NEW)
        self.bud.bud_start_app()
        first = self.call(p.POST, p.USERS_PATH, json=p.USERS_DUPLICATE).status_code
        second = self.call(p.POST, p.USERS_PATH, json=p.USERS_DUPLICATE)
        short = self.call(p.POST, p.USERS_PATH, json=p.USERS_SHORT).status_code
        emails = {user["email"] for user in listed.json()} if listed.status_code == 200 else set()
        return {
            "list answers": (listed.status_code, p.STATUS_OK),
            "list holds both users": ({"one@example.com", "two@example.com"} <= emails, True),
            "create answers": (created.status_code, p.STATUS_CREATED),
            "created email": (created.json().get("email"), p.USERS_NEW["email"]),
            "no password shown": (
                "password" in created.json() or "hashed_password" in created.json(),
                False,
            ),
            "first of a duplicate": (first, p.STATUS_CREATED),
            "duplicate refused": (second.status_code, p.STATUS_BAD_REQUEST),
            "duplicate text": (
                p.USERS_DUPLICATE_TEXT in str(second.json().get("detail")).lower(),
                True,
            ),
            "short password refused": (short, p.STATUS_UNPROCESSABLE),
        }

    def invitations(self):
        """Invite, keep a single-use token, resend and revoke."""
        p = self.parameters
        self.bud.bud_start_app()
        invited = self.call(
            p.POST,
            p.INVITE_PATH,
            json={"email": "invitee@example.com", "full_name": "Invitee", "role": "viewer"},
        )
        self.bud.bud_start_app()
        self.call(
            p.POST, p.INVITE_PATH, json={"email": "tokened@example.com", "full_name": "Tokened"}
        )
        tokens = self.bud.bud_find_in_app(UserToken, purpose=UserTokenPurpose.invite)
        self.bud.bud_start_app()
        resend_id = self.call(
            p.POST, p.INVITE_PATH, json={"email": "resend@example.com", "full_name": "Resend"}
        ).json()["user"]["id"]
        resent = self.call(p.POST, p.RESEND_PATH.format(resend_id)).status_code
        revoke_id = self.call(
            p.POST, p.INVITE_PATH, json={"email": "revoke@example.com", "full_name": "Revoke"}
        ).json()["user"]["id"]
        revoked = self.call(p.POST, p.REVOKE_PATH.format(revoke_id)).status_code
        return {
            "invite answers": (invited.status_code, p.STATUS_CREATED),
            "invited email": (
                (invited.json().get("user") or {}).get("email"),
                "invitee@example.com",
            ),
            "one invite token": (len(tokens), 1),
            "token unused": (tokens[0].used_at is None if tokens else None, True),
            "resend answers": (resent, p.STATUS_OK),
            "resend to unknown": (
                self.call(p.POST, p.RESEND_PATH.format(p.USERS_MISSING)).status_code,
                p.STATUS_NOT_FOUND,
            ),
            "revoke answers": (revoked, p.STATUS_OK),
            "revoke for unknown": (
                self.call(p.POST, p.REVOKE_PATH.format(p.USERS_MISSING)).status_code,
                p.STATUS_NOT_FOUND,
            ),
        }

    def email_change(self):
        """Start a change, refuse a taken address, cancel a change and an unknown user."""
        p = self.parameters
        self.bud.bud_start_app()
        before = self.user("before@example.com")
        started = self.call(
            p.POST, p.USER_EMAIL_PATH.format(before.id), json={"new_email": "after@example.com"}
        )
        self.bud.bud_start_app()
        self.user("taken@example.com")
        mover = self.user("mover@example.com")
        taken = self.call(
            p.POST, p.USER_EMAIL_PATH.format(mover.id), json={"new_email": "taken@example.com"}
        ).status_code
        self.bud.bud_start_app()
        cancelling = self.user("cancel@example.com")
        self.call(
            p.POST,
            p.USER_EMAIL_PATH.format(cancelling.id),
            json={"new_email": "cancelled@example.com"},
        )
        cancelled = self.call(p.DELETE, p.USER_EMAIL_PATH.format(cancelling.id))
        unknown = self.call(
            p.POST, p.USER_EMAIL_PATH.format(p.USERS_MISSING), json={"new_email": "x@example.com"}
        ).status_code
        return {
            "change answers": (started.status_code, p.STATUS_OK),
            "login moves only after confirmation": (
                started.json().get("email"),
                "before@example.com",
            ),
            "pending address": (started.json().get("pending_email"), "after@example.com"),
            "taken address refused": (taken, p.STATUS_BAD_REQUEST),
            "cancel answers": (cancelled.status_code, p.STATUS_OK),
            "cancel clears the pending address": (
                type(cancelled.json().get("pending_email")).__name__,
                p.NONE_TYPE,
            ),
            "unknown user": (unknown, p.STATUS_NOT_FOUND),
        }

    def update_and_delete(self):
        """Rename, keep admin fixed, restate a role, refuse odd roles and emails, deactivate, delete."""
        p = self.parameters
        self.bud.bud_start_app()
        patch = lambda user, body: self.call(p.PATCH, p.USER_PATH.format(user.id), json=body)
        renamed = patch(self.user("patch@example.com"), {"full_name": "Renamed"})
        demoted = patch(self.user("demote@example.com", role=UserRole.admin), {"role": "viewer"})
        restated = patch(self.user("same@example.com"), {"role": "viewer"})
        bogus = patch(self.user("bogus@example.com"), {"role": "superuser"}).status_code
        promoted = patch(self.user("climber@example.com"), {"role": "admin"})
        deactivated = patch(self.user("deactivate@example.com"), {"is_active": False})
        sneaky = patch(self.user("sneaky@example.com"), {"email": "other@example.com"}).status_code
        unknown = self.call(
            p.PATCH, p.USER_PATH.format(p.USERS_MISSING), json={"full_name": "X"}
        ).status_code
        gone = self.user("gone@example.com")
        deleted = self.call(p.DELETE, p.USER_PATH.format(gone.id)).status_code
        return {
            "rename answers": (renamed.status_code, p.STATUS_OK),
            "renamed": (renamed.json().get("full_name"), "Renamed"),
            "admin demotion refused": (demoted.status_code, p.STATUS_BAD_REQUEST),
            "admin role fixed text": (
                p.USERS_ROLE_FIXED_TEXT in str(demoted.json().get("detail")).lower(),
                True,
            ),
            "restated role accepted": (
                (restated.status_code, restated.json().get("role")),
                (p.STATUS_OK, "viewer"),
            ),
            "odd role refused": (bogus, p.STATUS_UNPROCESSABLE),
            "promotion refused": (promoted.status_code, p.STATUS_BAD_REQUEST),
            "promotion text": (
                p.USERS_ADMIN_TEXT in str(promoted.json().get("detail")).lower(),
                True,
            ),
            "deactivated": (
                (deactivated.status_code, deactivated.json().get("is_active")),
                (p.STATUS_OK, False),
            ),
            "email patch refused": (sneaky, p.STATUS_UNPROCESSABLE),
            "unknown user": (unknown, p.STATUS_NOT_FOUND),
            "delete answers": (deleted, p.STATUS_NO_CONTENT),
            "deleted user gone": (len(self.bud.bud_find_in_app(User, id=gone.id)), 0),
            "delete unknown": (
                self.call(p.DELETE, p.USER_PATH.format(p.USERS_MISSING)).status_code,
                p.STATUS_NOT_FOUND,
            ),
        }

    def tearDownClass(self):
        for patch in self.mail:
            patch.stop()
        super().tearDownClass()


if __name__ == "__main__":
    UsersApiTest().run()
