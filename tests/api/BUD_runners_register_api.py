"""
* @file     ${tests/api/BUD_runners_register_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    A Test Station registers only with a known enrolment key, which it is pinned to.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests each scenario on a freshly started app with the rate limiter off.
"""

from unittest import mock

from app.core.deps import limiter
from app.core.runner_keys import mint_key
from app.core.security import get_password_hash
from app.models import Runner, RunnerApiKey
from app.models.user import UserRole
from tests.api.runners_register_api import RunnersRegisterApiBase


class RunnersRegisterApiTest(RunnersRegisterApiBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.unlimited = mock.patch.object(limiter, "enabled", False)
        self.unlimited.start()
        self.tc_minted = []
        self.bud.bud_start_app()
        self.tc_no_key = self.bud.bud_request(
            p.POST, p.REGISTER_PATH, json=p.REGISTER_PAYLOAD
        ).status_code
        self.tc_unknown_key = self.register(p.KEYS_UNKNOWN).status_code
        self.bud.bud_start_app()
        response = self.register(self.mint())
        station = self.bud.bud_find_in_app(Runner, account=p.REGISTER_PAYLOAD["username"])
        keys = self.bud.bud_find_in_app(RunnerApiKey)
        self.tc_pinned = {
            "status": response.status_code,
            "account": response.json().get("account"),
            "token": response.json().get("token"),
            "station id": station[0].id if station else None,
            "pinned": (
                (keys[0].runner_id, keys[0].last_used_at is not None) if len(keys) == 1 else keys
            ),
        }
        self.bud.bud_start_app()
        key = self.mint()
        first = self.register(key).status_code
        second = self.register(key)
        self.tc_again = {"first": first, "second": (second.status_code, "token" in second.json())}
        self.tc_wrong_password = self.refusal(password=p.REGISTER_WRONG_PASSWORD)
        self.tc_other_station = self.refusal(username=p.REGISTER_OTHER_USERNAME)
        self.bud.bud_start_app()
        first = self.register(self.mint(p.KEYS_LABELS[0])).status_code
        response = self.register(self.mint(p.KEYS_LABELS[1]))
        self.tc_displace = {
            "first": first,
            "status": response.status_code,
            "detail": str(response.json().get("detail")),
        }
        self.bud.bud_start_app()
        legacy = self.bud.bud_add_to_app(
            Runner(
                account=p.REGISTER_LEGACY,
                password_hash=get_password_hash(p.REGISTER_PAYLOAD["password"]),
                token="legacy-token",
                socket_port=p.KEYS_PORT,
            )
        )
        response = self.register(self.mint(), username=p.REGISTER_LEGACY)
        self.tc_adopt = {
            "status": response.status_code,
            "pinned": [key.runner_id for key in self.bud.bud_find_in_app(RunnerApiKey)],
            "legacy id": legacy.id,
        }
        self.tc_deletes = self.deletes()

    def mint(self, label=None):
        """Mint a key as the administrator and return it."""
        p = self.parameters
        response = self.bud.bud_request(
            p.POST, p.API_KEYS_PATH, json={"label": label or p.KEYS_LABELS[0]}
        )
        self.tc_minted.append(response.status_code)
        return response.json().get("api_key")

    def register(self, key, **changes):
        """Register the station with a key."""
        p = self.parameters
        return self.bud.bud_request(
            p.POST,
            p.REGISTER_PATH,
            json={**p.REGISTER_PAYLOAD, **changes},
            headers={p.API_KEY_HEADER: key or ""},
        )

    def refusal(self, **changes):
        """Register, then register again with the same key and the changes."""
        self.bud.bud_start_app()
        key = self.mint()
        first = self.register(key).status_code
        response = self.register(key, **changes)
        return {
            "first": first,
            "status": response.status_code,
            "detail": str(response.json().get("detail")),
        }

    def deletes(self):
        """Who may delete a station and manage keys."""
        p = self.parameters
        found = {"registered": []}
        self.bud.bud_start_app(signed_in=False)
        record, key = mint_key(label="seeded", created_by_user_id=None)
        self.bud.bud_add_to_app(record)
        found["registered"].append(self.register(key).status_code)
        found["key delete"] = self.bud.bud_request(
            p.DELETE,
            p.STATION_PATH.format(p.REGISTER_PAYLOAD["username"]),
            headers={p.API_KEY_HEADER: key},
        ).status_code
        self.bud.bud_start_app()
        found["registered"].append(self.register(self.mint()).status_code)
        self.bud.admin.role = UserRole.viewer
        found["viewer delete"] = self.bud.bud_request(
            p.DELETE, p.STATION_PATH.format(p.REGISTER_PAYLOAD["username"])
        ).status_code
        found["viewer keys"] = [
            self.bud.bud_request(p.POST, p.API_KEYS_PATH, json={"label": "x"}).status_code,
            self.bud.bud_request(p.GET, p.API_KEYS_PATH).status_code,
            self.bud.bud_request(p.DELETE, p.API_KEY_PATH.format(1)).status_code,
        ]
        self.bud.bud_start_app()
        found["registered"].append(self.register(self.mint()).status_code)
        found["admin delete"] = self.bud.bud_request(
            p.DELETE, p.STATION_PATH.format(p.REGISTER_PAYLOAD["username"])
        ).status_code
        return found

    def tearDownClass(self):
        self.unlimited.stop()
        super().tearDownClass()


if __name__ == "__main__":
    RunnersRegisterApiTest().run()
