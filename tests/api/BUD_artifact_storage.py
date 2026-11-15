"""
* @file     ${tests/api/BUD_artifact_storage.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Uploads reserve only a run's remaining quota, one at a time and at a limited rate;
*           the cleanup removes expired artifacts, old orphan files and expired leases.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests each scenario on a fresh app database with its own settings.
"""

import os
from datetime import datetime, timezone
from unittest import mock

from app.core.config import settings
from app.models import Artifact, UploadAttempt, UploadLease
from app.models.user import User, UserRole
from app.services import artifact_cleanup, artifact_storage
from tests.api.artifact_storage import ArtifactStorageBase


class ArtifactStorageTest(ArtifactStorageBase):

    def setUpClass(self):
        super().setUpClass()
        p, run, attempt = self.parameters, self.bud.bud_await, self.bud.bud_attempt
        limits = {
            "MAX_UPLOAD_SIZE": p.UPLOAD_MAX_SIZE,
            "MAX_RUN_UPLOAD_BYTES": p.UPLOAD_MAX_RUN_BYTES,
        }
        with mock.patch.multiple(settings, **limits):
            db = self.fresh_session()
            self.bud.bud_add_to_app(Artifact(**p.UPLOAD_EXISTING))
            self.tc_lease = attempt(
                lambda: run(
                    artifact_storage.reserve_upload(
                        db, self.uploader(), test_run_id=p.UPLOAD_RUN_ID
                    )
                )
            )
            db = self.fresh_session()
            first = run(artifact_storage.reserve_upload(db, self.uploader(), test_run_id=None))
            self.tc_second_upload = attempt(
                lambda: run(artifact_storage.reserve_upload(db, self.uploader(), test_run_id=None))
            )
            run(artifact_storage.release_upload(db, first.id))
        with mock.patch.object(settings, "UPLOADS_PER_15_MINUTES", p.UPLOADS_PER_WINDOW):
            db = self.fresh_session()
            for _ in range(p.UPLOADS_PER_WINDOW):
                lease = run(artifact_storage.reserve_upload(db, self.uploader(), test_run_id=None))
                run(artifact_storage.release_upload(db, lease.id))
            self.tc_third_upload = attempt(
                lambda: run(artifact_storage.reserve_upload(db, self.uploader(), test_run_id=None))
            )
        self.cleanup()

    def cleanup(self):
        """Run the cleanup over an expired artifact, an old orphan, an expired lease and attempt."""
        p, run = self.parameters, self.bud.bud_await
        db = self.fresh_session()
        folder = self.bud.bud_work_folder()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        orphan = folder / p.CLEANUP_ORPHAN
        orphan.write_bytes(p.CLEANUP_ORPHAN_BYTES)
        old = (now - p.CLEANUP_ORPHAN_AGE).replace(tzinfo=timezone.utc).timestamp()
        os.utime(orphan, (old, old))
        expired = folder / p.CLEANUP_EXPIRED
        expired.write_bytes(p.CLEANUP_EXPIRED_BYTES)
        settings_used = {
            "UPLOAD_DIR": str(folder),
            "ARTIFACT_RETENTION_DAYS": p.CLEANUP_RETENTION_DAYS,
        }
        with mock.patch.multiple(settings, **settings_used):
            self.bud.bud_add_to_app(
                Artifact(
                    filename=p.CLEANUP_EXPIRED,
                    original_filename=p.CLEANUP_EXPIRED,
                    content_type=p.LOGO_TEXT_TYPE,
                    size_bytes=len(p.CLEANUP_EXPIRED_BYTES),
                    storage_path=p.CLEANUP_EXPIRED,
                    created_at=now - p.CLEANUP_EXPIRED_AGE,
                )
            )
            self.bud.bud_add_to_app(
                UploadLease(
                    id=p.CLEANUP_LEASE,
                    principal_key=p.CLEANUP_PRINCIPAL,
                    reserved_bytes=p.CLEANUP_LEASE_BYTES,
                    expires_at=now - p.CLEANUP_LEASE_AGE,
                )
            )
            self.bud.bud_add_to_app(
                UploadAttempt(
                    principal_key=p.CLEANUP_PRINCIPAL, created_at=now - p.CLEANUP_ATTEMPT_AGE
                )
            )
            self.tc_report = run(
                artifact_cleanup.reconcile_artifacts(
                    db, orphan_grace_seconds=p.CLEANUP_GRACE_SECONDS
                )
            )
        self.tc_expired_file_left = expired.exists()
        self.tc_orphan_left = orphan.exists()
        self.tc_lease_left = (self.bud.bud_find_in_app(UploadLease, id=p.CLEANUP_LEASE) or [None])[
            0
        ]

    def fresh_session(self):
        """A session on a freshly started app's database."""
        self.bud.bud_start_app()
        return self.bud.bud_open_session(on_app=True)

    def uploader(self):
        """The administrator who uploads."""
        return User(**self.parameters.UPLOADER, role=UserRole.admin, is_active=True)

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    ArtifactStorageTest().run()
