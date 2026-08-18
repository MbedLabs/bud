"""The one-time link flows, end to end.

Invitation, password reset, email verification and email change all hand out a
single-use token and then consume it. These drive each flow with the real token
rather than a stub, so the acceptance path - not just the rejection path - is
covered.
"""

from __future__ import annotations

import re

import pytest
from sqlalchemy import select

from app.core.security import get_password_hash, verify_password
from app.models.user import User, UserRole
from app.models.user_token import UserToken, UserTokenPurpose

PASSWORD = "a-sufficiently-long-password"
NEW_PASSWORD = "an-entirely-different-password"


@pytest.fixture(autouse=True)
def _no_rate_limit():
    from app.core.deps import limiter

    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture
def mailbox(monkeypatch):
    """Capture every outbound message so the token in its body can be read back."""
    from app.services import mail_service

    sent: list[dict] = []

    def _capture(*, to_email, subject, text_body, html_body=None):
        sent.append(
            {"to": to_email, "subject": subject, "text": text_body, "html": html_body or ""}
        )

    monkeypatch.setattr(mail_service, "send_email", _capture)
    return sent


def token_in(mailbox: list[dict]) -> str:
    """Pull the ``#token=`` fragment out of the most recent message."""
    assert mailbox, "no message was sent"
    body = mailbox[-1]["text"] + mailbox[-1]["html"]
    match = re.search(r"#token=([A-Za-z0-9_\-]+)", body)
    assert match, f"no token in the message body: {body[:400]}"
    return match.group(1)


def token_in_link(link: str) -> str:
    match = re.search(r"#token=([A-Za-z0-9_\-]+)", link)
    assert match, f"no token in {link}"
    return match.group(1)


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


class TestInvitationLifecycle:
    def test_the_invite_link_carries_the_token_in_the_fragment(self, client, mailbox):
        """A fragment never reaches the server, so the token stays out of logs."""
        response = client.post(
            "/api/users/invite", json={"email": "new@example.com", "full_name": "New"}
        )
        assert response.status_code == 201, response.text
        link = response.json()["invite_link"]
        assert "#token=" in link
        assert "?token=" not in link

    def test_invite_info_describes_a_valid_invitation(
        self, client, mailbox, unauthenticated_client
    ):
        created = client.post(
            "/api/users/invite", json={"email": "info@example.com", "full_name": "Info"}
        )
        token = token_in_link(created.json()["invite_link"])

        info = unauthenticated_client.post("/api/auth/invite-info", json={"token": token})
        assert info.status_code == 200, info.text
        body = info.json()
        assert body["valid"] is True
        assert body["email"] == "info@example.com"
        assert body["expired"] is False

    @pytest.mark.asyncio
    async def test_accepting_an_invitation_sets_the_password(
        self, client, unauthenticated_client, db_session, mailbox
    ):
        created = client.post(
            "/api/users/invite", json={"email": "accept@example.com", "full_name": "Accept"}
        )
        token = token_in_link(created.json()["invite_link"])

        accepted = unauthenticated_client.post(
            "/api/auth/accept-invite", json={"token": token, "password": NEW_PASSWORD}
        )
        assert accepted.status_code == 200, accepted.text

        user = (
            await db_session.execute(select(User).where(User.email == "accept@example.com"))
        ).scalar_one()
        assert verify_password(NEW_PASSWORD, user.hashed_password)

    @pytest.mark.asyncio
    async def test_an_invitation_cannot_be_accepted_twice(
        self, client, unauthenticated_client, db_session, mailbox
    ):
        created = client.post(
            "/api/users/invite", json={"email": "once@example.com", "full_name": "Once"}
        )
        token = token_in_link(created.json()["invite_link"])

        first = unauthenticated_client.post(
            "/api/auth/accept-invite", json={"token": token, "password": NEW_PASSWORD}
        )
        assert first.status_code == 200, first.text

        second = unauthenticated_client.post(
            "/api/auth/accept-invite", json={"token": token, "password": "yet-another-password"}
        )
        assert second.status_code in (400, 401, 404)

    def test_revoking_invalidates_the_outstanding_token(
        self, client, unauthenticated_client, mailbox
    ):
        created = client.post(
            "/api/users/invite", json={"email": "revoked@example.com", "full_name": "Revoked"}
        )
        token = token_in_link(created.json()["invite_link"])
        user_id = created.json()["user"]["id"]

        assert client.post(f"/api/users/{user_id}/revoke-invite").status_code == 200

        accepted = unauthenticated_client.post(
            "/api/auth/accept-invite", json={"token": token, "password": NEW_PASSWORD}
        )
        assert accepted.status_code in (400, 401, 404)

    def test_a_revoked_invitation_cannot_seed_a_password_for_later(
        self, client, unauthenticated_client, mailbox
    ):
        """The whole attack path, not just the status code.

        Revoking used only to deactivate the account, leaving the emailed link
        live. Whoever held it could still accept and choose a password - which
        then worked the moment an administrator reactivated the account.
        """
        created = client.post(
            "/api/users/invite", json={"email": "victim@example.com", "full_name": "Victim"}
        )
        token = token_in_link(created.json()["invite_link"])
        user_id = created.json()["user"]["id"]

        client.post(f"/api/users/{user_id}/revoke-invite")
        unauthenticated_client.post(
            "/api/auth/accept-invite",
            json={"token": token, "password": "attacker-chosen-password"},
        )

        assert client.patch(f"/api/users/{user_id}", json={"is_active": True}).status_code == 200

        login = unauthenticated_client.post(
            "/api/auth/login",
            json={"email": "victim@example.com", "password": "attacker-chosen-password"},
        )
        assert login.status_code == 401, "a revoked invitation must not leave a usable password"

    def test_resending_issues_a_fresh_token(self, client, unauthenticated_client, mailbox):
        created = client.post(
            "/api/users/invite", json={"email": "resend@example.com", "full_name": "Resend"}
        )
        first_token = token_in_link(created.json()["invite_link"])
        user_id = created.json()["user"]["id"]

        resent = client.post(f"/api/users/{user_id}/resend-invite")
        assert resent.status_code == 200, resent.text
        second_token = token_in_link(resent.json()["invite_link"])
        assert second_token != first_token


class TestPasswordResetLifecycle:
    @pytest.mark.asyncio
    async def test_resets_the_password_with_the_emailed_token(
        self, unauthenticated_client, db_session, mailbox
    ):
        user = await _account(db_session, email="reset@example.com")
        unauthenticated_client.post(
            "/api/auth/forgot-password", json={"email": "reset@example.com"}
        )
        token = token_in(mailbox)

        response = unauthenticated_client.post(
            "/api/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}
        )
        assert response.status_code == 200, response.text

        await db_session.refresh(user)
        assert verify_password(NEW_PASSWORD, user.hashed_password)

    @pytest.mark.asyncio
    async def test_a_reset_signs_existing_sessions_out(
        self, unauthenticated_client, db_session, mailbox
    ):
        user = await _account(db_session, email="signout@example.com")
        before = user.session_version

        unauthenticated_client.post(
            "/api/auth/forgot-password", json={"email": "signout@example.com"}
        )
        unauthenticated_client.post(
            "/api/auth/reset-password",
            json={"token": token_in(mailbox), "new_password": NEW_PASSWORD},
        )

        await db_session.refresh(user)
        assert user.session_version > before

    @pytest.mark.asyncio
    async def test_a_reset_token_is_single_use(self, unauthenticated_client, db_session, mailbox):
        await _account(db_session, email="single@example.com")
        unauthenticated_client.post(
            "/api/auth/forgot-password", json={"email": "single@example.com"}
        )
        token = token_in(mailbox)

        first = unauthenticated_client.post(
            "/api/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}
        )
        assert first.status_code == 200, first.text

        second = unauthenticated_client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "a-third-long-password"},
        )
        assert second.status_code in (400, 401, 404)

    @pytest.mark.asyncio
    async def test_the_new_password_must_meet_the_policy(
        self, unauthenticated_client, db_session, mailbox
    ):
        await _account(db_session, email="weak@example.com")
        unauthenticated_client.post("/api/auth/forgot-password", json={"email": "weak@example.com"})
        response = unauthenticated_client.post(
            "/api/auth/reset-password", json={"token": token_in(mailbox), "new_password": "short"}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_no_token_is_issued_for_an_unknown_address(
        self, unauthenticated_client, db_session, mailbox
    ):
        unauthenticated_client.post(
            "/api/auth/forgot-password", json={"email": "ghost@example.com"}
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
        assert tokens == []
        assert mailbox == []


class TestEmailChangeLifecycle:
    @pytest.mark.asyncio
    async def test_the_login_only_moves_after_the_new_mailbox_confirms(
        self, client, unauthenticated_client, db_session, mailbox
    ):
        user = await _account(db_session, email="old@example.com")

        started = client.post(f"/api/users/{user.id}/email", json={"new_email": "new@example.com"})
        assert started.status_code == 200, started.text
        await db_session.refresh(user)
        assert user.email == "old@example.com"
        assert user.pending_email == "new@example.com"

        confirmed = unauthenticated_client.post(
            "/api/auth/confirm-email-change", json={"token": token_in(mailbox)}
        )
        assert confirmed.status_code == 200, confirmed.text

        await db_session.refresh(user)
        assert user.email == "new@example.com"
        assert user.pending_email is None

    @pytest.mark.asyncio
    async def test_the_confirmation_is_sent_to_the_new_address(self, client, db_session, mailbox):
        user = await _account(db_session, email="from@example.com")
        client.post(f"/api/users/{user.id}/email", json={"new_email": "to@example.com"})
        assert mailbox[-1]["to"] == "to@example.com"

    @pytest.mark.asyncio
    async def test_a_cancelled_change_cannot_be_confirmed(
        self, client, unauthenticated_client, db_session, mailbox
    ):
        user = await _account(db_session, email="cancel@example.com")
        client.post(f"/api/users/{user.id}/email", json={"new_email": "never@example.com"})
        token = token_in(mailbox)

        assert client.delete(f"/api/users/{user.id}/email").status_code == 200

        confirmed = unauthenticated_client.post(
            "/api/auth/confirm-email-change", json={"token": token}
        )
        assert confirmed.status_code in (400, 401, 404)

        await db_session.refresh(user)
        assert user.email == "cancel@example.com"

    @pytest.mark.asyncio
    async def test_a_confirmation_token_is_single_use(
        self, client, unauthenticated_client, db_session, mailbox
    ):
        user = await _account(db_session, email="reuse@example.com")
        client.post(f"/api/users/{user.id}/email", json={"new_email": "fresh@example.com"})
        token = token_in(mailbox)

        assert (
            unauthenticated_client.post(
                "/api/auth/confirm-email-change", json={"token": token}
            ).status_code
            == 200
        )
        replay = unauthenticated_client.post(
            "/api/auth/confirm-email-change", json={"token": token}
        )
        assert replay.status_code in (400, 401, 404)
