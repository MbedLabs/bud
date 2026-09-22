import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "cloudron" / "CloudronManifest.json"
DESCRIPTION = ROOT / "cloudron" / "DESCRIPTION.md"


def _version_tuple(value):
    return tuple(int(part) for part in value.split("."))


def test_cloudron_metadata_uses_canonical_product_positioning():
    manifest = json.loads(MANIFEST.read_text())
    description = DESCRIPTION.read_text().strip()

    assert manifest["title"] == "Bud TMP by EmbedLabs"
    assert manifest["tagline"] == "Automated software, hardware and system testing"
    assert description == (
        "Bud TMP by EmbedLabs provides test management and execution for automated "
        "software, hardware and system testing."
    )
    assert "embedded" not in json.dumps(manifest).lower()
    assert "embedded" not in description.lower()
    assert "self-hosted" not in description.lower()


def test_cloudron_release_metadata_matches_product_version():
    manifest = json.loads(MANIFEST.read_text())
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert manifest["version"] == version
    assert manifest["upstreamVersion"] == version
    changelog = (ROOT / "cloudron" / "CHANGELOG").read_text()
    # The changelog may open with a prerelease entry for the next, unreleased
    # version; what must hold is that the shipped version has its own section.
    assert f"[{version}]\n" in changelog
    top = changelog.splitlines()[0]
    match = re.fullmatch(r"\[(\d+(?:\.\d+){0,2})[^\]]*\]", top)
    assert match, f"changelog must open with a version header, got {top!r}"
    assert _version_tuple(match.group(1)) >= _version_tuple(version)
