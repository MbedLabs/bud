from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.core.config import settings
from app.db import database as db_module
from app.models import SystemSetting, TestResult, TestRun, TestRunEvent
from app.services import bloom_sync as bloom_sync_service
from app.services.bloom_sync import _coalesce_results_by_tc_id
from app.services.integration_secrets import encrypt_integration_secret


async def async_iter(iterable):
    for item in iterable:
        yield item


async def test_coalesce_results_by_tc_id_reduces_methods_to_one_tc_result():
    results = [
        SimpleNamespace(
            passed=True,
            error_message=None,
            created_at=None,
            test_metadata={"tc_id": "FLT-TC-001"},
        ),
        SimpleNamespace(
            passed=False,
            error_message="Invalid credentials produce a documented failure outcome",
            created_at=None,
            test_metadata={"tc_id": "FLT-TC-001"},
        ),
        SimpleNamespace(
            passed=True,
            error_message=None,
            created_at=None,
            test_metadata={"tc_id": "FLT-TC-035"},
        ),
    ]

    coalesced = await _coalesce_results_by_tc_id(async_iter(results), 5)
    payload = sorted(coalesced, key=lambda item: item["tc_id"])

    assert payload == [
        {
            "bud_run_id": 5,
            "comment": "Invalid credentials produce a documented failure outcome",
            "executed_at": payload[0]["executed_at"],
            "status": "Failed",
            "tc_id": "FLT-TC-001",
        },
        {
            "bud_run_id": 5,
            "comment": f"Last result from Bud run 5, executed at {payload[1]['executed_at']}",
            "executed_at": payload[1]["executed_at"],
            "status": "Passed",
            "tc_id": "FLT-TC-035",
        },
    ]


@pytest.mark.asyncio
async def test_sync_results_to_bloom_skips_when_settings_missing(_engine):
    async with db_module.async_session_maker() as session:
        run = TestRun(name="sync-missing-config", test_case_list="Bud.Tests", status="Completed")
        session.add(run)
        await session.commit()
        await session.refresh(run)
        run_id = run.id

    await bloom_sync_service.sync_results_to_bloom(run_id)

    async with db_module.async_session_maker() as session:
        events = (
            (
                await session.execute(
                    select(TestRunEvent)
                    .where(TestRunEvent.test_run_id == run_id)
                    .order_by(TestRunEvent.sequence)
                )
            )
            .scalars()
            .all()
        )

    assert len(events) == 1
    assert events[0].stage == "bloom_sync"
    assert events[0].status == "skipped"
    assert events[0].title == "Bloom sync skipped"
    assert "not configured" in (events[0].message or "").lower()


@pytest.mark.asyncio
async def test_sync_results_to_bloom_records_failed_event_on_401(_engine, monkeypatch):
    monkeypatch.setattr(settings, "INTEGRATION_ENCRYPTION_KEY", Fernet.generate_key().decode())

    class FakeResponse:
        status_code = 401
        text = "unauthorized"

        def json(self):
            return {"detail": "unauthorized"}

    async def fake_post_to_bloom_with_retry(
        bloom_url: str, bloom_token: str, payload_results: list[dict]
    ):
        assert bloom_url == "https://bloom.example.com"
        assert bloom_token == "cached-bloom-token"
        assert payload_results == [
            {
                "tc_id": "PRJ-TC-001",
                "status": "Passed",
                "comment": payload_results[0]["comment"],
                "executed_at": payload_results[0]["executed_at"],
                "bud_run_id": 1,
            }
        ]
        return FakeResponse()

    monkeypatch.setattr(
        bloom_sync_service,
        "_post_to_bloom_with_retry",
        fake_post_to_bloom_with_retry,
    )

    async with db_module.async_session_maker() as session:
        run = TestRun(name="sync-401", test_case_list="Bud.Tests", status="Completed")
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

    async with db_module.async_session_maker() as session:
        events = (
            (
                await session.execute(
                    select(TestRunEvent)
                    .where(TestRunEvent.test_run_id == run_id)
                    .order_by(TestRunEvent.sequence)
                )
            )
            .scalars()
            .all()
        )

    assert len(events) == 2
    assert events[0].status == "running"
    assert events[0].title == "Bloom sync requested"
    assert events[1].status == "failed"
    assert events[1].title == "Bloom sync failed"
    assert events[1].message == "Bloom returned HTTP 401."
    assert events[1].event_metadata == {"response": "unauthorized"}
