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
    "BUD_MAX_UPLOAD_SIZE",
    "BUD_PASSWORD_RESET_TOKEN_TTL_HOURS",
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
    "MAX_UPLOAD_SIZE",
    "PASSWORD_RESET_TOKEN_TTL_HOURS",
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
    monkeypatch.setenv("BUD_SMTP_FROM_NAME", "Bud Mailer")
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
    assert settings.SMTP_FROM_NAME == "Bud Mailer"
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
    monkeypatch.setenv("BUD_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BUD_ADMIN_PASSWORD", "this-is-a-long-password")

    import pytest

    with pytest.raises(ValueError, match="ADMIN_EMAIL"):
        Settings(_env_file=None)


def test_production_rejects_default_admin_password(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("BUD_ENV", "production")
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    monkeypatch.setenv("BUD_ADMIN_EMAIL", "ops@embedlabs.de")
    monkeypatch.setenv("BUD_ADMIN_PASSWORD", "changeme123")

    import pytest

    with pytest.raises(ValueError, match="ADMIN_PASSWORD"):
        Settings(_env_file=None)


def test_production_rejects_short_admin_password(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("BUD_ENV", "production")
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    monkeypatch.setenv("BUD_ADMIN_EMAIL", "ops@embedlabs.de")
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


def test_production_auto_seed_admin_defaults_off(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("BUD_ENV", "production")
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    monkeypatch.setenv("BUD_ADMIN_EMAIL", "ops@embedlabs.de")
    monkeypatch.setenv("BUD_ADMIN_PASSWORD", "this-is-a-long-password")

    settings = Settings(_env_file=None)

    assert settings.AUTO_SEED_ADMIN is False


def test_production_auto_seed_admin_can_be_explicitly_enabled(monkeypatch):
    clear_config_env(monkeypatch)

    monkeypatch.setenv("BUD_ENV", "production")
    monkeypatch.setenv("BUD_SECRET_KEY", "b" * 32)
    monkeypatch.setenv("BUD_ADMIN_EMAIL", "ops@embedlabs.de")
    monkeypatch.setenv("BUD_ADMIN_PASSWORD", "this-is-a-long-password")
    monkeypatch.setenv("BUD_AUTO_SEED_ADMIN", "true")

    settings = Settings(_env_file=None)

    assert settings.AUTO_SEED_ADMIN is True
