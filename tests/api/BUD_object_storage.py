"""
* @file     ${tests/api/BUD_object_storage.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Run artifacts are stored in S3 with a local mirror, cleaned up and migrated.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests against moto's in-process S3, each scenario on a fresh app and bucket.
"""

import contextlib
import io
from datetime import datetime, timezone
from unittest import mock

from moto import mock_aws

from app import storage as storage_cli
from app.api import uploads
from app.core.config import Settings, settings
from app.models import Artifact
from app.services import artifact_cleanup, artifact_storage, object_store
from tests.api.object_storage import ObjectStorageBase


class ObjectStorageTest(ObjectStorageBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.tc_round_trip = self.on_s3(self.round_trip)
        self.tc_unmirrored = self.on_s3(self.unmirrored)
        self.tc_refused = self.on_s3(self.refused)
        self.tc_read_stored = self.on_s3(self.read_stored)
        self.tc_cleanup = self.on_s3(self.cleanup)
        self.tc_migrations = self.on_s3(self.migrations)
        self.tc_command_codes, self.tc_command_output = self.on_s3(self.command)
        self.tc_readiness = self.on_s3(self.readiness)
        self.tc_no_bucket = self.bud.bud_attempt(
            lambda: Settings(STORAGE_BACKEND="s3", S3_BUCKET="")
        )
        self.tc_prefix = Settings(STORAGE_BACKEND="s3", S3_BUCKET="b").S3_PREFIX

    def on_s3(self, scenario):
        """Run one scenario on a fresh app whose storage is a fresh moto bucket."""
        self.bud.bud_start_app()
        self.bud.bud_add_test_station()
        object_store.client.cache_clear()
        try:
            with mock.patch.multiple(settings, **self.parameters.S3_SETTINGS), mock_aws():
                object_store.client().create_bucket(Bucket=self.parameters.S3_BUCKET)
                return scenario(object_store.client())
        finally:
            object_store.client.cache_clear()

    def keys(self, s3):
        """The keys of the bucket's objects."""
        return sorted(
            item["Key"]
            for item in s3.list_objects_v2(Bucket=self.parameters.S3_BUCKET).get("Contents", [])
        )

    def upload(self, name=None, data=None):
        """Upload evidence as the test station."""
        p = self.parameters
        return self.bud.bud_station_upload(
            name or p.S3_EVIDENCE_NAME, io.BytesIO(data or p.S3_EVIDENCE), p.LOGO_TEXT_TYPE
        )

    def round_trip(self, s3):
        """Upload, download, lose the bucket copy, lose the mirror and delete."""
        p, request = self.parameters, self.bud.bud_request
        uploaded = self.upload()
        artifact = uploaded.json()
        stored = uploads.get_upload_root() / artifact.get("filename", "")
        found = {
            "uploaded": uploaded.status_code,
            "keys": self.keys(s3),
            "expected keys": [p.S3_KEY.format(artifact.get("filename"))],
            "mirrored": stored.exists(),
        }
        path = p.UPLOAD_PATH.format(artifact.get("id"))
        downloaded = request(p.GET, path)
        found.update(
            {
                "downloaded": downloaded.status_code,
                "content": downloaded.content,
                "disposition": downloaded.headers.get("content-disposition", ""),
                "policy": downloaded.headers.get("content-security-policy"),
            }
        )
        s3.delete_object(Bucket=p.S3_BUCKET, Key=p.S3_KEY.format(artifact.get("filename")))
        fallback = request(p.GET, path)
        found["fallback"] = (fallback.status_code, fallback.content)
        if stored.exists():
            stored.unlink()
        found["unreachable"] = request(p.GET, path).status_code
        found["deleted"] = request(p.DELETE, path).status_code
        return found

    def unmirrored(self, s3):
        """Upload and delete without the local mirror."""
        p, request = self.parameters, self.bud.bud_request
        with mock.patch.object(settings, "STORAGE_LOCAL_MIRROR", False):
            uploaded = self.upload()
            artifact = uploaded.json()
            path = p.UPLOAD_PATH.format(artifact.get("id"))
            return {
                "uploaded": uploaded.status_code,
                "mirrored": (uploads.get_upload_root() / artifact.get("filename", "")).exists(),
                "content": request(p.GET, path).content,
                "deleted": request(p.DELETE, path).status_code,
                "keys": self.keys(s3),
            }

    def refused(self, s3):
        """Upload to a bucket that does not exist."""
        p = self.parameters
        with mock.patch.object(settings, "S3_BUCKET", p.S3_OTHER_BUCKET):
            status = self.upload(p.S3_REFUSED_NAME, p.S3_REFUSED_DATA).status_code
        files = [path.name for path in uploads.get_upload_root().iterdir() if path.is_file()]
        return {"status": status, "files": files}

    def read_stored(self, s3):
        """Read a file from the mirror, then from the bucket, then a missing one twice."""
        p, run = self.parameters, self.bud.bud_await
        root = uploads.ensure_upload_dir()
        (root / p.S3_READ_NAME).write_bytes(p.S3_LOCAL_BYTES)
        found = [run(artifact_storage.read_stored(root, p.S3_READ_NAME))]
        run(artifact_storage.persist(root / p.S3_READ_NAME, p.S3_READ_NAME, p.LOGO_TEXT_TYPE))
        s3.put_object(
            Bucket=p.S3_BUCKET, Key=p.S3_KEY.format(p.S3_READ_NAME), Body=p.S3_BUCKET_BYTES
        )
        found.append(run(artifact_storage.read_stored(root, p.S3_READ_NAME)))
        with mock.patch.object(settings, "STORAGE_LOCAL_MIRROR", False):
            found.append(type(run(artifact_storage.read_stored(root, p.S3_MISSING_NAME))).__name__)
            with mock.patch.object(settings, "STORAGE_BACKEND", "local"):
                found.append(
                    type(run(artifact_storage.read_stored(root, p.S3_MISSING_NAME))).__name__
                )
        return found

    def cleanup(self, s3):
        """Reconcile a kept, an orphan and an expired file and an artifact whose file is missing."""
        p, run = self.parameters, self.bud.bud_await
        root = uploads.ensure_upload_dir()
        for name in p.S3_CLEANUP_FILES:
            (root / name).write_bytes(p.S3_REFUSED_DATA)
            run(artifact_storage.persist(root / name, name, p.LOGO_TEXT_TYPE))
        expired_at = datetime.now(timezone.utc).replace(tzinfo=None) - p.CLEANUP_EXPIRED_AGE
        for name, original, created_at in (
            (p.S3_KEPT, p.S3_KEPT, None),
            (*p.S3_MISSING, None),
            (p.S3_OLD, p.S3_OLD, expired_at),
        ):
            self.bud.bud_add_to_app(
                Artifact(
                    filename=name,
                    original_filename=original,
                    content_type=p.LOGO_TEXT_TYPE,
                    size_bytes=1,
                    storage_path=name,
                    **({"created_at": created_at} if created_at else {}),
                )
            )
        db = self.bud.bud_open_session(on_app=True)
        with mock.patch.object(settings, "ARTIFACT_RETENTION_DAYS", p.CLEANUP_RETENTION_DAYS):
            report = run(
                artifact_cleanup.reconcile_artifacts(db, orphan_grace_seconds=p.S3_GRACE_SECONDS)
            )
        return {
            "expired": report.expired_artifacts,
            "keys": self.keys(s3),
            "missing": report.missing_files,
            "old left": (root / p.S3_OLD).exists(),
        }

    def migrations(self, s3):
        """Migrate twice, then again with one size the bucket reports wrongly."""
        p, run = self.parameters, self.bud.bud_await
        root = uploads.ensure_upload_dir()
        for name, data in p.S3_MIGRATE_FILES.items():
            (root / name).write_bytes(data)
        (root / p.S3_PARTIAL[0]).write_bytes(p.S3_PARTIAL[1])
        found = [run(storage_cli.migrate_to_s3()), run(storage_cli.migrate_to_s3())]
        real = object_store.size_of
        (root / p.S3_MISMATCHED[0]).write_bytes(p.S3_MISMATCHED[1])

        async def wrong(name):
            return 1 if name == p.S3_MISMATCHED[0] else await real(name)

        with mock.patch.object(object_store, "size_of", wrong):
            found.append(run(storage_cli.migrate_to_s3()))
        return [(copied, present, list(mismatched)) for copied, present, mismatched in found]

    def command(self, s3):
        """Run the migrate command when it copies, when sizes mismatch and without a bucket."""
        p = self.parameters
        output = io.StringIO()

        async def done():
            return p.S3_COMMAND_DONE

        async def mismatch():
            return p.S3_COMMAND_MISMATCH

        codes = []
        with contextlib.redirect_stdout(output):
            with mock.patch.object(storage_cli, "migrate_to_s3", done):
                codes.append(storage_cli.main(p.S3_MIGRATE_ARGUMENTS))
            with mock.patch.object(storage_cli, "migrate_to_s3", mismatch):
                codes.append(storage_cli.main(p.S3_MIGRATE_ARGUMENTS))
                with mock.patch.object(settings, "S3_BUCKET", ""):
                    codes.append(storage_cli.main(p.S3_MIGRATE_ARGUMENTS))
        return codes, output.getvalue()

    def readiness(self, s3):
        """Readiness on the bucket, on a missing bucket and on local storage."""
        p = self.parameters
        storage = [self.bud.bud_request(p.GET, p.READY_PATH).json().get("storage")]
        with mock.patch.object(settings, "S3_BUCKET", p.S3_OTHER_BUCKET):
            storage.append(self.bud.bud_request(p.GET, p.READY_PATH).json().get("storage"))
            with mock.patch.object(settings, "STORAGE_BACKEND", "local"):
                storage.append(self.bud.bud_request(p.GET, p.READY_PATH).json().get("storage"))
        return storage

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ObjectStorageTest().run()
