"""Listing the files a run left behind, and the types it will accept.

Artifacts could be uploaded and downloaded by id, but nothing enumerated them:
a screenshot or a packet capture attached to a run was reachable only by someone
who already knew its integer primary key. Nothing in the UI referenced them at
all, so in practice a run's evidence was write-only.

These cover the listing, and the media types a run actually produces - the
allowlist is what decides whether a plot, a trace or a capture can be sent at
all, and a rejection there surfaces as an opaque 415 in CI.
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta

import pytest

from app.core.config import settings
from app.models import Artifact, TestRun


@pytest.fixture
def run_with_artifacts(db_session):
    async def _make():
        run = TestRun(name="Nightly", test_case_list="SmokeTests", status="Completed")
        other = TestRun(name="Other", test_case_list="SmokeTests", status="Completed")
        db_session.add_all([run, other])
        await db_session.flush()

        now = datetime.utcnow()
        db_session.add_all(
            [
                Artifact(
                    filename="b.png",
                    original_filename="failure-screenshot.png",
                    content_type="image/png",
                    size_bytes=2048,
                    storage_path="b.png",
                    sha256="b" * 64,
                    test_case="BootTests",
                    test_run_id=run.id,
                    created_at=now,
                ),
                Artifact(
                    filename="a.pcap",
                    original_filename="throughput.pcap",
                    content_type="application/vnd.tcpdump.pcap",
                    size_bytes=4096,
                    storage_path="a.pcap",
                    sha256="a" * 64,
                    test_case=None,
                    test_run_id=run.id,
                    created_at=now - timedelta(minutes=1),
                ),
                Artifact(
                    filename="c.log",
                    original_filename="other-run.log",
                    content_type="text/plain",
                    size_bytes=10,
                    storage_path="c.log",
                    test_run_id=other.id,
                    created_at=now,
                ),
                # Uploaded by an admin without a run: it belongs to no listing.
                Artifact(
                    filename="d.log",
                    original_filename="unattached.log",
                    content_type="text/plain",
                    size_bytes=10,
                    storage_path="d.log",
                    test_run_id=None,
                    created_at=now,
                ),
            ]
        )
        await db_session.commit()
        return run.id, other.id

    return _make


class TestListingARunsArtifacts:
    @pytest.mark.asyncio
    async def test_lists_the_files_attached_to_the_run(self, client, run_with_artifacts):
        run_id, _ = await run_with_artifacts()

        response = client.get(f"/api/test-runs/{run_id}/artifacts")

        assert response.status_code == 200, response.text
        names = [item["original_filename"] for item in response.json()]
        assert names == ["throughput.pcap", "failure-screenshot.png"]

    @pytest.mark.asyncio
    async def test_orders_them_oldest_first(self, client, run_with_artifacts):
        run_id, _ = await run_with_artifacts()

        items = client.get(f"/api/test-runs/{run_id}/artifacts").json()

        # A run produces evidence in the order it executes, and reading it back
        # in that order is what makes a failure legible.
        stamps = [item["created_at"] for item in items]
        assert stamps == sorted(stamps)

    @pytest.mark.asyncio
    async def test_excludes_another_runs_artifacts(self, client, run_with_artifacts):
        run_id, other_id = await run_with_artifacts()

        items = client.get(f"/api/test-runs/{run_id}/artifacts").json()

        assert "other-run.log" not in [item["original_filename"] for item in items]
        assert client.get(f"/api/test-runs/{other_id}/artifacts").status_code == 200

    @pytest.mark.asyncio
    async def test_excludes_artifacts_attached_to_no_run(self, client, run_with_artifacts):
        run_id, _ = await run_with_artifacts()

        items = client.get(f"/api/test-runs/{run_id}/artifacts").json()

        assert "unattached.log" not in [item["original_filename"] for item in items]

    @pytest.mark.asyncio
    async def test_carries_what_the_panel_renders(self, client, run_with_artifacts):
        run_id, _ = await run_with_artifacts()

        item = client.get(f"/api/test-runs/{run_id}/artifacts").json()[0]

        for field in ("id", "original_filename", "content_type", "size_bytes", "created_at"):
            assert field in item, field
        assert item["test_run_id"] == run_id

    @pytest.mark.asyncio
    async def test_never_reveals_the_storage_path(self, client, run_with_artifacts):
        run_id, _ = await run_with_artifacts()

        item = client.get(f"/api/test-runs/{run_id}/artifacts").json()[0]

        # The stored name is a UUID under the upload root; the download route
        # rebuilds the path from it. Publishing it invites a client to try.
        assert "storage_path" not in item

    def test_a_run_with_nothing_attached_is_an_empty_list(self, client):
        run_id = client.post(
            "/api/test-runs",
            json={"test_suite_name": "Empty", "test_case_list": "SmokeTests"},
        ).json()["id"]

        response = client.get(f"/api/test-runs/{run_id}/artifacts")

        assert response.status_code == 200
        assert response.json() == []

    def test_an_unknown_run_is_a_404(self, client):
        assert client.get("/api/test-runs/999999/artifacts").status_code == 404

    def test_requires_authentication(self, unauthenticated_client):
        assert unauthenticated_client.get("/api/test-runs/1/artifacts").status_code == 401


class TestWhatARunIsAllowedToUpload:
    """The allowlist decides what evidence can reach Bud at all.

    A type missing here is a 415 in the middle of a CI run, which reads as the
    upload being broken rather than as the file being unwelcome.
    """

    @pytest.mark.parametrize(
        "content_type,why",
        [
            ("text/xml", "JUnit XML"),
            ("application/xml", "JUnit XML, the other spelling"),
            ("application/json", "structured report output"),
            ("text/plain", "a log or a text trace"),
            ("text/csv", "performance samples"),
            ("image/png", "a screenshot"),
            ("image/jpeg", "a screenshot"),
            ("image/svg+xml", "a plot exported as vector"),
            ("application/pdf", "a plot or report exported as PDF"),
            ("application/vnd.tcpdump.pcap", "a packet capture"),
            ("application/x-pcapng", "a packet capture, the newer format"),
            ("application/zip", "a bundle of the above"),
            ("application/gzip", "a compressed trace"),
            ("application/octet-stream", "a binary trace a client cannot name"),
        ],
    )
    def test_the_types_a_run_produces_are_accepted(self, content_type, why):
        assert content_type in settings.ALLOWED_UPLOAD_MIME_TYPES, why

    def test_html_is_still_refused(self):
        # Stored HTML served back from the API origin is the one shape that
        # turns an artifact into a cross-site scripting vector.
        assert "text/html" not in settings.ALLOWED_UPLOAD_MIME_TYPES

    def test_an_upload_of_an_allowed_type_is_accepted(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
        from app.api import uploads

        monkeypatch.setattr(uploads, "_UPLOAD_ROOT", None)

        run_id = client.post(
            "/api/test-runs",
            json={"test_suite_name": "Captures", "test_case_list": "SmokeTests"},
        ).json()["id"]

        response = client.post(
            "/api/uploads",
            files={
                "file": ("throughput.pcap", io.BytesIO(b"\xd4\xc3\xb2\xa1"), "application/x-pcapng")
            },
            data={"run_id": str(run_id)},
        )

        assert response.status_code == 201, response.text
        assert (
            client.get(f"/api/test-runs/{run_id}/artifacts").json()[0]["original_filename"]
            == "throughput.pcap"
        )

    def test_an_upload_of_a_refused_type_says_which_are_allowed(
        self, client, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
        from app.api import uploads

        monkeypatch.setattr(uploads, "_UPLOAD_ROOT", None)

        response = client.post(
            "/api/uploads",
            files={"file": ("page.html", io.BytesIO(b"<b>x</b>"), "text/html")},
            data={},
        )

        assert response.status_code == 415
        assert "text/html" in response.json()["detail"]
