"""Bloom integration credentials are write-only and encrypted at rest."""

import pytest
from cryptography.fernet import Fernet

from app.core.config import settings
from app.models import SystemSetting


@pytest.mark.asyncio
async def test_bloom_token_is_encrypted_and_never_echoed(client, db_session, monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "INTEGRATION_ENCRYPTION_KEY", key)
    raw = "blm_sync_this-is-a-test-service-token"

    update = client.post(
        "/api/settings/integrations/PLM",
        json={"bloom_url": "https://bloom.example.com", "bloom_token": raw},
    )

    assert update.status_code == 200
    body = update.json()
    assert body["has_bloom_token"] is True
    assert body["bloom_token_prefix"] == raw[:20]
    assert "bloom_token" not in body
    stored = await db_session.get(SystemSetting, "bloom_token_encrypted")
    assert stored is not None
    assert raw not in stored.value

    get_response = client.get("/api/settings/integrations/PLM")
    assert raw not in get_response.text
    assert "bloom_token" not in get_response.json()


@pytest.mark.asyncio
async def test_destination_origin_change_requires_new_or_cleared_token(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(settings, "INTEGRATION_ENCRYPTION_KEY", Fernet.generate_key().decode())
    raw = "blm_sync_keep-this-secret"
    client.post(
        "/api/settings/integrations/PLM",
        json={"bloom_url": "https://bloom.example.com", "bloom_token": raw},
    )
    before = (await db_session.get(SystemSetting, "bloom_token_encrypted")).value

    response = client.post(
        "/api/settings/integrations/PLM",
        json={"bloom_url": "https://new.example.com", "bloom_token": "********"},
    )

    assert response.status_code == 422
    await db_session.refresh(await db_session.get(SystemSetting, "bloom_token_encrypted"))
    after = (await db_session.get(SystemSetting, "bloom_token_encrypted")).value
    assert after == before


@pytest.mark.asyncio
async def test_same_origin_url_change_retains_saved_token(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "INTEGRATION_ENCRYPTION_KEY", Fernet.generate_key().decode())
    raw = "blm_sync_keep-this-secret"
    client.post(
        "/api/settings/integrations/PLM",
        json={"bloom_url": "https://bloom.example.com", "bloom_token": raw},
    )
    before = (await db_session.get(SystemSetting, "bloom_token_encrypted")).value

    response = client.post(
        "/api/settings/integrations/PLM",
        json={"bloom_url": "https://bloom.example.com/root", "bloom_token": "********"},
    )

    assert response.status_code == 200
    after = (await db_session.get(SystemSetting, "bloom_token_encrypted")).value
    assert after == before


def test_bloom_url_with_invalid_port_is_rejected(client):
    response = client.post(
        "/api/settings/integrations/PLM",
        json={"bloom_url": "https://bloom.example.com:not-a-port"},
    )

    assert response.status_code == 422


def test_generic_settings_endpoints_cannot_read_or_write_bloom_secret(client):
    read = client.get("/api/settings/bloom_token_encrypted")
    write = client.put(
        "/api/settings/bloom_token_encrypted",
        json={"value": "plaintext"},
    )

    assert read.status_code == 404
    assert write.status_code == 403
