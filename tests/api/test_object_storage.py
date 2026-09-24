"""S3 storage for run artifacts, against moto's in-process S3.

Covers upload and download over HTTP with the bucket and its local mirror, the
fallback when the bucket loses a file, publishing and deleting, retention and orphan
cleanup of the bucket, and the migrate command.
"""

import io

import pytest
from moto import mock_aws

from app import storage as storage_cli
from app.api import uploads
from app.core.config import Settings, settings
from app.services import artifact_cleanup, artifact_storage, object_store

BUCKET = "bud-test"


@pytest.fixture
def s3(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    for name, value in {
        "STORAGE_BACKEND": "s3",
        "STORAGE_LOCAL_MIRROR": True,
        "S3_BUCKET": BUCKET,
        "S3_REGION": "us-east-1",
        "S3_PREFIX": "bud",
        "S3_ENDPOINT_URL": "",
        "UPLOAD_DIR": str(tmp_path / "uploads"),
    }.items():
        monkeypatch.setattr(settings, name, value)
    monkeypatch.setattr(uploads, "_UPLOAD_ROOT", None)
    object_store.client.cache_clear()
    with mock_aws():
        object_store.client().create_bucket(Bucket=BUCKET)
        yield object_store.client()
    object_store.client.cache_clear()


def _keys(client):
    return sorted(o["Key"] for o in client.list_objects_v2(Bucket=BUCKET).get("Contents", []))


def _upload(client, name="trace.txt", data=b"evidence"):
    response = client.post("/api/uploads", files={"file": (name, io.BytesIO(data), "text/plain")})
    assert response.status_code == 201, response.text
    return response.json()


def test_upload_and_download_through_the_bucket(client, s3):
    artifact = _upload(client)
    stored = uploads.get_upload_root() / artifact["filename"]
    assert _keys(s3) == [f"bud/{artifact['filename']}"] and stored.exists()

    downloaded = client.get(f"/api/uploads/{artifact['id']}")
    assert downloaded.status_code == 200 and downloaded.content == b"evidence"
    assert downloaded.headers["content-disposition"].startswith("attachment;")
    assert downloaded.headers["content-security-policy"] == "sandbox"

    s3.delete_object(Bucket=BUCKET, Key=f"bud/{artifact['filename']}")
    fallback = client.get(f"/api/uploads/{artifact['id']}")
    assert fallback.status_code == 200 and fallback.content == b"evidence"

    stored.unlink()
    assert client.get(f"/api/uploads/{artifact['id']}").status_code == 503

    assert client.delete(f"/api/uploads/{artifact['id']}").status_code == 204


def test_without_the_mirror_only_the_bucket_holds_it(client, s3, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_LOCAL_MIRROR", False)
    artifact = _upload(client)
    assert not (uploads.get_upload_root() / artifact["filename"]).exists()
    assert client.get(f"/api/uploads/{artifact['id']}").content == b"evidence"
    assert client.delete(f"/api/uploads/{artifact['id']}").status_code == 204
    assert _keys(s3) == []


def test_a_refused_upload_leaves_nothing(client, s3, monkeypatch):
    monkeypatch.setattr(settings, "S3_BUCKET", "no-such-bucket")
    response = client.post(
        "/api/uploads", files={"file": ("t.txt", io.BytesIO(b"x"), "text/plain")}
    )
    assert response.status_code == 503
    assert [p for p in uploads.get_upload_root().iterdir() if p.is_file()] == []


async def test_read_stored_prefers_the_bucket_then_the_mirror(s3, monkeypatch):
    root = await uploads.ensure_upload_dir()
    (root / "r.txt").write_bytes(b"local")
    assert await artifact_storage.read_stored(root, "r.txt") == b"local"
    await artifact_storage.persist(root / "r.txt", "r.txt", "text/plain")
    s3.put_object(Bucket=BUCKET, Key="bud/r.txt", Body=b"bucket")
    assert await artifact_storage.read_stored(root, "r.txt") == b"bucket"
    monkeypatch.setattr(settings, "STORAGE_LOCAL_MIRROR", False)
    assert await artifact_storage.read_stored(root, "gone.txt") is None
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    assert await artifact_storage.read_stored(root, "gone.txt") is None


async def test_cleanup_reconciles_the_bucket(s3, db_session, monkeypatch):
    from datetime import datetime, timedelta

    from app.models import Artifact

    root = await uploads.ensure_upload_dir()
    for name in ("kept.txt", "orphan.txt", "old.txt"):
        (root / name).write_bytes(b"x")
        await artifact_storage.persist(root / name, name, "text/plain")
    db_session.add_all(
        [
            Artifact(
                filename="kept.txt",
                original_filename="kept.txt",
                content_type="text/plain",
                size_bytes=1,
                storage_path="kept.txt",
            ),
            Artifact(
                filename="missing.txt",
                original_filename="m.txt",
                content_type="text/plain",
                size_bytes=1,
                storage_path="missing.txt",
            ),
            Artifact(
                filename="old.txt",
                original_filename="old.txt",
                content_type="text/plain",
                size_bytes=1,
                storage_path="old.txt",
                created_at=datetime.utcnow() - timedelta(days=settings.ARTIFACT_RETENTION_DAYS + 1),
            ),
        ]
    )
    await db_session.commit()

    report = await artifact_cleanup.reconcile_artifacts(db_session, orphan_grace_seconds=-60)
    assert report.expired_artifacts == 1
    assert _keys(s3) == ["bud/kept.txt"]
    assert report.missing_files == 1
    assert not (root / "old.txt").exists()


async def test_migrate_copies_once_and_checks_sizes(s3, monkeypatch):
    root = await uploads.ensure_upload_dir()
    (root / "m1.txt").write_bytes(b"one")
    (root / "m2.txt").write_bytes(b"two two")
    (root / ".upload-x.part").write_bytes(b"partial")
    assert await storage_cli.migrate_to_s3() == (2, 0, [])
    assert await storage_cli.migrate_to_s3() == (0, 2, [])
    real = object_store.size_of
    (root / "m3.txt").write_bytes(b"three")

    async def wrong(name):
        return 1 if name == "m3.txt" else await real(name)

    monkeypatch.setattr(object_store, "size_of", wrong)
    assert await storage_cli.migrate_to_s3() == (0, 2, ["m3.txt"])


def test_migrate_command(s3, monkeypatch, capsys):
    async def done():
        return (1, 2, [])

    async def mismatch():
        return (0, 0, ["x.txt"])

    monkeypatch.setattr(storage_cli, "migrate_to_s3", done)
    assert storage_cli.main(["migrate", "--to", "s3"]) == 0
    assert "copied 1, already there 2, size mismatches 0" in capsys.readouterr().out
    monkeypatch.setattr(storage_cli, "migrate_to_s3", mismatch)
    assert storage_cli.main(["migrate", "--to", "s3"]) == 1
    monkeypatch.setattr(settings, "S3_BUCKET", "")
    assert storage_cli.main(["migrate", "--to", "s3"]) == 2


def test_readiness_names_the_storage(client, s3, monkeypatch):
    assert client.get("/api/ready").json()["storage"] == "s3"
    monkeypatch.setattr(settings, "S3_BUCKET", "no-such-bucket")
    assert client.get("/api/ready").json()["storage"] == "s3-unreachable"
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    assert client.get("/api/ready").json()["storage"] == "local"


def test_s3_needs_a_bucket():
    with pytest.raises(ValueError, match="needs S3_BUCKET"):
        Settings(STORAGE_BACKEND="s3", S3_BUCKET="")
    assert Settings(STORAGE_BACKEND="s3", S3_BUCKET="b").S3_PREFIX == "bud"
