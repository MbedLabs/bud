"""Test run and system settings endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import Runner, SystemSetting, TestResult, TestRun


def _payload(**overrides) -> dict:
    base = {
        "test_suite_name": "Nightly",
        "test_case_list": "SmokeTests",
        "url_test_software": "https://github.test/tests",
        "ref_test_software": "main",
    }
    base.update(overrides)
    return base


class TestRunCreation:
    def test_creates_a_run(self, client):
        response = client.post("/api/test-runs", json=_payload())
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["name"] == "Nightly"
        # The runner creates the run as execution starts, so it is already Running.
        assert body["status"] == "Running"

    def test_records_a_creation_event(self, client):
        created = client.post("/api/test-runs", json=_payload())
        run_id = created.json()["id"]

        events = client.get(f"/api/test-runs/{run_id}/events")
        assert events.status_code == 200, events.text
        assert len(events.json()) >= 1

    def test_events_for_an_unknown_run_are_404(self, client):
        assert client.get("/api/test-runs/99999/events").status_code == 404


class TestRunRetrieval:
    def test_fetches_a_run(self, client):
        run_id = client.post("/api/test-runs", json=_payload()).json()["id"]
        response = client.get(f"/api/test-runs/{run_id}")
        assert response.status_code == 200, response.text
        assert response.json()["id"] == run_id

    def test_unknown_run_is_404(self, client):
        assert client.get("/api/test-runs/99999").status_code == 404

    def test_lists_runs(self, client):
        client.post("/api/test-runs", json=_payload(test_suite_name="One"))
        client.post("/api/test-runs", json=_payload(test_suite_name="Two"))

        body = client.get("/api/test-runs").json()
        assert body["total"] >= 2
        assert {item["name"] for item in body["runs"]} >= {"One", "Two"}

    def test_filters_by_suite(self, client):
        client.post("/api/test-runs", json=_payload(test_suite_name="Wanted"))
        client.post("/api/test-runs", json=_payload(test_suite_name="Unwanted"))

        names = {i["name"] for i in client.get("/api/test-runs?suite=Wanted").json()["runs"]}
        assert names == {"Wanted"}

    def test_filters_by_status(self, client):
        client.post("/api/test-runs", json=_payload())
        body = client.get("/api/test-runs?status=Running").json()
        assert body["runs"], "the freshly created run should match"
        assert all(item["status"] == "Running" for item in body["runs"])

    def test_paginates(self, client):
        for index in range(3):
            client.post("/api/test-runs", json=_payload(test_suite_name=f"Suite{index}"))
        page = client.get("/api/test-runs?limit=2&offset=0").json()
        assert len(page["runs"]) <= 2
        assert page["limit"] == 2

    @pytest.mark.asyncio
    async def test_latest_per_suite_returns_one_run_each(self, client, db_session):
        now = datetime.utcnow()
        db_session.add_all(
            [
                TestRun(
                    name="Repeated",
                    test_case_list="c",
                    status="Completed",
                    created_at=now - timedelta(hours=2),
                ),
                TestRun(name="Repeated", test_case_list="c", status="Completed", created_at=now),
                TestRun(name="Other", test_case_list="c", status="Completed", created_at=now),
            ]
        )
        await db_session.commit()

        items = client.get("/api/test-runs?latest_per_suite=true").json()["runs"]
        names = [item["name"] for item in items]
        assert names.count("Repeated") == 1
        assert "Other" in names


class TestRunUpdate:
    def test_records_the_final_counters(self, client):
        run_id = client.post("/api/test-runs", json=_payload()).json()["id"]
        response = client.patch(
            f"/api/test-runs/{run_id}",
            json={
                "status": "Completed",
                "total_tests": 10,
                "passed_tests": 8,
                "failed_tests": 1,
                "skipped_tests": 1,
                "duration_seconds": 42.5,
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "Completed"
        assert body["passed_tests"] == 8
        assert body["duration_seconds"] == 42.5

    def test_completing_a_run_stamps_completed_at(self, client):
        run_id = client.post("/api/test-runs", json=_payload()).json()["id"]
        assert client.get(f"/api/test-runs/{run_id}").json()["completed_at"] is None

        client.patch(f"/api/test-runs/{run_id}", json={"status": "Completed"})
        assert client.get(f"/api/test-runs/{run_id}").json()["completed_at"] is not None

    def test_a_status_change_is_recorded_as_an_event(self, client):
        run_id = client.post("/api/test-runs", json=_payload()).json()["id"]
        before = len(client.get(f"/api/test-runs/{run_id}/events").json())

        client.patch(f"/api/test-runs/{run_id}", json={"status": "Completed"})
        after = len(client.get(f"/api/test-runs/{run_id}/events").json())
        assert after > before

    def test_updating_an_unknown_run_is_404(self, client):
        assert client.patch("/api/test-runs/99999", json={"status": "Completed"}).status_code == 404

    def test_rejects_an_unknown_status(self, client):
        run_id = client.post("/api/test-runs", json=_payload()).json()["id"]
        response = client.patch(f"/api/test-runs/{run_id}", json={"status": "Elsewhere"})
        assert response.status_code == 422


class TestRunDeletion:
    @pytest.mark.asyncio
    async def test_deletes_a_run(self, client, db_session):
        run_id = client.post("/api/test-runs", json=_payload()).json()["id"]
        assert client.delete(f"/api/test-runs/{run_id}").status_code == 204

        remaining = (
            await db_session.execute(select(TestRun).where(TestRun.id == run_id))
        ).scalar_one_or_none()
        assert remaining is None

    def test_deleting_an_unknown_run_is_404(self, client):
        assert client.delete("/api/test-runs/99999").status_code == 404

    @pytest.mark.asyncio
    async def test_deleting_a_run_takes_its_results_with_it(self, client, db_session):
        run_id = client.post("/api/test-runs", json=_payload()).json()["id"]
        db_session.add(
            TestResult(test_class="Smoke", test_method="test_x", passed=True, test_run_id=run_id)
        )
        await db_session.commit()

        assert client.delete(f"/api/test-runs/{run_id}").status_code == 204
        orphans = (
            (await db_session.execute(select(TestResult).where(TestResult.test_run_id == run_id)))
            .scalars()
            .all()
        )
        assert orphans == []


class TestStatsAndFilterOptions:
    @pytest.mark.asyncio
    async def test_stats_aggregate_the_whole_filtered_set(self, client, db_session):
        station = Runner(account="stats-station", password_hash="x", token="t")
        db_session.add(station)
        await db_session.flush()
        now = datetime.utcnow()
        db_session.add_all(
            [
                TestRun(
                    name="Alpha",
                    test_case_list="c",
                    status="Completed",
                    total_tests=10,
                    passed_tests=10,
                    failed_tests=0,
                    created_at=now,
                    runner_id=station.id,
                ),
                TestRun(
                    name="Beta",
                    test_case_list="c",
                    status="Completed",
                    total_tests=10,
                    passed_tests=6,
                    failed_tests=4,
                    created_at=now,
                    runner_id=station.id,
                ),
            ]
        )
        await db_session.commit()

        stats = client.get("/api/test-runs/stats").json()
        assert stats["total_runs"] >= 2
        assert stats["total_tests"] >= 20
        assert stats["passed_tests"] >= 16
        assert 0 <= stats["test_pass_rate"] <= 100

    @pytest.mark.asyncio
    async def test_stats_respect_the_suite_filter(self, client, db_session):
        db_session.add(
            TestRun(
                name="Only",
                test_case_list="c",
                status="Completed",
                total_tests=4,
                passed_tests=4,
                created_at=datetime.utcnow(),
            )
        )
        await db_session.commit()

        stats = client.get("/api/test-runs/stats?suite=Only").json()
        assert stats["total_tests"] == 4

    def test_stats_for_an_unknown_station_are_empty(self, client):
        stats = client.get("/api/test-runs/stats?runner_account=nobody").json()
        assert stats["total_runs"] == 0
        assert stats["test_pass_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_filter_options_list_real_suites_and_stations(self, client, db_session):
        station = Runner(account="opt-station", password_hash="x", token="t")
        db_session.add(station)
        await db_session.flush()
        db_session.add(
            TestRun(
                name="Optioned",
                test_case_list="c",
                status="Completed",
                created_at=datetime.utcnow(),
                runner_id=station.id,
            )
        )
        await db_session.commit()

        options = client.get("/api/test-runs/filter-options").json()
        assert "Optioned" in options["suites"]
        assert "opt-station" in options["runner_accounts"]


class TestSystemSettings:
    def test_lists_settings(self, client):
        assert client.get("/api/settings").status_code == 200

    def test_writes_and_reads_a_setting(self, client):
        written = client.put("/api/settings/retention_days", json={"value": "30"})
        assert written.status_code == 200, written.text

        read = client.get("/api/settings/retention_days")
        assert read.status_code == 200
        assert read.json()["value"] == "30"

    def test_unknown_setting_is_404(self, client):
        assert client.get("/api/settings/not-a-setting").status_code == 404

    @pytest.mark.asyncio
    async def test_overwrites_an_existing_setting(self, client, db_session):
        client.put("/api/settings/mode", json={"value": "first"})
        client.put("/api/settings/mode", json={"value": "second"})

        stored = await db_session.get(SystemSetting, "mode")
        await db_session.refresh(stored)
        assert stored.value == "second"


class TestPlmIntegrationSettings:
    @pytest.fixture
    def encryption_key(self, monkeypatch):
        """Bud refuses to store a Bloom token without a key to encrypt it with."""
        from cryptography.fernet import Fernet

        from app.core.config import settings

        monkeypatch.setattr(settings, "INTEGRATION_ENCRYPTION_KEY", Fernet.generate_key().decode())

    def test_refuses_to_store_a_token_without_an_encryption_key(self, client, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "INTEGRATION_ENCRYPTION_KEY", "")
        response = client.post(
            "/api/settings/integrations/PLM",
            json={"bloom_url": "https://bloom.example.com", "bloom_token": "blm_sync_x"},
        )
        assert response.status_code == 503
        assert "ENCRYPTION_KEY" in response.json()["detail"]

    def test_reports_an_unconfigured_integration(self, client):
        response = client.get("/api/settings/integrations/PLM")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["bloom_url"] == ""
        assert body["has_bloom_token"] is False

    def test_rejects_a_token_that_is_not_a_scoped_service_credential(self, client, encryption_key):
        """Bud must never be handed a full administrator token."""
        response = client.post(
            "/api/settings/integrations/PLM",
            json={"bloom_url": "https://bloom.example.com", "bloom_token": "an-admin-token"},
        )
        assert response.status_code == 422
        assert "blm_sync_" in response.json()["detail"]

    def test_stores_a_bloom_url(self, client, encryption_key):
        response = client.post(
            "/api/settings/integrations/PLM",
            json={
                "bloom_url": "https://bloom.example.com/",
                "bloom_token": "blm_sync_a-real-token",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["bloom_url"] == "https://bloom.example.com"
        assert response.json()["has_bloom_token"] is True

    def test_never_returns_the_token(self, client, encryption_key):
        client.post(
            "/api/settings/integrations/PLM",
            json={"bloom_url": "https://bloom.example.com", "bloom_token": "blm_sync_super-secret"},
        )
        body = client.get("/api/settings/integrations/PLM").json()
        assert "blm_sync_super-secret" not in str(body)
        assert body["has_bloom_token"] is True

    @pytest.mark.parametrize(
        "bad_url",
        [
            "not-a-url",
            "ftp://bloom.example.com",
            "https://user:pass@bloom.example.com",
            "//bloom.example.com",
        ],
    )
    def test_rejects_a_url_that_is_not_a_plain_absolute_http_url(
        self, client, encryption_key, bad_url
    ):
        response = client.post(
            "/api/settings/integrations/PLM",
            json={"bloom_url": bad_url, "bloom_token": "blm_sync_t"},
        )
        assert response.status_code == 422, f"{bad_url} was accepted"

    def test_settings_require_authentication(self, unauthenticated_client):
        for method, path in [
            ("GET", "/api/settings"),
            ("GET", "/api/settings/anything"),
            ("PUT", "/api/settings/anything"),
            ("GET", "/api/settings/integrations/PLM"),
            ("POST", "/api/settings/integrations/PLM"),
        ]:
            response = unauthenticated_client.request(method, path, json={"value": "x"})
            assert response.status_code == 401, f"{method} {path} was {response.status_code}"
