import logging
import smtplib
from email.message import EmailMessage
from typing import Any, Dict

from fastapi import BackgroundTasks

from .config import settings


def _send_email(to_email: str, subject: str, body: str, context: Dict[str, Any] | None = None) -> None:
    context = context or {}
    if not settings.smtp_host or not settings.smtp_sender:
        logging.info(
            "SMTP not configured; skipping email",
            extra={"to": to_email, "subject": subject, **context},
        )
        return

    message = EmailMessage()
    message["From"] = settings.smtp_sender
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port or 25, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password or "")
            server.send_message(message)
        logging.info("Email sent", extra={"to": to_email, "subject": subject, **context})
    except Exception as exc:  # noqa: BLE001
        logging.exception("Failed to send email", extra={"to": to_email, "subject": subject, **context})


def send_registration_email(
    background_tasks: BackgroundTasks,
    to_email: str,
    subject: str,
    body: str,
    context: Dict[str, Any] | None = None,
) -> None:
    # Run email sending outside the request/response flow
    background_tasks.add_task(_send_email, to_email, subject, body, context or {})
