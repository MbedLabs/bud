"""Test Station enrolment keys."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.runner_keys import mint_key
from app.core.security import get_password_hash
from app.models import Runner, RunnerApiKey, TestResult, TestRun


async def _make_station(db_session, account: str) -> Runner:
    runner = Runner(
        account=account,
        password_hash=get_password_hash("a-very-long-runner-password-123"),
        token=f"token-for-{account}",
        socket_port=53035,
        location="lab-bench-row-1",
    )
    db_session.add(runner)
    await db_session.commit()
    await db_session.refresh(runner)
    return runner


async def _pin_key(db_session, label: str, runner: Runner | None) -> str:
    record, plaintext = mint_key(label=label, created_by_user_id=None)
    if runner is not None:
        record.runner_id = runner.id
    db_session.add(record)
    await db_session.commit()
    return plaintext


def _upload(results_for: str | None = None) -> dict:
    payload: dict = {
        "results": [
            {
                "test_class": "SmokeTests",
                "test_method": "test_boots",
                "passed": True,
                "duration_seconds": 1.5,
            }
        ],
        "test_suite_name": "smoke",
    }
    if results_for is not None:
        payload["runner_account"] = results_for
    return payload


@pytest_asyncio.fixture
async def two_stations(db_session):
    mine = await _make_station(db_session, "bench-mine")
    theirs = await _make_station(db_session, "bench-theirs")
    return mine, theirs


@pytest.mark.asyncio
async def test_key_cannot_file_results_as_another_station(
    unauthenticated_client, db_session, two_stations
):
    """The impersonation itself. Naming another station must not move the run."""
    mine, theirs = two_stations
    my_key = await _pin_key(db_session, "bench-mine key", mine)

    response = unauthenticated_client.post(
        "/api/results",
        json=_upload(results_for=theirs.account),
        headers={"X-API-Key": my_key},
    )

    assert response.status_code == 201, response.text

    runs = (await db_session.execute(select(TestRun))).scalars().all()
    assert len(runs) == 1
    # Attribution follows the credential, never the payload.
    assert runs[0].runner_id == mine.id
    assert runs[0].runner_id != theirs.id


@pytest.mark.asyncio
async def test_unpinned_key_cannot_upload_results(unauthenticated_client, db_session):
    """A key that has never enrolled a station names nobody, so it authorises nothing."""
    orphan_key = await _pin_key(db_session, "never used", None)

    response = unauthenticated_client.post(
        "/api/results",
        json=_upload(results_for="bench-mine"),
        headers={"X-API-Key": orphan_key},
    )

    assert response.status_code == 401, response.text


@pytest.mark.asyncio
async def test_unknown_key_is_rejected(unauthenticated_client, db_session, two_stations):
    response = unauthenticated_client.post(
        "/api/results",
        json=_upload(results_for="bench-mine"),
        headers={"X-API-Key": "budrnr_not-a-key-anyone-ever-issued"},
    )

    assert response.status_code == 401, response.text
    assert (await db_session.execute(select(TestResult))).scalars().first() is None


@pytest.mark.asyncio
async def test_inactive_station_cannot_upload(unauthenticated_client, db_session, two_stations):
    mine, _ = two_stations
    my_key = await _pin_key(db_session, "bench-mine key", mine)
    mine.is_active = False
    await db_session.commit()

    response = unauthenticated_client.post(
        "/api/results",
        json=_upload(),
        headers={"X-API-Key": my_key},
    )

    assert response.status_code == 401, response.text


@pytest.mark.asyncio
async def test_key_authenticates_its_own_station(unauthenticated_client, db_session, two_stations):
    """The key alone is enough - no account name in the body at all."""
    mine, _ = two_stations
    my_key = await _pin_key(db_session, "bench-mine key", mine)

    response = unauthenticated_client.post(
        "/api/results",
        json=_upload(),
        headers={"X-API-Key": my_key},
    )

    assert response.status_code == 201, response.text
    runs = (await db_session.execute(select(TestRun))).scalars().all()
    assert runs[0].runner_id == mine.id


@pytest.mark.asyncio
async def test_removing_a_station_keeps_its_runs_and_revokes_its_keys(client, db_session):
    """Retiring a bench must not unmake the evidence it produced."""
    station = await _make_station(db_session, "bench-retired")
    await _pin_key(db_session, "bench-retired key", station)
    # Read out before the row goes: an expired attribute would try to refresh.
    station_id = station.id
    account = station.account

    run = TestRun(
        name="nightly",
        test_case_list="smoke",
        status="Completed",
        runner_id=station_id,
    )
    db_session.add(run)
    await db_session.commit()
    run_id = run.id

    response = client.delete(f"/api/runners/{account}")
    assert response.status_code == 204, response.text

    db_session.expire_all()

    # The station is gone.
    assert (
        await db_session.execute(select(Runner).where(Runner.account == account))
    ).scalar_one_or_none() is None

    # Its credentials went with it.
    remaining_keys = (
        (await db_session.execute(select(RunnerApiKey).where(RunnerApiKey.runner_id == station_id)))
        .scalars()
        .all()
    )
    assert remaining_keys == []

    # The run survives, detached rather than deleted.
    surviving = await db_session.get(TestRun, run_id)
    assert surviving is not None
    assert surviving.runner_id is None


@pytest.mark.asyncio
async def test_minted_key_is_returned_once_and_never_listed(client, db_session):
    created = client.post("/api/runners/api-keys", json={"label": "bench-a"})
    assert created.status_code == 201, created.text
    body = created.json()
    secret = body["api_key"]
    assert secret.startswith("budrnr_")
    assert body["runner_account"] is None

    listed = client.get("/api/runners/api-keys")
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert len(rows) == 1
    # The listing carries enough to tell keys apart and nothing more.
    assert "api_key" not in rows[0]
    assert rows[0]["key_prefix"] == secret[:12]
    assert secret not in listed.text

    # Nothing anywhere stores the plaintext.
    stored = (await db_session.execute(select(RunnerApiKey))).scalars().all()
    assert len(stored) == 1
    assert stored[0].key_hash != secret


@pytest.mark.asyncio
async def test_a_revoked_key_no_longer_authenticates(
    unauthenticated_client, db_session, two_stations
):
    """Must not take the ``client`` fixture: it overrides get_uploader_entity
    globally, which would make this pass whatever the key did."""
    mine, _ = two_stations
    my_key = await _pin_key(db_session, "bench-mine key", mine)

    accepted = unauthenticated_client.post(
        "/api/results", json=_upload(), headers={"X-API-Key": my_key}
    )
    assert accepted.status_code == 201, accepted.text

    record = (
        await db_session.execute(select(RunnerApiKey).where(RunnerApiKey.runner_id == mine.id))
    ).scalar_one()
    await db_session.delete(record)
    await db_session.commit()

    refused = unauthenticated_client.post(
        "/api/results", json=_upload(), headers={"X-API-Key": my_key}
    )
    assert refused.status_code == 401, refused.text


@pytest.mark.asyncio
async def test_admin_can_revoke_a_key(client, db_session):
    created = client.post("/api/runners/api-keys", json={"label": "bench-b"})
    assert created.status_code == 201, created.text
    key_id = created.json()["id"]

    revoked = client.delete(f"/api/runners/api-keys/{key_id}")
    assert revoked.status_code == 204, revoked.text

    assert client.get("/api/runners/api-keys").json() == []
    db_session.expire_all()
    assert await db_session.get(RunnerApiKey, key_id) is None

    # A second attempt has nothing left to act on.
    assert client.delete(f"/api/runners/api-keys/{key_id}").status_code == 404
