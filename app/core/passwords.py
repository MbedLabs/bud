"""
Shared password policy.

One validator, applied at every entry point where a user chooses a password
(direct creation, invitation acceptance, password change, password reset) so the
rules cannot drift between endpoints.
"""

# Normal user passwords must be at least this long. The production administrator
# bootstrap keeps its own, stronger requirement (>= 16) in app.core.config.
PASSWORD_MIN_LENGTH = 12

# bcrypt only hashes the first 72 bytes of a password; any tail beyond that is
# silently ignored by the hashing backend. Reject longer inputs rather than
# accept a password whose end does not actually protect the account.
PASSWORD_MAX_BYTES = 72


def validate_password_strength(password: str) -> str:
    """Validate a chosen password against the shared policy.

    Returns the password unchanged when valid; raises ``ValueError`` with a
    human-readable message otherwise. Designed to be used both as a Pydantic
    ``AfterValidator`` and called directly from service code.
    """
    if not isinstance(password, str):
        raise ValueError("Password must be a string.")
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.")
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(f"Password is too long; it must not exceed {PASSWORD_MAX_BYTES} bytes.")
    return password
