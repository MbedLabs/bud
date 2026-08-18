"""User administration endpoints: CRUD, invitations, and the email-change workflow."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.user import User, UserRole
from app.models.user_token import UserToken, UserTokenPurpose


@pytest.fixture
def smtp(monkeypatch):
    """Invitations refuse to issue a token they cannot deliver, so enable SMTP
    and capture what would have been sent instead of sending it."""
    from app.services import mail_service

    sent: list[dict] = []

    def _capture(*, to_email, subject, text_body, html_body=None):
        sent.append({"to": to_email, "subject": subject, "text": text_body})

    monkeypatch.setattr(mail_service, "send_email", _capture)
    for module_name in ("app.api.users", "app.api.auth"):
        module = __import__(module_name, fromlist=["send_email"])
        if hasattr(module, "send_email"):
            monkeypatch.setattr(module, "send_email", _capture)
    return sent


async def _user(db_session, email: str, **overrides) -> User:
    user = User(
        email=email,
        full_name=overrides.pop("full_name", "Someone"),
        hashed_password=overrides.pop("hashed_password", "hashed"),
        role=overrides.pop("role", UserRole.viewer),
        is_active=overrides.pop("is_active", True),
        session_version=1,
        **overrides,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


class TestListAndCreate:
    @pytest.mark.asyncio
    async def test_lists_every_user(self, client, db_session):
        await _user(db_session, "one@example.com")
        await _user(db_session, "two@example.com")

        response = client.get("/api/users")
        assert response.status_code == 200
        emails = {u["email"] for u in response.json()}
        assert {"one@example.com", "two@example.com"} <= emails

    def test_creates_a_user(self, client):
        response = client.post(
            "/api/users",
            json={
                "email": "new@example.com",
                "full_name": "New Person",
                "password": "a-long-enough-password",
                "role": "viewer",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["email"] == "new@example.com"
        assert "password" not in body
        assert "hashed_password" not in body

    def test_rejects_a_duplicate_email(self, client):
        payload = {
            "email": "dup@example.com",
            "full_name": "Dup",
            "password": "a-long-enough-password",
        }
        assert client.post("/api/users", json=payload).status_code == 201
        second = client.post("/api/users", json=payload)
        assert second.status_code == 400
        assert "already registered" in second.json()["detail"].lower()

    def test_rejects_a_short_password(self, client):
        response = client.post(
            "/api/users",
            json={"email": "short@example.com", "full_name": "Short", "password": "abc"},
        )
        assert response.status_code == 422


class TestInvitations:
    def test_invites_a_new_user(self, client, smtp):
        response = client.post(
            "/api/users/invite",
            json={"email": "invitee@example.com", "full_name": "Invitee", "role": "viewer"},
        )
        assert response.status_code == 201, response.text
        assert response.json()["user"]["email"] == "invitee@example.com"

    @pytest.mark.asyncio
    async def test_an_invitation_stores_a_single_use_token(self, client, db_session, smtp):
        client.post(
            "/api/users/invite",
            json={"email": "tokened@example.com", "full_name": "Tokened"},
        )
        tokens = (
            (
                await db_session.execute(
                    select(UserToken).where(UserToken.purpose == UserTokenPurpose.invite)
                )
            )
            .scalars()
            .all()
        )
        assert len(tokens) == 1
        assert tokens[0].used_at is None

    @pytest.mark.asyncio
    async def test_resends_an_invitation(self, client, db_session, smtp):
        created = client.post(
            "/api/users/invite", json={"email": "resend@example.com", "full_name": "Resend"}
        )
        user_id = created.json()["user"]["id"]

        response = client.post(f"/api/users/{user_id}/resend-invite")
        assert response.status_code == 200, response.text

    def test_resending_to_an_unknown_user_is_404(self, client):
        assert client.post("/api/users/99999/resend-invite").status_code == 404

    @pytest.mark.asyncio
    async def test_revokes_an_invitation(self, client, db_session, smtp):
        created = client.post(
            "/api/users/invite", json={"email": "revoke@example.com", "full_name": "Revoke"}
        )
        user_id = created.json()["user"]["id"]

        response = client.post(f"/api/users/{user_id}/revoke-invite")
        assert response.status_code == 200, response.text

    def test_revoking_for_an_unknown_user_is_404(self, client):
        assert client.post("/api/users/99999/revoke-invite").status_code == 404


class TestEmailChangeWorkflow:
    """Administrators drive the change; the new mailbox still has to confirm."""

    @pytest.mark.asyncio
    async def test_admin_starts_a_change(self, client, db_session, smtp):
        user = await _user(db_session, "before@example.com")
        response = client.post(
            f"/api/users/{user.id}/email", json={"new_email": "after@example.com"}
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["email"] == "before@example.com", "the login only moves after confirmation"
        assert body["pending_email"] == "after@example.com"

    @pytest.mark.asyncio
    async def test_a_change_to_a_taken_address_is_refused(self, client, db_session):
        await _user(db_session, "taken@example.com")
        user = await _user(db_session, "mover@example.com")
        response = client.post(
            f"/api/users/{user.id}/email", json={"new_email": "taken@example.com"}
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_admin_cancels_a_pending_change(self, client, db_session, smtp):
        user = await _user(db_session, "cancel@example.com")
        client.post(f"/api/users/{user.id}/email", json={"new_email": "cancelled@example.com"})

        response = client.delete(f"/api/users/{user.id}/email")
        assert response.status_code == 200, response.text
        assert response.json()["pending_email"] is None

    def test_starting_a_change_for_an_unknown_user_is_404(self, client):
        response = client.post("/api/users/99999/email", json={"new_email": "x@example.com"})
        assert response.status_code == 404


class TestUpdateAndDelete:
    @pytest.mark.asyncio
    async def test_updates_the_name(self, client, db_session):
        user = await _user(db_session, "patch@example.com")
        response = client.patch(f"/api/users/{user.id}", json={"full_name": "Renamed"})
        assert response.status_code == 200, response.text
        assert response.json()["full_name"] == "Renamed"

    @pytest.mark.asyncio
    async def test_refuses_to_demote_an_admin(self, client, db_session):
        """Admin is immutable in both directions: it is granted out of band."""
        user = await _user(db_session, "demote@example.com", role=UserRole.admin)
        response = client.patch(f"/api/users/{user.id}", json={"role": "viewer"})
        assert response.status_code == 400
        assert "cannot be changed" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_restating_the_current_role_is_accepted(self, client, db_session):
        user = await _user(db_session, "same@example.com", role=UserRole.viewer)
        response = client.patch(f"/api/users/{user.id}", json={"role": "viewer"})
        assert response.status_code == 200, response.text
        assert response.json()["role"] == "viewer"

    @pytest.mark.asyncio
    async def test_rejects_a_role_outside_the_enum(self, client, db_session):
        user = await _user(db_session, "bogus@example.com")
        assert client.patch(f"/api/users/{user.id}", json={"role": "superuser"}).status_code == 422

    @pytest.mark.asyncio
    async def test_refuses_to_promote_to_admin(self, client, db_session):
        """Admin is granted deliberately, never through a generic user patch."""
        user = await _user(db_session, "climber@example.com")
        response = client.patch(f"/api/users/{user.id}", json={"role": "admin"})
        assert response.status_code == 400
        assert "admin" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_deactivates_a_user(self, client, db_session):
        user = await _user(db_session, "deactivate@example.com")
        response = client.patch(f"/api/users/{user.id}", json={"is_active": False})
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    @pytest.mark.asyncio
    async def test_the_generic_update_cannot_replace_an_email(self, client, db_session):
        """Email changes go through the confirmed workflow, never a plain patch."""
        user = await _user(db_session, "sneaky@example.com")
        response = client.patch(f"/api/users/{user.id}", json={"email": "other@example.com"})
        assert response.status_code == 422

    def test_updating_an_unknown_user_is_404(self, client):
        assert client.patch("/api/users/99999", json={"full_name": "X"}).status_code == 404

    @pytest.mark.asyncio
    async def test_deletes_a_user(self, client, db_session):
        user = await _user(db_session, "gone@example.com")
        assert client.delete(f"/api/users/{user.id}").status_code == 204

        remaining = (
            await db_session.execute(select(User).where(User.id == user.id))
        ).scalar_one_or_none()
        assert remaining is None

    def test_deleting_an_unknown_user_is_404(self, client):
        assert client.delete("/api/users/99999").status_code == 404


class TestAuthorization:
    def test_every_user_route_requires_authentication(self, unauthenticated_client):
        for method, path in [
            ("get", "/api/users"),
            ("post", "/api/users"),
            ("post", "/api/users/invite"),
            ("post", "/api/users/1/resend-invite"),
            ("post", "/api/users/1/revoke-invite"),
            ("post", "/api/users/1/email"),
            ("post", "/api/users/1/email/approve"),
            ("delete", "/api/users/1/email"),
            ("patch", "/api/users/1"),
            ("delete", "/api/users/1"),
        ]:
            response = unauthenticated_client.request(method.upper(), path, json={})
            assert (
                response.status_code == 401
            ), f"{method.upper()} {path} was {response.status_code}"
