"""Test bootstrap credential and SMTP isolation in fresh Python processes."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TEST_DATABASE = "test_bud"


def run_bootstrap(code, extra_env=None):
    """Load pytest configuration with synthetic inherited credentials and no dotenv reads."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "PYTHONPATH", "HOME", "LANG"}
    }
    for prefix in ("", "BUD_"):
        env.update(
            {
                prefix + "SECRET_KEY": "synthetic-inherited-secret-key-at-least-32-characters",
                prefix + "SMTP_HOST": "smtp.example.com",
                prefix + "SMTP_USERNAME": "synthetic-user",
                prefix + "SMTP_PASSWORD": "synthetic-password",
                prefix + "S3_ACCESS_KEY_ID": "synthetic-access",
                prefix + "S3_SECRET_ACCESS_KEY": "synthetic-storage-secret",
                prefix + "ADMIN_PASSWORD": "synthetic-admin-password",
            }
        )
    env["BUD_TESTS_USE_DOTENV"] = "1"
    env["BUD_DOTENV_DISABLED"] = "0"
    env["CONFTEST_PATH"] = str(ROOT / "tests" / "conftest.py")
    env["BUD_DATABASE_URL"] = "postgresql://synthetic:synthetic@db.example.com/live"
    env.update(extra_env or {})
    script = (
        """
import json, os, runpy, smtplib, socket, sys
from pathlib import Path
original_read = Path.read_text
def safe_read(path, *args, **kwargs):
    if path.name == '.env':
        raise PermissionError('Operator dotenv reads are forbidden')
    return original_read(path, *args, **kwargs)
Path.read_text = safe_read
runpy.run_path(os.environ['CONFTEST_PATH'])
"""
        + code
    )
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def test_bootstrap_replaces_inherited_credentials_and_disables_dotenv():
    observed = json.loads(
        run_bootstrap(
            """
keys = ['SECRET_KEY', 'SMTP_HOST', 'SMTP_USERNAME', 'SMTP_PASSWORD', 'S3_ACCESS_KEY_ID', 'S3_SECRET_ACCESS_KEY', 'ADMIN_PASSWORD']
print(json.dumps({prefix + key: os.environ.get(prefix + key) for prefix in ('', 'BUD_') for key in keys} | {'dotenv': os.environ.get('BUD_DOTENV_DISABLED')}))
"""
        )
    )
    assert observed["dotenv"] == "1"
    for prefix in ("", "BUD_"):
        assert (
            observed[prefix + "SECRET_KEY"] == "test-secret-key-for-ci-at-least-32-characters-long"
        )
        assert observed[prefix + "SMTP_HOST"] == "127.0.0.1"
        assert observed[prefix + "SMTP_USERNAME"] == ""
        assert observed[prefix + "SMTP_PASSWORD"] == ""
        assert observed[prefix + "S3_ACCESS_KEY_ID"] == ""
        assert observed[prefix + "S3_SECRET_ACCESS_KEY"] == ""
        assert observed[prefix + "ADMIN_PASSWORD"] == "ci-admin-password-123"


def test_external_smtp_is_blocked_before_network_connection():
    outcome = run_bootstrap(
        """
def attempted(*args, **kwargs):
    raise RuntimeError('Network connection was attempted')
socket.create_connection = attempted
try:
    smtplib.SMTP('smtp.example.com', 587)
except PermissionError:
    print('blocked before network')
"""
    )
    assert outcome == "blocked before network"


def test_smtp_auth_is_blocked_before_credential_transmission():
    outcome = run_bootstrap(
        """
try:
    sys.audit('smtplib.send', smtplib.SMTP(), b'AUTH PLAIN synthetic')
except PermissionError:
    print('blocked before credentials')
"""
    )
    assert outcome == "blocked before credentials"


def test_mailpit_connection_is_allowed_by_guard():
    assert (
        run_bootstrap(
            "sys.audit('smtplib.connect', smtplib.SMTP(), '127.0.0.1', 1025); print('allowed')"
        )
        == "allowed"
    )


def test_unsafe_database_is_rejected_without_exposing_its_url():
    with pytest.raises(subprocess.CalledProcessError) as failure:
        run_bootstrap(
            "",
            {"DATABASE_URL": "postgresql://synthetic-user:synthetic-password@db.example.com/live"},
        )
    assert "Tests require the isolated test database" in failure.value.stderr
    assert "synthetic-password" not in failure.value.stderr
    assert "db.example.com" not in failure.value.stderr


def test_operator_dotenv_reads_are_blocked_even_if_flags_are_changed():
    outcome = run_bootstrap(
        """
try:
    sys.audit('open', str(Path.cwd() / '.env'), 'r', 0)
except PermissionError:
    print('operator dotenv blocked')
"""
    )
    assert outcome == "operator dotenv blocked"


@pytest.mark.parametrize(
    "suffix", ["?host=db.example.com", "?password=synthetic-password", "#fragment", "?port=5433"]
)
def test_database_connection_overrides_are_rejected(suffix):
    database = TEST_DATABASE
    with pytest.raises(subprocess.CalledProcessError):
        run_bootstrap(
            "",
            {
                "DATABASE_URL": f"postgresql+asyncpg://test_user:test_password@localhost:5432/{database}{suffix}"
            },
        )


def test_ambient_aws_credentials_are_replaced():
    output = run_bootstrap(
        """
import boto3
credentials = boto3.Session().get_credentials()
print(json.dumps({'access_key': credentials.access_key, 'secret_key': credentials.secret_key, 'source': credentials.method, 'credentials_file': os.environ.get('AWS_SHARED_CREDENTIALS_FILE'), 'config_file': os.environ.get('AWS_CONFIG_FILE'), 'metadata_disabled': os.environ.get('AWS_EC2_METADATA_DISABLED')}))
""",
        {
            "AWS_ACCESS_KEY_ID": "synthetic-inherited-access",
            "AWS_SECRET_ACCESS_KEY": "synthetic-inherited-secret",
            "AWS_SESSION_TOKEN": "synthetic-inherited-session",
        },
    )
    assert json.loads(output) == {
        "access_key": "test-access-key",
        "secret_key": "test-secret-key",
        "source": "env",
        "credentials_file": "/dev/null",
        "config_file": "/dev/null",
        "metadata_disabled": "true",
    }


def test_settings_disable_dotenv_before_source_construction():
    output = run_bootstrap(
        """
import tempfile
from app.core.config import Settings
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / '.env'
    path.write_text('SECRET_KEY=synthetic-file-secret-key-at-least-32-characters\\n')
    opened = []
    sys.addaudithook(lambda event, args: opened.append(args[0]) if event == 'open' and str(args[0]) == str(path) else None)
    Settings(_env_file=path)
    print('dotenv source opened' if opened else 'dotenv source not opened')
"""
    )
    assert output == "dotenv source not opened"


def test_enabled_dotenv_reads_the_file_so_the_detector_is_sound():
    output = run_bootstrap(
        """
import os, tempfile
from pydantic_settings import BaseSettings, SettingsConfigDict
class Probe(BaseSettings):
    model_config = SettingsConfigDict(extra='ignore')
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / '.env'
    path.write_text('SYNTHETIC=1\\n')
    opened = []
    sys.addaudithook(lambda event, args: opened.append(args[0]) if event == 'open' and str(args[0]) == str(path) else None)
    Probe(_env_file=path)
    print('dotenv source opened' if opened else 'dotenv source not opened')
"""
    )
    assert output == "dotenv source opened"


def test_rate_limiter_does_not_read_a_dotenv_in_the_working_directory():
    output = run_bootstrap(
        """
import tempfile
from slowapi import Limiter
from slowapi.util import get_remote_address
with tempfile.TemporaryDirectory() as directory:
    sys.path.insert(0, os.getcwd())
    os.chdir(directory)
    path = Path(directory).resolve() / '.env'
    path.write_text('SYNTHETIC=1\\n')
    opened = []
    sys.addaudithook(lambda event, args: opened.append(args[0]) if event == 'open' and Path(str(args[0])).name == '.env' and Path(str(args[0])).resolve() == path else None)
    Limiter(key_func=get_remote_address)
    control = bool(opened)
    opened.clear()
    from app.core.deps import limiter
    print(json.dumps({'control_reads_dotenv': control, 'app_limiter_reads_dotenv': bool(opened)}))
"""
    )
    assert json.loads(output) == {"control_reads_dotenv": True, "app_limiter_reads_dotenv": False}


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite+aiosqlite:////tmp/operator.db",
        "postgresql+psycopg://test_user:test_password@localhost:5432/test_bud",
    ],
)
def test_non_test_database_paths_or_drivers_are_rejected(database_url):
    with pytest.raises(subprocess.CalledProcessError):
        run_bootstrap("", {"DATABASE_URL": database_url})
