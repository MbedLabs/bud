"""
Application configuration.

Loads settings from environment variables with sensible defaults.
"""

import secrets
from functools import lru_cache
from typing import List, Optional

from pydantic import EmailStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = ""
    DB_USER: str = "bud"
    DB_PASSWORD: str = "bud"
    DB_NAME: str = "buddb"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432

    # Security
    # C1: SECRET_KEY must be set explicitly — no insecure fallback in production
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    BUD_APP_NAME: str = "Bud Test Platform"
    BUD_APP_VERSION: str = "0.1.0"

    APP_BASE_URL: str = "http://localhost:8001"
    FRONTEND_BASE_URL: str = "http://localhost:3000"

    # H1: Shorter runner token lifetime (24 hours, renewable via heartbeat)
    RUNNER_TOKEN_EXPIRE_HOURS: int = 24

    # CORS
    # M1: Restrict CORS to explicit origins only (no wildcard)
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://bud.embedlabs.de",
    ]

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

    SMTP_ENABLED: bool = False
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: Optional[EmailStr] = None
    SMTP_FROM_NAME: str = ""
    SMTP_REPLY_TO: Optional[EmailStr] = None
    SMTP_STARTTLS: bool = True
    SMTP_SSL: bool = False
    SMTP_TIMEOUT_SECONDS: int = 30

    INVITE_TOKEN_TTL_HOURS: int = 72
    EMAIL_VERIFICATION_TOKEN_TTL_HOURS: int = 24
    PASSWORD_RESET_TOKEN_TTL_HOURS: int = 2

    # L1: Disable API docs in production (set ENABLE_DOCS=true to enable locally)
    ENABLE_DOCS: bool = False

    @model_validator(mode="after")
    def populate_database_url(self):
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
                f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            )
        return self

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
                'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long.")
        return v


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
