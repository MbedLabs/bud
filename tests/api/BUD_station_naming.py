"""
* @file     ${tests/api/BUD_station_naming.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    An administrator names the Test Station, and that name wins.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests each scenario on a freshly started app with the rate limiter off.
"""

from unittest import mock

from app.core import runner_auth
from app.core.deps import limiter
from app.core.security import decode_access_token
from app.models import Runner, RunnerApiKey
from tests.api.station_naming import StationNamingBase


class StationNamingTest(StationNamingBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.unlimited = mock.patch.object(limiter, "enabled", False)
        self.unlimited.start()
        self.tc_minted = []
        self.bud.bud_start_app()
        self.tc_named = self.register(self.mint(p.STATION_KEY_LABEL, p.STATION_NAMED))
        self.bud.bud_start_app()
        self.tc_unnamed = self.register(self.mint(p.STATION_UNNAMED_LABEL))
        self.bud.bud_start_app()
        token = self.register(self.mint(p.STATION_KEY_LABEL, p.STATION_NAMED)).json().get("token")
        station = self.bud.bud_find_in_app(Runner, account=p.STATION_NAMED)
        self.tc_station_id = station[0].id if station else None
        self.tc_claims = decode_access_token(token) if token else None
        self.bud.bud_start_app()
        self.register(self.mint(p.STATION_KEY_LABEL, p.STATION_NAMED))
        self.tc_taken = self.mint_response(p.STATION_SECOND_LABEL, p.STATION_NAMED)
        self.bud.bud_start_app()
        self.mint(p.STATION_KEY_LABEL, p.STATION_NAMED)
        self.tc_reserved = self.mint_response(p.STATION_SECOND_LABEL, p.STATION_NAMED)
        self.bud.bud_start_app()
        self.tc_bad_names = {
            name: self.mint_response(p.STATION_SECOND_LABEL, name).status_code
            for name in p.STATION_BAD_NAMES
        }
        self.bud.bud_start_app()
        self.register(self.mint(p.STATION_KEY_LABEL, p.STATION_NAMED))
        self.tc_renamed = self.rename(p.STATION_NAMED, p.STATION_RENAMED)
        keys = self.bud.bud_find_in_app(RunnerApiKey)
        self.tc_key_name = keys[0].station_name if keys else None
        self.bud.bud_start_app()
        token = self.register(self.mint(p.STATION_KEY_LABEL, p.STATION_NAMED)).json().get("token")
        self.tc_moved = self.rename(p.STATION_NAMED, p.STATION_MOVED).status_code
        db = self.bud.bud_open_session(on_app=True)
        self.tc_resolved = self.bud.bud_attempt(
            lambda: self.bud.bud_await(runner_auth.authenticate_runner_token(token, db))
        )
        self.bud.bud_start_app()
        self.register(self.mint(p.STATION_KEY_LABEL, p.STATION_NAMED))
        self.register(
            self.mint(p.STATION_SECOND_LABEL, p.STATION_OTHER),
            username=p.STATION_IGNORED_USERNAME,
        )
        self.tc_rename_taken = self.rename(p.STATION_OTHER, p.STATION_NAMED).status_code
        self.bud.bud_start_app()
        self.tc_rename_unknown = self.rename(p.STATION_UNKNOWN, p.STATION_UNKNOWN_NEW).status_code

    def mint_response(self, label, station_name=None):
        """Ask for an enrolment key with a label and an optional station name."""
        body = {"label": label}
        if station_name is not None:
            body["station_name"] = station_name
        return self.bud.bud_request(self.parameters.POST, self.parameters.API_KEYS_PATH, json=body)

    def mint(self, label, station_name=None):
        """Mint an enrolment key and return it, recording the answer's status."""
        response = self.mint_response(label, station_name)
        self.tc_minted.append(response.status_code)
        return response.json().get("api_key")

    def register(self, key, **changes):
        """Register the station with an enrolment key."""
        return self.bud.bud_request(
            self.parameters.POST,
            self.parameters.REGISTER_PATH,
            json={**self.parameters.STATION_REGISTRATION, **changes},
            headers={self.parameters.API_KEY_HEADER: key or ""},
        )

    def rename(self, account, new_account):
        """Rename a station."""
        return self.bud.bud_request(
            self.parameters.PATCH,
            self.parameters.STATION_PATH.format(account),
            json={"account": new_account},
        )

    def tearDownClass(self):
        self.unlimited.stop()
        super().tearDownClass()


if __name__ == "__main__":
    StationNamingTest().run()
