"""Release promotion regression checks, independent of a registry."""
import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location("image_release", Path(__file__).parents[1] / "scripts/image_release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
DIGEST = "sha256:" + "a" * 64
OTHER = "sha256:" + "b" * 64
IMAGE = "ghcr.io/mbedlabs/product@" + DIGEST


def test_older_release_does_not_move_floating_tags():
    aliases = ["image:v1.0.0", "image:1.0.0", "image:1", "image:1.0", "image:stable"]
    assert release.eligible_aliases(aliases, "refs/tags/v1.0.0", "v1.1.0") == aliases[:2]


def test_current_release_can_promote_stable():
    assert release.eligible_aliases(["image:stable"], "refs/tags/v1.1.0", "v1.1.0") == ["image:stable"]


def test_stale_branch_run_does_not_promote_latest():
    assert release.eligible_aliases(["image:latest"], "refs/heads/main", "v1.1.0", False) == []


def test_prerelease_does_not_promote_stable():
    assert release.eligible_aliases(["image:stable"], "refs/tags/v1.2.0-beta.1", "v1.1.0") == []


def test_version_conflict_aborts_before_any_alias_is_changed():
    execute = Mock()
    with pytest.raises(RuntimeError, match="Refusing to overwrite"):
        release.promote(IMAGE, ["image:stable", "image:1.1.0"], lambda _: OTHER, execute)
    execute.assert_not_called()


def test_repeated_promotion_preserves_digest():
    execute = Mock()
    release.promote(IMAGE, ["image:1.1.0", "image:stable"], lambda _: DIGEST, execute)
    assert execute.call_count == 2
    for call in execute.call_args_list:
        assert call.args[-1] == IMAGE


def test_post_promotion_digest_mismatch_fails():
    with pytest.raises(RuntimeError, match="Digest verification"):
        release.promote(IMAGE, ["image:stable"], lambda _: OTHER, Mock())
