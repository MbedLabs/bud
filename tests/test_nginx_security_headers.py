"""Every location must carry the security headers, not just the ones that forget to override.

nginx inherits `add_header` from an outer level only when the current level
declares no `add_header` of its own. Every location that set a Cache-Control
header therefore dropped the four security headers defined on the server block -
including `location = /index.html`, which is the document the
Content-Security-Policy exists to protect and which every SPA deep link resolves
to through `try_files`.

Checked against nginx 1.24 before the fix: `/`, `/index.html`, `/runs`,
`/runtime-config.js` and `/assets/*` carried none of the four, while `/api/*` -
a location with no `add_header` of its own - carried all four. The policy
applied to JSON responses and to nothing else.

The failure mode is silent: the config is valid, nginx starts, every page loads.
So this reads the config as a document and fails when a location sets a header
without pulling the shared file back in.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

DOCKER_DIR = Path(__file__).resolve().parents[1] / "docker"
NGINX_CONF = DOCKER_DIR / "nginx.conf"
HEADERS_CONF = DOCKER_DIR / "security-headers.conf"
DOCKERFILE = Path(__file__).resolve().parents[1] / "Dockerfile"

REQUIRED_HEADERS = (
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Permissions-Policy",
    "Content-Security-Policy",
)


def _locations() -> list[tuple[str, str]]:
    """Each `location` block in the config, as (header line, body).

    A brace counter rather than a regex: the bodies are one level deep, and a
    regex for balanced braces is the kind of cleverness that fails quietly.
    """
    text = NGINX_CONF.read_text()
    blocks: list[tuple[str, str]] = []
    for match in re.finditer(r"^\s*(location[^\n{]*)\{", text, re.MULTILINE):
        start = match.end()
        depth = 1
        index = start
        while index < len(text) and depth:
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
            index += 1
        blocks.append((match.group(1).strip(), text[start : index - 1]))
    return blocks


def test_the_shared_header_file_exists_and_holds_all_four():
    source = HEADERS_CONF.read_text()

    for header in REQUIRED_HEADERS:
        assert f'add_header {header} ' in source, header


def test_every_header_is_marked_always():
    """Without `always` the header is dropped on 4xx and 5xx responses."""
    for line in HEADERS_CONF.read_text().splitlines():
        if line.strip().startswith("add_header"):
            assert line.rstrip().endswith("always;"), line.strip()


def test_the_server_block_includes_the_shared_file():
    text = NGINX_CONF.read_text()
    # Everything before the first location *block* - matched the same way the
    # blocks themselves are, so the word "location" in a comment is not it.
    first = re.search(r"^\s*location[^\n{]*\{", text, re.MULTILINE)
    server_head = text[: first.start()] if first else text

    assert "include /etc/nginx/security-headers.conf;" in server_head


@pytest.mark.parametrize("location,body", _locations(), ids=lambda value: str(value)[:40])
def test_a_location_that_sets_a_header_re_includes_the_shared_file(location, body):
    """The inheritance rule, enforced.

    A location with no `add_header` inherits the server block's and is fine. One
    that sets any header of its own - a Cache-Control, a Pragma - silently loses
    all four and has to pull them back in.
    """
    if "add_header" not in body:
        return

    assert "include /etc/nginx/security-headers.conf;" in body, (
        f"`{location}` sets a header of its own, so nginx will not inherit the "
        f"security headers here. Add `include /etc/nginx/security-headers.conf;`."
    )


def test_the_csp_still_forbids_inline_script():
    source = HEADERS_CONF.read_text()
    csp = next(
        line for line in source.splitlines() if "Content-Security-Policy" in line and "add_header" in line
    )

    assert "script-src 'self'" in csp
    assert "unsafe-inline" not in csp.split("script-src")[1].split(";")[0]
    assert "frame-ancestors 'self'" in csp


def test_the_image_ships_the_shared_file():
    """A config that includes a file the image does not carry will not start."""
    dockerfile = DOCKERFILE.read_text()

    assert "docker/security-headers.conf /etc/nginx/security-headers.conf" in dockerfile
