import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "cloudron" / "CloudronManifest.json"
DESCRIPTION = ROOT / "cloudron" / "DESCRIPTION.md"


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
