"""Fixtures for the real-PostgreSQL integration suite."""

import os
import secrets

import pytest
from fastapi.testclient import TestClient

REQUIRES_PG_REASON = "tests_pg requires a PostgreSQL DATABASE_URL (CI-only)"


def unique_suffix() -> str:
    """A short token unique to this call."""
    return secrets.token_hex(4)


def unique_email(stem: str = "user", domain: str = "example.com") -> str:
    """A fresh address per call."""
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

    # This suite drives many real logins across a single client IP within a minute; the
    # login rate limiter (10/min) is not what these flows test, so disable it here to
    # avoid cross-test 429s.
    limiter.enabled = False

    # Entering the context runs the lifespan: with RUN_STARTUP_DATA_REPAIR=false
    # the schema must already exist (built by the empty-DB alembic step), and
    # AUTO_SEED_ADMIN=true seeds the admin this suite logs in as.
    with TestClient(app) as test_client:
        yield test_client
