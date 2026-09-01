"""
First-run setup flow.

The endpoints are unauthenticated, so the tests that matter are the ones
proving the window closes: once any user exists, the instance must refuse to
create another administrator and must stop advertising that setup is needed.

Note the interaction with AUTO_SEED_ADMIN. When that is on, the lifespan seeds
an administrator before the first request, so setup is never required — which
is why a packaged deployment that wants the setup screen must leave it off.
"""

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
    """A client whose instance has never had a user.

    Depends on ``unauthenticated_client`` so the app's lifespan has already run;
    the seeded administrator it may have created is then removed, leaving the
    empty-table state a packaged first boot actually starts from.
    """
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
