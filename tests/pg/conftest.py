"""Fixtures for the real-PostgreSQL integration suite."""

import os
import secrets

import pytest
from fastapi.testclient import TestClient

REQUIRES_PG_REASON = "tests/pg requires a PostgreSQL DATABASE_URL"


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
    """Session-wide TestClient on the real PostgreSQL database with the login rate limiter disabled."""
    if not _is_postgres():
        pytest.skip(REQUIRES_PG_REASON)
    from app.core.deps import limiter
    from app.main import app

    limiter.enabled = False
    with TestClient(app) as test_client:
        yield test_client
