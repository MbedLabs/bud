"""Fixtures for the real-PostgreSQL integration suite.

Unlike ``tests/`` (which forces SQLite and overrides ``get_db`` / auth with an
admin), this suite runs the app unmodified against the alembic-built PostgreSQL
schema: real login, real JWTs, real database I/O, no dependency overrides.

It is a separate directory precisely so ``tests/conftest.py`` (which pins SQLite
at import time) never applies here. CI runs it as its own ``pytest tests_pg/``
invocation with ``DATABASE_URL`` pointing at PostgreSQL.
"""

import os

import pytest
from fastapi.testclient import TestClient

REQUIRES_PG_REASON = "tests_pg requires a PostgreSQL DATABASE_URL (CI-only)"


def _is_postgres() -> bool:
    return "postgres" in os.environ.get("DATABASE_URL", "")


@pytest.fixture(scope="session")
def client():
    if not _is_postgres():
        pytest.skip(REQUIRES_PG_REASON)
    # Import lazily so a non-PG local run skips before the app/engine is built.
    from app.main import app

    # Entering the context runs the lifespan: with RUN_STARTUP_DATA_REPAIR=false
    # the schema must already exist (built by the empty-DB alembic step), and
    # AUTO_SEED_ADMIN=true seeds the admin this suite logs in as.
    with TestClient(app) as test_client:
        yield test_client
