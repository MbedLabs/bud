"""
* @file     ${tests/api/BUD_run_artifacts_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    A run lists only its own files, and the allowlist decides what evidence reaches Bud.
* @author   Amine El Omari
* @date     2026-11-11
* @version  1.0.0
* @note     This module tests two runs with their files, a file attached to no run and station uploads.
"""

import io
from datetime import datetime, timedelta, timezone

from app.api import uploads
from app.core.config import settings
from app.models import Artifact, TestRun
from tests.api.run_artifacts_api import RunArtifactsApiBase


class RunArtifactsApiTest(RunArtifactsApiBase):

    def setUpClass(self):
        super().setUpClass()
        p, request = self.parameters, self.bud.bud_request
        self.bud.bud_start_app()
        self.bud.bud_add_test_station(with_run=False)
        runs = {
            key: self.bud.bud_add_to_app(
                TestRun(name=name, test_case_list=p.ARTIFACT_CASE_LIST, status="Completed")
            )
            for key, name in zip(("run", "other"), p.ARTIFACT_RUNS)
        }
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for (
            filename,
            original,
            content_type,
            size,
            digest,
            test_case,
            run,
            minutes,
        ) in p.ARTIFACT_ROWS:
            self.bud.bud_add_to_app(
                Artifact(
                    filename=filename,
                    original_filename=original,
                    content_type=content_type,
                    size_bytes=size,
                    storage_path=filename,
                    sha256=digest * 64 if digest else None,
                    test_case=test_case,
                    test_run_id=runs[run].id if run else None,
                    created_at=now - timedelta(minutes=minutes),
                )
            )
        self.tc_run_id = runs["run"].id
        self.tc_listing = request(p.GET, p.RUN_ARTIFACTS_PATH.format(self.tc_run_id))
        self.tc_items = self.tc_listing.json() if self.tc_listing.status_code == 200 else []
        self.tc_names = [item.get("original_filename") for item in self.tc_items]
        self.tc_first = self.tc_items[0] if self.tc_items else {}
        self.tc_other_status = request(
            p.GET, p.RUN_ARTIFACTS_PATH.format(runs["other"].id)
        ).status_code
        empty = (
            self.bud.bud_station_request(p.POST, p.TEST_RUNS_PATH, json=p.ARTIFACT_EMPTY_RUN)
            .json()
            .get("id")
        )
        empty_listing = request(p.GET, p.RUN_ARTIFACTS_PATH.format(empty))
        self.tc_empty = (empty_listing.status_code, empty_listing.json())
        self.tc_missing = request(
            p.GET, p.RUN_ARTIFACTS_PATH.format(p.ARTIFACT_MISSING_RUN)
        ).status_code
        self.tc_allowed = list(settings.ALLOWED_UPLOAD_MIME_TYPES)
        self.tc_download_policy = uploads.ARTIFACT_DOWNLOAD_HEADERS.get("Content-Security-Policy")
        capture_run = (
            self.bud.bud_station_request(p.POST, p.TEST_RUNS_PATH, json=p.ARTIFACT_CAPTURE_RUN)
            .json()
            .get("id")
        )
        name, data, content_type = p.ARTIFACT_CAPTURE
        self.tc_capture = self.bud.bud_station_request(
            p.POST,
            p.UPLOADS_POST_PATH,
            files={"file": (name, io.BytesIO(data), content_type)},
            data={"run_id": str(capture_run)},
        )
        listed = request(p.GET, p.RUN_ARTIFACTS_PATH.format(capture_run)).json()
        self.tc_capture_listed = (
            listed[0].get("original_filename") if isinstance(listed, list) and listed else None
        )
        name, data, content_type = p.ARTIFACT_REFUSED
        self.tc_refused = self.bud.bud_station_request(
            p.POST,
            p.UPLOADS_POST_PATH,
            files={"file": (name, io.BytesIO(data), content_type)},
            data={"run_id": str(capture_run)},
        )
        self.bud.bud_start_app(signed_in=False)
        self.tc_signed_out = request(p.GET, p.RUN_ARTIFACTS_PATH.format(1)).status_code

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    RunArtifactsApiTest().run()
