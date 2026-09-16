"""First-run setup flow."""

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from app.models.user import User, UserRole

VALID_PASSWORD = "a-sufficiently-long-passphrase"


def _payload(**overrides):
    body = {
        "email": "owner@example.com",
        "password": VALID_PASSWORD,
        "full_name": "Instance Owner",
    }
    body.update(overrides)
    return body


@pytest_asyncio.fixture
async def fresh_client(unauthenticated_client, db_session):
    """A client whose instance has never had a user."""
    await db_session.execute(delete(User))
    await db_session.commit()
    return unauthenticated_client


def test_status_reports_setup_required_on_empty_instance(fresh_client):
    response = fresh_client.get("/api/setup/status")

    assert response.status_code == 200
    assert response.json() == {"setup_required": True}


def test_status_reports_setup_done_once_a_user_exists(unauthenticated_client):
    """AUTO_SEED_ADMIN has already produced a user, so setup must not offer itself."""
    response = unauthenticated_client.get("/api/setup/status")

    assert response.status_code == 200
    assert response.json() == {"setup_required": False}


@pytest.mark.asyncio
async def test_creates_an_active_admin_then_closes_the_window(fresh_client, db_session):
    created = fresh_client.post("/api/setup", json=_payload())
    assert created.status_code == 201

    result = await db_session.execute(select(User).where(User.email == "owner@example.com"))
    admin = result.scalar_one()
    assert admin.role is UserRole.admin
    assert admin.is_active is True
    # The password must be hashed, never stored as given.
    assert admin.hashed_password != VALID_PASSWORD

    assert fresh_client.get("/api/setup/status").json() == {"setup_required": False}

    second = fresh_client.post("/api/setup", json=_payload(email="squatter@example.com"))
    assert second.status_code == 409

    total = await db_session.execute(select(func.count()).select_from(User))
    assert total.scalar_one() == 1


def test_rejects_a_password_below_the_shared_policy(fresh_client):
    response = fresh_client.post("/api/setup", json=_payload(password="short"))

    assert response.status_code == 422


def test_setup_returns_no_secret(fresh_client, monkeypatch):
    """Setup hands over no secret at all."""
    monkeypatch.setattr("app.api.setup.send_admin_welcome_email", lambda **kw: None)

    body = fresh_client.post("/api/setup", json=_payload()).json()
    assert "runner_api_key" not in body
    assert body["message"]

    # Setup is closed now.
    assert fresh_client.get("/api/setup/status").json() == {"setup_required": False}


def test_setup_succeeds_when_mail_is_unavailable(fresh_client, monkeypatch):
    """No SMTP is a supported deployment, not a failure."""
    from app.services.mail_service import MailConfigurationError

    def _boom(**kwargs):
        raise MailConfigurationError("SMTP is disabled")

    monkeypatch.setattr("app.api.setup.send_admin_welcome_email", _boom)

    response = fresh_client.post("/api/setup", json=_payload())

    assert response.status_code == 201
    assert fresh_client.get("/api/setup/status").json() == {"setup_required": False}


def test_setup_emails_the_new_administrator(fresh_client, monkeypatch):
    sent = {}
    monkeypatch.setattr("app.api.setup.send_admin_welcome_email", lambda **kw: sent.update(kw))

    fresh_client.post("/api/setup", json=_payload())

    assert sent["to_email"] == "owner@example.com"
    assert sent["full_name"] == "Instance Owner"
    assert sent["login_link"].endswith("/login")
