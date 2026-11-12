"""
* @file     ${tests/pg/BUD_token_concurrency_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Refresh, reset, invitation and verification tokens used six times at once succeed exactly once.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module fires the six uses from six threads on the live app.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from app.api import auth, users
from app.core.config import settings
from tests.pg.token_concurrency_pg import TokenConcurrencyPgBase

TIMES = 6


def token_in(link):
    """The token of a link, or nothing."""
    match = re.search(r"token=([^&\s]+)", link or "")
    return match.group(1) if match else ""


class TokenConcurrencyPgTest(TokenConcurrencyPgBase):

    def setUpClass(self):
        super().setUpClass()
        self.client = self.bud.bud_start_live_app()
        self.tc_checks = {"refresh": self.refresh(), "reset": self.reset(), "invite": self.invite(), "verify": self.verify()}

    @staticmethod
    def fire(request):
        """The status codes of six concurrent copies of a request."""
        with ThreadPoolExecutor(max_workers=TIMES) as pool:
            return [future.result() for future in [pool.submit(request) for _ in range(TIMES)]]

    def outcome(self, codes, refused):
        """The checks of six concurrent uses of one token."""
        return {
            "one use succeeds": (codes.count(200), 1),
            "the other uses are refused": (all(code in (200, refused) for code in codes), True),
        }

    def person(self, stem, password):
        """Create a viewer as the administrator and return the checks and the address."""
        login, admin = self.bud.bud_live_bearer()
        email = self.bud.bud_unique(stem) + "@example.com"
        created = self.client.post(
            "/api/users", json={"email": email, "full_name": "Racer", "password": password, "role": "viewer"}, headers=admin
        )
        return {"the administrator signs in": (login, 200), "the viewer is created": (created.status_code, 201)}, email

    def refresh(self):
        p = self.parameters
        self.client.cookies.clear()
        login = self.client.post(p.LOGIN_PATH, json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD})
        old = self.client.cookies.get(p.PG_REFRESH_COOKIE)
        self.client.cookies.clear()
        codes = self.fire(lambda: self.client.post(p.PG_REFRESH_PATH, cookies={p.PG_REFRESH_COOKIE: old}).status_code)
        return {"the administrator signs in": (login.status_code, 200), **self.outcome(codes, 401)}

    def reset(self):
        checks, email = self.person("reset-racer", "Reset-Racer-123")
        captured = {}
        with mock.patch.object(auth, "send_password_reset_email", lambda **mail: captured.update(link=mail["reset_link"])):
            checks["the reset is asked for"] = (self.client.post("/api/auth/forgot-password", json={"email": email}).status_code, 200)
        token = token_in(captured.get("link"))
        checks["the link carries a token"] = (bool(token), True)
        codes = self.fire(lambda: self.client.post("/api/auth/reset-password", json={"token": token, "new_password": "Fresh-Reset-456"}).status_code)
        return {**checks, **self.outcome(codes, 400)}

    def invite(self):
        login, admin = self.bud.bud_live_bearer()
        captured = {}
        with mock.patch.object(users, "send_invite_email", lambda **mail: captured.update(link=mail["invite_link"])):
            invited = self.client.post(
                "/api/users/invite",
                json={"email": self.bud.bud_unique("invite-racer") + "@example.com", "full_name": "Invite Racer", "role": "viewer"},
                headers=admin,
            )
        token = token_in(captured.get("link"))
        codes = self.fire(lambda: self.client.post("/api/auth/accept-invite", json={"token": token, "password": "Invite-Racer-789"}).status_code)
        return {
            "the administrator signs in": (login, 200),
            "the invitation is sent": (invited.status_code, 201),
            "the link carries a token": (bool(token), True),
            **self.outcome(codes, 400),
        }

    def verify(self):
        p = self.parameters
        checks, email = self.person("verify-racer", "Verify-Racer-123")
        self.client.cookies.clear()
        login = self.client.post(p.LOGIN_PATH, json={"email": email, "password": "Verify-Racer-123"})
        access = login.json().get("access_token") if login.status_code == 200 else ""
        captured = {}
        with mock.patch.object(auth, "send_verification_email", lambda **mail: captured.update(link=mail["verification_link"])):
            resent = self.client.post("/api/auth/resend-verification", headers={"Authorization": f"Bearer {access}"})
        token = token_in(captured.get("link"))
        codes = self.fire(lambda: self.client.post("/api/auth/verify-email", json={"token": token}).status_code)
        return {
            **checks,
            "the viewer signs in": (login.status_code, 200),
            "the verification is sent": (resent.status_code, 200),
            "the link carries a token": (bool(token), True),
            **self.outcome(codes, 400),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    TokenConcurrencyPgTest().run()
