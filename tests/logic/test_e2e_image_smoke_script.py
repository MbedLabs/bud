import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "e2e_image_smoke.sh"


def test_admin_full_name_remains_one_docker_environment_argument(tmp_path):
    docker_log = tmp_path / "docker-argv.jsonl"
    fake_docker = tmp_path / "docker"
    fake_docker.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
with open(os.environ["DOCKER_ARGV_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\\n")

# `alembic current` is run before the app boots; emit a head marker so the
# migration-completeness check passes and the script proceeds to the app run.
if "current" in args:
    print("0123456789ab (head)")
    sys.exit(0)

if args and args[0] == "run" and "--name" in args:
    name = args[args.index("--name") + 1]
    if name.startswith("bud-e2e-app-"):
        sys.exit(23)
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)

    env = os.environ.copy()
    env["DOCKER_ARGV_LOG"] = str(docker_log)
    env["PATH"] = f"{tmp_path}{os.pathsep}{env['PATH']}"

    subprocess.run(
        ["bash", str(SCRIPT), "ghcr.io/mbedlabs/bud:test"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    calls = [json.loads(line) for line in docker_log.read_text().splitlines()]
    app_run = next(
        call
        for call in calls
        if call[:3] == ["run", "-d", "--name"] and call[3].startswith("bud-e2e-app-")
    )
    assert "ADMIN_FULL_NAME=E2E Admin" in app_run


def test_evidence_upload_uses_station_credentials_and_its_own_run(tmp_path):
    """Run the smoke script with station-owned uploads and rejected human uploads."""
    docker = tmp_path / "docker"
    docker.write_text(
        """#!/usr/bin/env python3
import sys
args = sys.argv[1:]
if args[0] == "port":
    print("127.0.0.1:18080")
elif "current" in args:
    print("017_release120 (head)")
"""
    )
    curl = tmp_path / "curl"
    curl.write_text(
        """#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from urllib.parse import urlparse
args = sys.argv[1:]
url = next(arg for arg in args if arg.startswith("http://"))
path = urlparse(url).path
headers = [args[i + 1] for i, arg in enumerate(args) if arg == "-H"]
fields = [args[i + 1] for i, arg in enumerate(args) if arg == "-F"]
station = "Authorization: Bearer station-fixture-token" in headers
admin = "Authorization: Bearer admin-fixture-token" in headers
if path == "/api/health":
    print('{"status":"healthy"}')
elif path == "/api/ready":
    print('{"status":"ready","database":"connected"}')
elif path == "/api/version":
    root = Path(sys.argv[0]).parent
    print(json.dumps({"version": (root / "version").read_text()}))
elif path == "/api/auth/login":
    print('{"access_token":"admin-fixture-token"}')
elif path == "/api/products":
    assert admin
    print('[]')
elif path == "/api/runners/api-keys":
    assert admin
    print('{"api_key":"enrolment-fixture-key"}')
elif path == "/api/runners/register":
    assert "X-API-Key: enrolment-fixture-key" in headers
    print('{"token":"station-fixture-token"}')
elif path == "/api/test-runs":
    assert station
    print('{"id":7}')
elif path == "/api/uploads":
    if admin:
        if "-w" not in args:
            sys.exit(22)
        print("403", end="")
    else:
        assert station
        assert "run_id=7" in fields
        print('{"id":9}')
elif path == "/api/uploads/info/9":
    assert admin
    print('{"id":9}')
elif path == "/api/uploads/9":
    assert admin
    Path(args[args.index("-o") + 1]).write_bytes(b"A" * 2097152)
else:
    raise AssertionError(path)
"""
    )
    docker.chmod(0o755)
    curl.chmod(0o755)
    import tomllib

    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    (tmp_path / "version").write_text(version)
    env = {**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"}
    result = subprocess.run(
        ["bash", str(SCRIPT), "ghcr.io/mbedlabs/bud:test"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "verified sha256" in result.stdout
    assert "PASS: Bud published image" in result.stdout
