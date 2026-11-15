"""
* @file     ${tests/pg/BUD_email_change_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    An email change needs approval and confirmation, ends sessions and verifies; an invitation verifies too.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module creates fresh viewers through the live app's administrator and captures the mails.
"""

import os
import re
from unittest import mock

import asyncpg

from app.api import users
from tests.pg.email_change_pg import EmailChangePgBase


def body_of(response):
    """The JSON answer, or an empty one."""
    try:
        return response.json() or {}
    except ValueError:
        return {}


def type_name(value):
    """The type name of a value."""
    return type(value).__name__


def token_in(link):
    """The token of a link, or nothing."""
    match = re.search(r"token=([^&\s]+)", link or "")
    return match.group(1) if match else ""


class EmailChangePgTest(EmailChangePgBase):

    def setUpClass(self):
        super().setUpClass()
        self.client = self.bud.bud_start_live_app()
        self.tc_checks = {
            "flow": self.flow(),
            "race": self.race(),
            "wrong password": self.wrong_password(),
            "admin": self.admin_change(),
            "invite": self.invite(),
        }

    def email(self, stem):
        return self.bud.bud_unique(stem) + "@example.com"

    def setup(self, email, password):
        """Sign the administrator in and create a viewer; return the admin header and the checks."""
        login, admin = self.bud.bud_live_bearer()
        created = self.client.post(
            "/api/users", json={"email": email, "full_name": "Mover", "password": password, "role": "viewer"}, headers=admin
        )
        return admin, {"the administrator signs in": (login, 200), "the viewer is created": (created.status_code, 201)}

    def log_in(self, email, password):
        """Sign a person in with a cleared cookie jar."""
        self.client.cookies.clear()
        return self.client.post(self.parameters.LOGIN_PATH, json={"email": email, "password": password})

    def bearer(self, response):
        return {"Authorization": f"Bearer {body_of(response).get('access_token')}"}

    def me(self, headers):
        return self.client.get("/api/auth/me", headers=headers)

    def flow(self):
        p = self.parameters
        old_email, new_email, password = self.email("mover-old"), self.email("mover-new"), "Mover-Password-123"
        admin, checks = self.setup(old_email, password)
        login = self.log_in(old_email, password)
        access = self.bearer(login)
        refresh = self.client.cookies.get(p.PG_REFRESH_COOKIE)
        captured = {}
        with mock.patch.object(
            users,
            "send_email_change_email",
            lambda **mail: captured.update(link=mail["confirm_link"], old_email=mail["old_email"], new_email=mail["new_email"]),
        ):
            requested = self.client.post("/api/auth/me/email", json={"current_password": password, "new_email": new_email}, headers=access)
            mailed_before = dict(captured)
            pending = body_of(self.me(access))
            approved = self.client.post(f"/api/users/{pending.get('id')}/email/approve", headers=admin)
        me = self.me(access)
        waiting = body_of(me)
        new_before = self.log_in(new_email, password).status_code
        old_before = self.log_in(old_email, password).status_code
        confirm = self.client.post("/api/auth/confirm-email-change", json={"token": token_in(captured.get("link"))})
        stale = self.me(access).status_code
        self.client.cookies.clear()
        replay = self.client.post(p.PG_REFRESH_PATH, cookies={p.PG_REFRESH_COOKIE: refresh}).status_code
        old_after = self.log_in(old_email, password).status_code
        after = self.log_in(new_email, password)
        moved = body_of(self.me(self.bearer(after)))
        checks.update(
            {
                "the viewer signs in": (login.status_code, 200),
                "the change is requested": (requested.status_code, 200),
                "no mail is sent before approval": (mailed_before, {}),
                "the change waits for approval": (pending.get("email_change_status"), "requested"),
                "the administrator approves": (approved.status_code, 200),
                "the profile is read": (me.status_code, 200),
                "the login keeps the old address": (waiting.get("email"), old_email),
                "the new address waits": (waiting.get("pending_email"), new_email),
                "the change waits for confirmation": (waiting.get("email_change_status"), "awaiting_confirmation"),
                "the mail names the old address": (captured.get("old_email"), old_email),
                "the mail names the new address": (captured.get("new_email"), new_email),
                "the new address cannot sign in yet": (new_before, 401),
                "the old address still signs in": (old_before, 200),
                "the link carries a token": (bool(token_in(captured.get("link"))), True),
                "the change is confirmed": (confirm.status_code, 200),
                "the old access token is refused": (stale, 401),
                "the old refresh token is refused": (replay, 401),
                "the old address is refused": (old_after, 401),
                "the new address signs in": (after.status_code, 200),
                "the login moved": (moved.get("email"), new_email),
                "nothing waits any more": (type_name(moved.get("pending_email")), p.NONE_TYPE),
                "no change status is left": (type_name(moved.get("email_change_status")), p.NONE_TYPE),
                "the account is verified": (type_name(moved.get("email_verified_at")) != p.NONE_TYPE, True),
            }
        )
        return checks

    def replace_pending(self, user_id, pending_email):
        """Set a pending address directly in the database."""

        async def run():
            connection = await asyncpg.connect(os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://", 1))
            try:
                await connection.execute("UPDATE users SET pending_email = $1 WHERE id = $2", pending_email, user_id)
            finally:
                await connection.close()

        self.bud.bud_await(run())

    def race(self):
        old_email, approved_email, unapproved_email = self.email("race-old"), self.email("race-approved"), self.email("race-unapproved")
        password = "Race-Password-123"
        admin, checks = self.setup(old_email, password)
        access = self.bearer(self.log_in(old_email, password))
        pending = self.client.post("/api/auth/me/email", json={"current_password": password, "new_email": approved_email}, headers=access)
        user_id = body_of(self.me(access)).get("id")
        captured = {}
        with mock.patch.object(users, "send_email_change_email", lambda **mail: captured.update(link=mail["confirm_link"])):
            approved = self.client.post(f"/api/users/{user_id}/email/approve", headers=admin)
        self.replace_pending(user_id, unapproved_email)
        confirmed = self.client.post("/api/auth/confirm-email-change", json={"token": token_in(captured.get("link"))})
        checks.update(
            {
                "the change is requested": (pending.status_code, 200),
                "the administrator approves": (approved.status_code, 200),
                "the token is refused for another address": (confirmed.status_code, 400),
                "the old address still signs in": (self.log_in(old_email, password).status_code, 200),
                "the approved address cannot sign in": (self.log_in(approved_email, password).status_code, 401),
                "the other address cannot sign in": (self.log_in(unapproved_email, password).status_code, 401),
            }
        )
        return checks

    def wrong_password(self):
        p = self.parameters
        email, password = self.email("mover-guard"), "Mover-Guard-123"
        _, checks = self.setup(email, password)
        access = self.bearer(self.log_in(email, password))
        response = self.client.post(
            "/api/auth/me/email", json={"current_password": "wrong-password-xx", "new_email": self.email("guard-new")}, headers=access
        )
        checks.update(
            {
                "a wrong password is refused": (response.status_code, 400),
                "nothing waits": (type_name(body_of(self.me(access)).get("pending_email")), p.NONE_TYPE),
            }
        )
        return checks

    def admin_change(self):
        old_email, new_email, password = self.email("admin-flow-old"), self.email("admin-flow-new"), "Admin-Flow-Password-123"
        admin, checks = self.setup(old_email, password)
        listed = self.client.get("/api/users", headers=admin)
        rows = listed.json() if listed.status_code == 200 else []
        user = next((item for item in rows if isinstance(item, dict) and item.get("email") == old_email), {})
        bypass = self.client.patch(f"/api/users/{user.get('id')}", json={"email": new_email}, headers=admin)
        captured = {}
        with mock.patch.object(users, "send_email_change_email", lambda **mail: captured.update(link=mail["confirm_link"])):
            started = self.client.post(f"/api/users/{user.get('id')}/email", json={"new_email": new_email}, headers=admin)
        confirmed = self.client.post("/api/auth/confirm-email-change", json={"token": token_in(captured.get("link"))})
        checks.update(
            {
                "a direct email update is refused": (bypass.status_code, 422),
                "the change is started": (started.status_code, 200),
                "the login keeps the old address": (body_of(started).get("email"), old_email),
                "the change waits for confirmation": (body_of(started).get("email_change_status"), "awaiting_confirmation"),
                "the change is confirmed": (confirmed.status_code, 200),
                "the old address is refused": (self.log_in(old_email, password).status_code, 401),
                "the new address signs in": (self.log_in(new_email, password).status_code, 200),
            }
        )
        return checks

    def invite(self):
        p = self.parameters
        login, admin = self.bud.bud_live_bearer()
        email = self.email("invited-verified")
        captured = {}
        with mock.patch.object(users, "send_invite_email", lambda **mail: captured.update(link=mail["invite_link"])):
            invited = self.client.post("/api/users/invite", json={"email": email, "full_name": "Invited", "role": "viewer"}, headers=admin)
        accept = self.client.post("/api/auth/accept-invite", json={"token": token_in(captured.get("link")), "password": "Invited-Password-123"})
        signed_in = self.log_in(email, "Invited-Password-123")
        me = body_of(self.me(self.bearer(signed_in)))
        return {
            "the administrator signs in": (login, 200),
            "the invitation is sent": (invited.status_code, 201),
            "the invitation is accepted": (accept.status_code, 200),
            "no further verification is asked": (body_of(accept).get("requires_email_verification"), False),
            "the person signs in": (signed_in.status_code, 200),
            "the account is verified": (type_name(me.get("email_verified_at")) != p.NONE_TYPE, True),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    EmailChangePgTest().run()
