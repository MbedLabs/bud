"""
* @file     ${tests/pg/application_policies_pg.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    This module tests users' application policies on PostgreSQL: the schema, repeats, simultaneous changes and cascades.
* @author   Amine El Omari
* @date     2026-11-18
* @version  1.0.0
* @note     Base class containing the bud methods of the checks against the live app and its database.
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor

import asyncpg
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from tests.bud_test_base import BudAppTestCase


def database_url(driver):
    """The test database address for a driver."""
    url = os.environ["DATABASE_URL"]
    for prefix in ("postgresql+asyncpg://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return f"{driver}://{url[len(prefix):]}"
    return url


class ApplicationPoliciesPgBase(BudAppTestCase):

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
        """How many application policies the user holds."""
        return self.count(
            f"SELECT count(*) FROM {self.parameters.APG_TABLE} WHERE user_id = $1", user_id
        )

    def person(self, stem="member"):
        """Create a developer through the live app and return its id."""
        response = self.client.post(
            self.parameters.APG_USERS_PATH,
            json={
                "email": self.bud.bud_unique(stem) + "@example.com",
                "full_name": self.bud.bud_unique("Member"),
                "password": self.parameters.APG_PASSWORD,
                "role": "developer",
            },
            headers=self.headers,
        )
        return (
            response.json().get("id")
            if response.status_code == self.parameters.STATUS_CREATED
            else 0
        )

    def policy_ids(self, *names):
        """The ids of the policies with these names."""
        listed = self.client.get(self.parameters.POLICIES_PATH, headers=self.headers).json()
        known = {row.get("name"): row.get("id") for row in listed if isinstance(row, dict)}
        return [known.get(name) for name in names]

    def set_policies(self, user_id, policy_ids):
        """Set the user's application policies through the live app."""
        return self.client.put(
            self.parameters.APG_PATH.format(user_id),
            json={"policy_ids": policy_ids},
            headers=self.headers,
        )

    def bud_the_key_is_the_person_and_the_policy(self):
        p = self.parameters

        async def inspected():
            engine = create_async_engine(database_url("postgresql+asyncpg"))
            try:
                async with engine.connect() as connection:
                    return await connection.run_sync(
                        lambda sync: (
                            inspect(sync).get_pk_constraint(p.APG_TABLE),
                            inspect(sync).get_foreign_keys(p.APG_TABLE),
                        )
                    )
            finally:
                await engine.dispose()

        key, foreign = self.bud.bud_await(inspected())
        cascades = sorted(
            (fk["referred_table"], fk.get("options", {}).get("ondelete")) for fk in foreign
        )
        self.print_variables({"key": key, "foreign keys": cascades})
        self.assertEqual(
            key.get("constrained_columns"), ["user_id", "policy_id"], msg=p.MSG_APG_KEY
        )
        self.assertEqual(cascades, p.APG_CASCADES, msg=p.MSG_APG_CASCADES)

    def bud_two_policies_make_two_rows_and_a_repeat_keeps_them(self):
        p = self.parameters
        person = self.person()
        ids = self.policy_ids(*p.APG_TWO_POLICIES)
        given = self.set_policies(person, ids).status_code
        rows = self.rows_of_user(person)
        again = self.set_policies(person, ids).status_code
        named_twice = self.set_policies(person, [ids[0], ids[0]]).status_code
        self.print_variables({"given": given, "rows": rows, "again": again, "twice": named_twice})
        self.assertEqual((given, rows), (p.STATUS_OK, 2), msg=p.MSG_APG_TWO_ROWS)
        self.assertEqual((again, self.rows_of_user(person)), (p.STATUS_OK, 2), msg=p.MSG_APG_REPEAT)
        self.assertEqual(named_twice, p.STATUS_UNPROCESSABLE, msg=p.MSG_APG_NAMED_TWICE)

    def bud_simultaneous_identical_changes_leave_one_row(self):
        p = self.parameters
        person = self.person()
        ids = self.policy_ids(p.APG_ONE_POLICY)
        barrier = threading.Barrier(2)

        def change():
            barrier.wait()
            return self.set_policies(person, ids).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            codes = sorted(f.result() for f in [pool.submit(change), pool.submit(change)])
        self.print_variables({"codes": codes, "rows": self.rows_of_user(person)})
        self.assertEqual(codes, [p.STATUS_OK, p.STATUS_OK], msg=p.MSG_APG_RACE_CODES)
        self.assertEqual(self.rows_of_user(person), 1, msg=p.MSG_APG_RACE_ROWS)

    def bud_deleting_a_person_removes_only_their_rows(self):
        p = self.parameters
        leaving, staying = self.person("leaving"), self.person("staying")
        ids = self.policy_ids(*p.APG_TWO_POLICIES)
        given = [self.set_policies(person, ids).status_code for person in (leaving, staying)]
        deleted = self.client.delete(
            p.APG_USER_PATH.format(leaving), headers=self.headers
        ).status_code
        left = (self.rows_of_user(leaving), self.rows_of_user(staying))
        self.print_variables({"given": given, "deleted": deleted, "left": left})
        self.assertEqual(given, [p.STATUS_OK, p.STATUS_OK], msg=p.MSG_APG_GIVEN)
        self.assertEqual(deleted, p.STATUS_NO_CONTENT, msg=p.MSG_APG_PERSON_DELETED)
        self.assertEqual(left, (0, 2), msg=p.MSG_APG_ONLY_THEIR_ROWS)

    def bud_a_held_policy_is_kept_until_taken_away(self):
        p = self.parameters
        person = self.person()
        created = self.client.post(
            p.POLICIES_PATH,
            json={
                "name": self.bud.bud_unique(p.APG_CUSTOM_POLICY),
                "permissions": p.APG_CUSTOM_PERMISSIONS,
            },
            headers=self.headers,
        ).json()
        self.set_policies(person, [created.get("id")])
        refused = self.client.delete(
            f"{p.POLICIES_PATH}/{created.get('id')}", headers=self.headers
        ).status_code
        self.set_policies(person, [])
        deleted = self.client.delete(
            f"{p.POLICIES_PATH}/{created.get('id')}", headers=self.headers
        ).status_code
        self.assertEqual(
            (refused, deleted), (p.STATUS_CONFLICT, p.STATUS_NO_CONTENT), msg=p.MSG_APG_HELD_KEPT
        )
