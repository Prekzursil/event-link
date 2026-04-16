"""Support module: task queue shared."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .logging_utils import log_event

JOB_TYPE_SEND_EMAIL = "send_email"
JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML = "recompute_recommendations_ml"
JOB_TYPE_REFRESH_USER_RECOMMENDATIONS_ML = "refresh_user_recommendations_ml"
JOB_TYPE_EVALUATE_PERSONALIZATION_GUARDRAILS = "evaluate_personalization_guardrails"
JOB_TYPE_SEND_WEEKLY_DIGEST = "send_weekly_digest"
JOB_TYPE_SEND_FILLING_FAST_ALERTS = "send_filling_fast_alerts"


def _find_existing_duplicate(
    db: Session, job_type: str, dedupe_key: str
) -> models.BackgroundJob | None:
    """Returns the most recent queued/running job with the same dedupe key, if any."""
    return (
        db.query(models.BackgroundJob)
        .filter(
            models.BackgroundJob.job_type == job_type,
            models.BackgroundJob.dedupe_key == dedupe_key,
            models.BackgroundJob.status.in_(["queued", "running"]),
        )
        .order_by(models.BackgroundJob.id.desc())
        .first()
    )


# pylint: disable-next=too-many-arguments,too-many-positional-arguments
def enqueue_job(
    db: Session,
    job_type: str,
    payload: dict[str, Any],
    *,
    dedupe_key: str | None = None,
    run_at: datetime | None = None,
    max_attempts: int | None = None,
) -> models.BackgroundJob:
    """Persists a new ``BackgroundJob`` row or reuses a matching queued entry.

    Signature intentionally spans scheduling + dedupe + retry controls so
    callers can issue a fully-described enqueue in one statement.
    """
    job = models.BackgroundJob(
        job_type=job_type,
        dedupe_key=dedupe_key,
        payload=payload,
        status="queued",
        attempts=0,
        max_attempts=max_attempts or settings.task_queue_max_attempts,
        run_at=run_at or datetime.now(timezone.utc),
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if dedupe_key is None:
            raise
        existing = _find_existing_duplicate(db, job_type, dedupe_key)
        if existing is None:
            raise
        setattr(existing, "_deduped", True)
        return existing
    db.refresh(job)
    log_event("job_enqueued", job_id=job.id, job_type=job.job_type)
    return job


def _coerce_bool(value: object) -> bool:
    """Implements the coerce bool helper."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}
    return bool(value)


def _load_personalization_exclusions(
    *, db: Session, user_id: int
) -> tuple[set[int], set[int]]:
    """Loads the personalization exclusions resource."""
    hidden_tag_ids = {
        int(row[0])
        for row in db.query(models.user_hidden_tags.c.tag_id)
        .filter(models.user_hidden_tags.c.user_id == user_id)
        .all()
    }
    blocked_organizer_ids = {
        int(row[0])
        for row in db.query(models.user_blocked_organizers.c.organizer_id)
        .filter(models.user_blocked_organizers.c.user_id == user_id)
        .all()
    }
    return hidden_tag_ids, blocked_organizer_ids


def _preferred_lang(value: str | None) -> str:
    """Implements the preferred lang helper."""
    return "ro" if not value or value == "system" else value


def _notification_exists(*, db: Session, dedupe_key: str) -> bool:
    """Implements the notification exists helper."""
    return (
        db.query(models.NotificationDelivery.id)
        .filter(models.NotificationDelivery.dedupe_key == dedupe_key)
        .first()
        is not None
    )


def _send_email_payload(
    *,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: str | None,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Implements the send email payload helper."""
    return {
        "to_email": to_email,
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
        "context": context,
    }
