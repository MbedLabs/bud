"""
* @file     ${tests/logic/BUD_mail_service.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Emails leave with the product identity, failures name the relay, and every email shares one structure.
* @author   Amine El Omari
* @date     2026-11-12
* @version  1.0.0
* @note     This module tests the mail service with a faked SMTP relay and with the delivery itself captured.
"""

import logging
import smtplib
from html.parser import HTMLParser
from unittest import mock

from app.services import mail_service
from tests.logic.mail_service import MailServiceBase


class Relay:
    """A faked SMTP relay that keeps the messages it is given."""

    opened = []

    def __init__(self, host, port, timeout):
        self.messages = []
        Relay.opened.append(self)

    def __enter__(self):
        return self

    def __exit__(self, kind, error, trace):
        return False

    def starttls(self):
        pass

    def login(self, username, password):
        pass

    def send_message(self, message):
        self.messages.append(message)


class WithoutStartTls(Relay):
    """A relay that does not offer STARTTLS."""

    def starttls(self):
        raise smtplib.SMTPNotSupportedError("STARTTLS extension not supported by server.")


class Copy(HTMLParser):
    """The heading, the paragraphs and the action links of a rendered email."""

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
            self._href = dict(attrs).get("href")
            self._label = []

    def handle_endtag(self, tag):
        if tag == "h1" and self._heading is not None:
            self.heading = "".join(self._heading)
            self._heading = None
        elif tag == "a" and self._label is not None:
            if self._block is not None:
                self._block.append(f"{''.join(self._label)}: {self._href}")
            self._label = None
        elif tag == "p" and self._block is not None:
            self.blocks.append("".join(self._block).strip())
            self._block = None

    def handle_data(self, data):
        if self._label is not None:
            self._label.append(data)
        elif self._block is not None:
            self._block.append(data)
        elif self._heading is not None:
            self._heading.append(data)


def refuse(error):
    """A relay factory that raises error."""

    def relay(host, port, timeout):
        raise error

    return relay


class MailServiceTest(MailServiceBase):

    def setUpClass(self):
        super().setUpClass()
        p = self.parameters
        self.tc_checks = {}
        self.sender()
        self.tc_checks["starttls"] = self.failed_delivery(
            WithoutStartTls, {"SMTP_STARTTLS": True}, p.MAIL_STARTTLS_TEXTS
        )
        self.tc_checks["handlers"] = {
            "MailDeliveryError is a MailConfigurationError": (
                issubclass(mail_service.MailDeliveryError, mail_service.MailConfigurationError),
                True,
            )
        }
        self.tc_checks["unreachable"] = self.failed_delivery(
            refuse(OSError("Connection refused")), {}, (p.MAIL_RELAY,)
        )
        self.logs()
        emails = {name: self.email(name) for name in p.MAIL_SENDERS}
        for name, message in emails.items():
            self.tc_checks[name] = self.structure(message)
        self.requests(emails["access_request"], emails["report_request"])

    def deliver(self, relay, settings=None, **message):
        """Send one email through relay with the test SMTP settings; return the error it raises."""
        values = {**self.parameters.MAIL_SETTINGS, **(settings or {})}
        Relay.opened = []
        with (
            mock.patch.multiple(mail_service.settings, **values),
            mock.patch.object(mail_service.smtplib, "SMTP", relay),
        ):
            try:
                mail_service.send_email(
                    **{"to_email": "a@example.com", "subject": "s", "text_body": "t", **message}
                )
            except Exception as error:
                return error
        return None

    def sender(self):
        """An email sent through a relay that accepts it."""
        p = self.parameters
        self.deliver(
            Relay,
            {**p.MAIL_SENDER_HOST, "SMTP_STARTTLS": False},
            to_email="user@example.com",
            subject="Test subject",
            text_body="plain text",
        )
        messages = [message for relay in Relay.opened for message in relay.messages]
        self.tc_checks["sender"] = {
            "one message is handed over": (len(messages), 1),
            "the sender is the product identity": (
                (messages or [{}])[0].get("From"),
                p.MAIL_FROM,
            ),
        }

    def failed_delivery(self, relay, settings, texts):
        """The error a failing relay raises and the relay facts it names."""
        error = self.deliver(relay, settings)
        checks = {
            "the delivery raises MailDeliveryError": (
                type(error).__name__,
                self.parameters.MAIL_DELIVERY_ERROR,
            )
        }
        for text in texts:
            checks[f"the error names {text}"] = (text in str(error), True)
        return checks

    def logged(self, relay, level, **message):
        """The log text and the error of one delivery."""
        self.bud.bud_start_log_capture(level)
        error = self.deliver(relay, **message)
        records = self.bud.bud_stop_log_capture()
        text = "\n".join(
            logging.Formatter().format(record)
            for record in records
            if record.name == mail_service.__name__
        )
        return text, error

    def logs(self):
        """A delivered and a refused email with private values."""
        p = self.parameters
        text, _ = self.logged(Relay, logging.INFO, **p.MAIL_PRIVATE)
        self.tc_checks["sent log"] = {"the delivery is logged": (p.MAIL_SENT in text, True)}
        for private in p.MAIL_PRIVATE_TEXTS:
            self.tc_checks["sent log"][f"the log leaves out {private}"] = (private in text, False)
        text, error = self.logged(
            refuse(smtplib.SMTPException(p.MAIL_SERVER_RESPONSE)),
            logging.ERROR,
            to_email="private-recipient@example.com",
            subject="private",
            text_body="body",
        )
        self.tc_checks["error log"] = {
            "the delivery raises MailDeliveryError": (type(error).__name__, p.MAIL_DELIVERY_ERROR),
            "the log names the exception type": ("SMTPException" in text, True),
        }
        for server_text in p.MAIL_SERVER_TEXTS:
            self.tc_checks["error log"][f"the log leaves out {server_text}"] = (
                server_text in text,
                False,
            )
        self.tc_checks["error log"]["the error keeps the server response"] = (
            p.MAIL_SERVER_TEXTS[0] in str(error),
            True,
        )

    def email(self, name):
        """The message one sender hands to the delivery."""
        function, arguments = self.parameters.MAIL_SENDERS[name]
        messages = []
        with mock.patch.object(
            mail_service, "send_email", lambda **message: messages.append(message)
        ):
            getattr(mail_service, function)(**arguments)
        return (messages or [{}])[0]

    def structure(self, message):
        """The structure checks of one rendered email."""
        p = self.parameters
        html = message.get("html_body") or ""
        text = message.get("text_body") or ""
        subject = message.get("subject") or ""
        copy = Copy()
        copy.feed(html)
        blocks = [block.replace("©", "(c)") for block in copy.blocks] or [""]
        action = [index for index, block in enumerate(blocks) if block.endswith(p.MAIL_LINK)]
        return {
            "no placeholder is left": ("${" in html + text, False),
            "the title is the product identity": (p.MAIL_TITLE in html, True),
            "the heading holds the product identity": (p.MAIL_IDENTITY in copy.heading, True),
            "the subject names the product": (p.MAIL_PRODUCT in subject, True),
            "the text names the product": (p.MAIL_PRODUCT in text, True),
            "the email holds one link": (copy.links, 1),
            "the action button has the product colours": (p.MAIL_BUTTON in html, True),
            "the HTML ends with the copyright": (blocks[-1], p.MAIL_FOOTER),
            "the text ends with the copyright": (text.endswith(p.MAIL_FOOTER + "\n"), True),
            "the text holds the same paragraphs": (text.strip().split("\n\n"), blocks),
            "the email starts with a greeting": (blocks[0].startswith(p.MAIL_GREETING), True),
            "one paragraph holds the action": (len(action), 1),
            "the action sits between the greeting and the closing": (
                bool(action) and 2 <= action[0] <= len(blocks) - 3,
                True,
            ),
        }

    def requests(self, access, report):
        """The escaping, subjects and next steps of the access and report request emails."""
        p = self.parameters
        bodies = {"access": access, "report": report}
        self.tc_checks["escaped"] = {
            name: (value in (bodies[email].get(part) or ""), True)
            for name, (email, part, value) in p.MAIL_ESCAPED.items()
        }
        self.tc_checks["requests"] = {
            "the access request subject": (access.get("subject"), p.MAIL_ACCESS_SUBJECT),
            "the report request subject": (report.get("subject"), p.MAIL_REPORT_SUBJECT),
        }
        for email, step in (("access", p.MAIL_GRANT), ("report", p.MAIL_PUBLISH)):
            for part in ("html_body", "text_body"):
                self.tc_checks["requests"][f"the {email} {part} names the next step"] = (
                    step in (bodies[email].get(part) or ""),
                    True,
                )

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    MailServiceTest().run()
