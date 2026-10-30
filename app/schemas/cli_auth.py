"""Inputs and responses for browser-approved CLI sessions."""

from datetime import datetime
from typing import Literal
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.schemas.auth import UserResponse


def validate_callback_uri(uri: str) -> str:
    """Accept HTTP loopback callbacks with an explicit port and unambiguous parameters."""
    try:
        parsed = urlsplit(uri)
        valid = (
            parsed.scheme == "http"
            and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
            and parsed.port is not None
            and 1 <= parsed.port <= 65535
            and parsed.username is None
            and parsed.password is None
            and "#" not in uri
            and "\\" not in uri
            and not any(character.isspace() or ord(character) < 32 for character in uri)
            and not any(
                key.lower() in {"code", "state"}
                for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
            )
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(
            "Use an HTTP loopback callback with an explicit port and no code or state parameters"
        )
    return uri


class CliStartRequest(BaseModel):
    """A client name, callback choice and S256 proof-key challenge."""

    model_config = ConfigDict(extra="forbid")

    client_name: str = Field(min_length=1, max_length=100)
    mode: Literal["callback", "code"]
    redirect_uri: str | None = Field(default=None, max_length=500)
    code_challenge: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    state: str = Field(min_length=1, max_length=128)

    @field_validator("client_name")
    @classmethod
    def validate_client_name(cls, value: str) -> str:
        """Normalize the client label shown to the approving user."""
        value = value.strip()
        if not value:
            raise ValueError("A client name is required")
        return value

    @model_validator(mode="after")
    def validate_redirect(self):
        """Require a safe callback only for callback-mode clients."""
        if self.mode == "callback":
            if self.redirect_uri is None:
                raise ValueError("A callback URI is required")
            validate_callback_uri(self.redirect_uri)
        elif self.redirect_uri is not None:
            raise ValueError("Code mode does not use a callback URI")
        return self


class CliExpiringResponse(BaseModel):
    """An authorization response with an explicit UTC expiry."""

    expires_at: datetime

    @field_serializer("expires_at")
    def serialize_expiry(self, value: datetime) -> str:
        """Represent stored UTC timestamps with a timezone for browser clients."""
        return value.isoformat() + "Z"


class CliStartResponse(CliExpiringResponse):
    """The approval link and its expiry."""

    session_id: UUID
    authorize_url: str


class CliSessionResponse(CliExpiringResponse):
    """Client metadata and request time shown to an authenticated approver, without the code."""

    session_id: UUID
    client_name: str
    mode: Literal["callback", "code"]
    redirect_uri: str | None
    consumed: bool
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        """Represent the stored UTC request time with a timezone for browser clients."""
        return value.isoformat() + "Z"


class CliCheckRequest(BaseModel):
    """The request code the approver typed for one pending session."""

    model_config = ConfigDict(extra="forbid")
    session_id: UUID
    request_code: str = Field(max_length=16)


class CliApproveRequest(CliCheckRequest):
    """The pending session selected for approval with the typed request code."""


class CliDenyRequest(BaseModel):
    """The pending session selected for denial."""

    model_config = ConfigDict(extra="forbid")
    session_id: UUID


class CliCallbackApproval(BaseModel):
    """A validated loopback target carrying the single-use approval code."""

    redirect_to: str


class CliCallbackDenial(BaseModel):
    """A validated loopback target carrying error=access_denied and the original state."""

    redirect_to: str


class CliCodeDenial(BaseModel):
    """An empty answer to a denied code-mode request."""


class CliCodeApproval(CliExpiringResponse):
    """A single-use code for a client without a loopback listener."""

    exchange_code: str


class CliExchangeRequest(BaseModel):
    """The approval code and original proof-key verifier."""

    model_config = ConfigDict(extra="forbid")
    session_id: UUID
    code: str = Field(min_length=1, max_length=256)
    code_verifier: str = Field(pattern=r"^[A-Za-z0-9._~-]{43,128}$")


class CliRefreshRequest(BaseModel):
    """A single-use rotating refresh token supplied by the client."""

    model_config = ConfigDict(extra="forbid")
    refresh_token: str = Field(min_length=1, max_length=256)


class CliTokenResponse(BaseModel):
    """User-scoped access credentials and the user's existing effective permissions."""

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserResponse
