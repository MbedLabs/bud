"""
* @file     ${tests/pg/BUD_refresh_flow_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The refresh cookie is HTTP only, gives working access tokens, rotates once and dies on logout.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests the seeded administrator's sessions on the live app.
"""

from app.core.config import settings
from tests.pg.refresh_flow_pg import RefreshFlowPgBase


class RefreshFlowPgTest(RefreshFlowPgBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.client = self.bud.bud_start_live_app()
        cookie = p.PG_REFRESH_COOKIE
        login = self.log_in()
        set_cookie = login.headers.get("set-cookie", "")
        self.tc_checks = {
            "cookie": {
                "the login succeeds": (login.status_code, p.STATUS_OK),
                "the cookie is named": (cookie in set_cookie, True),
                "the cookie is HTTP only": ("HttpOnly" in set_cookie, True),
                "the cookie is kept to the sign-in routes": ("Path=/api/auth" in set_cookie, True),
                "the client holds the cookie": (bool(self.client.cookies.get(cookie)), True),
            }
        }
        login = self.log_in()
        refreshed = self.client.post(p.PG_REFRESH_PATH)
        access = refreshed.json().get("access_token") if refreshed.status_code == 200 else ""
        me = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {access}"})
        self.tc_checks["refresh"] = {
            "the login succeeds": (login.status_code, p.STATUS_OK),
            "the refresh succeeds": (refreshed.status_code, p.STATUS_OK),
            "the new token signs in": (me.status_code, p.STATUS_OK),
            "the new token names the administrator": (me.json().get("email") if me.status_code == 200 else None, settings.ADMIN_EMAIL),
        }
        self.client.cookies.clear()
        self.tc_checks["no cookie"] = {"a refresh without a cookie is refused": (self.client.post(p.PG_REFRESH_PATH).status_code, p.STATUS_UNAUTHORIZED)}
        login = self.log_in()
        old = self.client.cookies.get(cookie)
        first = self.client.post(p.PG_REFRESH_PATH)
        new = self.client.cookies.get(cookie)
        self.client.cookies.clear()
        replay = self.client.post(p.PG_REFRESH_PATH, cookies={cookie: old})
        self.tc_checks["rotation"] = {
            "the login succeeds": (login.status_code, p.STATUS_OK),
            "the refresh succeeds": (first.status_code, p.STATUS_OK),
            "a new cookie is set": (bool(new), True),
            "the cookie rotates": (new != old, True),
            "the old cookie is refused": (replay.status_code, p.STATUS_UNAUTHORIZED),
        }
        login = self.log_in()
        logout = self.client.post("/api/auth/logout")
        self.tc_checks["logout"] = {
            "the login succeeds": (login.status_code, p.STATUS_OK),
            "the logout succeeds": (logout.status_code, p.STATUS_OK),
            "the revoked cookie is refused": (self.client.post(p.PG_REFRESH_PATH).status_code, p.STATUS_UNAUTHORIZED),
        }

    def log_in(self):
        """Sign the seeded administrator in with a cleared cookie jar."""
        self.client.cookies.clear()
        return self.client.post(self.parameters.LOGIN_PATH, json={"email": settings.ADMIN_EMAIL, "password": settings.ADMIN_PASSWORD})

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    RefreshFlowPgTest().run()
