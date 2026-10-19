"""Shared password policy.

PASSWORD_MIN_LENGTH applies to user passwords; the production administrator bootstrap in
app.core.config requires 16 characters. PASSWORD_MAX_BYTES is the 72-byte limit bcrypt
hashes.
"""

PASSWORD_MIN_LENGTH = 12

PASSWORD_MAX_BYTES = 72


def validate_password_strength(password: str) -> str:
    """Validate a chosen password against the shared policy."""
    if not isinstance(password, str):
        raise ValueError("Password must be a string.")
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.")
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(f"Password is too long; it must not exceed {PASSWORD_MAX_BYTES} bytes.")
    return password
