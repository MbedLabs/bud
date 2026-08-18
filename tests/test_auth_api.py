"""Authentication endpoints exercised against real credentials.

These use ``unauthenticated_client`` so login, the refresh rotation and the
one-time link flows all run for real, rather than through the dependency
overrides that the ``client`` fixture installs.
"""

from __future__ import annotations

import re

import pytest
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.user_token import UserToken, UserTokenPurpose

PASSWORD = "a-sufficiently-long-password"


def refresh_cookie(response) -> str | None:
    """Read the refresh token from Set-Cookie.

    The TestClient's jar is not a reliable source here: reading it back can come
    up empty, and a per-request cookie merges with whatever the jar already
    holds - which quietly sends the *rotated* token instead of the one under
    test.
    """
    match = re.search(r"refresh_token=([^;]+)", response.headers.get("set-cookie", ""))
    return match.group(1) if match else None


@pytest.fixture(autouse=True)
def _no_rate_limit():
    """The limiter guards login at 10/minute; these tests are not about it."""
    from app.core.deps import limiter

    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture
def smtp(monkeypatch):
    """Capture outbound mail instead of requiring a server."""
    from app.services import mail_service

    sent: list[dict] = []
    monkeypatch.setattr(
        mail_service,
        "send_email",
        lambda **kwargs: sent.append(kwargs),
    )
    return sent


async def _account(db_session, email="person@example.com", **overrides) -> User:
    user = User(
        email=email,
        full_name=overrides.pop("full_name", "Person"),
        hashed_password=get_password_hash(overrides.pop("password", PASSWORD)),
        role=overrides.pop("role", UserRole.viewer),
        is_active=overrides.pop("is_active", True),
        session_version=overrides.pop("session_version", 1),
        **overrides,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


class TestLogin:
    @pytest.mark.asyncio
    async def test_returns_an_access_token_and_the_user(self, unauthenticated_client, db_session):
        await _account(db_session)
        response = unauthenticated_client.post(
            "/api/auth/login", json={"email": "person@example.com", "password": PASSWORD}
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["access_token"]
        assert body["user"]["email"] == "person@example.com"
        assert "hashed_password" not in body["user"]

    @pytest.mark.asyncio
    async def test_sets_an_httponly_refresh_cookie(self, unauthenticated_client, db_session):
        await _account(db_session)
        response = unauthenticated_client.post(
            "/api/auth/login", json={"email": "person@example.com", "password": PASSWORD}
        )
        cookie_header = response.headers.get("set-cookie", "")
        assert "refresh_token=" in cookie_header
        assert "HttpOnly" in cookie_header

    @pytest.mark.asyncio
    async def test_rejects_a_wrong_password(self, unauthenticated_client, db_session):
        await _account(db_session)
        response = unauthenticated_client.post(
            "/api/auth/login", json={"email": "person@example.com", "password": "wrong-password"}
        )
        assert response.status_code == 401

    def test_rejects_an_unknown_address(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_an_unknown_address_is_indistinguishable_from_a_wrong_password(
        self, unauthenticated_client, db_session
    ):
        """Neither response may reveal whether the account exists."""
        await _account(db_session)
        wrong_password = unauthenticated_client.post(
            "/api/auth/login", json={"email": "person@example.com", "password": "nope"}
        )
        unknown = unauthenticated_client.post(
            "/api/auth/login", json={"email": "ghost@example.com", "password": "nope"}
        )
        assert wrong_password.status_code == unknown.status_code
        assert wrong_password.json()["detail"] == unknown.json()["detail"]

    @pytest.mark.asyncio
    async def test_a_deactivated_account_is_refused(self, unauthenticated_client, db_session):
        await _account(db_session, email="off@example.com", is_active=False)
        response = unauthenticated_client.post(
            "/api/auth/login", json={"email": "off@example.com", "password": PASSWORD}
        )
        assert response.status_code == 403


class TestRefreshRotation:
    async def _login(self, client, db_session):
        await _account(db_session)
        response = client.post(
            "/api/auth/login", json={"email": "person@example.com", "password": PASSWORD}
        )
        assert response.status_code == 200, response.text
        return response

    @pytest.mark.asyncio
    async def test_exchanges_the_cookie_for_a_new_access_token(
        self, unauthenticated_client, db_session
    ):
        login = await self._login(unauthenticated_client, db_session)
        response = unauthenticated_client.post(
            "/api/auth/refresh", cookies={"refresh_token": refresh_cookie(login)}
        )
        assert response.status_code == 200, response.text
        assert response.json()["access_token"]

    @pytest.mark.asyncio
    async def test_a_refresh_token_is_single_use(self, unauthenticated_client, db_session):
        """The rotated-away token must not work again, even for the real client."""
        login = await self._login(unauthenticated_client, db_session)
        first_token = refresh_cookie(login)
        assert first_token

        rotation = unauthenticated_client.post(
            "/api/auth/refresh", cookies={"refresh_token": first_token}
        )
        assert rotation.status_code == 200
        assert refresh_cookie(rotation) != first_token, "the token must rotate"

        # Clear the jar so only the consumed token is presented.
        unauthenticated_client.cookies.clear()
        replay = unauthenticated_client.post(
            "/api/auth/refresh", cookies={"refresh_token": first_token}
        )
        assert replay.status_code == 401

    def test_refusing_without_a_cookie(self, unauthenticated_client):
        assert unauthenticated_client.post("/api/auth/refresh").status_code == 401

    def test_refusing_a_forged_cookie(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/auth/refresh", cookies={"refresh_token": "not-a-real-token"}
        )
        assert response.status_code == 401


class TestLogout:
    @pytest.mark.asyncio
    async def test_revokes_the_refresh_token(self, unauthenticated_client, db_session):
        await _account(db_session)
        login = unauthenticated_client.post(
            "/api/auth/login", json={"email": "person@example.com", "password": PASSWORD}
        )
        token = refresh_cookie(login)
        assert token

        logout = unauthenticated_client.post("/api/auth/logout", cookies={"refresh_token": token})
        assert logout.status_code == 200

        unauthenticated_client.cookies.clear()
        reused = unauthenticated_client.post("/api/auth/refresh", cookies={"refresh_token": token})
        assert reused.status_code == 401

    def test_logging_out_without_a_session_still_succeeds(self, unauthenticated_client):
        assert unauthenticated_client.post("/api/auth/logout").status_code == 200


class TestCurrentUser:
    def test_me_requires_a_token(self, unauthenticated_client):
        assert unauthenticated_client.get("/api/auth/me").status_code == 401

    @pytest.mark.asyncio
    async def test_me_returns_the_authenticated_user(self, unauthenticated_client, db_session):
        await _account(db_session)
        login = unauthenticated_client.post(
            "/api/auth/login", json={"email": "person@example.com", "password": PASSWORD}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        response = unauthenticated_client.get("/api/auth/me", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["email"] == "person@example.com"

    @pytest.mark.asyncio
    async def test_updates_the_display_name(self, unauthenticated_client, db_session):
        await _account(db_session)
        login = unauthenticated_client.post(
            "/api/auth/login", json={"email": "person@example.com", "password": PASSWORD}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        response = unauthenticated_client.put(
            "/api/auth/me", json={"full_name": "Renamed"}, headers=headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["full_name"] == "Renamed"


class TestSelfServiceEmailChange:
    @pytest.mark.asyncio
    async def test_admin_authorizes_from_current_then_verifies_new_mailbox(
        self, unauthenticated_client, db_session, smtp
    ):
        admin = await _account(
            db_session,
            email="admin-before@example.com",
            role=UserRole.admin,
        )
        login = unauthenticated_client.post(
            "/api/auth/login",
            json={"email": admin.email, "password": PASSWORD},
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        response = unauthenticated_client.post(
            "/api/auth/me/email",
            json={
                "current_password": PASSWORD,
                "new_email": "admin-after@example.com",
            },
            headers=headers,
        )

        assert response.status_code == 200, response.text
        assert "current email" in response.json()["message"].lower()
        await db_session.refresh(admin)
        assert admin.email == "admin-before@example.com"
        assert admin.pending_email == "admin-after@example.com"
        assert admin.email_change_status == "awaiting_current_confirmation"
        token = (
            await db_session.scalars(
                select(UserToken).where(
                    UserToken.user_id == admin.id,
                    UserToken.purpose == UserTokenPurpose.email_change,
                )
            )
        ).one()
        assert token.created_by_user_id == admin.id
        assert token.target_email == "admin-after@example.com"
        assert smtp and smtp[0]["to_email"] == "admin-before@example.com"
        assert "authorize" in smtp[0]["subject"].lower()

        current_mailbox_token = re.search(r"#token=([^\s<]+)", smtp[0]["text_body"])
        assert current_mailbox_token
        current_confirmation = unauthenticated_client.post(
            "/api/auth/confirm-email-change",
            json={"token": current_mailbox_token.group(1)},
        )

        assert current_confirmation.status_code == 200, current_confirmation.text
        assert "new email" in current_confirmation.json()["message"].lower()
        await db_session.refresh(admin)
        assert admin.email == "admin-before@example.com"
        assert admin.pending_email == "admin-after@example.com"
        assert admin.email_change_status == "awaiting_confirmation"
        assert len(smtp) == 2
        assert smtp[1]["to_email"] == "admin-after@example.com"

        new_mailbox_token = re.search(r"#token=([^\s<]+)", smtp[1]["text_body"])
        assert new_mailbox_token
        new_confirmation = unauthenticated_client.post(
            "/api/auth/confirm-email-change",
            json={"token": new_mailbox_token.group(1)},
        )

        assert new_confirmation.status_code == 200, new_confirmation.text
        await db_session.refresh(admin)
        assert admin.email == "admin-after@example.com"
        assert admin.pending_email is None
        assert admin.email_change_status is None
        assert admin.session_version == 2

    @pytest.mark.asyncio
    async def test_non_admin_still_waits_for_approval(
        self, unauthenticated_client, db_session, smtp
    ):
        viewer = await _account(db_session, email="viewer-before@example.com")
        login = unauthenticated_client.post(
            "/api/auth/login",
            json={"email": viewer.email, "password": PASSWORD},
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        response = unauthenticated_client.post(
            "/api/auth/me/email",
            json={
                "current_password": PASSWORD,
                "new_email": "viewer-after@example.com",
            },
            headers=headers,
        )

        assert response.status_code == 200, response.text
        await db_session.refresh(viewer)
        assert viewer.email_change_status == "requested"
        assert smtp == []


class TestPasswordChange:
    @pytest.mark.asyncio
    async def test_changing_a_password_requires_the_current_one(
        self, unauthenticated_client, db_session
    ):
        await _account(db_session)
        login = unauthenticated_client.post(
            "/api/auth/login", json={"email": "person@example.com", "password": PASSWORD}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        wrong = unauthenticated_client.put(
            "/api/auth/me/password",
            json={"current_password": "not-it", "new_password": "another-long-password"},
            headers=headers,
        )
        assert wrong.status_code in (400, 401)

    @pytest.mark.asyncio
    async def test_a_changed_password_signs_other_sessions_out(
        self, unauthenticated_client, db_session
    ):
        """Changing the password bumps session_version, invalidating old tokens."""
        user = await _account(db_session)
        login = unauthenticated_client.post(
            "/api/auth/login", json={"email": "person@example.com", "password": PASSWORD}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        changed = unauthenticated_client.put(
            "/api/auth/me/password",
            json={"current_password": PASSWORD, "new_password": "a-brand-new-long-password"},
            headers=headers,
        )
        assert changed.status_code == 200, changed.text

        await db_session.refresh(user)
        assert user.session_version > 1

        stale = unauthenticated_client.get("/api/auth/me", headers=headers)
        assert stale.status_code == 401

    @pytest.mark.asyncio
    async def test_rejects_a_short_new_password(self, unauthenticated_client, db_session):
        await _account(db_session)
        login = unauthenticated_client.post(
            "/api/auth/login", json={"email": "person@example.com", "password": PASSWORD}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        response = unauthenticated_client.put(
            "/api/auth/me/password",
            json={"current_password": PASSWORD, "new_password": "short"},
            headers=headers,
        )
        assert response.status_code == 422


class TestPasswordReset:
    @pytest.mark.asyncio
    async def test_forgot_password_does_not_reveal_whether_an_account_exists(
        self, unauthenticated_client, db_session, smtp
    ):
        await _account(db_session)
        known = unauthenticated_client.post(
            "/api/auth/forgot-password", json={"email": "person@example.com"}
        )
        unknown = unauthenticated_client.post(
            "/api/auth/forgot-password", json={"email": "ghost@example.com"}
        )
        assert known.status_code == unknown.status_code
        assert known.json() == unknown.json()

    @pytest.mark.asyncio
    async def test_a_reset_token_is_issued_for_a_real_account(
        self, unauthenticated_client, db_session, smtp
    ):
        await _account(db_session)
        unauthenticated_client.post(
            "/api/auth/forgot-password", json={"email": "person@example.com"}
        )
        tokens = (
            (
                await db_session.execute(
                    select(UserToken).where(UserToken.purpose == UserTokenPurpose.password_reset)
                )
            )
            .scalars()
            .all()
        )
        assert len(tokens) == 1

    def test_resetting_with_a_bogus_token_is_refused(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/auth/reset-password",
            json={"token": "nonsense", "new_password": "a-long-enough-password"},
        )
        assert response.status_code in (400, 401, 404)


class TestInviteInfo:
    def test_an_unknown_invite_token_is_reported_invalid(self, unauthenticated_client):
        response = unauthenticated_client.post("/api/auth/invite-info", json={"token": "nope"})
        assert response.status_code in (200, 400, 404)
        if response.status_code == 200:
            assert response.json()["valid"] is False

    def test_accepting_an_unknown_invite_is_refused(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/auth/accept-invite",
            json={"token": "nope", "password": "a-long-enough-password"},
        )
        assert response.status_code in (400, 401, 404)


class TestEmailVerification:
    def test_verifying_with_a_bogus_token_is_refused(self, unauthenticated_client):
        response = unauthenticated_client.post("/api/auth/verify-email", json={"token": "nope"})
        assert response.status_code in (400, 401, 404)

    def test_confirming_an_email_change_with_a_bogus_token_is_refused(self, unauthenticated_client):
        response = unauthenticated_client.post(
            "/api/auth/confirm-email-change", json={"token": "nope"}
        )
        assert response.status_code in (400, 401, 404)
