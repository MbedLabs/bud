"""Release promotion regression checks, independent of a registry."""

import importlib.util
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location(
    "image_release", Path(__file__).parents[2] / "scripts/image_release.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
DIGEST = "sha256:" + "a" * 64
OTHER = "sha256:" + "b" * 64
REPOSITORY = "ghcr.io/mbedlabs/product"
IMAGE = REPOSITORY + "@" + DIGEST


def test_older_release_does_not_move_floating_tags():
    aliases = ["image:v1.0.0", "image:1.0.0", "image:1", "image:1.0", "image:stable"]
    assert release.eligible_aliases(aliases, "refs/tags/v1.0.0", "v1.1.0") == aliases[:2]


def test_current_release_can_promote_stable():
    assert release.eligible_aliases(["image:stable"], "refs/tags/v1.1.0", "v1.1.0") == [
        "image:stable"
    ]


def test_stale_branch_run_does_not_promote_latest():
    assert release.eligible_aliases(["image:latest"], "refs/heads/main", "v1.1.0", False) == []


def test_prerelease_does_not_promote_stable():
    assert release.eligible_aliases(["image:stable"], "refs/tags/v1.2.0-beta.1", "v1.1.0") == []


def test_version_conflict_aborts_before_any_alias_is_changed():
    execute = Mock()
    with pytest.raises(RuntimeError, match="Refusing to overwrite"):
        release.promote(
            IMAGE, [REPOSITORY + ":stable", REPOSITORY + ":1.1.0"], lambda _: OTHER, execute
        )
    execute.assert_not_called()


def test_repeated_promotion_preserves_digest():
    execute = Mock()
    release.promote(
        IMAGE, [REPOSITORY + ":1.1.0", REPOSITORY + ":stable"], lambda _: DIGEST, execute
    )
    assert execute.call_count == 2
    for call in execute.call_args_list:
        assert call.args[-1] == IMAGE


def test_post_promotion_digest_mismatch_fails():
    with pytest.raises(RuntimeError, match="Digest verification"):
        release.promote(IMAGE, [REPOSITORY + ":stable"], lambda _: OTHER, Mock())


@pytest.mark.parametrize(
    "reference",
    [
        "",
        "-v",
        "--format={{json .}}",
        "image:stable",
        "mbedlabs/product:1.1.0",
        "ghcr.io/MbedLabs/product:1.1.0",
        "ghcr.io/mbedlabs/product@sha256:abc",
        "ghcr.io/mbedlabs/product:sha-1@" + DIGEST,
        "ghcr.io/mbedlabs/product:1.1.0 --push",
        "ghcr.io/mbedlabs/product:-latest",
        "ghcr.io/mbedlabs/product/",
        None,
    ],
)
def test_digest_refuses_malformed_reference_before_calling_docker(monkeypatch, reference):
    docker = Mock()
    monkeypatch.setattr(release.subprocess, "run", docker)
    with pytest.raises(ValueError, match="Invalid image reference"):
        release.digest(reference)
    docker.assert_not_called()


@pytest.mark.parametrize(
    "reference",
    [
        REPOSITORY,
        REPOSITORY + ":sha-" + "0" * 40,
        REPOSITORY + ":v1.2.0",
        IMAGE,
        "localhost:5000/team/product_name:1.2.0-beta.1",
        "registry.example.com:443/a/b-c/d__e:latest",
    ],
)
def test_digest_inspects_a_registry_reference(monkeypatch, reference):
    docker = Mock(return_value=subprocess.CompletedProcess([], 0, stdout=DIGEST + "\n", stderr=""))
    monkeypatch.setattr(release.subprocess, "run", docker)
    assert release.digest(reference) == DIGEST
    assert docker.call_args.args[0][:5] == ["docker", "buildx", "imagetools", "inspect", reference]


@pytest.mark.parametrize(
    ("image", "aliases"),
    [
        (IMAGE, [REPOSITORY + ":stable", "-x"]),
        (IMAGE, ["image:stable"]),
        ("-" + REPOSITORY + "@" + DIGEST, [REPOSITORY + ":stable"]),
    ],
)
def test_promotion_refuses_malformed_reference_before_calling_docker(image, aliases):
    inspect, execute = Mock(), Mock()
    with pytest.raises(ValueError, match="Invalid image reference"):
        release.promote(image, aliases, inspect, execute)
    inspect.assert_not_called()
    execute.assert_not_called()
