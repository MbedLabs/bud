import logging
import smtplib
from email.message import EmailMessage
from pathlib import Path
from string import Template

from app.core.config import settings

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"


class MailConfigurationError(Exception):
    pass


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
    message["From"] = (
        f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        if settings.SMTP_FROM_NAME
        else settings.SMTP_FROM_EMAIL
    )
    message["To"] = to_email
    if settings.SMTP_REPLY_TO:
        message["Reply-To"] = settings.SMTP_REPLY_TO
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    smtp_class = smtplib.SMTP_SSL if settings.SMTP_SSL else smtplib.SMTP
    with smtp_class(
        settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT_SECONDS
    ) as smtp:
        if settings.SMTP_STARTTLS and not settings.SMTP_SSL:
            smtp.starttls()
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(message)

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
