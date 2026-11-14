"""
* @file     ${tests/sec/BUD_audit_log_http.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    The audit log records security-relevant events with who, where and the outcome.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module signs every person in with a real token, each scenario on a fresh app.
"""

import io
import json

from fastapi.routing import APIRoute
from PIL import Image

from app import main
from app.core.security import get_password_hash
from app.models import AuditEvent
from app.models.user import User, UserRole
from tests.sec.audit_log_http import AuditLogHttpBase


def api_routes(routes):
    """Every API route, those of included routers too."""
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        included = getattr(route, "original_router", None)
        if included is not None:
            yield from api_routes(included.routes)


class AuditLogHttpTest(AuditLogHttpBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.tc_logins = []
        self.fresh()
        user = self.user("someone@example.com")
        response = self.bud.bud_request(
            p.POST,
            p.LOGIN_PATH,
            json={"email": user.email, "password": p.AUDIT_WRONG_PASSWORD},
            headers={"user-agent": p.AUDIT_USER_AGENT},
        )
        events = self.events(p.AUDIT_LOGIN_ACTION)
        self.tc_failed = {
            "status": response.status_code,
            "events": events,
            "user id": str(user.id),
            "request id": response.headers.get("x-request-id"),
            "details": json.dumps(events[0].details) if events else "",
        }
        self.fresh()
        admin, member = self.user("boss@example.com", UserRole.admin), self.user(
            "member@example.com"
        )
        headers = self.login(admin.email)
        response = self.bud.bud_request(
            p.PATCH, p.USER_PATH.format(member.id), json={"is_active": False}, headers=headers
        )
        self.tc_deactivated = {
            "status": response.status_code,
            "events": self.events(p.AUDIT_DEACTIVATED_ACTION),
            "admin id": admin.id,
            "member id": str(member.id),
        }
        self.fresh()
        headers = self.login(self.user("boss@example.com", UserRole.admin).email)
        minted = self.bud.bud_request(
            p.POST, p.API_KEYS_PATH, json={"label": p.AUDIT_KEY_LABEL}, headers=headers
        )
        key_id = minted.json().get("id")
        revoked = self.bud.bud_request(p.DELETE, p.API_KEY_PATH.format(key_id), headers=headers)
        minted_events = self.events(p.AUDIT_MINTED_ACTION)
        self.tc_key = {
            "statuses": (minted.status_code, revoked.status_code),
            "minted": minted_events,
            "revoked": self.events(p.AUDIT_REVOKED_ACTION),
            "key": minted.json().get("api_key") or "",
            "key id": str(key_id),
            "details": json.dumps(minted_events[0].details) if minted_events else "",
        }
        self.fresh()
        self.user("boss@example.com", UserRole.admin)
        self.user("member@example.com")
        member_headers = self.login("member@example.com")
        admin_headers = self.login("boss@example.com")
        refused = self.bud.bud_request(p.GET, p.AUDIT_PATH, headers=member_headers)
        page = self.bud.bud_request(
            p.GET, p.AUDIT_PATH, params={"action": p.AUDIT_AUTH_PREFIX}, headers=admin_headers
        )
        items = page.json().get("items", []) if page.status_code == 200 else []
        self.tc_readers = {
            "refused": refused.status_code,
            "page": page.status_code,
            "total": page.json().get("total"),
            "actions": {item["action"] for item in items},
            "first actor": items[0].get("actor_name") if items else None,
        }
        self.tc_audit_methods = {
            method
            for route in api_routes(main.app.routes)
            if route.endpoint.__module__ == p.AUDIT_MODULE
            for method in route.methods
        }
        self.tc_pictures = self.pictures()

    def pictures(self):
        """Three accounts' picture links on the audit page and the user list as one changes."""
        p = self.fresh()
        admin = self.user("picture-admin@example.com", UserRole.admin)
        member = self.user("picture-member@example.com")
        plain = self.user("picture-none@example.com")
        admin_headers, member_headers = self.login(admin.email), self.login(member.email)
        self.login(plain.email)
        admin_saved, admin_picture = self.upload(admin_headers, p.AUDIT_PICTURE_COLORS[0])
        member_saved, member_picture = self.upload(member_headers, p.AUDIT_PICTURE_COLORS[1])
        found = {
            "saved": [admin_saved, member_saved],
            "admin picture": admin_picture,
            "member picture": member_picture,
            "signed out": [
                self.bud.bud_request(p.GET, path).status_code for path in p.AUDIT_GUARDED_PATHS
            ],
            "member": [
                self.bud.bud_request(p.GET, path, headers=member_headers).status_code
                for path in p.AUDIT_GUARDED_PATHS
            ],
            "rounds": [],
        }
        for color in p.AUDIT_NEXT_COLORS:
            if color is None:
                changed = self.bud.bud_request(
                    p.DELETE, p.PICTURE_PATH, headers=member_headers
                ).status_code
                next_picture = None
            else:
                changed, next_picture = self.upload(member_headers, color)
            page = self.bud.bud_request(
                p.GET, p.AUDIT_PATH, params={"action": p.AUDIT_LOGIN_ACTION}, headers=admin_headers
            )
            actors = {item["actor_user_id"]: item for item in page.json().get("items", [])}
            listed = self.bud.bud_request(p.GET, p.USERS_PATH, headers=admin_headers)
            users = (
                {item["id"]: item for item in listed.json()} if listed.status_code == 200 else {}
            )
            ids = (admin.id, member.id, plain.id)
            found["rounds"].append(
                {
                    "changed": changed,
                    "page": page.status_code,
                    "actors": [actors.get(i, {}).get("actor_profile_picture_url") for i in ids],
                    "listed": listed.status_code,
                    "users": [users.get(i, {}).get("profile_picture_url") for i in ids],
                    "expected": [admin_picture, next_picture, None],
                }
            )
        return found

    def fresh(self):
        """Start the app with no one signed in and return the parameters."""
        self.bud.bud_start_app(signed_in=False)
        return self.parameters

    def user(self, email, role=UserRole.viewer):
        """Store an active user with the shared password."""
        return self.bud.bud_add_to_app(
            User(
                email=email,
                full_name=email.split("@")[0],
                hashed_password=get_password_hash(self.parameters.SEC_PASSWORD),
                role=role,
                is_active=True,
            )
        )

    def events(self, action):
        """The audit events of one action."""
        return self.bud.bud_find_in_app(AuditEvent, action=action)

    def login(self, email):
        """Sign in with the shared password and return the bearer header."""
        response = self.bud.bud_request(
            self.parameters.POST,
            self.parameters.LOGIN_PATH,
            json={"email": email, "password": self.parameters.SEC_PASSWORD},
        )
        self.tc_logins.append(response.status_code)
        return {"Authorization": f"Bearer {response.json().get('access_token')}"}

    def upload(self, headers, color):
        """Upload a small PNG as the account's picture; return the status and the picture link."""
        data = io.BytesIO()
        Image.new("RGB", self.parameters.AUDIT_PICTURE_PIXELS, color=color).save(data, format="PNG")
        result = self.bud.bud_request(
            self.parameters.PUT,
            self.parameters.PICTURE_PATH,
            headers=headers,
            files={
                "file": (self.parameters.PICTURE_FILE, data.getvalue(), self.parameters.PICTURE_PNG)
            },
        )
        return result.status_code, result.json().get("profile_picture_url")

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    AuditLogHttpTest().run()
