"""The image starts as root only for preparation and hands every process to appuser."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
START_SH = ROOT / "docker" / "start.sh"
SUPERVISORD_CONF = ROOT / "docker" / "supervisord.conf"
DOCKERFILE = ROOT / "Dockerfile"


def _commands(path: Path) -> list[str]:
    """Non-empty lines of a file, stripped."""
    return [line.strip() for line in path.read_text().splitlines() if line.strip()]


def test_start_script_hands_supervisord_to_appuser():
    """The last command of start.sh replaces the shell with supervisord run as appuser."""
    lines = _commands(START_SH)
    assert lines[-1] == 'exec gosu "$APP_USER" /usr/local/bin/supervisord -c /etc/supervisord.conf'
    assert lines.count('exec gosu "$APP_USER" /usr/local/bin/supervisord -c /etc/supervisord.conf') == 1
    assert "APP_USER=appuser" in lines


def test_start_script_makes_container_output_writable_for_appuser():
    """Descriptors 1 and 2 are chowned to appuser where they are not writable for appuser."""
    text = START_SH.read_text()
    assert "for fd in 1 2; do" in text
    assert 'if ! gosu "$APP_USER" test -w "/proc/self/fd/$fd"; then' in text
    assert 'chown "$APP_UID:$APP_GID" "/proc/self/fd/$fd"' in text
    assert text.index("for fd in 1 2; do") < text.index('exec gosu "$APP_USER" /usr/local/bin/supervisord')


def test_start_script_chowns_cloudron_data_recursively():
    """On Cloudron every file under /app/data is given to appuser before the app starts."""
    text = START_SH.read_text()
    cloudron_block = text[text.index('if [ -n "${CLOUDRON_APP_ORIGIN:-}" ]; then') : text.index("\nelse\n")]
    assert 'chown -R "$APP_UID:$APP_GID" /app/data' in cloudron_block
    assert cloudron_block.index('chown -R "$APP_UID:$APP_GID" /app/data') < cloudron_block.index(
        'gosu "$APP_USER" alembic upgrade head'
    )


def test_supervisord_does_not_run_as_root():
    """supervisord has no root user setting and keeps its pid file in the appuser runtime folder."""
    lines = _commands(SUPERVISORD_CONF)
    assert "user=root" not in lines
    assert "pidfile=/run/bud/supervisord.pid" in lines


def test_dockerfile_keeps_root_start_and_drops_the_nginx_user_directive():
    """The image starts as root, and nginx.conf keeps no user directive for the appuser master."""
    text = DOCKERFILE.read_text()
    assert re.search(r"^USER root$", text, re.MULTILINE)
    assert "user appuser;" not in text
    assert "-e '/^[[:space:]]*user[[:space:]]/d'" in text
