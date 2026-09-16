"""Bud keeps the Bloom suite a sync reached, so a run can point back at it."""

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.core.config import settings
from app.db import database as db_module
from app.models import SystemSetting, TestResult, TestRun
from app.services import bloom_sync as bloom_sync_service
from app.services.bloom_sync import _suite_reference
from app.services.integration_secrets import encrypt_integration_secret

SUITE = {
    "id": 7,
    "suite_id": "FLT-TS-002",
    "name": "Nightly regression",
    "url": "https://bloom.example.com/projects/FLT/suites/7",
    "matched": 3,
    "size": 3,
}
SUPERSET = {**SUITE, "id": 8, "suite_id": "FLT-TS-008", "name": "Everything", "size": 40}
PARTIAL = {**SUITE, "id": 9, "suite_id": "FLT-TS-009", "name": "Smoke", "matched": 1, "size": 1}


def test_the_suite_holding_every_synced_case_is_the_reference():
    assert _suite_reference({"suites": [SUITE]}, 3) == SUITE


def test_the_smallest_covering_suite_wins_over_a_superset():
    assert _suite_reference({"suites": [SUPERSET, SUITE]}, 3) == SUITE


def test_a_suite_holding_only_some_synced_cases_is_no_reference():
    assert _suite_reference({"suites": [PARTIAL]}, 3) is None


def test_two_covering_suites_of_the_same_size_are_no_reference():
    assert _suite_reference({"suites": [SUITE, {**SUITE, "id": 10, "suite_id": "FLT-TS-010"}]}, 3) is None


def test_no_suite_is_no_reference():
    assert _suite_reference({"suites": []}, 3) is None
    assert _suite_reference({}, 3) is None
    assert _suite_reference({"suites": [SUITE]}, 0) is None


def test_a_malformed_suite_is_no_reference():
    assert _suite_reference({"suites": ["FLT-TS-002"]}, 3) is None
    assert _suite_reference({"suites": "FLT-TS-002"}, 3) is None
    assert _suite_reference({"suites": [{"suite_id": "FLT-TS-002"}]}, 3) is None


async def _run_sync_against(monkeypatch, body: dict, run_name: str) -> int:
    monkeypatch.setattr(settings, "INTEGRATION_ENCRYPTION_KEY", Fernet.generate_key().decode())

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return body

    async def fake_post(bloom_url: str, bloom_token: str, payload_results: list[dict]):
        return FakeResponse()

    monkeypatch.setattr(bloom_sync_service, "_post_to_bloom_with_retry", fake_post)

    async with db_module.async_session_maker() as session:
        run = TestRun(name=run_name, test_case_list="Bud.Tests", status="Completed")
        session.add(run)
        await session.flush()
        session.add_all(
            [
                SystemSetting(key="bloom_url", value="https://bloom.example.com"),
                SystemSetting(
                    key="bloom_token_encrypted",
                    value=encrypt_integration_secret("cached-bloom-token"),
                ),
                TestResult(
                    test_run_id=run.id,
                    test_class="VoltageTest",
                    test_method="bud_check",
                    passed=True,
                    test_metadata={"tc_id": "PRJ-TC-001"},
                ),
            ]
        )
        await session.commit()
        run_id = run.id

    await bloom_sync_service.sync_results_to_bloom(run_id)
    return run_id


@pytest.mark.asyncio
async def test_a_sync_stores_the_suite_bloom_named(_engine, monkeypatch):
    run_id = await _run_sync_against(
        monkeypatch,
        {"updated": 1, "not_found": [], "suites": [{**SUITE, "matched": 1, "size": 1}]},
        "sync-backlink",
    )

    async with db_module.async_session_maker() as session:
        run = (await session.execute(select(TestRun).where(TestRun.id == run_id))).scalar_one()

    assert run.bloom_artefact_id == "FLT-TS-002"
    assert run.bloom_artefact_name == "Nightly regression"
    assert run.bloom_artefact_url == "https://bloom.example.com/projects/FLT/suites/7"


@pytest.mark.asyncio
async def test_a_bloom_that_names_no_suite_leaves_the_run_unmarked(_engine, monkeypatch):
    """A Bloom reply without a suites key leaves the three columns null."""
    run_id = await _run_sync_against(
        monkeypatch, {"updated": 1, "not_found": [], "campaigns": []}, "sync-no-suite"
    )

    async with db_module.async_session_maker() as session:
        run = (await session.execute(select(TestRun).where(TestRun.id == run_id))).scalar_one()

    assert run.bloom_artefact_id is None
    assert run.bloom_artefact_name is None
    assert run.bloom_artefact_url is None


@pytest.mark.asyncio
async def test_the_run_endpoint_exposes_the_backlink(client, db_session):
    run = TestRun(
        name="exposed-backlink",
        test_case_list="Bud.Tests",
        status="Completed",
        bloom_artefact_id="FLT-TS-002",
        bloom_artefact_name="Nightly regression",
        bloom_artefact_url="https://bloom.example.com/projects/FLT/suites/7",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)

    response = client.get(f"/api/test-runs/{run.id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["bloom_artefact_id"] == "FLT-TS-002"
    assert body["bloom_artefact_name"] == "Nightly regression"
    assert body["bloom_artefact_url"] == "https://bloom.example.com/projects/FLT/suites/7"
