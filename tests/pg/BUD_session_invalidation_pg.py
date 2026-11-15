"""
* @file     ${tests/pg/BUD_session_invalidation_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    A password change or reset ends every access and refresh token of the account.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module creates a fresh viewer per scenario through the live app's administrator.
"""

import re
from unittest import mock

from app.api import auth
from tests.pg.session_invalidation_pg import SessionInvalidationPgBase


class SessionInvalidationPgTest(SessionInvalidationPgBase):

    def setUpClass(self):
        super().setUpClass()
        self.client = self.bud.bud_start_live_app()
        self.tc_checks = {"change": self.scenario("change"), "reset": self.scenario("reset")}

    def log_in(self, email, password):
        """Sign a person in with a cleared cookie jar."""
        self.client.cookies.clear()
        return self.client.post(self.parameters.LOGIN_PATH, json={"email": email, "password": password})

    def scenario(self, how):
        p = self.parameters
        cookie = p.PG_REFRESH_COOKIE
        admin_login, admin = self.bud.bud_live_bearer()
        email = self.bud.bud_unique(f"pw{how}-victim") + "@example.com"
        old_pw, new_pw = f"Old{how.title()}-Password-123", f"New{how.title()}-Password-456"
        created = self.client.post(
            "/api/users", json={"email": email, "full_name": "Victim", "password": old_pw, "role": "viewer"}, headers=admin
        )
        login = self.log_in(email, old_pw)
        access = login.json().get("access_token") if login.status_code == 200 else ""
        bearer = {"Authorization": f"Bearer {access}"}
        refresh = self.client.cookies.get(cookie)
        before = self.client.get("/api/auth/me", headers=bearer).status_code
        checks = {
            "the administrator signs in": (admin_login, p.STATUS_OK),
            "the viewer is created": (created.status_code, p.STATUS_CREATED),
            "the viewer signs in": (login.status_code, p.STATUS_OK),
            "the viewer's token works": (before, p.STATUS_OK),
        }
        if how == "change":
            change = self.client.put("/api/auth/me/password", json={"current_password": old_pw, "new_password": new_pw}, headers=bearer)
            checks["the password is changed"] = (change.status_code, p.STATUS_OK)
        else:
            captured = {}
            with mock.patch.object(auth, "send_password_reset_email", lambda **mail: captured.update(link=mail.get("reset_link", ""))):
                forgot = self.client.post("/api/auth/forgot-password", json={"email": email})
            match = re.search(r"token=([^&\s]+)", captured.get("link", ""))
            reset = self.client.post("/api/auth/reset-password", json={"token": match.group(1) if match else "", "new_password": new_pw})
            checks["the reset is asked for"] = (forgot.status_code, p.STATUS_OK)
            checks["the link carries a token"] = (bool(match), True)
            checks["the password is reset"] = (reset.status_code, p.STATUS_OK)
        after = self.client.get("/api/auth/me", headers=bearer).status_code
        self.client.cookies.clear()
        replay = self.client.post(p.PG_REFRESH_PATH, cookies={cookie: refresh}).status_code
        checks.update(
            {
                "the old access token is refused": (after, p.STATUS_UNAUTHORIZED),
                "the old refresh token is refused": (replay, p.STATUS_UNAUTHORIZED),
                "the old password is refused": (self.log_in(email, old_pw).status_code, p.STATUS_UNAUTHORIZED),
                "the new password signs in": (self.log_in(email, new_pw).status_code, p.STATUS_OK),
            }
        )
        return checks

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    SessionInvalidationPgTest().run()
