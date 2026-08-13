"""Fixtures for the real-PostgreSQL integration suite.

Unlike ``tests/`` (which forces SQLite and overrides ``get_db`` / auth with an
admin), this suite runs the app unmodified against the alembic-built PostgreSQL
schema: real login, real JWTs, real database I/O, no dependency overrides.

It is a separate directory precisely so ``tests/conftest.py`` (which pins SQLite
at import time) never applies here. CI runs it as its own ``pytest tests_pg/``
invocation with ``DATABASE_URL`` pointing at PostgreSQL.
"""

import os
import secrets

import pytest
from fastapi.testclient import TestClient

REQUIRES_PG_REASON = "tests_pg requires a PostgreSQL DATABASE_URL (CI-only)"


def unique_suffix() -> str:
    """A short token unique to this call."""
    return secrets.token_hex(4)


def unique_email(stem: str = "user", domain: str = "example.com") -> str:
    """A fresh address per call.

    Email is unique per row, so a test that hardcodes one passes against an
    empty database and fails on every later run with "Email already
    registered". CI never noticed because it gets a new service container each
    time, but it makes the suite unrunnable twice against the same database and
    hides real failures behind collisions. Product names are unique the same
    way; see ``unique_name``.
    """
    return f"{stem}-{unique_suffix()}@{domain}"


def unique_name(stem: str) -> str:
    return f"{stem} {unique_suffix()}"


@pytest.fixture
def make_email():
    """Factory so a test can mint as many distinct addresses as it needs."""
    return unique_email


def _is_postgres() -> bool:
    return "postgres" in os.environ.get("DATABASE_URL", "")


@pytest.fixture(scope="session")
def client():
    if not _is_postgres():
        pytest.skip(REQUIRES_PG_REASON)
    # Import lazily so a non-PG local run skips before the app/engine is built.
    from app.core.deps import limiter
    from app.main import app

    # This suite drives many real logins across a single client IP within a
    # minute; the login rate limiter (10/min) is not what these flows test, so
    # disable it here to avoid cross-test 429s. Rate limiting has its own tests.
    limiter.enabled = False

    # Entering the context runs the lifespan: with RUN_STARTUP_DATA_REPAIR=false
    # the schema must already exist (built by the empty-DB alembic step), and
    # AUTO_SEED_ADMIN=true seeds the admin this suite logs in as.
    with TestClient(app) as test_client:
        yield test_client
