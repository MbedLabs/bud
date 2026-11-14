"""
* @file     ${tests/config.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Set-up of Bud's suites: their test-only settings and the guard on files and SMTP they may reach.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     Imported before any app module: the settings and the audit hook apply to the whole run.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

TEST_POSTGRES_PORT = 15432
TEST_SMTP_PORT = 11025
DEV_POSTGRES_PORTS = frozenset({5432, 5433, 5434})
DEV_SMTP_PORTS = frozenset({25, 465, 587, 1025, 2525, 8025})
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _test_smtp_port() -> int:
    """Return the dedicated Mailpit SMTP port, refusing privileged and local development ports."""
    raw = os.environ.get("TEST_SMTP_PORT", str(TEST_SMTP_PORT))
    if not raw.isdigit() or not 1024 < int(raw) < 65536 or int(raw) in DEV_SMTP_PORTS:
        raise RuntimeError("Tests require a dedicated test Mailpit port, not a local development port")
    return int(raw)


def _postgres_port_allowed(port: int | None) -> bool:
    """Return True for an explicit non-development PostgreSQL port."""
    return port is not None and 1024 < port < 65536 and port not in DEV_POSTGRES_PORTS


SMTP_PORT = _test_smtp_port()


def _isolate_test_environment() -> None:
    """Configure test-only application credentials and the unauthenticated test Mailpit."""
    from urllib.parse import urlparse

    from cryptography.fernet import Fernet

    database_url = os.environ.get("DATABASE_URL", "")
    if database_url:
        parsed = urlparse(database_url)
        if parsed.scheme.startswith("postgres") and (
            parsed.scheme not in {"postgres", "postgresql", "postgresql+asyncpg"}
            or parsed.hostname not in LOOPBACK_HOSTS
            or parsed.username != "test_user"
            or parsed.password != "test_password"
            or parsed.path != "/test_bud"
            or not _postgres_port_allowed(parsed.port)
            or parsed.query
            or parsed.fragment
        ):
            raise RuntimeError("Tests require the isolated test database and test credentials")
        if parsed.scheme.startswith("sqlite") and database_url not in {
            "sqlite:///:memory:",
            "sqlite+aiosqlite:///:memory:",
        }:
            raise RuntimeError("Tests require an in-memory SQLite database")
        if not parsed.scheme.startswith(("postgres", "sqlite")):
            raise RuntimeError("Tests require an isolated PostgreSQL or SQLite database")
    else:
        database_url = (
            f"postgresql+asyncpg://test_user:test_password@localhost:{TEST_POSTGRES_PORT}/test_bud"
        )

    values = {
        "DOTENV_DISABLED": "1",
        "SECRET_KEY": "test-secret-key-for-ci-at-least-32-characters-long",
        "SERVICE_TOKEN_PEPPER": "test-service-token-pepper-for-ci-at-least-32-characters-long",
        "INTEGRATION_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "RUNNER_API_KEY": "test-runner-api-key",
        "ADMIN_EMAIL": "admin@example.com",
        "ADMIN_PASSWORD": "ci-admin-password-123",
        "ADMIN_FULL_NAME": "CI Admin",
        "DATABASE_URL": database_url,
        "SMTP_ENABLED": "true",
        "SMTP_HOST": "127.0.0.1",
        "SMTP_PORT": str(SMTP_PORT),
        "SMTP_USERNAME": "",
        "SMTP_PASSWORD": "",
        "SMTP_FROM_EMAIL": "noreply@example.com",
        "SMTP_STARTTLS": "false",
        "SMTP_SSL": "false",
        "STORAGE_BACKEND": "local",
        "S3_BUCKET": "",
        "S3_ENDPOINT_URL": "",
        "S3_ACCESS_KEY_ID": "",
        "S3_SECRET_ACCESS_KEY": "",
        "APP_BASE_URL": "http://localhost:8001",
        "FRONTEND_BASE_URL": "http://localhost:8001",
        "AUTO_SEED_ADMIN": "true",
        "RUN_STARTUP_DATA_REPAIR": "false",
    }
    for key, value in values.items():
        for prefix in ("", "BUD_"):
            os.environ[prefix + key] = value
    for key in ("SMTP_REPLY_TO", "BUD_SMTP_REPLY_TO", "BUD_TESTS_USE_DOTENV"):
        os.environ.pop(key, None)
    for key in ("DB_USER", "DB_PASSWORD", "DB_NAME", "DB_HOST", "DB_PORT"):
        for prefix in ("", "BUD_"):
            os.environ.pop(prefix + key, None)
    for key in tuple(os.environ):
        if key.startswith("AWS_"):
            os.environ.pop(key, None)
    os.environ.update(
        {
            "AWS_ACCESS_KEY_ID": "test-access-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret-key",
            "AWS_SHARED_CREDENTIALS_FILE": "/dev/null",
            "AWS_CONFIG_FILE": "/dev/null",
            "AWS_EC2_METADATA_DISABLED": "true",
            "AWS_DEFAULT_REGION": "us-east-1",
        }
    )
    os.environ["APP_ENV"] = "development"
    os.environ["BUD_ENV"] = "development"


def _guard_test_smtp(event: str, args: tuple) -> None:
    """Reject operator dotenv reads, external SMTP and authentication payloads."""
    if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0]))
        if path.name == ".env" and path.absolute().parent.resolve() in Path(__file__).resolve().parents:
            raise PermissionError("Operator dotenv files are forbidden in tests")
    if event == "smtplib.connect":
        _, host, port = args
        if host not in LOOPBACK_HOSTS or port != SMTP_PORT:
            raise PermissionError(f"Tests may connect only to the test Mailpit on port {SMTP_PORT}")
    elif event == "smtplib.send":
        _, data = args
        command = data.lstrip().split(None, 1)
        if command and command[0].upper() == b"AUTH":
            raise PermissionError("SMTP authentication is forbidden in tests")


_isolate_test_environment()
sys.addaudithook(_guard_test_smtp)
