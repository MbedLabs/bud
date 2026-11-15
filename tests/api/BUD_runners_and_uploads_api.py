"""
* @file     ${tests/api/BUD_runners_and_uploads_api.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Stations beat and upload for their own runs only, within the file, run and free-space limits.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests each scenario on a fresh app database with the station or person signed in.
"""

from datetime import datetime
from unittest import mock

from app.api import uploads
from app.core.config import settings
from app.models import Artifact, Runner, TestRun
from app.models.user import User, UserRole
from app.services import artifact_storage
from tests.api.runners_and_uploads_api import RunnersAndUploadsApiBase


def body_of(response):
    """The JSON answer, or an empty one."""
    try:
        return response.json() or {}
    except ValueError:
        return {}


def type_name(value):
    """The type name of a value."""
    return type(value).__name__


class RunnersAndUploadsApiTest(RunnersAndUploadsApiBase):

    def setUpClass(self):
        super().setUpClass()
        self.tc_checks = {}
        for scenario in (
            self.heartbeat,
            self.unowned,
            self.owned,
            self.delete,
            self.foreign_upload,
            self.own_upload,
            self.unknown_run,
            self.oversized,
            self.at_limit,
            self.long_name,
            self.free_space,
            self.remaining,
            self.beyond,
            self.viewer,
            self.no_run,
            self.admin,
            self.quota,
        ):
            self.bud.bud_start_app()
            scenario()

    def runner(self, account, port=53035):
        """Store a station."""
        return self.bud.bud_add_to_app(
            Runner(
                account=account, password_hash="hash", token=f"{account}-token", socket_port=port
            )
        )

    def stored_run(self, station, status="Running"):
        """Store a run of a station."""
        return self.bud.bud_add_to_app(
            TestRun(
                name="owned-run",
                test_case_list="[]",
                status=status,
                started_at=datetime.utcnow(),
                runner_id=station.id,
            )
        )

    def artifact(self, run_id=None, size=4, name="artifact.txt"):
        """Store an artifact record."""
        return self.bud.bud_add_to_app(
            Artifact(
                filename=name,
                original_filename=name,
                content_type="text/plain",
                size_bytes=size,
                sha256="0" * 64,
                storage_path=name,
                test_run_id=run_id,
            )
        )

    def upload(self, run_id=None, file=None):
        """Upload one file as the signed-in entity."""
        p = self.parameters
        data = {"run_id": str(run_id)} if run_id is not None else None
        return self.bud.bud_request(
            p.POST, p.UPLOAD_API_PATH, files={"file": file or p.UPLOAD_FILE}, data=data
        )

    def refusal(self, response, status, text):
        """The checks of a refused request and the text of its detail."""
        return {
            "the request is refused": (response.status_code, status),
            f"the refusal says {text}": (
                text.lower() in str(body_of(response).get("detail")).lower(),
                True,
            ),
        }

    def files(self):
        """The names of the files in the upload folder."""
        root = uploads.get_upload_root()
        return sorted(path.name for path in root.glob("*")) if root.exists() else []

    def heartbeat(self):
        p = self.parameters
        mine, theirs = self.runner("runner-a"), self.runner("runner-b")
        self.bud.bud_sign_in_as(mine, as_person=False, as_uploader=True, as_runner=True)
        response = self.bud.bud_request(
            p.POST, "/api/runners/heartbeat", json={"runner_account": "runner-b", "location": "lab"}
        )
        theirs_now = self.bud.bud_find_in_app(Runner, id=theirs.id)[0]
        self.tc_checks["heartbeat"] = {
            "the heartbeat is answered": (response.status_code, p.STATUS_OK),
            "the answer names the signed-in station": (
                body_of(response).get("account"),
                "runner-a",
            ),
            "the signed-in station beats": (type_name(mine.last_heartbeat) != p.NONE_TYPE, True),
            "the named station does not beat": (type_name(theirs_now.last_heartbeat), p.NONE_TYPE),
            "the named station keeps its location": (type_name(theirs_now.location), p.NONE_TYPE),
        }

    def unowned(self):
        p = self.parameters
        owner, other = self.runner("owner-runner"), self.runner("other-runner", 53036)
        artifact = self.artifact(self.stored_run(owner, "Completed").id)
        self.bud.bud_sign_in_as(other, as_person=False, as_uploader=True)
        response = self.bud.bud_request(p.GET, p.UPLOAD_INFO_PATH.format(artifact.id))
        self.tc_checks["unowned"] = {
            "another station's artifact is refused": (response.status_code, p.STATUS_FORBIDDEN)
        }

    def owned(self):
        p = self.parameters
        owner = self.runner("owner-runner")
        artifact = self.artifact(self.stored_run(owner, "Completed").id)
        self.bud.bud_sign_in_as(owner, as_person=False, as_uploader=True)
        response = self.bud.bud_request(p.GET, p.UPLOAD_INFO_PATH.format(artifact.id))
        self.tc_checks["owned"] = {
            "its own artifact is read": (response.status_code, p.STATUS_OK),
            "the artifact read is the one stored": (body_of(response).get("id"), artifact.id),
        }

    def delete(self):
        p = self.parameters
        user = self.bud.bud_add_to_app(
            User(
                id=2,
                email="maintainer@example.com",
                full_name="Maintainer",
                hashed_password="hash",
                role=UserRole.viewer,
                is_active=True,
            )
        )
        artifact = self.artifact()
        self.bud.bud_sign_in_as(user)
        response = self.bud.bud_request(p.DELETE, f"{p.UPLOAD_API_PATH}/{artifact.id}")
        self.tc_checks["delete"] = self.refusal(response, p.STATUS_FORBIDDEN, p.UPLOAD_ONLY_ADMINS)

    def foreign_upload(self):
        p = self.parameters
        owner, other = self.runner("owner-upload-runner"), self.runner("other-upload-runner", 53036)
        run = self.stored_run(owner)
        self.bud.bud_sign_in_as(other, as_person=False)
        self.tc_checks["foreign upload"] = self.refusal(
            self.upload(run.id), p.STATUS_FORBIDDEN, p.UPLOAD_NOT_AUTHORIZED
        )

    def own_upload(self):
        p = self.parameters
        station = self.runner("owned-upload-runner")
        run = self.stored_run(station)
        self.bud.bud_sign_in_as(station, as_person=False)
        response = self.upload(run.id)
        self.tc_checks["own upload"] = {
            "the upload is stored": (response.status_code, p.STATUS_CREATED),
            "the upload belongs to the run": (body_of(response).get("test_run_id"), run.id),
        }

    def unknown_run(self):
        p = self.parameters
        self.bud.bud_sign_in_as(self.runner("missing-run-upload-runner"), as_person=False)
        self.tc_checks["unknown run"] = self.refusal(
            self.upload(999999), p.STATUS_NOT_FOUND, p.UPLOAD_RUN_NOT_FOUND
        )

    def station_upload(self, name, content):
        """Upload as the test station to its own run."""
        self.bud.bud_add_test_station()
        return self.bud.bud_station_upload(name, content, "text/plain")

    def oversized(self):
        p = self.parameters
        before = self.files()
        with mock.patch.object(settings, "MAX_UPLOAD_SIZE", 10):
            response = self.station_upload("too-big.txt", b"x" * 64)
        self.tc_checks["oversized"] = {
            **self.refusal(response, p.STATUS_TOO_LARGE, p.UPLOAD_TOO_LARGE),
            "no partial file is left": (self.files(), before),
        }

    def at_limit(self):
        p = self.parameters
        with (
            mock.patch.object(settings, "MAX_UPLOAD_SIZE", 10),
            mock.patch.object(settings, "MIN_UPLOAD_FREE_BYTES", 0),
        ):
            response = self.station_upload("at-limit.txt", b"x" * 10)
        self.tc_checks["at limit"] = {
            "the upload is stored": (response.status_code, p.STATUS_CREATED),
            "the whole file is stored": (body_of(response).get("size_bytes"), 10),
        }

    def long_name(self):
        p = self.parameters
        response = self.station_upload(("x" * 256) + ".txt", b"safe")
        self.tc_checks["long name"] = {
            "a name too long is refused": (response.status_code, p.STATUS_UNPROCESSABLE)
        }

    def free_space(self):
        p = self.parameters
        usage = type("Usage", (), {"free": 1024})()
        with (
            mock.patch.object(settings, "MIN_UPLOAD_FREE_BYTES", 1024),
            mock.patch.object(artifact_storage.shutil, "disk_usage", return_value=usage),
        ):
            response = self.station_upload("trace.txt", b"data")
        self.tc_checks["free space"] = self.refusal(
            response, p.STATUS_INSUFFICIENT_STORAGE, p.UPLOAD_FREE_SPACE
        )

    def capacity(self, content, name):
        """Upload content to a station run holding 249 of its 250 bytes."""
        station = self.bud.bud_add_test_station(with_run=False)
        run = self.bud.bud_add_to_app(
            TestRun(name=name, test_case_list="[]", status="Running", runner_id=station.id)
        )
        self.artifact(run.id, size=249, name="existing")
        values = {"MIN_UPLOAD_FREE_BYTES": 0, "MAX_UPLOAD_SIZE": 25, "MAX_RUN_UPLOAD_BYTES": 250}
        with mock.patch.multiple(settings, **values):
            return self.bud.bud_station_request(
                self.parameters.POST,
                self.parameters.UPLOAD_API_PATH,
                files={"file": ("trace.txt", content, "text/plain")},
                data={"run_id": str(run.id)},
            )

    def remaining(self):
        p = self.parameters
        response = self.capacity(b"x", "quota-run")
        self.tc_checks["remaining"] = {
            "the last byte is stored": (response.status_code, p.STATUS_CREATED),
            "one byte is stored": (body_of(response).get("size_bytes"), 1),
        }

    def beyond(self):
        p = self.parameters
        response = self.capacity(b"xx", "quota-overflow")
        self.tc_checks["beyond"] = {
            "two bytes are refused": (response.status_code, p.STATUS_TOO_LARGE),
            "no file is written": (self.files(), []),
        }

    def viewer(self):
        p = self.parameters
        self.bud.bud_sign_in_as(
            User(
                id=88,
                email="viewer-upload@example.com",
                full_name="Viewer",
                hashed_password="hash",
                role=UserRole.viewer,
                is_active=True,
            ),
            as_person=False,
        )
        self.tc_checks["viewer"] = {
            "a viewer's upload is refused": (
                self.upload(file=("trace.txt", b"x", "text/plain")).status_code,
                p.STATUS_FORBIDDEN,
            )
        }

    def no_run(self):
        p = self.parameters
        self.bud.bud_sign_in_as(self.runner("no-run-id-runner", 53040), as_person=False)
        self.tc_checks["no run"] = self.refusal(
            self.upload(), p.STATUS_BAD_REQUEST, p.UPLOAD_RUN_ID_REQUIRED
        )

    def admin(self):
        p = self.parameters
        response = self.upload()
        self.tc_checks["admin"] = {
            "an administrator's upload is refused": (response.status_code, p.STATUS_FORBIDDEN),
            "the refusal says stations upload": (
                body_of(response).get("detail"),
                p.UPLOAD_STATIONS_ONLY,
            ),
        }

    def quota(self):
        p = self.parameters
        station = self.runner("quota-runner", 53041)
        run = self.stored_run(station)
        self.artifact(run.id, size=1000, name="prefill")
        self.bud.bud_sign_in_as(station, as_person=False)
        with mock.patch.object(settings, "MAX_RUN_UPLOAD_BYTES", 1000):
            response = self.upload(run.id)
        self.tc_checks["quota"] = self.refusal(response, p.STATUS_TOO_LARGE, p.UPLOAD_QUOTA)

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    RunnersAndUploadsApiTest().run()
