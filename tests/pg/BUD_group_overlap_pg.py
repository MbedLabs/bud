"""
* @file     ${tests/pg/BUD_group_overlap_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Memberships are keyed by group and person; a repeat is refused and deletions drop only their own rows.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module reads the membership table directly next to the live app.
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor

import asyncpg
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from tests.pg.group_overlap_pg import GroupOverlapPgBase

TABLE = "access_group_members"
DUPLICATE = "The user already has this group"


def database_url(driver):
    """The test database address for a driver."""
    url = os.environ["DATABASE_URL"]
    for prefix in ("postgresql+asyncpg://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return f"{driver}://{url[len(prefix):]}"
    return url


class GroupOverlapPgTest(GroupOverlapPgBase):

    def setUpClass(self):
        super().setUpClass()
        self.client = self.bud.bud_start_live_app()
        self.tc_checks = {"schema": self.schema(), "duplicates": self.duplicates(), "race": self.race(), "cascades": self.cascades()}

    def count(self, sql, *args):
        """Run one counting query on the test database."""

        async def run():
            connection = await asyncpg.connect(database_url("postgresql"))
            try:
                return await connection.fetchval(sql, *args)
            finally:
                await connection.close()

        return self.bud.bud_await(run())

    def rows_of_user(self, user_id):
        return self.count(f"SELECT count(*) FROM {TABLE} WHERE user_id = $1", user_id)

    def rows_of_group(self, group_id):
        return self.count(f"SELECT count(*) FROM {TABLE} WHERE group_id = $1", group_id)

    def admin(self):
        """The administrator's bearer header and the checks of the sign-in."""
        login, headers = self.bud.bud_live_bearer()
        self.setup_statuses = [login]
        return headers

    def person(self, headers, stem="member"):
        """Create a developer and return its id."""
        response = self.client.post(
            "/api/users",
            json={
                "email": self.bud.bud_unique(stem) + "@example.com",
                "full_name": self.bud.bud_unique("Member"),
                "password": "Member-Password-123",
                "role": "developer",
            },
            headers=headers,
        )
        self.setup_statuses.append(response.status_code)
        return response.json().get("id") if response.status_code == 201 else 0

    def group(self, headers, *policies):
        """Create a custom group bundling the named policies and return its id."""
        listed = self.client.get("/api/policies", headers=headers)
        rows = listed.json() if listed.status_code == 200 else []
        known = {row.get("name"): row.get("id") for row in rows if isinstance(row, dict)}
        response = self.client.post(
            "/api/groups", json={"name": self.bud.bud_unique("Overlap"), "policy_ids": [known.get(name) for name in policies]}, headers=headers
        )
        self.setup_statuses.append(response.status_code)
        return response.json().get("id") if response.status_code == 201 else 0

    def give(self, headers, group_id, user_id):
        return self.client.post(f"/api/groups/{group_id}/members", json={"user_id": user_id}, headers=headers)

    def setup_check(self):
        """The check that the sign-in and every creation succeeded."""
        return {"the setup succeeds": (self.setup_statuses[0] == 200 and set(self.setup_statuses[1:]) == {201}, True)}

    def schema(self):
        async def inspected():
            engine = create_async_engine(database_url("postgresql+asyncpg"))
            try:
                async with engine.connect() as connection:
                    return await connection.run_sync(
                        lambda sync: (
                            inspect(sync).get_pk_constraint(TABLE),
                            inspect(sync).get_unique_constraints(TABLE),
                            inspect(sync).get_indexes(TABLE),
                        )
                    )
            finally:
                await engine.dispose()

        key, uniques, indexes = self.bud.bud_await(inspected())
        return {
            "the key is the group and the person": (key.get("constrained_columns"), ["group_id", "user_id"]),
            "no unique rule covers the person alone": ([u for u in uniques if u["column_names"] == ["user_id"]], []),
            "no unique index covers the person alone": ([i for i in indexes if i["unique"] and i["column_names"] == ["user_id"]], []),
        }

    def duplicates(self):
        headers = self.admin()
        person = self.person(headers)
        first = self.group(headers, "Results")
        second = self.group(headers, "Results", "Products")
        given = [self.give(headers, first, person).status_code, self.give(headers, second, person).status_code]
        rows = self.rows_of_user(person)
        again = self.give(headers, first, person)
        try:
            body = again.json()
        except ValueError:
            body = {}
        return {
            **self.setup_check(),
            "both groups are given": (given, [201, 201]),
            "the person has two rows": (rows, 2),
            "a repeat is a conflict": ((again.status_code, body), (409, {"detail": DUPLICATE})),
            "the person still has two rows": (self.rows_of_user(person), 2),
        }

    def race(self):
        headers = self.admin()
        person = self.person(headers)
        group = self.group(headers, "Results")
        barrier = threading.Barrier(2)

        def assign():
            barrier.wait()
            return self.give(headers, group, person).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            codes = sorted(f.result() for f in [pool.submit(assign), pool.submit(assign)])
        return {
            **self.setup_check(),
            "one is created and one conflicts": (codes, [201, 409]),
            "one row is left": (self.rows_of_user(person), 1),
        }

    def cascades(self):
        headers = self.admin()
        leaving = self.person(headers, "leaving")
        staying = self.person(headers, "staying")
        doomed = self.group(headers, "Results")
        kept = self.group(headers, "Results", "Products")
        given = [self.give(headers, group, person).status_code for group in (doomed, kept) for person in (leaving, staying)]
        before = (self.rows_of_group(doomed), self.rows_of_group(kept))
        group_deleted = self.client.delete(f"/api/groups/{doomed}", headers=headers).status_code
        after_group = (self.rows_of_group(doomed), self.rows_of_group(kept))
        people_after_group = (self.rows_of_user(leaving), self.rows_of_user(staying))
        user_deleted = self.client.delete(f"/api/users/{leaving}", headers=headers).status_code
        return {
            **self.setup_check(),
            "every membership is given": (given, [201] * 4),
            "both groups hold two rows": (before, (2, 2)),
            "the group is deleted": (group_deleted, 204),
            "only the deleted group's rows go": (after_group, (0, 2)),
            "each person keeps one row": (people_after_group, (1, 1)),
            "the person is deleted": (user_deleted, 204),
            "only the deleted person's rows go": ((self.rows_of_user(leaving), self.rows_of_user(staying)), (0, 1)),
            "the kept group holds one row": (self.rows_of_group(kept), 1),
        }

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    GroupOverlapPgTest().run()
