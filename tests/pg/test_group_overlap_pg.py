"""A person holds any number of groups on real PostgreSQL: schema, duplicates and cascades."""

import asyncio
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import asyncpg
import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from tests.pg.conftest import unique_email, unique_name

pytestmark = pytest.mark.skipif(
    "postgres" not in os.environ.get("DATABASE_URL", ""),
    reason="requires a PostgreSQL DATABASE_URL (CI-only)",
)

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "ci-admin@example.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ci-admin-password-123")
TABLE = "access_group_members"
DUPLICATE = "The user already has this group"


def _database_url(driver: str) -> str:
    """The test database URL for the given driver prefix."""
    url = os.environ["DATABASE_URL"]
    for prefix in ("postgresql+asyncpg://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return f"{driver}://{url[len(prefix):]}"
    raise AssertionError("not a PostgreSQL URL")


def _count(sql: str, *args) -> int:
    """Run a counting query against the test database."""

    async def run() -> int:
        """Open one connection, fetch the count and close it."""
        connection = await asyncpg.connect(_database_url("postgresql"))
        try:
            return await connection.fetchval(sql, *args)
        finally:
            await connection.close()

    return asyncio.run(run())


def _rows_of_user(user_id: int) -> int:
    """How many membership rows the user has."""
    return _count(f"SELECT count(*) FROM {TABLE} WHERE user_id = $1", user_id)


def _rows_of_group(group_id: int) -> int:
    """How many membership rows the group has."""
    return _count(f"SELECT count(*) FROM {TABLE} WHERE group_id = $1", group_id)


def _admin(client) -> dict:
    """Sign in as the administrator and return the bearer header."""
    client.cookies.clear()
    response = client.post(
        "/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _person(client, headers, stem: str = "member") -> int:
    """Create a Developer and return its id."""
    response = client.post(
        "/api/users",
        json={
            "email": unique_email(stem),
            "full_name": unique_name("Member"),
            "password": "Member-Password-123",
            "role": "developer",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _group(client, headers, *policies: str) -> int:
    """Create a custom group bundling the named policies and return its id."""
    known = {row["name"]: row["id"] for row in client.get("/api/policies", headers=headers).json()}
    response = client.post(
        "/api/groups",
        json={"name": unique_name("Overlap"), "policy_ids": [known[name] for name in policies]},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _give(client, headers, group_id: int, user_id: int):
    """Give the user the group."""
    return client.post(
        f"/api/groups/{group_id}/members", json={"user_id": user_id}, headers=headers
    )


def test_membership_key_is_the_pair_and_nothing_is_unique_on_the_user_alone():
    """After the migrations the key is (group_id, user_id) and no unique rule covers user_id."""

    async def inspected():
        """Read the key, unique constraints and indexes of the membership table."""
        engine = create_async_engine(_database_url("postgresql+asyncpg"))
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

    key, uniques, indexes = asyncio.run(inspected())

    assert key["constrained_columns"] == ["group_id", "user_id"]
    assert not [u for u in uniques if u["column_names"] == ["user_id"]]
    assert not [i for i in indexes if i["unique"] and i["column_names"] == ["user_id"]]


def test_two_groups_make_two_rows_and_the_same_pair_again_is_refused(client):
    """One person given two groups has two rows; giving one of them again answers 409."""
    headers = _admin(client)
    person = _person(client, headers)
    first = _group(client, headers, "Results")
    second = _group(client, headers, "Results", "Products")

    assert _give(client, headers, first, person).status_code == 201
    assert _give(client, headers, second, person).status_code == 201
    assert _rows_of_user(person) == 2

    again = _give(client, headers, first, person)

    assert (again.status_code, again.json()) == (409, {"detail": DUPLICATE})
    assert _rows_of_user(person) == 2


def test_two_simultaneous_identical_assignments_give_one_created_and_one_conflict(client):
    """Two requests released together for the same pair answer 201 and 409 and leave one row."""
    headers = _admin(client)
    person = _person(client, headers)
    group = _group(client, headers, "Results")
    barrier = threading.Barrier(2)

    def assign():
        """Wait for the other request, then give the group."""
        barrier.wait()
        return _give(client, headers, group, person).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = sorted(f.result() for f in [pool.submit(assign), pool.submit(assign)])

    assert codes == [201, 409], codes
    assert _rows_of_user(person) == 1


def test_deleting_a_group_or_a_user_removes_only_their_own_rows(client):
    """A custom group's deletion drops its rows only; a user's deletion drops that user's rows."""
    headers = _admin(client)
    leaving = _person(client, headers, "leaving")
    staying = _person(client, headers, "staying")
    doomed = _group(client, headers, "Results")
    kept = _group(client, headers, "Results", "Products")
    for group in (doomed, kept):
        for person in (leaving, staying):
            assert _give(client, headers, group, person).status_code == 201
    assert (_rows_of_group(doomed), _rows_of_group(kept)) == (2, 2)

    assert client.delete(f"/api/groups/{doomed}", headers=headers).status_code == 204
    assert (_rows_of_group(doomed), _rows_of_group(kept)) == (0, 2)
    assert (_rows_of_user(leaving), _rows_of_user(staying)) == (1, 1)

    assert client.delete(f"/api/users/{leaving}", headers=headers).status_code == 204
    assert (_rows_of_user(leaving), _rows_of_user(staying)) == (0, 1)
    assert _rows_of_group(kept) == 1
