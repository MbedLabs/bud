from app.core.config import Settings

CONFIG_ENV_KEYS = [
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "ADMIN_EMAIL",
    "ADMIN_FULL_NAME",
    "ADMIN_PASSWORD",
    "AUTO_SEED_ADMIN",
    "APP_BASE_URL",
    "BUD_ACCESS_TOKEN_EXPIRE_MINUTES",
    "BUD_ADMIN_EMAIL",
    "BUD_ADMIN_FULL_NAME",
    "BUD_ADMIN_PASSWORD",
    "BUD_AUTO_SEED_ADMIN",
    "BUD_APP_BASE_URL",
    "BUD_CORS_ORIGINS",
    "BUD_DATABASE_URL",
    "BUD_ENV",
    "BUD_EMAIL_VERIFICATION_TOKEN_TTL_HOURS",
    "BUD_ENABLE_DOCS",
    "BUD_FRONTEND_BASE_URL",
    "BUD_INVITE_TOKEN_TTL_HOURS",
    "BUD_INTEGRATION_ENCRYPTION_KEY",
    "BUD_MAX_UPLOAD_SIZE",
    "BUD_MAX_UPLOAD_SIZE_BYTES",
    "BUD_MAX_RUN_UPLOAD_BYTES",
    "BUD_MIN_UPLOAD_FREE_BYTES",
    "BUD_UPLOADS_PER_15_MINUTES",
    "BUD_MAX_CONCURRENT_UPLOADS_PER_PRINCIPAL",
    "BUD_ARTIFACT_RETENTION_DAYS",
    "BUD_UPLOAD_STREAM_CHUNK_BYTES",
    "BUD_PASSWORD_RESET_TOKEN_TTL_HOURS",
    "BUD_RUN_STARTUP_DATA_REPAIR",
    "BUD_RUNNER_API_KEY",
    "BUD_RUNNER_HEARTBEAT_TIMEOUT",
    "BUD_RUNNER_TOKEN_EXPIRE_HOURS",
    "BUD_SECRET_KEY",
    "BUD_SMTP_ENABLED",
    "BUD_SMTP_FROM_EMAIL",
    "BUD_SMTP_FROM_NAME",
    "BUD_SMTP_HOST",
    "BUD_SMTP_PASSWORD",
    "BUD_SMTP_PORT",
    "BUD_SMTP_REPLY_TO",
    "BUD_SMTP_SSL",
    "BUD_SMTP_STARTTLS",
    "BUD_SMTP_TIMEOUT_SECONDS",
    "BUD_SMTP_USERNAME",
    "BUD_UPLOAD_DIR",
    "CORS_ORIGINS",
    "DATABASE_URL",
    "APP_ENV",
    "EMAIL_VERIFICATION_TOKEN_TTL_HOURS",
    "ENABLE_DOCS",
    "FRONTEND_BASE_URL",
    "INVITE_TOKEN_TTL_HOURS",
    "INTEGRATION_ENCRYPTION_KEY",
    "MAX_UPLOAD_SIZE",
    "MAX_UPLOAD_SIZE_BYTES",
    "MAX_RUN_UPLOAD_BYTES",
    "MIN_UPLOAD_FREE_BYTES",
    "UPLOADS_PER_15_MINUTES",
    "MAX_CONCURRENT_UPLOADS_PER_PRINCIPAL",
    "ARTIFACT_RETENTION_DAYS",
    "UPLOAD_STREAM_CHUNK_BYTES",
    "PASSWORD_RESET_TOKEN_TTL_HOURS",
    "RUN_STARTUP_DATA_REPAIR",
    "RUNNER_API_KEY",
    "RUNNER_HEARTBEAT_TIMEOUT",
    "RUNNER_TOKEN_EXPIRE_HOURS",
    "SECRET_KEY",
    "SMTP_ENABLED",
    "SMTP_FROM_EMAIL",
    "SMTP_FROM_NAME",
    "SMTP_HOST",
    "SMTP_PASSWORD",
    "SMTP_PORT",
    "SMTP_REPLY_TO",
    "SMTP_SSL",
    "SMTP_STARTTLS",
    "SMTP_TIMEOUT_SECONDS",
    "SMTP_USERNAME",
    "UPLOAD_DIR",
]


def clear_config_env(monkeypatch):
    for key in CONFIG_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def set_prod_baseline(monkeypatch):
    """Supply the secrets production now requires so each test can exercise a
    single validator in isolation. A full DATABASE_URL is provided (so the
    DB_PASSWORD-from-parts guard is not what fires) alongside a strong
    RUNNER_API_KEY (>= 32 chars, no placeholder)."""
    monkeypatch.setenv("BUD_DATABASE_URL", "postgresql://bud:strong-db-pass@db:5432/buddb")
    monkeypatch.setenv("BUD_RUNNER_API_KEY", "r" * 32)


def test_settings_reads_bud_prefixed_env(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    monkeypatch.setenv("BUD_DATABASE_URL", "postgresql://bud:bud@localhost:5432/buddb")
    monkeypatch.setenv("BUD_ACCESS_TOKEN_EXPIRE_MINUTES", "42")
    monkeypatch.setenv("BUD_APP_BASE_URL", "http://localhost:8001")
    monkeypatch.setenv("BUD_FRONTEND_BASE_URL", "http://localhost:5174")
    monkeypatch.setenv("BUD_CORS_ORIGINS", '["http://localhost:5174"]')
    monkeypatch.setenv("BUD_ENABLE_DOCS", "true")
    monkeypatch.setenv("BUD_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BUD_ADMIN_PASSWORD", "admin-password")
    monkeypatch.setenv("BUD_ADMIN_FULL_NAME", "Bud Admin")
    monkeypatch.setenv("BUD_RUNNER_API_KEY", "runner-key")
    monkeypatch.setenv("BUD_RUNNER_TOKEN_EXPIRE_HOURS", "12")
    monkeypatch.setenv("BUD_RUNNER_HEARTBEAT_TIMEOUT", "45")
    monkeypatch.setenv("BUD_UPLOAD_DIR", "/tmp/bud-uploads")
    monkeypatch.setenv("BUD_MAX_UPLOAD_SIZE", "12345")
    monkeypatch.setenv("BUD_INVITE_TOKEN_TTL_HOURS", "48")
    monkeypatch.setenv("BUD_EMAIL_VERIFICATION_TOKEN_TTL_HOURS", "6")
    monkeypatch.setenv("BUD_PASSWORD_RESET_TOKEN_TTL_HOURS", "3")
    monkeypatch.setenv("BUD_SMTP_ENABLED", "true")
    monkeypatch.setenv("BUD_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("BUD_SMTP_PORT", "2525")
    monkeypatch.setenv("BUD_SMTP_USERNAME", "smtp-user")
    monkeypatch.setenv("BUD_SMTP_PASSWORD", "smtp-password")
    monkeypatch.setenv("BUD_SMTP_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setenv("BUD_SMTP_FROM_NAME", "Attempted Override")
    monkeypatch.setenv("BUD_SMTP_REPLY_TO", "reply@example.com")
    monkeypatch.setenv("BUD_SMTP_STARTTLS", "false")
    monkeypatch.setenv("BUD_SMTP_SSL", "true")
    monkeypatch.setenv("BUD_SMTP_TIMEOUT_SECONDS", "9")

    settings = Settings(_env_file=None)

    assert settings.SECRET_KEY == "b" * 32
    assert settings.DATABASE_URL == "postgresql://bud:bud@localhost:5432/buddb"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 42
    assert settings.APP_BASE_URL == "http://localhost:8001"
    assert settings.FRONTEND_BASE_URL == "http://localhost:5174"
    assert settings.CORS_ORIGINS == ["http://localhost:5174"]
    assert settings.ENABLE_DOCS is True
    assert settings.ADMIN_EMAIL == "admin@example.com"
    assert settings.ADMIN_PASSWORD == "admin-password"
    assert settings.ADMIN_FULL_NAME == "Bud Admin"
    assert settings.RUNNER_API_KEY == "runner-key"
    assert settings.RUNNER_TOKEN_EXPIRE_HOURS == 12
    assert settings.RUNNER_HEARTBEAT_TIMEOUT == 45
    assert settings.UPLOAD_DIR == "/tmp/bud-uploads"
    assert settings.MAX_UPLOAD_SIZE == 12345
    assert settings.INVITE_TOKEN_TTL_HOURS == 48
    assert settings.EMAIL_VERIFICATION_TOKEN_TTL_HOURS == 6
    assert settings.PASSWORD_RESET_TOKEN_TTL_HOURS == 3
    assert settings.SMTP_ENABLED is True
    assert settings.SMTP_HOST == "smtp.example.com"
    assert settings.SMTP_PORT == 2525
    assert settings.SMTP_USERNAME == "smtp-user"
    assert settings.SMTP_PASSWORD == "smtp-password"
    assert str(settings.SMTP_FROM_EMAIL) == "noreply@example.com"
    assert not hasattr(settings, "SMTP_FROM_NAME")
    assert str(settings.SMTP_REPLY_TO) == "reply@example.com"
    assert settings.SMTP_STARTTLS is False
    assert settings.SMTP_SSL is True
    assert settings.SMTP_TIMEOUT_SECONDS == 9


def test_settings_falls_back_to_unprefixed_env(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("SMTP_ENABLED", "true")
    monkeypatch.setenv("SMTP_HOST", "smtp.unprefixed.example.com")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "noreply@example.com")

    settings = Settings(_env_file=None)

    assert settings.SECRET_KEY == "s" * 32
    assert settings.SMTP_ENABLED is True
    assert settings.SMTP_HOST == "smtp.unprefixed.example.com"
    assert str(settings.SMTP_FROM_EMAIL) == "noreply@example.com"


def test_upload_limits_have_safe_public_beta_defaults(monkeypatch):
    clear_config_env(monkeypatch)
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)

    settings = Settings(_env_file=None)

    assert settings.MAX_UPLOAD_SIZE == 25 * 1024 * 1024
    assert settings.MAX_UPLOAD_SIZE_HARD_LIMIT_BYTES == 100 * 1024 * 1024
    assert settings.MAX_RUN_UPLOAD_BYTES == 250 * 1024 * 1024
    assert settings.MIN_UPLOAD_FREE_BYTES == 1024 * 1024 * 1024
    assert settings.UPLOADS_PER_15_MINUTES == 10
    assert settings.MAX_CONCURRENT_UPLOADS_PER_PRINCIPAL == 1
    assert settings.ARTIFACT_RETENTION_DAYS == 30
    assert settings.UPLOAD_STREAM_CHUNK_BYTES == 1024 * 1024


def test_operator_can_raise_file_limit_to_100_mib(monkeypatch):
    clear_config_env(monkeypatch)
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    monkeypatch.setenv("BUD_MAX_UPLOAD_SIZE_BYTES", str(100 * 1024 * 1024))

    settings = Settings(_env_file=None)

    assert settings.MAX_UPLOAD_SIZE == 100 * 1024 * 1024


def test_upload_file_limit_above_100_mib_is_rejected(monkeypatch):
    clear_config_env(monkeypatch)
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    monkeypatch.setenv("BUD_MAX_UPLOAD_SIZE_BYTES", str(100 * 1024 * 1024 + 1))

    import pytest

    with pytest.raises(ValueError, match="100 MiB"):
        Settings(_env_file=None)


def test_settings_prefers_bud_prefixed_env(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("SECRET_KEY", "s" * 32)
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    monkeypatch.setenv("SMTP_HOST", "smtp.unprefixed.example.com")
    monkeypatch.setenv("BUD_SMTP_HOST", "smtp.bud-prefixed.example.com")

    settings = Settings(_env_file=None)

    assert settings.SECRET_KEY == "b" * 32
    assert settings.SMTP_HOST == "smtp.bud-prefixed.example.com"


def test_production_rejects_default_admin_email(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("BUD_ENV", "production")
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    set_prod_baseline(monkeypatch)
    monkeypatch.setenv("BUD_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BUD_ADMIN_PASSWORD", "this-is-a-long-password")

    import pytest

    with pytest.raises(ValueError, match="ADMIN_EMAIL"):
        Settings(_env_file=None)


def test_production_rejects_default_admin_password(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("BUD_ENV", "production")
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    set_prod_baseline(monkeypatch)
    monkeypatch.setenv("BUD_ADMIN_EMAIL", "ops@embedlabs.net")
    monkeypatch.setenv("BUD_ADMIN_PASSWORD", "changeme123")

    import pytest

    with pytest.raises(ValueError, match="ADMIN_PASSWORD"):
        Settings(_env_file=None)


def test_production_rejects_short_admin_password(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("BUD_ENV", "production")
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    set_prod_baseline(monkeypatch)
    monkeypatch.setenv("BUD_ADMIN_EMAIL", "ops@embedlabs.net")
    monkeypatch.setenv("BUD_ADMIN_PASSWORD", "short-password")

    import pytest

    with pytest.raises(ValueError, match="at least 16"):
        Settings(_env_file=None)


def test_development_allows_bootstrap_defaults(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("BUD_ENV", "development")
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    monkeypatch.setenv("BUD_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BUD_ADMIN_PASSWORD", "changeme123")

    settings = Settings(_env_file=None)

    assert settings.ADMIN_EMAIL == "admin@example.com"
    assert settings.ADMIN_PASSWORD == "changeme123"


def test_development_auto_seed_admin_defaults_on(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("BUD_ENV", "development")
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)

    settings = Settings(_env_file=None)

    assert settings.AUTO_SEED_ADMIN is True


def test_development_startup_data_repair_defaults_on(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("BUD_ENV", "development")
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)

    settings = Settings(_env_file=None)

    assert settings.RUN_STARTUP_DATA_REPAIR is True


def test_production_auto_seed_admin_defaults_off(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("BUD_ENV", "production")
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    set_prod_baseline(monkeypatch)
    monkeypatch.setenv("BUD_ADMIN_EMAIL", "ops@embedlabs.net")
    monkeypatch.setenv("BUD_ADMIN_PASSWORD", "this-is-a-long-password")

    settings = Settings(_env_file=None)

    assert settings.AUTO_SEED_ADMIN is False


def test_production_startup_data_repair_defaults_off(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("BUD_ENV", "production")
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    set_prod_baseline(monkeypatch)
    monkeypatch.setenv("BUD_ADMIN_EMAIL", "ops@embedlabs.net")
    monkeypatch.setenv("BUD_ADMIN_PASSWORD", "this-is-a-long-password")

    settings = Settings(_env_file=None)

    assert settings.RUN_STARTUP_DATA_REPAIR is False


def test_production_auto_seed_admin_can_be_explicitly_enabled(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("BUD_ENV", "production")
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    set_prod_baseline(monkeypatch)
    monkeypatch.setenv("BUD_ADMIN_EMAIL", "ops@embedlabs.net")
    monkeypatch.setenv("BUD_ADMIN_PASSWORD", "this-is-a-long-password")
    monkeypatch.setenv("BUD_AUTO_SEED_ADMIN", "true")

    settings = Settings(_env_file=None)

    assert settings.AUTO_SEED_ADMIN is True


def test_production_startup_data_repair_can_be_explicitly_enabled(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("BUD_ENV", "production")
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    set_prod_baseline(monkeypatch)
    monkeypatch.setenv("BUD_ADMIN_EMAIL", "ops@embedlabs.net")
    monkeypatch.setenv("BUD_ADMIN_PASSWORD", "this-is-a-long-password")
    monkeypatch.setenv("BUD_RUN_STARTUP_DATA_REPAIR", "true")

    settings = Settings(_env_file=None)

    assert settings.RUN_STARTUP_DATA_REPAIR is True


def test_production_rejects_replace_with_secret_key_placeholder(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("BUD_ENV", "production")
    # 35 chars — long enough to clear the length gate, but still the placeholder.
    monkeypatch.setenv("BUD_SECRET_KEY", "replace-with-a-strong-random-secret")
    set_prod_baseline(monkeypatch)
    monkeypatch.setenv("BUD_ADMIN_EMAIL", "ops@embedlabs.net")
    monkeypatch.setenv("BUD_ADMIN_PASSWORD", "this-is-a-long-password")

    import pytest

    with pytest.raises(ValueError, match="placeholder"):
        Settings(_env_file=None)


def test_production_rejects_short_runner_api_key(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("BUD_ENV", "production")
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    monkeypatch.setenv("BUD_DATABASE_URL", "postgresql://bud:strong-db-pass@db:5432/buddb")
    monkeypatch.setenv("BUD_ADMIN_EMAIL", "ops@embedlabs.net")
    monkeypatch.setenv("BUD_ADMIN_PASSWORD", "this-is-a-long-password")
    monkeypatch.setenv("BUD_RUNNER_API_KEY", "too-short-runner-key")

    import pytest

    with pytest.raises(ValueError, match="RUNNER_API_KEY"):
        Settings(_env_file=None)


def test_production_rejects_replace_with_runner_api_key_even_if_long(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("BUD_ENV", "production")
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    monkeypatch.setenv("BUD_DATABASE_URL", "postgresql://bud:strong-db-pass@db:5432/buddb")
    monkeypatch.setenv("BUD_ADMIN_EMAIL", "ops@embedlabs.net")
    monkeypatch.setenv("BUD_ADMIN_PASSWORD", "this-is-a-long-password")
    # 48 chars: clears the length gate but is still the .env.example placeholder.
    monkeypatch.setenv("BUD_RUNNER_API_KEY", "replace-with-a-shared-runner-registration-secret")

    import pytest

    with pytest.raises(ValueError, match="placeholder"):
        Settings(_env_file=None)


def test_production_rejects_default_db_password_when_url_built_from_parts(monkeypatch):
    clear_config_env(monkeypatch)

    # No DATABASE_URL -> the URL is assembled from DB_* parts, so the default
    # DB_PASSWORD ("bud") must be rejected.
    monkeypatch.setenv("BUD_ENV", "production")
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    monkeypatch.setenv("BUD_ADMIN_EMAIL", "ops@embedlabs.net")
    monkeypatch.setenv("BUD_ADMIN_PASSWORD", "this-is-a-long-password")
    monkeypatch.setenv("BUD_RUNNER_API_KEY", "r" * 32)

    import pytest

    with pytest.raises(ValueError, match="DB_PASSWORD"):
        Settings(_env_file=None)


def test_production_allows_default_db_password_when_full_url_provided(monkeypatch):
    clear_config_env(monkeypatch)

    # The docker-compose path: a complete DATABASE_URL carries the real password,
    # so an unset DB_PASSWORD (default "bud") must NOT be a false-positive boot
    # failure. This guards the actual production deployment.
    monkeypatch.setenv("BUD_ENV", "production")
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    monkeypatch.setenv(
        "BUD_DATABASE_URL", "postgresql://bud:an-actually-strong-password@db:5432/buddb"
    )
    monkeypatch.setenv("BUD_ADMIN_EMAIL", "ops@embedlabs.net")
    monkeypatch.setenv("BUD_ADMIN_PASSWORD", "this-is-a-long-password")
    monkeypatch.setenv("BUD_RUNNER_API_KEY", "r" * 32)

    settings = Settings(_env_file=None)

    assert settings.DATABASE_URL == ("postgresql://bud:an-actually-strong-password@db:5432/buddb")
    assert settings.DB_PASSWORD == "bud"  # unused, and therefore not fatal


def test_production_accepts_fully_valid_config(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("BUD_ENV", "production")
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    monkeypatch.setenv("BUD_ADMIN_EMAIL", "ops@embedlabs.net")
    monkeypatch.setenv("BUD_ADMIN_PASSWORD", "this-is-a-long-password")
    monkeypatch.setenv("BUD_DB_PASSWORD", "a-strong-non-default-db-password")
    monkeypatch.setenv("BUD_RUNNER_API_KEY", "r" * 32)

    settings = Settings(_env_file=None)

    # URL assembled from parts using the strong password.
    assert "a-strong-non-default-db-password" in settings.DATABASE_URL
    assert settings.RUNNER_API_KEY == "r" * 32
