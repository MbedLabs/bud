import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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
        if call[:3] == ["run", "-d", "--name"]
        and call[3].startswith("bud-e2e-app-")
    )
    assert "ADMIN_FULL_NAME=E2E Admin" in app_run
