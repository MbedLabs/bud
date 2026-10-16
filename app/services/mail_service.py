import html
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
    """SMTP is configured, but the message could not be handed to the server."""


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
        logger.error("Mail delivery failed (%s)", type(exc).__name__)
        raise MailDeliveryError(detail) from exc

    logger.info("Email sent")


def _send_template(to_email: str, subject: str, template: str, context: dict[str, str]) -> None:
    """Send the text and HTML versions of a template, with the app name in its context."""
    context = {**context, "app_name": settings.BUD_APP_NAME}
    send_email(
        to_email=to_email,
        subject=subject,
        text_body=render_template(f"{template}.txt", context),
        html_body=render_template(f"{template}.html", context),
    )


def send_invite_email(*, to_email: str, full_name: str, invite_link: str) -> None:
    _send_template(
        to_email,
        f"You're invited to {settings.BUD_APP_NAME}",
        "invite",
        {"full_name": full_name, "invite_link": invite_link},
    )


def send_verification_email(*, to_email: str, full_name: str, verification_link: str) -> None:
    _send_template(
        to_email,
        f"Verify your email for {settings.BUD_APP_NAME}",
        "verify_email",
        {"full_name": full_name, "verification_link": verification_link},
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
    _send_template(
        to_email,
        f"Confirm your approved email change for {settings.BUD_APP_NAME}",
        "email_change",
        {
            "full_name": full_name,
            "old_email": old_email,
            "new_email": new_email,
            "confirm_link": confirm_link,
        },
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
    _send_template(
        to_email,
        f"Authorize your email change for {settings.BUD_APP_NAME}",
        "email_change_authorization",
        {
            "full_name": full_name,
            "old_email": old_email,
            "new_email": new_email,
            "confirm_link": confirm_link,
        },
    )


def send_password_reset_email(*, to_email: str, full_name: str, reset_link: str) -> None:
    _send_template(
        to_email,
        f"Reset your password for {settings.BUD_APP_NAME}",
        "reset_password",
        {"full_name": full_name, "reset_link": reset_link},
    )


def send_admin_welcome_email(*, to_email: str, full_name: str, login_link: str) -> None:
    """Confirm to the first administrator that their account exists."""
    _send_template(
        to_email,
        f"You are the administrator of {settings.BUD_APP_NAME}",
        "admin_welcome",
        {"full_name": full_name, "login_link": login_link},
    )


def send_access_request_email(
    *,
    to_email: str,
    admin_name: str,
    requester_name: str,
    requester_email: str,
    resource: str,
    project: str,
    requested_at: str,
    request_id: str,
    review_link: str,
) -> None:
    """Tell an administrator that a user asks for access to a resource."""
    context = {
        "admin_name": admin_name,
        "requester_name": requester_name,
        "requester_email": requester_email,
        "resource": resource,
        "project_part": f" in project {project}" if project else "",
        "requested_at": requested_at,
        "request_id": request_id,
        "review_link": review_link,
        "app_name": settings.BUD_APP_NAME,
    }
    send_email(
        to_email=to_email,
        subject=f"Access requested on {settings.BUD_APP_NAME}: {resource}",
        text_body=render_template("access_request.txt", context),
        html_body=render_template(
            "access_request.html", {key: html.escape(value) for key, value in context.items()}
        ),
    )


def send_report_request_email(
    *,
    to_email: str,
    publisher_name: str,
    requester_name: str,
    requester_email: str,
    project: str,
    run_id: str,
    review_link: str,
) -> None:
    """Tell a report publisher about a Bloom reader's pending request."""
    context = {
        "publisher_name": publisher_name,
        "requester_name": requester_name,
        "requester_email": requester_email,
        "project": project,
        "run_id": run_id,
        "review_link": review_link,
        "app_name": settings.BUD_APP_NAME,
    }
    send_email(
        to_email=to_email,
        subject=f"Report requested on {settings.BUD_APP_NAME}: run #{run_id}",
        text_body=render_template("report_request.txt", context),
        html_body=render_template(
            "report_request.html", {key: html.escape(value) for key, value in context.items()}
        ),
    )
