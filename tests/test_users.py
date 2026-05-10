from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.models.user_token import UserToken, UserTokenPurpose


@pytest.mark.asyncio
async def test_delete_user_success(client: TestClient, db_session: AsyncSession):
    # 1. Create a user to delete
    user_to_delete = User(
        email="to_delete@example.com",
        full_name="To Delete",
        hashed_password="hash",
        role=UserRole.viewer,
        is_active=True,
    )
    db_session.add(user_to_delete)
    await db_session.flush()
    user_id = user_to_delete.id

    # 2. Add a token for this user
    token = UserToken(
        user_id=user_id,
        purpose=UserTokenPurpose.invite,
        token_hash="some-hash",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    db_session.add(token)
    await db_session.flush()

    # 3. Delete the user (using /api/users prefix)
    response = client.delete(f"/api/users/{user_id}")
    assert response.status_code == 204

    # 4. Verify user and tokens are gone
    result = await db_session.execute(select(User).where(User.id == user_id))
    assert result.scalar_one_or_none() is None

    result = await db_session.execute(select(UserToken).where(UserToken.user_id == user_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_user_with_invites(client: TestClient, db_session: AsyncSession):
    # 1. Create an inviter and an invitee
    inviter = User(
        email="inviter@example.com",
        full_name="Inviter",
        hashed_password="hash",
        role=UserRole.admin,
    )
    db_session.add(inviter)
    await db_session.flush()
    inviter_id = inviter.id

    invitee = User(
        email="invitee@example.com",
        full_name="Invitee",
        hashed_password="hash",
        role=UserRole.viewer,
        invited_by_user_id=inviter_id,
    )
    db_session.add(invitee)
    await db_session.flush()

    # 2. Delete the inviter
    response = client.delete(f"/api/users/{inviter_id}")
    assert response.status_code == 204

    # 3. Verify invitee's invited_by_user_id is now None
    await db_session.refresh(invitee)
    assert invitee.invited_by_user_id is None


@pytest.mark.asyncio
async def test_delete_self_fails(client: TestClient, test_user: User):
    # test_user.id is 1 (from conftest)
    response = client.delete(f"/api/users/{test_user.id}")
    assert response.status_code == 400
    assert response.json()["detail"] == "Admin users cannot delete their own account"


@pytest.mark.asyncio
async def test_delete_nonexistent_user(client: TestClient):
    response = client.delete("/api/users/9999")
    assert response.status_code == 404
