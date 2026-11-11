"""
* @file     ${tests/api/BUD_runner_api_keys.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    An enrolment key files results only as its own active station and is shown once.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests key uploads with no one signed in and key management as an administrator.
"""

from app.core.runner_keys import mint_key
from app.core.security import get_password_hash
from app.models import Runner, RunnerApiKey, TestResult, TestRun
from tests.api.runner_api_keys import RunnerApiKeysBase


class RunnerApiKeysTest(RunnerApiKeysBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        mine, theirs = self.signed_out_with_stations()
        key = self.pin(mine)
        response = self.upload(key, runner_account=theirs.account)
        self.tc_impersonation = {
            "status": response.status_code,
            "owners": [run.runner_id for run in self.bud.bud_find_in_app(TestRun)],
            "mine": mine.id,
        }
        mine, _ = self.signed_out_with_stations()
        refused = {"unpinned": self.upload(self.pin(None)).status_code}
        refused["unknown"] = self.upload(p.KEYS_UNKNOWN).status_code
        refused["unknown results"] = len(self.bud.bud_find_in_app(TestResult))
        mine, _ = self.signed_out_with_stations(mine_active=False)
        refused["inactive"] = self.upload(self.pin(mine)).status_code
        self.tc_refused = refused
        mine, _ = self.signed_out_with_stations()
        response = self.upload(self.pin(mine))
        runs = self.bud.bud_find_in_app(TestRun)
        self.tc_own = {
            "status": response.status_code,
            "owner": runs[0].runner_id if runs else None,
            "mine": mine.id,
        }
        self.tc_removed = self.removed()
        self.tc_minted = self.minted()
        mine, _ = self.signed_out_with_stations()
        key = self.pin(mine)
        accepted = self.upload(key).status_code
        self.bud.bud_delete_in_app(RunnerApiKey, runner_id=mine.id)
        self.tc_revoked = {"accepted": accepted, "refused": self.upload(key).status_code}
        self.tc_admin_revoke = self.admin_revoke()

    def station(self, account, active=True):
        """Store a station with the given account."""
        p = self.parameters
        return self.bud.bud_add_to_app(
            Runner(
                account=account,
                password_hash=get_password_hash(p.KEYS_STATION_PASSWORD),
                token=f"token-for-{account}",
                socket_port=p.KEYS_PORT,
                location=p.KEYS_LOCATION,
                is_active=active,
            )
        )

    def signed_out_with_stations(self, mine_active=True):
        """Start the app with no one signed in and two stations."""
        self.bud.bud_start_app(signed_in=False)
        return self.station(self.parameters.KEYS_MINE, mine_active), self.station(
            self.parameters.KEYS_THEIRS
        )

    def pin(self, station):
        """Mint a key, pinned to the station when one is given, and return it."""
        record, plaintext = mint_key(label="key", created_by_user_id=None)
        if station is not None:
            record.runner_id = station.id
        self.bud.bud_add_to_app(record)
        return plaintext

    def upload(self, key, **extra):
        """Upload one result with a key."""
        p = self.parameters
        return self.bud.bud_request(
            p.POST, p.RESULTS_PATH, json={**p.KEYS_UPLOAD, **extra}, headers={p.API_KEY_HEADER: key}
        )

    def removed(self):
        """An administrator removes a station with a key and a run."""
        p = self.parameters
        self.bud.bud_start_app()
        station = self.station(p.KEYS_RETIRED)
        self.pin(station)
        run = self.bud.bud_add_to_app(
            TestRun(
                name="nightly", test_case_list="smoke", status="Completed", runner_id=station.id
            )
        )
        status = self.bud.bud_request(p.DELETE, p.STATION_PATH.format(station.account)).status_code
        surviving = self.bud.bud_find_in_app(TestRun, id=run.id)
        return {
            "status": status,
            "stations": len(self.bud.bud_find_in_app(Runner, account=p.KEYS_RETIRED)),
            "keys": len(self.bud.bud_find_in_app(RunnerApiKey, runner_id=station.id)),
            "run": (bool(surviving), type(surviving[0].runner_id).__name__ if surviving else None),
        }

    def minted(self):
        """An administrator mints a key and lists the keys."""
        p = self.parameters
        self.bud.bud_start_app()
        created = self.bud.bud_request(p.POST, p.API_KEYS_PATH, json={"label": p.KEYS_LABELS[0]})
        listed = self.bud.bud_request(p.GET, p.API_KEYS_PATH)
        return {
            "status": created.status_code,
            "secret": created.json().get("api_key") or "",
            "station": created.json().get("runner_account"),
            "listed status": listed.status_code,
            "rows": listed.json() if listed.status_code == 200 else [],
            "listed text": listed.text,
            "hashes": [record.key_hash for record in self.bud.bud_find_in_app(RunnerApiKey)],
        }

    def admin_revoke(self):
        """An administrator mints a key and revokes it twice."""
        p = self.parameters
        self.bud.bud_start_app()
        created = self.bud.bud_request(p.POST, p.API_KEYS_PATH, json={"label": p.KEYS_LABELS[1]})
        key_id = created.json().get("id")
        revoked = self.bud.bud_request(p.DELETE, p.API_KEY_PATH.format(key_id)).status_code
        return {
            "created": created.status_code,
            "revoked": revoked,
            "listed": self.bud.bud_request(p.GET, p.API_KEYS_PATH).json(),
            "stored": len(self.bud.bud_find_in_app(RunnerApiKey, id=key_id)),
            "again": self.bud.bud_request(p.DELETE, p.API_KEY_PATH.format(key_id)).status_code,
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    RunnerApiKeysTest().run()
