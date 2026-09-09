"""An administrator names the Test Station, and that name wins."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.security import decode_access_token
from app.models import Runner, RunnerApiKey

PAYLOAD = {
    "username": "whatever-the-bench-typed",
    "password": "a-very-long-runner-password-123",
    "socket_port": 53035,
}


@pytest.fixture(autouse=True)
def _no_rate_limit():
    from app.core.deps import limiter

    limiter.enabled = False
    yield
    limiter.enabled = True


def _mint(client, label: str, station_name: str | None = None) -> str:
    body: dict = {"label": label}
    if station_name is not None:
        body["station_name"] = station_name
    response = client.post("/api/runners/api-keys", json=body)
    assert response.status_code == 201, response.text
    return response.json()["api_key"]


def test_the_name_the_administrator_chose_wins(client):
    key = _mint(client, "bench-a key", "bench-a")

    response = client.post("/api/runners/register", json=PAYLOAD, headers={"X-API-Key": key})

    assert response.status_code == 201, response.text
    assert response.json()["account"] == "bench-a"


def test_a_key_with_no_name_leaves_the_bench_its_own(client):
    key = _mint(client, "unnamed key")

    response = client.post("/api/runners/register", json=PAYLOAD, headers={"X-API-Key": key})

    assert response.status_code == 201, response.text
    assert response.json()["account"] == PAYLOAD["username"]


@pytest.mark.asyncio
async def test_the_token_identifies_the_station_by_id(client, db_session):
    key = _mint(client, "bench-a key", "bench-a")
    token = client.post("/api/runners/register", json=PAYLOAD, headers={"X-API-Key": key}).json()[
        "token"
    ]

    runner = (
        await db_session.execute(select(Runner).where(Runner.account == "bench-a"))
    ).scalar_one()

    payload = decode_access_token(token)
    assert payload["rid"] == str(runner.id)


def test_a_name_already_taken_is_refused(client):
    first = _mint(client, "bench-a key", "bench-a")
    client.post("/api/runners/register", json=PAYLOAD, headers={"X-API-Key": first})

    response = client.post(
        "/api/runners/api-keys", json={"label": "second", "station_name": "bench-a"}
    )

    assert response.status_code == 409, response.text
    assert "already named" in response.json()["detail"]


def test_a_name_another_unused_key_reserves_is_refused(client):
    _mint(client, "bench-a key", "bench-a")

    response = client.post(
        "/api/runners/api-keys", json={"label": "second", "station_name": "bench-a"}
    )

    assert response.status_code == 409, response.text
    assert "already reserves" in response.json()["detail"]


def test_a_name_that_would_break_a_url_is_refused(client):
    for bad in ["Ada's bench", "lab 2", "bench/a", "bench#3", "ab"]:
        response = client.post("/api/runners/api-keys", json={"label": "x", "station_name": bad})
        assert response.status_code == 422, f"{bad} was accepted"


@pytest.mark.asyncio
async def test_an_administrator_renames_a_station(client, db_session):
    key = _mint(client, "bench-a key", "bench-a")
    client.post("/api/runners/register", json=PAYLOAD, headers={"X-API-Key": key})

    response = client.patch("/api/runners/bench-a", json={"account": "bench-a-renamed"})

    assert response.status_code == 200, response.text
    assert response.json()["account"] == "bench-a-renamed"

    db_session.expire_all()
    record = (await db_session.execute(select(RunnerApiKey))).scalars().first()
    assert record.station_name == "bench-a-renamed"


@pytest.mark.asyncio
async def test_a_renamed_station_keeps_its_token(client, db_session):
    """The whole point of identifying a station by id."""
    key = _mint(client, "bench-a key", "bench-a")
    token = client.post("/api/runners/register", json=PAYLOAD, headers={"X-API-Key": key}).json()[
        "token"
    ]

    assert client.patch("/api/runners/bench-a", json={"account": "moved"}).status_code == 200

    db_session.expire_all()
    from app.core.runner_auth import authenticate_runner_token

    resolved = await authenticate_runner_token(token, db_session)
    assert resolved is not None
    assert resolved.account == "moved"


def test_renaming_onto_a_taken_name_is_refused(client):
    first = _mint(client, "a", "bench-a")
    client.post("/api/runners/register", json=PAYLOAD, headers={"X-API-Key": first})
    second = _mint(client, "b", "bench-b")
    other = dict(PAYLOAD, username="ignored-anyway")
    client.post("/api/runners/register", json=other, headers={"X-API-Key": second})

    response = client.patch("/api/runners/bench-b", json={"account": "bench-a"})

    assert response.status_code == 409, response.text


def test_renaming_an_unknown_station_is_a_404(client):
    assert client.patch("/api/runners/nobody", json={"account": "somebody"}).status_code == 404
