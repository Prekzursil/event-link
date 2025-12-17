from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from . import models
from .config import settings
from .logging_utils import log_event, log_warning


JOB_TYPE_SEND_EMAIL = "send_email"


def enqueue_job(
    db: Session,
    job_type: str,
    payload: dict[str, Any],
    *,
    run_at: datetime | None = None,
    max_attempts: int | None = None,
) -> models.BackgroundJob:
    job = models.BackgroundJob(
        job_type=job_type,
        payload=payload,
        status="queued",
        attempts=0,
        max_attempts=max_attempts or settings.task_queue_max_attempts,
        run_at=run_at or datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    log_event("job_enqueued", job_id=job.id, job_type=job.job_type)
    return job


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def requeue_stale_jobs(db: Session, *, stale_after_seconds: int | None = None) -> int:
    stale_after_seconds = stale_after_seconds or settings.task_queue_stale_after_seconds
    cutoff = _now_utc() - timedelta(seconds=stale_after_seconds)
    count = (
        db.query(models.BackgroundJob)
        .filter(models.BackgroundJob.status == "running", models.BackgroundJob.locked_at != None, models.BackgroundJob.locked_at < cutoff)  # noqa: E711
        .update(
            {
                "status": "queued",
                "locked_at": None,
                "locked_by": None,
            },
            synchronize_session=False,
        )
    )
    if count:
        db.commit()
        log_warning("jobs_requeued_stale", count=count)
    return int(count or 0)


def claim_next_job(db: Session, *, worker_id: str) -> models.BackgroundJob | None:
    now = _now_utc()
    query = (
        db.query(models.BackgroundJob)
        .filter(models.BackgroundJob.status == "queued", models.BackgroundJob.run_at <= now)
        .order_by(models.BackgroundJob.id.asc())
    )
    if db.bind and db.bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    job = query.first()
    if not job:
        return None
    job.status = "running"
    job.locked_at = now
    job.locked_by = worker_id
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def mark_job_succeeded(db: Session, job: models.BackgroundJob) -> None:
    job.status = "succeeded"
    job.finished_at = _now_utc()
    db.add(job)
    db.commit()
    log_event("job_succeeded", job_id=job.id, job_type=job.job_type, attempts=job.attempts)


def mark_job_failed(db: Session, job: models.BackgroundJob, error: str) -> None:
    job.attempts = (job.attempts or 0) + 1
    job.last_error = error
    job.locked_at = None
    job.locked_by = None
    if job.attempts < (job.max_attempts or settings.task_queue_max_attempts):
        backoff_seconds = min(60, 2 ** max(0, job.attempts - 1))
        job.status = "queued"
        job.run_at = _now_utc() + timedelta(seconds=backoff_seconds)
        db.add(job)
        db.commit()
        log_warning(
            "job_failed_retrying",
            job_id=job.id,
            job_type=job.job_type,
            attempts=job.attempts,
            max_attempts=job.max_attempts,
            backoff_seconds=backoff_seconds,
            error=error,
        )
        return

    job.status = "failed"
    job.finished_at = _now_utc()
    db.add(job)
    db.commit()
    log_warning(
        "job_failed",
        job_id=job.id,
        job_type=job.job_type,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        error=error,
    )


def process_job(db: Session, job: models.BackgroundJob) -> None:
    payload = job.payload or {}
    if job.job_type == JOB_TYPE_SEND_EMAIL:
        from .email_service import send_email_now

        send_email_now(
            to_email=payload["to_email"],
            subject=payload["subject"],
            body_text=payload["body_text"],
            body_html=payload.get("body_html"),
            context=payload.get("context") or {},
        )
        mark_job_succeeded(db, job)
        return

    mark_job_failed(db, job, error=f"Unknown job_type: {job.job_type}")


def idle_sleep() -> None:
    time.sleep(max(0.1, float(settings.task_queue_poll_interval_seconds)))

