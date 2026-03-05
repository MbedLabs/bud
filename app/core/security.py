"""
Security utilities for authentication and authorization.
"""

from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from jose import JWTError, jwt

from app.core.config import settings


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Data to encode in the token.
        expires_delta: Token expiration time.

    Returns:
        Encoded JWT token.
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode a JWT access token.

    Args:
        token: JWT token to decode.

    Returns:
        Decoded token data or None if invalid.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_runner_token(runner_account: str) -> str:
    """
    Generate a short-lived token for a runner.

    H1: Tokens expire after RUNNER_TOKEN_EXPIRE_HOURS (default 24h) instead of
    the previous 365-day lifetime.

    Args:
        runner_account: Runner account name.

    Returns:
        Runner token (JWT).
    """
    return create_access_token(
        data={"sub": runner_account, "type": "runner"},
        expires_delta=timedelta(hours=settings.RUNNER_TOKEN_EXPIRE_HOURS),
    )
