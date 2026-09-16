"""
Password policy is enforced identically at every entry point where a user
chooses a password. All four request schemas share one validator, so testing
the schemas proves the policy holds for direct creation, invitation acceptance,
password change, and password reset.
"""

import pytest
from pydantic import ValidationError

from app.core.passwords import (
    PASSWORD_MAX_BYTES,
    PASSWORD_MIN_LENGTH,
    validate_password_strength,
)
from app.schemas.auth import (
    AcceptInviteRequest,
    PasswordChange,
    ResetPasswordRequest,
    UserCreate,
)

VALID = "correct horse battery"  # 21 chars, well within limits


def test_validator_accepts_minimum_length():
    pw = "x" * PASSWORD_MIN_LENGTH
    assert validate_password_strength(pw) == pw


@pytest.mark.parametrize("length", [0, 1, PASSWORD_MIN_LENGTH - 1])
def test_validator_rejects_short(length):
    with pytest.raises(ValueError, match="at least"):
        validate_password_strength("x" * length)


def test_validator_rejects_overlong_bytes():
    # Multi-byte chars must be counted as bytes, not characters, because bcrypt
    # truncates on bytes.
    too_long = "a" * (PASSWORD_MAX_BYTES + 1)
    with pytest.raises(ValueError, match="too long"):
        validate_password_strength(too_long)
    # 37 two-byte chars = 74 bytes > 72, even though only 37 "characters".
    multibyte = "é" * 37
    assert len(multibyte) < PASSWORD_MAX_BYTES
    with pytest.raises(ValueError, match="too long"):
        validate_password_strength(multibyte)


# Each schema that carries a user-chosen password must reject a short one and
# accept a compliant one.
SHORT = "short"


def _build(model, **overrides):
    base = {
        UserCreate: dict(email="u@example.com", full_name="U", password=VALID),
        PasswordChange: dict(current_password="whatever-old", new_password=VALID),
        AcceptInviteRequest: dict(token="t", password=VALID),
        ResetPasswordRequest: dict(token="t", new_password=VALID),
    }[model]
    base.update(overrides)
    return model(**base)


@pytest.mark.parametrize(
    "model,field",
    [
        (UserCreate, "password"),
        (PasswordChange, "new_password"),
        (AcceptInviteRequest, "password"),
        (ResetPasswordRequest, "new_password"),
    ],
)
def test_schema_rejects_short_password(model, field):
    with pytest.raises(ValidationError):
        _build(model, **{field: SHORT})


@pytest.mark.parametrize(
    "model,field",
    [
        (UserCreate, "password"),
        (PasswordChange, "new_password"),
        (AcceptInviteRequest, "password"),
        (ResetPasswordRequest, "new_password"),
    ],
)
def test_schema_accepts_valid_password(model, field):
    obj = _build(model)
    assert getattr(obj, field) == VALID
