"""Notification channels API: admin-only, URL and secret write-only and encrypted, test message."""

import httpx
import pytest
from cryptography.fernet import Fernet

from app.core.config import settings
from app.models import NotificationChannel
from app.services import notify

HOOK = "https://hooks.slack.com/services/T000/B000/abcdefghijklmnopqrstuvwxyz"


class _Accepting:
    """A stand-in httpx.AsyncClient that accepts every post."""

    calls: list = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, content=None, headers=None):
        _Accepting.calls.append(url)
        return httpx.Response(200, text="ok")


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setattr(settings, "INTEGRATION_ENCRYPTION_KEY", Fernet.generate_key().decode())
    _Accepting.calls = []


def _create(client, **overrides):
    body = {
        "name": "qa",
        "format": "slack",
        "url": HOOK,
        "secret": "s3cr3t",
        "run_filter": "failures",
    }
    body.update(overrides)
    return client.post("/api/settings/notifications/channels", json=body)


@pytest.mark.asyncio
async def test_url_and_secret_are_write_only_and_encrypted(client, db_session):
    created = _create(client)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["url_prefix"] == HOOK[:40] + "..."
    assert body["has_secret"] is True
    assert "url" not in body and "secret" not in body and HOOK not in created.text

    listed = client.get("/api/settings/notifications/channels")
    assert listed.status_code == 200
    assert HOOK not in listed.text and "s3cr3t" not in listed.text

    stored = await db_session.get(NotificationChannel, body["id"])
    assert HOOK not in stored.url_encrypted
    assert "s3cr3t" not in stored.secret_encrypted


@pytest.mark.asyncio
async def test_update_keeps_the_url_unless_given_and_clears_the_secret(client, db_session):
    channel_id = _create(client).json()["id"]
    before = (await db_session.get(NotificationChannel, channel_id)).url_encrypted

    patched = client.patch(
        f"/api/settings/notifications/channels/{channel_id}",
        json={"run_filter": "all", "secret": ""},
    )

    assert patched.status_code == 200, patched.text
    assert patched.json()["run_filter"] == "all"
    assert patched.json()["has_secret"] is False
    db_session.expire_all()
    assert (await db_session.get(NotificationChannel, channel_id)).url_encrypted == before


def test_invalid_input_is_rejected(client):
    assert _create(client, url="ftp://hooks.example.com/x").status_code == 422
    assert _create(client, url="https://user:pw@hooks.example.com/x").status_code == 422
    assert _create(client, format="email").status_code == 422
    assert _create(client, run_filter="sometimes").status_code == 422
    assert _create(client).status_code == 201
    assert _create(client).status_code == 400


def test_delete_and_missing_channel(client):
    channel_id = _create(client).json()["id"]
    assert client.delete(f"/api/settings/notifications/channels/{channel_id}").status_code == 204
    assert client.delete(f"/api/settings/notifications/channels/{channel_id}").status_code == 404
    assert client.patch("/api/settings/notifications/channels/999", json={}).status_code == 404


def test_send_test_message(client, monkeypatch):
    monkeypatch.setattr(notify.httpx, "AsyncClient", _Accepting)
    channel_id = _create(client).json()["id"]

    result = client.post(f"/api/settings/notifications/channels/{channel_id}/test")

    assert result.status_code == 200, result.text
    assert result.json() == {"delivered": True, "attempts": 1, "status_code": 200, "error": None}
    assert _Accepting.calls == [HOOK]


def test_channels_need_an_authenticated_administrator(unauthenticated_client):
    assert unauthenticated_client.get("/api/settings/notifications/channels").status_code == 401
