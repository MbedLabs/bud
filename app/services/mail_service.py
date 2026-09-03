import logging
import smtplib
from email.message import EmailMessage
from pathlib import Path
from string import Template

from app.core.config import settings

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"
BUD_FROM_NAME = "Bud TMP by EmbedLabs"


class MailConfigurationError(Exception):
    pass


class MailDeliveryError(MailConfigurationError):
    """SMTP is configured, but the message could not be handed to the server.

    Deliberately a subclass: every endpoint that sends mail already turns
    MailConfigurationError into a 503 carrying the message, so a transport
    failure now reaches the operator with a reason attached instead of
    escaping as a bare 500 with an empty body.
    """


def render_template(template_name: str, context: dict[str, str]) -> str:
    template_path = TEMPLATE_DIR / template_name
    content = template_path.read_text(encoding="utf-8")
    return Template(content).safe_substitute(context)


def send_email(
    *, to_email: str, subject: str, text_body: str, html_body: str | None = None
) -> None:
    if not settings.SMTP_ENABLED:
        raise MailConfigurationError("SMTP is disabled")
    if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
        raise MailConfigurationError("SMTP is not fully configured")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{BUD_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    message["To"] = to_email
    if settings.SMTP_REPLY_TO:
        message["Reply-To"] = settings.SMTP_REPLY_TO
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    smtp_class = smtplib.SMTP_SSL if settings.SMTP_SSL else smtplib.SMTP
    try:
        with smtp_class(
            settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT_SECONDS
        ) as smtp:
            if settings.SMTP_STARTTLS and not settings.SMTP_SSL:
                smtp.starttls()
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        # Name the endpoint and the TLS mode: the failures seen in practice are
        # a port/TLS mismatch or an unreachable relay, and neither is
        # identifiable from the exception text alone.
        detail = (
            f"Could not send mail via {settings.SMTP_HOST}:{settings.SMTP_PORT} "
            f"(STARTTLS={settings.SMTP_STARTTLS}, SSL={settings.SMTP_SSL}): "
            f"{type(exc).__name__}: {exc}"
        )
        logger.error("Mail delivery failed: %s", detail)
        raise MailDeliveryError(detail) from exc

    logger.info("Sent email '%s' to %s", subject, to_email)


def send_invite_email(*, to_email: str, full_name: str, invite_link: str) -> None:
    context = {
        "full_name": full_name,
        "invite_link": invite_link,
        "app_name": settings.BUD_APP_NAME,
    }
    send_email(
        to_email=to_email,
        subject=f"You're invited to {settings.BUD_APP_NAME}",
        text_body=render_template("invite.txt", context),
        html_body=render_template("invite.html", context),
    )


def send_verification_email(*, to_email: str, full_name: str, verification_link: str) -> None:
    context = {
        "full_name": full_name,
        "verification_link": verification_link,
        "app_name": settings.BUD_APP_NAME,
    }
    send_email(
        to_email=to_email,
        subject=f"Verify your email for {settings.BUD_APP_NAME}",
        text_body=render_template("verify_email.txt", context),
        html_body=render_template("verify_email.html", context),
    )


def send_email_change_email(
    *,
    to_email: str,
    full_name: str,
    old_email: str,
    new_email: str,
    confirm_link: str,
) -> None:
    """Ask the approved new mailbox to confirm an administrator-controlled change."""
    context = {
        "full_name": full_name,
        "old_email": old_email,
        "new_email": new_email,
        "confirm_link": confirm_link,
        "app_name": settings.BUD_APP_NAME,
    }
    send_email(
        to_email=to_email,
        subject=f"Confirm your approved email change for {settings.BUD_APP_NAME}",
        text_body=render_template("email_change.txt", context),
        html_body=render_template("email_change.html", context),
    )


def send_email_change_authorization_email(
    *,
    to_email: str,
    full_name: str,
    old_email: str,
    new_email: str,
    confirm_link: str,
) -> None:
    """Ask the current administrator mailbox to authorize a login change."""
    context = {
        "full_name": full_name,
        "old_email": old_email,
        "new_email": new_email,
        "confirm_link": confirm_link,
        "app_name": settings.BUD_APP_NAME,
    }
    send_email(
        to_email=to_email,
        subject=f"Authorize your email change for {settings.BUD_APP_NAME}",
        text_body=render_template("email_change_authorization.txt", context),
        html_body=render_template("email_change_authorization.html", context),
    )


def send_password_reset_email(*, to_email: str, full_name: str, reset_link: str) -> None:
    context = {
        "full_name": full_name,
        "reset_link": reset_link,
        "app_name": settings.BUD_APP_NAME,
    }
    send_email(
        to_email=to_email,
        subject=f"Reset your password for {settings.BUD_APP_NAME}",
        text_body=render_template("reset_password.txt", context),
        html_body=render_template("reset_password.html", context),
    )
