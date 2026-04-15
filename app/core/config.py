"""
Application configuration.

Loads settings from environment variables with sensible defaults.
"""

import secrets
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = "postgresql://bud:bud@localhost:5432/buddb"

    # Security
    # C1: SECRET_KEY must be set explicitly — no insecure fallback in production
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # H1: Shorter runner token lifetime (24 hours, renewable via heartbeat)
    RUNNER_TOKEN_EXPIRE_HOURS: int = 24

    # CORS
    # M1: Restrict CORS to explicit origins only (no wildcard)
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://bud.embedlabs.de",
    ]

    # OpenProject integration
    PM_URL: str = "https://pm.embedlabs.de"
    PM_TOKEN: str = ""

    # File uploads
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100 MB

    # H4: Allowlist of accepted MIME types for uploads
    ALLOWED_UPLOAD_MIME_TYPES: List[str] = [
        "application/json",
        "text/plain",
        "text/xml",
        "application/xml",
        "application/zip",
        "application/octet-stream",
        "application/x-zip-compressed",
        "image/png",
        "image/jpeg",
    ]

    # C2: Shared API key for runner-registration mutations (must be set in production)
    RUNNER_API_KEY: str = ""

    # Default admin user (seeded on first startup)
    ADMIN_EMAIL: str = "admin@embedlabs.de"
    ADMIN_PASSWORD: str = "changeme123"
    ADMIN_FULL_NAME: str = "Admin"

    # Runner settings
    RUNNER_HEARTBEAT_TIMEOUT: int = 120  # seconds

    # L1: Disable API docs in production (set ENABLE_DOCS=true to enable locally)
    ENABLE_DOCS: bool = False

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_set(cls, v: str) -> str:
        """C1: Reject startup if SECRET_KEY is missing or is the insecure placeholder."""
        insecure_placeholders = {
            "",
            "your-secret-key-change-in-production",
            "change-me-in-production",
            "secret",
        }
        if v in insecure_placeholders:
            raise ValueError(
                "SECRET_KEY must be set to a strong random value. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long.")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
