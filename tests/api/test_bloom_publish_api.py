"""Publishing a run's report to Bloom, on request."""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-at-least-32-characters-long")

from datetime import datetime  # noqa: E402
from unittest.mock import AsyncMock, patch  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from cryptography.fernet import Fernet  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.models import Artifact, SystemSetting, TestResult, TestRun  # noqa: E402
from app.services.bloom_publish import publishable_artifacts  # noqa: E402


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch):
    """Settings are already built by the time this module loads."""
    monkeypatch.setattr(
        settings, "INTEGRATION_ENCRYPTION_KEY", Fernet.generate_key().decode(), raising=False
    )


async def _run_with_reports(db_session, upload_root, name="Nightly HIL"):
    run = TestRun(
        name=name,
        test_case_list="Suite.CASES",
        status="Completed",
        total_tests=3,
        passed_tests=2,
        failed_tests=1,
        created_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)

    db_session.add(
        TestResult(
            test_run_id=run.id,
            test_class="VoltageTests",
            test_method="test_supply",
            passed=True,
            assertions=[{"passed": True, "message": "supply is in range"}],
            test_metadata={"tc_id": "VCU-TC-001"},
        )
    )

    upload_root.mkdir(parents=True, exist_ok=True)
    for filename, content_type, payload in (
        (f"bud-run-{run.id}.pdf", "application/pdf", b"%PDF-1.4 run"),
        ("report_junit.xml", "application/xml", b"<testsuites/>"),
        ("bench.log", "application/octet-stream", b"INFO boot"),
        ("failure.png", "image/png", b"PNG"),
    ):
        stored = f"stored-{filename}"
        (upload_root / stored).write_bytes(payload)
        db_session.add(
            Artifact(
                filename=stored,
                original_filename=filename,
                content_type=content_type,
                size_bytes=len(payload),
                sha256="0" * 64,
                storage_path=stored,
                test_run_id=run.id,
            )
        )
    await db_session.commit()
    return run


async def _configure_bloom(db_session):
    from app.services.integration_secrets import encrypt_integration_secret

    db_session.add(SystemSetting(key="bloom_url", value="https://bloom.test"))
    db_session.add(
        SystemSetting(
            key="bloom_token_encrypted", value=encrypt_integration_secret("blm_sync_token")
        )
    )
    await db_session.commit()


class TestWhatGetsPublished:
    @pytest.mark.asyncio
    async def test_only_the_reports_go(self, db_session, tmp_path, monkeypatch):
        """Logs and screenshots stay in Bud: they are for debugging, not the record."""
        from app.api import uploads

        monkeypatch.setattr(uploads, "_UPLOAD_ROOT", tmp_path.resolve())
        run = await _run_with_reports(db_session, tmp_path)

        chosen = await publishable_artifacts(db_session, run.id)

        assert sorted(a.original_filename for a in chosen) == [
            f"bud-run-{run.id}.pdf",
            "report_junit.xml",
        ]


class TestTheEndpoint:
    @pytest.mark.asyncio
    async def test_sends_the_reports_and_records_the_outcome(
        self, client, db_session, tmp_path, monkeypatch
    ):
        from app.api import uploads

        monkeypatch.setattr(uploads, "_UPLOAD_ROOT", tmp_path.resolve())
        run = await _run_with_reports(db_session, tmp_path)
        await _configure_bloom(db_session)

        sent = {}

        async def fake_post(url, token, payload):
            sent["url"] = url
            sent["payload"] = payload
            return {"document_id": 12, "doc_id": "VCU-RPT-001", "created": True}

        with patch("app.api.test_runs.post_to_bloom", side_effect=fake_post):
            response = client.post(f"/api/test-runs/{run.id}/publish-to-bloom")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["doc_id"] == "VCU-RPT-001"
        assert sorted(body["published_files"]) == [f"bud-run-{run.id}.pdf", "report_junit.xml"]

        assert sent["payload"]["project_prefix"] == "VCU"
        assert sent["payload"]["bud_run_id"] == run.id
        assert len(sent["payload"]["files"]) == 2

    @pytest.mark.asyncio
    async def test_the_files_travel_as_their_bytes(self, client, db_session, tmp_path, monkeypatch):
        import base64

        from app.api import uploads

        monkeypatch.setattr(uploads, "_UPLOAD_ROOT", tmp_path.resolve())
        run = await _run_with_reports(db_session, tmp_path)
        await _configure_bloom(db_session)

        captured = {}

        async def fake_post(url, token, payload):
            captured["files"] = payload["files"]
            return {"document_id": 1, "doc_id": "X-RPT-001", "created": True}

        with patch("app.api.test_runs.post_to_bloom", side_effect=fake_post):
            client.post(f"/api/test-runs/{run.id}/publish-to-bloom")

        xml = next(f for f in captured["files"] if f["filename"] == "report_junit.xml")
        assert base64.b64decode(xml["content_base64"]) == b"<testsuites/>"

    @pytest.mark.asyncio
    async def test_refuses_when_bloom_is_not_configured(
        self, client, db_session, tmp_path, monkeypatch
    ):
        from app.api import uploads

        monkeypatch.setattr(uploads, "_UPLOAD_ROOT", tmp_path.resolve())
        run = await _run_with_reports(db_session, tmp_path)

        response = client.post(f"/api/test-runs/{run.id}/publish-to-bloom")

        assert response.status_code == 409
        assert "not configured" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_refuses_an_unfinished_run_with_no_report(self, client, db_session):
        await _configure_bloom(db_session)
        run = TestRun(
            name="No reports yet",
            test_case_list="Suite.CASES",
            status="Running",
            created_at=datetime.utcnow(),
        )
        db_session.add(run)
        await db_session.flush()
        db_session.add(
            TestResult(
                test_run_id=run.id,
                test_class="VoltageTests",
                test_method="test_supply",
                passed=True,
                assertions=[{"passed": True}],
                test_metadata={"tc_id": "VCU-TC-001"},
            )
        )
        await db_session.commit()
        await db_session.refresh(run)

        response = client.post(f"/api/test-runs/{run.id}/publish-to-bloom")

        assert response.status_code == 409
        assert "completed" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_backfills_reports_for_a_completed_legacy_run(
        self, client, db_session, tmp_path, monkeypatch
    ):
        from app.api import uploads

        monkeypatch.setattr(uploads, "_UPLOAD_ROOT", tmp_path.resolve())
        await _configure_bloom(db_session)
        run = TestRun(
            name="Legacy complete",
            test_case_list="Suite.CASES",
            status="Completed",
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        db_session.add(run)
        await db_session.flush()
        db_session.add(
            TestResult(
                test_run_id=run.id,
                test_class="VoltageTests",
                test_method="test_supply",
                passed=True,
                assertions=[{"passed": True, "message": "legacy assertion"}],
                test_metadata={"tc_id": "VCU-TC-001"},
            )
        )
        await db_session.commit()

        with patch(
            "app.api.test_runs.post_to_bloom",
            AsyncMock(return_value={"document_id": 1, "doc_id": "VCU-RPT-001", "created": True}),
        ) as posted:
            response = client.post(f"/api/test-runs/{run.id}/publish-to-bloom")

        assert response.status_code == 200, response.text
        assert sorted(response.json()["published_files"]) == [
            f"bud-run-{run.id}-Legacy-complete.pdf",
            "bud-suite-Legacy-complete.pdf",
        ]
        assert posted.await_args.args[2]["project_prefix"] == "VCU"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("tc_ids", "message"),
        [
            ([], "no canonical Bloom test-case IDs"),
            (["TC-1"], "not a canonical Bloom test-case ID"),
            (["VCU-TC-001", "DEM-TC-002"], "multiple Bloom projects"),
        ],
    )
    async def test_refuses_when_the_run_cannot_identify_one_bloom_project(
        self, client, db_session, tmp_path, monkeypatch, tc_ids, message
    ):
        from app.api import uploads

        monkeypatch.setattr(uploads, "_UPLOAD_ROOT", tmp_path.resolve())
        await _configure_bloom(db_session)
        run = await _run_with_reports(db_session, tmp_path, name="Bad identifiers")
        await db_session.execute(
            TestResult.__table__.delete().where(TestResult.test_run_id == run.id)
        )
        for index, tc_id in enumerate(tc_ids):
            db_session.add(
                TestResult(
                    test_run_id=run.id,
                    test_class=f"Case{index}",
                    test_method="test_case",
                    passed=True,
                    assertions=[{"passed": True}],
                    test_metadata={"tc_id": tc_id},
                )
            )
        await db_session.commit()

        response = client.post(f"/api/test-runs/{run.id}/publish-to-bloom")

        assert response.status_code == 409
        assert message in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_a_refusal_from_bloom_is_reported(
        self, client, db_session, tmp_path, monkeypatch
    ):
        from app.api import uploads

        monkeypatch.setattr(uploads, "_UPLOAD_ROOT", tmp_path.resolve())
        run = await _run_with_reports(db_session, tmp_path)
        await _configure_bloom(db_session)

        failure = httpx.HTTPStatusError(
            "404",
            request=httpx.Request("POST", "https://bloom.test"),
            response=httpx.Response(404, text="Project not found"),
        )
        with patch("app.api.test_runs.post_to_bloom", AsyncMock(side_effect=failure)):
            response = client.post(f"/api/test-runs/{run.id}/publish-to-bloom")

        assert response.status_code == 502
        assert "Project not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_an_unreachable_bloom_is_reported(
        self, client, db_session, tmp_path, monkeypatch
    ):
        from app.api import uploads

        monkeypatch.setattr(uploads, "_UPLOAD_ROOT", tmp_path.resolve())
        run = await _run_with_reports(db_session, tmp_path)
        await _configure_bloom(db_session)

        with patch(
            "app.api.test_runs.post_to_bloom",
            AsyncMock(side_effect=httpx.ConnectError("refused")),
        ):
            response = client.post(f"/api/test-runs/{run.id}/publish-to-bloom")

        assert response.status_code == 502
        assert "Could not reach Bloom" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_a_missing_run_is_not_found(self, client):
        response = client.post("/api/test-runs/999999/publish-to-bloom")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_nothing_is_published_by_finishing_a_run(
        self, client, db_session, tmp_path, monkeypatch
    ):
        """Publishing is asked for. A nightly suite must not fill Bloom on its own."""
        from app.api import uploads

        monkeypatch.setattr(uploads, "_UPLOAD_ROOT", tmp_path.resolve())
        await _configure_bloom(db_session)
        run = TestRun(
            name="Autopublish check",
            test_case_list="Suite.CASES",
            status="Running",
            created_at=datetime.utcnow(),
        )
        db_session.add(run)
        await db_session.commit()
        await db_session.refresh(run)

        with patch("app.api.test_runs.post_to_bloom", AsyncMock()) as posted:
            completed = client.patch(f"/api/test-runs/{run.id}", json={"status": "Completed"})

        assert completed.status_code == 200
        posted.assert_not_called()
