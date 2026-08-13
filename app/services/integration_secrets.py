"""Authenticated encryption for external integration credentials."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from app.core.config import settings

ENVELOPE_PREFIX = "fernet:v1:"


def _fernet() -> Fernet:
    if not settings.INTEGRATION_ENCRYPTION_KEY:
        raise HTTPException(
            status_code=503,
            detail="BUD_INTEGRATION_ENCRYPTION_KEY must be configured before storing a Bloom token.",
        )
    try:
        return Fernet(settings.INTEGRATION_ENCRYPTION_KEY.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise HTTPException(
            status_code=503,
            detail="BUD_INTEGRATION_ENCRYPTION_KEY must be a valid Fernet key.",
        ) from exc


def encrypt_integration_secret(secret: str) -> str:
    encrypted = _fernet().encrypt(secret.encode("utf-8")).decode("ascii")
    return ENVELOPE_PREFIX + encrypted


def decrypt_integration_secret(envelope: str) -> str:
    if not envelope.startswith(ENVELOPE_PREFIX):
        raise HTTPException(
            status_code=503,
            detail="Bloom token must be rotated because its stored format is no longer supported.",
        )
    try:
        plaintext = _fernet().decrypt(envelope[len(ENVELOPE_PREFIX) :].encode("ascii"))
    except (InvalidToken, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Bloom token could not be decrypted; rotate the integration credential.",
        ) from exc
    return plaintext.decode("utf-8")
