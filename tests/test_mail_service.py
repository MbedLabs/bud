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


def _configure_smtp(monkeypatch, *, starttls=True, port=2525):
    monkeypatch.setattr(mail_service.settings, "SMTP_ENABLED", True)
    monkeypatch.setattr(mail_service.settings, "SMTP_HOST", "mail")
    monkeypatch.setattr(mail_service.settings, "SMTP_PORT", port)
    monkeypatch.setattr(mail_service.settings, "SMTP_USERNAME", "")
    monkeypatch.setattr(mail_service.settings, "SMTP_PASSWORD", "")
    monkeypatch.setattr(mail_service.settings, "SMTP_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setattr(mail_service.settings, "SMTP_REPLY_TO", None)
    monkeypatch.setattr(mail_service.settings, "SMTP_STARTTLS", starttls)
    monkeypatch.setattr(mail_service.settings, "SMTP_SSL", False)
    monkeypatch.setattr(mail_service.settings, "SMTP_TIMEOUT_SECONDS", 9)


def test_starttls_on_a_plaintext_port_reports_where_and_why(monkeypatch):
    """The exact production failure: STARTTLS asked of a relay that does not offer it.

    It previously escaped mail_service uncaught and every caller returned a bare
    500 with an empty body, which is undiagnosable from the browser.
    """
    import smtplib

    class _NoStartTLS(_DummySMTP):
        def starttls(self):
            raise smtplib.SMTPNotSupportedError(
                "STARTTLS extension not supported by server."
            )

    _configure_smtp(monkeypatch, starttls=True, port=2525)
    monkeypatch.setattr(
        mail_service.smtplib, "SMTP", lambda host, port, timeout: _NoStartTLS(host, port, timeout)
    )

    try:
        mail_service.send_email(
            to_email="someone@example.com", subject="s", text_body="t"
        )
    except mail_service.MailDeliveryError as exc:
        message = str(exc)
    else:
        raise AssertionError("a failing STARTTLS handshake must not look like success")

    # The operator needs the endpoint and the TLS mode, not just the library text.
    assert "mail:2525" in message
    assert "STARTTLS=True" in message
    assert "SMTPNotSupportedError" in message


def test_delivery_failures_reach_the_existing_error_handlers(monkeypatch):
    """Every endpoint already maps MailConfigurationError to a 503 carrying the
    message. MailDeliveryError subclasses it so transport failures take that same
    path instead of escaping as an empty 500."""
    assert issubclass(mail_service.MailDeliveryError, mail_service.MailConfigurationError)


def test_an_unreachable_relay_is_also_reported(monkeypatch):
    """OSError, not SMTPException — a refused connection must be translated too."""
    _configure_smtp(monkeypatch, starttls=False, port=2525)

    def _refused(host, port, timeout):
        raise OSError("Connection refused")

    monkeypatch.setattr(mail_service.smtplib, "SMTP", _refused)

    try:
        mail_service.send_email(to_email="a@example.com", subject="s", text_body="t")
    except mail_service.MailDeliveryError as exc:
        assert "mail:2525" in str(exc)
    else:
        raise AssertionError("an unreachable relay must raise MailDeliveryError")
