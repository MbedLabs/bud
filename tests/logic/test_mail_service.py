import os
from html.parser import HTMLParser

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-at-least-32-characters-long")
os.environ.setdefault("RUNNER_API_KEY", "test-runner-api-key")

import pytest

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
    """The sender name has the form '<product> <suffix> by EmbedLabs', as Bloom's does."""
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
    """The exact production failure: STARTTLS asked of a relay that does not offer it."""
    import smtplib

    class _NoStartTLS(_DummySMTP):
        def starttls(self):
            raise smtplib.SMTPNotSupportedError("STARTTLS extension not supported by server.")

    _configure_smtp(monkeypatch, starttls=True, port=2525)
    monkeypatch.setattr(
        mail_service.smtplib, "SMTP", lambda host, port, timeout: _NoStartTLS(host, port, timeout)
    )

    try:
        mail_service.send_email(to_email="someone@example.com", subject="s", text_body="t")
    except mail_service.MailDeliveryError as exc:
        message = str(exc)
    else:
        raise AssertionError("a failing STARTTLS handshake must not look like success")

    assert "mail:2525" in message
    assert "STARTTLS=True" in message
    assert "SMTPNotSupportedError" in message


def test_delivery_failures_reach_the_existing_error_handlers(monkeypatch):
    """Every endpoint already maps MailConfigurationError to a 503 carrying the
    message. MailDeliveryError subclasses it so transport failures take that same
    path instead of escaping as an empty 500."""
    assert issubclass(mail_service.MailDeliveryError, mail_service.MailConfigurationError)


def test_an_unreachable_relay_is_also_reported(monkeypatch):
    """OSError, not SMTPException: a refused connection must be translated too."""
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


def test_delivery_log_excludes_message_and_recipient(monkeypatch, caplog):
    """Successful deliveries keep recipient and message content out of logs."""
    import logging

    _configure_smtp(monkeypatch, starttls=False)
    monkeypatch.setattr(mail_service.smtplib, "SMTP", _DummySMTP)
    with caplog.at_level(logging.INFO, logger=mail_service.__name__):
        mail_service.send_email(
            to_email="private-recipient@example.com",
            subject="Private subject with an untrusted marker",
            text_body="private message content",
        )
    assert "Email sent" in caplog.text
    assert "private-recipient" not in caplog.text
    assert "untrusted marker" not in caplog.text
    assert "private message content" not in caplog.text


def test_delivery_error_log_excludes_untrusted_server_response(monkeypatch, caplog):
    """SMTP errors retain diagnostic exceptions without logging server text."""
    import logging
    import smtplib

    import pytest

    _configure_smtp(monkeypatch, starttls=False)

    def refused(host, port, timeout):
        raise smtplib.SMTPException("remote response\nforged log entry")

    monkeypatch.setattr(mail_service.smtplib, "SMTP", refused)
    with caplog.at_level(logging.ERROR, logger=mail_service.__name__):
        with pytest.raises(mail_service.MailDeliveryError) as error:
            mail_service.send_email(
                to_email="private-recipient@example.com", subject="private", text_body="body"
            )
    assert "SMTPException" in caplog.text
    assert "remote response" not in caplog.text
    assert "forged log entry" not in caplog.text
    assert "remote response" in str(error.value)


LINK = "https://bud.example.com/action?first=1&second=2#token=abc"

SENDERS = {
    "invite": lambda: mail_service.send_invite_email(
        to_email="user@example.com", full_name="Test User", invite_link=LINK
    ),
    "verify_email": lambda: mail_service.send_verification_email(
        to_email="user@example.com", full_name="Test User", verification_link=LINK
    ),
    "reset_password": lambda: mail_service.send_password_reset_email(
        to_email="user@example.com", full_name="Test User", reset_link=LINK
    ),
    "email_change": lambda: mail_service.send_email_change_email(
        to_email="new@example.com",
        full_name="Test User",
        old_email="old@example.com",
        new_email="new@example.com",
        confirm_link=LINK,
    ),
    "email_change_authorization": lambda: mail_service.send_email_change_authorization_email(
        to_email="old@example.com",
        full_name="Test User",
        old_email="old@example.com",
        new_email="new@example.com",
        confirm_link=LINK,
    ),
    "admin_welcome": lambda: mail_service.send_admin_welcome_email(
        to_email="admin@example.com", full_name="Test Admin", login_link=LINK
    ),
    "access_request": lambda: mail_service.send_access_request_email(
        to_email="admin@example.com",
        admin_name="Administrator",
        requester_name="Writer <script>",
        requester_email="writer@example.com",
        resource="Publish to Bloom",
        project="PRJ",
        requested_at="2026-10-25T10:00:00Z",
        request_id="42",
        review_link=LINK,
    ),
    "report_request": lambda: mail_service.send_report_request_email(
        to_email="publisher@example.com",
        publisher_name="Publisher",
        requester_name="Reader <script>",
        requester_email="reader@example.com",
        project="PRJ",
        run_id="42",
        review_link=LINK,
    ),
}


class _Copy(HTMLParser):
    """Collect the heading, the paragraphs and the single action link of a rendered email."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.heading = ""
        self.blocks = []
        self.links = 0
        self._heading = None
        self._block = None
        self._label = None
        self._href = None

    def handle_starttag(self, tag, attrs):
        if tag == "h1":
            self._heading = []
        elif tag == "p":
            self._block = []
        elif tag == "br" and self._block is not None:
            self._block.append("\n")
        elif tag == "a":
            self.links += 1
            self._href = dict(attrs)["href"]
            self._label = []

    def handle_endtag(self, tag):
        if tag == "h1":
            self.heading = "".join(self._heading)
            self._heading = None
        elif tag == "a":
            self._block.append(f"{''.join(self._label)}: {self._href}")
            self._label = None
        elif tag == "p":
            self.blocks.append("".join(self._block).strip())
            self._block = None

    def handle_data(self, data):
        if self._label is not None:
            self._label.append(data)
        elif self._block is not None:
            self._block.append(data)
        elif self._heading is not None:
            self._heading.append(data)


def _send(monkeypatch, name):
    messages = []
    monkeypatch.setattr(mail_service, "send_email", lambda **message: messages.append(message))
    SENDERS[name]()
    return messages[0]


@pytest.mark.parametrize("name", SENDERS)
def test_every_email_follows_the_product_structure(monkeypatch, name):
    """Each email has the identity in its heading, one action and the same copy in HTML and text."""
    message = _send(monkeypatch, name)
    copy = _Copy()
    copy.feed(message["html_body"])
    assert "${" not in message["html_body"] + message["text_body"]
    assert "<title>Bud TMP by EmbedLabs</title>" in message["html_body"]
    assert "Bud TMP by EmbedLabs" in copy.heading
    assert "Bud TMP" in message["subject"]
    assert "Bud TMP" in message["text_body"]
    assert copy.links == 1
    assert "background:#208337;color:#ffffff" in message["html_body"]
    blocks = [block.replace("\u00a9", "(c)") for block in copy.blocks]
    assert blocks[-1] == "(c) 2026 EmbedLabs. All rights reserved."
    assert message["text_body"].endswith("(c) 2026 EmbedLabs. All rights reserved.\n")
    assert message["text_body"].strip().split("\n\n") == blocks
    assert blocks[0].startswith("Hello ")
    action = [index for index, block in enumerate(blocks) if block.endswith(LINK)]
    assert len(action) == 1
    assert 2 <= action[0] <= len(blocks) - 3


def test_html_values_are_escaped_and_text_values_are_not(monkeypatch):
    """Access and report request emails escape sender-supplied values in HTML only."""
    access = _send(monkeypatch, "access_request")
    report = _send(monkeypatch, "report_request")
    assert "Writer &lt;script&gt;" in access["html_body"]
    assert "Writer <script>" in access["text_body"]
    assert "Reader &lt;script&gt;" in report["html_body"]
    assert "Reader <script>" in report["text_body"]
    assert 'href="https://bud.example.com/action?first=1&amp;second=2#token=abc"' in (
        access["html_body"]
    )


def test_request_emails_keep_their_subject_and_next_steps(monkeypatch):
    """Access and report request emails keep their subjects and the product-specific next step."""
    access = _send(monkeypatch, "access_request")
    report = _send(monkeypatch, "report_request")
    assert access["subject"] == "Access requested on Bud TMP: Publish to Bloom"
    assert report["subject"] == "Report requested on Bud TMP: run #42"
    grant = "Grant access in Bud TMP, then mark the request granted or refused."
    publish = "Publish the report from Bud TMP to Bloom or refuse the request with a reason."
    assert grant in access["html_body"] and grant in access["text_body"]
    assert publish in report["html_body"] and publish in report["text_body"]
