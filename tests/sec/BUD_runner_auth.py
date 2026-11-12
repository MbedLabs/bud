"""
* @file     ${tests/sec/BUD_runner_auth.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Station tokens are accepted expired only with a recent heartbeat; odd tokens are refused.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests the authentication services on a fresh app database for each scenario.
"""

from datetime import datetime, timezone
from unittest import mock

from fastapi import HTTPException

from app.api import auth, results
from app.core import runner_auth
from app.core.runner_keys import mint_key
from app.core.security import create_access_token, decode_access_token
from app.models import Runner
from app.models.user import User, UserRole
from tests.sec.runner_auth import RunnerAuthBase


def now():
    """The current UTC time without its zone."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def type_name(value):
    """The type name of a value."""
    return type(value).__name__


async def refusal(check):
    """The status code of the HTTPException a check raises, or the type name of what it returns."""
    try:
        return type_name(await check)
    except HTTPException as error:
        return error.status_code


async def entity(check):
    """The type name and account of the entity a check returns, or the status code it raises."""
    try:
        found = await check
    except HTTPException as error:
        return error.status_code
    return type_name(found), getattr(found, "account", None)


class RunnerAuthTest(RunnerAuthBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        token = self.station_token("station-expired", expired=True)
        self.tc_ignore_exp = {
            "checked": type_name(decode_access_token(token)),
            "claims": {
                key: (runner_auth.decode_access_token_ignore_exp(token) or {}).get(key)
                for key in ("sub", "type")
            },
            "expected": {"sub": "station-expired", "type": p.RUNNER_TYPE},
        }
        self.tc_heartbeat = self.scenario(self.heartbeat)
        self.tc_uploader = self.scenario(self.uploader)
        self.tc_rotated = self.scenario(self.rotated)
        with mock.patch.object(
            runner_auth.settings, "RUNNER_HEARTBEAT_TIMEOUT", p.RUNNER_HEARTBEAT_TIMEOUT
        ):
            station = Runner(
                account="hb",
                password_hash="x",
                token="hb-token",
                last_heartbeat=now() - p.RUNNER_STALE_AGE,
            )
            stale = runner_auth.runner_has_recent_heartbeat(station)
            station.last_heartbeat = now()
            self.tc_timeout = (stale, runner_auth.runner_has_recent_heartbeat(station))
        self.tc_types = self.scenario(self.types)
        self.tc_stale_user = self.stale_user()

    def station_token(self, account, expired=False, **claims):
        """A station token, expired when asked."""
        expiry = {"expires_delta": self.parameters.RUNNER_EXPIRED} if expired else {}
        return create_access_token(
            {"sub": account, "type": self.parameters.RUNNER_TYPE, **claims}, **expiry
        )

    @staticmethod
    async def add(db, row):
        """Store a row through the scenario's session."""
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row

    async def station(self, db, account, token, heartbeat=None):
        """Store an active station."""
        return await self.add(
            db,
            Runner(
                account=account,
                password_hash="x",
                token=token,
                is_active=True,
                last_heartbeat=heartbeat,
            ),
        )

    def scenario(self, run):
        """Run one scenario on a fresh app database session."""
        self.bud.bud_start_app()
        return self.bud.bud_await(run(self.bud.bud_open_session(on_app=True)))

    async def heartbeat(self, db):
        """Expired tokens of a station without and with a recent heartbeat."""
        stale = self.station_token("station-stale", expired=True)
        await self.station(db, "station-stale", stale)
        live = self.station_token("station-live", expired=True)
        await self.station(db, "station-live", live, heartbeat=now())
        authed = await runner_auth.authenticate_runner_token(live, db)
        return {
            "stale": type_name(await runner_auth.authenticate_runner_token(stale, db)),
            "live": getattr(authed, "account", None),
            "live account": "station-live",
        }

    async def uploader(self, db):
        """Uploaders with an expired token, a pinned key and an unpinned key."""
        token = self.station_token("uploader-station", expired=True)
        await self.station(db, "uploader-station", token, heartbeat=now())
        by_token = await entity(results.get_uploader_entity(db=db, token=token, x_api_key=None))
        keyed = await self.station(db, "api-key-station", "stored-runner-token")
        record, pinned = mint_key(label="api-key-station key", created_by_user_id=None)
        record.runner_id = keyed.id
        await self.add(db, record)
        by_key = await entity(results.get_uploader_entity(db=db, token=None, x_api_key=pinned))
        unused, plaintext = mint_key(label="unused", created_by_user_id=None)
        await self.add(db, unused)
        return {
            "jwt": by_token,
            "jwt account": "uploader-station",
            "key": by_key,
            "key account": keyed.account,
            "unpinned": await refusal(
                results.get_uploader_entity(db=db, token=None, x_api_key=plaintext)
            ),
        }

    async def rotated(self, db):
        """The previous token of a station whose token was rotated."""
        old = self.station_token("station-rotated")
        current = self.station_token("station-rotated", jti="new")
        await self.station(db, "station-rotated", current, heartbeat=now())
        return (
            type_name(await runner_auth.authenticate_runner_token(old, db)),
            type_name(await runner_auth.authenticate_runner_token(current, db)),
        )

    async def types(self, db):
        """Tokens of an unknown type and without a type."""
        p = self.parameters
        if await db.get(User, 1) is None:
            await self.add(
                db,
                User(
                    id=1,
                    email="admin@example.com",
                    full_name="Admin",
                    hashed_password="x",
                    role=UserRole.admin,
                    is_active=True,
                ),
            )
        await self.station(db, p.RUNNER_NUMERIC_ACCOUNT, "stored-token")
        odd = create_access_token({"sub": p.RUNNER_NUMERIC_ACCOUNT, "type": p.RUNNER_ODD_TYPE})
        viewer = await self.add(
            db,
            User(
                email="viewer@example.com",
                full_name="Viewer",
                hashed_password="x",
                role=UserRole.viewer,
                is_active=True,
            ),
        )
        untyped = create_access_token({"sub": str(viewer.id)})
        return {
            "entity": await refusal(auth.get_current_active_entity(token=odd, db=db)),
            "uploader": await refusal(
                results.get_uploader_entity(db=db, token=odd, x_api_key=None)
            ),
            "untyped": await refusal(auth.get_current_active_entity(token=untyped, db=db)),
        }

    def stale_user(self):
        """A person's token issued before their session version changed."""
        p = self.parameters
        self.bud.bud_start_app(signed_in=False)
        user = self.bud.bud_add_to_app(
            User(
                email="stale-uploader@example.com",
                full_name="Stale Uploader",
                hashed_password="x",
                role=UserRole.admin,
                is_active=True,
                session_version=2,
            )
        )
        token = create_access_token({"sub": str(user.id), "type": "user", "ver": 1})
        response = self.bud.bud_request(
            p.POST,
            p.RESULTS_PATH,
            json={"results": []},
            headers={"Authorization": f"Bearer {token}"},
        )
        return {"status": response.status_code, "detail": str(response.json().get("detail"))}

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    RunnerAuthTest().run()
