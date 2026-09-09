"""Bud keeps the Bloom artefact a sync reached, so a run can point back at it."""

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.core.config import settings
from app.db import database as db_module
from app.models import SystemSetting, TestResult, TestRun
from app.services import bloom_sync as bloom_sync_service
from app.services.bloom_sync import _campaign_reference
from app.services.integration_secrets import encrypt_integration_secret

CAMPAIGN = {
    "id": 12,
    "campaign_id": "FLT-CMP-003",
    "name": "Nightly regression",
    "url": "https://bloom.example.com/projects/FLT/campaigns/12",
}


def test_one_campaign_is_a_reference():
    assert _campaign_reference({"campaigns": [CAMPAIGN]}) == CAMPAIGN


def test_no_campaign_is_no_reference():
    assert _campaign_reference({"campaigns": []}) is None
    assert _campaign_reference({}) is None


def test_several_campaigns_are_no_reference():
    """A run that reached two campaigns came from neither in particular."""
    assert _campaign_reference({"campaigns": [CAMPAIGN, {**CAMPAIGN, "id": 13}]}) is None


def test_a_malformed_campaign_is_no_reference():
    assert _campaign_reference({"campaigns": ["FLT-CMP-003"]}) is None
    assert _campaign_reference({"campaigns": "FLT-CMP-003"}) is None


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
async def test_a_sync_stores_the_campaign_bloom_named(_engine, monkeypatch):
    run_id = await _run_sync_against(
        monkeypatch, {"updated": 1, "not_found": [], "campaigns": [CAMPAIGN]}, "sync-backlink"
    )

    async with db_module.async_session_maker() as session:
        run = (await session.execute(select(TestRun).where(TestRun.id == run_id))).scalar_one()

    assert run.bloom_artefact_id == "FLT-CMP-003"
    assert run.bloom_artefact_name == "Nightly regression"
    assert run.bloom_artefact_url == "https://bloom.example.com/projects/FLT/campaigns/12"


@pytest.mark.asyncio
async def test_a_bloom_that_names_no_campaign_leaves_the_run_unmarked(_engine, monkeypatch):
    """An older Bloom returns no campaigns key at all, and Bud carries on."""
    run_id = await _run_sync_against(
        monkeypatch, {"updated": 1, "not_found": []}, "sync-no-campaign"
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
        bloom_artefact_id="FLT-CMP-003",
        bloom_artefact_name="Nightly regression",
        bloom_artefact_url="https://bloom.example.com/projects/FLT/campaigns/12",
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)

    response = client.get(f"/api/test-runs/{run.id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["bloom_artefact_id"] == "FLT-CMP-003"
    assert body["bloom_artefact_name"] == "Nightly regression"
    assert body["bloom_artefact_url"] == "https://bloom.example.com/projects/FLT/campaigns/12"
