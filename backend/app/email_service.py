import logging
import smtplib
import time
from email.message import EmailMessage
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from .config import settings
from .logging_utils import log_event, log_warning
from .task_queue import JOB_TYPE_SEND_EMAIL, enqueue_job

emails_sent_ok = 0
emails_send_failed = 0


def send_email_now(
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


def send_email_async(
    background_tasks: BackgroundTasks | None,
    db: Session | None,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    context: Dict[str, Any] | None = None,
) -> None:
    # Enqueue to persistent DB-backed task queue when enabled; otherwise run as FastAPI BackgroundTask.
    if getattr(settings, "task_queue_enabled", False):
        if db is None:
            raise RuntimeError("task_queue_enabled is true but no DB session was provided")
        enqueue_job(
            db,
            JOB_TYPE_SEND_EMAIL,
            {
                "to_email": to_email,
                "subject": subject,
                "body_text": body_text,
                "body_html": body_html,
                "context": context or {},
            },
        )
        return

    if background_tasks is None:
        send_email_now(to_email, subject, body_text, body_html, context or {})
        return

    background_tasks.add_task(send_email_now, to_email, subject, body_text, body_html, context or {})
