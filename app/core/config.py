"""
Application configuration.

Loads settings from environment variables with sensible defaults.
"""

import secrets
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import AliasChoices, EmailStr, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
WORKSPACE_DIR = BACKEND_DIR.parent
ENV_FILES = (WORKSPACE_DIR / ".env", BACKEND_DIR / ".env")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        case_sensitive=True,
        extra="ignore",
        populate_by_name=True,
    )

    # Database
    DATABASE_URL: str = Field(
        default="", validation_alias=AliasChoices("BUD_DATABASE_URL", "DATABASE_URL")
    )
    DB_USER: str = Field(default="bud", validation_alias=AliasChoices("BUD_DB_USER", "DB_USER"))
    DB_PASSWORD: str = Field(
        default="bud", validation_alias=AliasChoices("BUD_DB_PASSWORD", "DB_PASSWORD")
    )
    DB_NAME: str = Field(default="buddb", validation_alias=AliasChoices("BUD_DB_NAME", "DB_NAME"))
    DB_HOST: str = Field(
        default="localhost", validation_alias=AliasChoices("BUD_DB_HOST", "DB_HOST")
    )
    DB_PORT: int = Field(default=5432, validation_alias=AliasChoices("BUD_DB_PORT", "DB_PORT"))

    # Security
    # C1: SECRET_KEY must be set explicitly — no insecure fallback in production
    SECRET_KEY: str = Field(
        default="", validation_alias=AliasChoices("BUD_SECRET_KEY", "SECRET_KEY")
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=60 * 24 * 7,
        validation_alias=AliasChoices(
            "BUD_ACCESS_TOKEN_EXPIRE_MINUTES", "ACCESS_TOKEN_EXPIRE_MINUTES"
        ),
    )
    BUD_APP_NAME: str = "Bud Test Platform"
    BUD_APP_VERSION: str = "0.1.0"

    APP_BASE_URL: str = Field(
        default="http://localhost:8001",
        validation_alias=AliasChoices("BUD_APP_BASE_URL", "APP_BASE_URL"),
    )
    FRONTEND_BASE_URL: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("BUD_FRONTEND_BASE_URL", "FRONTEND_BASE_URL"),
    )

    # H1: Shorter runner token lifetime (24 hours, renewable via heartbeat)
    RUNNER_TOKEN_EXPIRE_HOURS: int = Field(
        default=24,
        validation_alias=AliasChoices("BUD_RUNNER_TOKEN_EXPIRE_HOURS", "RUNNER_TOKEN_EXPIRE_HOURS"),
    )

    # CORS
    # M1: Restrict CORS to explicit origins only (no wildcard)
    CORS_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:5173",
        ],
        validation_alias=AliasChoices("BUD_CORS_ORIGINS", "CORS_ORIGINS"),
    )

    # File uploads
    UPLOAD_DIR: str = Field(
        default="./uploads", validation_alias=AliasChoices("BUD_UPLOAD_DIR", "UPLOAD_DIR")
    )
    MAX_UPLOAD_SIZE: int = Field(
        default=100 * 1024 * 1024,
        validation_alias=AliasChoices("BUD_MAX_UPLOAD_SIZE", "MAX_UPLOAD_SIZE"),
    )

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
    RUNNER_API_KEY: str = Field(
        default="", validation_alias=AliasChoices("BUD_RUNNER_API_KEY", "RUNNER_API_KEY")
    )

    # Default admin user (seeded on first startup)
    ADMIN_EMAIL: str = Field(
        default="admin@embedlabs.de",
        validation_alias=AliasChoices("BUD_ADMIN_EMAIL", "ADMIN_EMAIL"),
    )
    ADMIN_PASSWORD: str = Field(
        default="changeme123", validation_alias=AliasChoices("BUD_ADMIN_PASSWORD", "ADMIN_PASSWORD")
    )
    ADMIN_FULL_NAME: str = Field(
        default="Admin", validation_alias=AliasChoices("BUD_ADMIN_FULL_NAME", "ADMIN_FULL_NAME")
    )

    # Runner settings
    RUNNER_HEARTBEAT_TIMEOUT: int = Field(
        default=120,
        validation_alias=AliasChoices("BUD_RUNNER_HEARTBEAT_TIMEOUT", "RUNNER_HEARTBEAT_TIMEOUT"),
    )  # seconds

    SMTP_ENABLED: bool = Field(
        default=False, validation_alias=AliasChoices("BUD_SMTP_ENABLED", "SMTP_ENABLED")
    )
    SMTP_HOST: str = Field(default="", validation_alias=AliasChoices("BUD_SMTP_HOST", "SMTP_HOST"))
    SMTP_PORT: int = Field(default=587, validation_alias=AliasChoices("BUD_SMTP_PORT", "SMTP_PORT"))
    SMTP_USERNAME: str = Field(
        default="", validation_alias=AliasChoices("BUD_SMTP_USERNAME", "SMTP_USERNAME")
    )
    SMTP_PASSWORD: str = Field(
        default="", validation_alias=AliasChoices("BUD_SMTP_PASSWORD", "SMTP_PASSWORD")
    )
    SMTP_FROM_EMAIL: Optional[EmailStr] = Field(
        default=None, validation_alias=AliasChoices("BUD_SMTP_FROM_EMAIL", "SMTP_FROM_EMAIL")
    )
    SMTP_FROM_NAME: str = Field(
        default="", validation_alias=AliasChoices("BUD_SMTP_FROM_NAME", "SMTP_FROM_NAME")
    )
    SMTP_REPLY_TO: Optional[EmailStr] = Field(
        default=None, validation_alias=AliasChoices("BUD_SMTP_REPLY_TO", "SMTP_REPLY_TO")
    )
    SMTP_STARTTLS: bool = Field(
        default=True, validation_alias=AliasChoices("BUD_SMTP_STARTTLS", "SMTP_STARTTLS")
    )
    SMTP_SSL: bool = Field(default=False, validation_alias=AliasChoices("BUD_SMTP_SSL", "SMTP_SSL"))
    SMTP_TIMEOUT_SECONDS: int = Field(
        default=30,
        validation_alias=AliasChoices("BUD_SMTP_TIMEOUT_SECONDS", "SMTP_TIMEOUT_SECONDS"),
    )

    INVITE_TOKEN_TTL_HOURS: int = Field(
        default=72,
        validation_alias=AliasChoices("BUD_INVITE_TOKEN_TTL_HOURS", "INVITE_TOKEN_TTL_HOURS"),
    )
    EMAIL_VERIFICATION_TOKEN_TTL_HOURS: int = Field(
        default=24,
        validation_alias=AliasChoices(
            "BUD_EMAIL_VERIFICATION_TOKEN_TTL_HOURS", "EMAIL_VERIFICATION_TOKEN_TTL_HOURS"
        ),
    )
    PASSWORD_RESET_TOKEN_TTL_HOURS: int = Field(
        default=2,
        validation_alias=AliasChoices(
            "BUD_PASSWORD_RESET_TOKEN_TTL_HOURS", "PASSWORD_RESET_TOKEN_TTL_HOURS"
        ),
    )

    # L1: Disable API docs in production (set ENABLE_DOCS=true to enable locally)
    ENABLE_DOCS: bool = Field(
        default=False, validation_alias=AliasChoices("BUD_ENABLE_DOCS", "ENABLE_DOCS")
    )

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
