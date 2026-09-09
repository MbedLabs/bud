"""Shared password policy."""

# Normal user passwords must be at least this long. The production administrator
# bootstrap keeps its own, stronger requirement (>= 16) in app.core.config.
PASSWORD_MIN_LENGTH = 12

# bcrypt only hashes the first 72 bytes of a password; any tail beyond that is silently
# ignored by the hashing backend.
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
