import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-at-least-32-characters-long")
os.environ.setdefault("RUNNER_API_KEY", "test-runner-api-key")

from app.services import mail_service


class _DummySMTP:
    def __init__(self, host: str, port: int, timeout: int):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.messages = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def starttls(self):
        pass

    def login(self, username: str, password: str):
        pass

    def send_message(self, message):
        self.messages.append(message)


def test_send_email_uses_fixed_bud_sender_name(monkeypatch):
    captured = {}

    def smtp_factory(host: str, port: int, timeout: int):
        smtp = _DummySMTP(host, port, timeout)
        captured["smtp"] = smtp
        return smtp

    monkeypatch.setattr(mail_service.settings, "SMTP_ENABLED", True)
    monkeypatch.setattr(mail_service.settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(mail_service.settings, "SMTP_PORT", 587)
    monkeypatch.setattr(mail_service.settings, "SMTP_USERNAME", "")
    monkeypatch.setattr(mail_service.settings, "SMTP_PASSWORD", "")
    monkeypatch.setattr(mail_service.settings, "SMTP_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setattr(mail_service.settings, "SMTP_REPLY_TO", None)
    monkeypatch.setattr(mail_service.settings, "SMTP_STARTTLS", False)
    monkeypatch.setattr(mail_service.settings, "SMTP_SSL", False)
    monkeypatch.setattr(mail_service.settings, "SMTP_TIMEOUT_SECONDS", 9)
    monkeypatch.setattr(mail_service.smtplib, "SMTP", smtp_factory)

    mail_service.send_email(
        to_email="user@example.com",
        subject="Test subject",
        text_body="plain text",
    )

    smtp = captured["smtp"]
    assert len(smtp.messages) == 1
    # Matches Bloom's "<product> <suffix> by EmbedLabs" sender style ("Bloom PLM by EmbedLabs").
    assert smtp.messages[0]["From"] == "Bud TMP by EmbedLabs <noreply@example.com>"
