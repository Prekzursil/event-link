import logging
import smtplib
import time
from email.message import EmailMessage
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks

from .config import settings
from .logging_utils import log_event, log_warning

emails_sent_ok = 0
emails_send_failed = 0


def _send_email(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    context: Dict[str, Any] | None = None,
) -> None:
    context = context or {}
    if not settings.email_enabled:
        log_warning("email_disabled", to=to_email, subject=subject, **context)
        return
    if not settings.smtp_host or not settings.smtp_sender:
        log_warning("email_smtp_not_configured", to=to_email, subject=subject, **context)
        return

    message = EmailMessage()
    message["From"] = settings.smtp_sender
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body_text)
    if body_html:
        message.add_alternative(body_html, subtype="html")

    global emails_sent_ok, emails_send_failed
    for attempt in range(1, 4):
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port or 25, timeout=10) as server:
                if settings.smtp_use_tls:
                    server.starttls()
                if settings.smtp_username:
                    server.login(settings.smtp_username, settings.smtp_password or "")
                server.send_message(message)
            emails_sent_ok += 1
            log_event("email_sent", to=to_email, subject=subject, attempt=attempt, **context)
            return
        except Exception as exc:  # noqa: BLE001
            log_warning(
                "email_send_failed_attempt",
                to=to_email,
                subject=subject,
                attempt=attempt,
                error=str(exc),
                smtp_host=settings.smtp_host,
                smtp_port=settings.smtp_port,
                **context,
            )
            if attempt < 3:
                time.sleep(0.5 * attempt)
    emails_send_failed += 1
    logging.exception(
        "Failed to send email after retries",
        extra={
            "to": to_email,
            "subject": subject,
            "smtp_host": settings.smtp_host,
            "smtp_port": settings.smtp_port,
            **context,
        },
    )


def send_registration_email(
    background_tasks: BackgroundTasks,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    context: Dict[str, Any] | None = None,
) -> None:
    # Run email sending outside the request/response flow
    background_tasks.add_task(_send_email, to_email, subject, body_text, body_html, context or {})
