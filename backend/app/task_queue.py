"""Support module: task queue."""

from __future__ import annotations

import contextlib
import functools
import io
import multiprocessing
import os
import queue
import runpy
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .logging_utils import log_event, log_warning
from .task_queue_delivery import (
    evaluate_personalization_guardrails as _evaluate_personalization_guardrails_impl,
    send_filling_fast_alerts as _send_filling_fast_alerts_impl,
    send_weekly_digest as _send_weekly_digest_impl,
)
from .task_queue_shared import _coerce_bool, _load_personalization_exclusions

__all__ = [
    "JOB_TYPE_EVALUATE_PERSONALIZATION_GUARDRAILS",
    "JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML",
    "JOB_TYPE_REFRESH_USER_RECOMMENDATIONS_ML",
    "JOB_TYPE_SEND_EMAIL",
    "JOB_TYPE_SEND_FILLING_FAST_ALERTS",
    "JOB_TYPE_SEND_WEEKLY_DIGEST",
    "_coerce_bool",
]


JOB_TYPE_SEND_EMAIL = "send_email"
JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML = "recompute_recommendations_ml"
JOB_TYPE_REFRESH_USER_RECOMMENDATIONS_ML = "refresh_user_recommendations_ml"
JOB_TYPE_EVALUATE_PERSONALIZATION_GUARDRAILS = "evaluate_personalization_guardrails"
JOB_TYPE_SEND_WEEKLY_DIGEST = "send_weekly_digest"
JOB_TYPE_SEND_FILLING_FAST_ALERTS = "send_filling_fast_alerts"


@dataclass
class _PythonRunResult:
    """Python Run Result value object used in the surrounding module."""

    returncode: int
    stdout: str
    stderr: str


def _run_python_entrypoint_worker(
    script_path: str,
    argv: list[str],
    cwd: str,
    env_overrides: dict[str, str],
    result_queue,
) -> None:
    """Runs the python entrypoint worker helper path."""
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    original_cwd = os.getcwd()
    original_argv = list(sys.argv)
    previous_env: dict[str, str | None] = {}
    returncode = 0
    try:
        os.chdir(cwd)
        for key, value in env_overrides.items():
            previous_env[key] = os.environ.get(key)
            os.environ[key] = value
        sys.argv = list(argv)
        with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
            runpy.run_path(script_path, run_name="__main__")
    except SystemExit as exc:  # pragma: no cover - exercised via parent result handling
        code = exc.code
        returncode = code if isinstance(code, int) else 1
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc(file=stderr_buffer)
        returncode = 1
    finally:
        sys.argv = original_argv
        os.chdir(original_cwd)
        for key, previous in previous_env.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous
        result_queue.put(
            {
                "returncode": returncode,
                "stdout": stdout_buffer.getvalue(),
                "stderr": stderr_buffer.getvalue(),
            }
        )


def _execute_python_script(
    *,
    script_path: Path,
    argv: list[str],
    cwd: Path,
    env_overrides: dict[str, str],
    timeout_seconds: int,
) -> _PythonRunResult:
    """Implements the execute python script helper."""
    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(
        target=_run_python_entrypoint_worker,
        args=(str(script_path), list(argv), str(cwd), dict(env_overrides), result_queue),
    )
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join()
        return _PythonRunResult(
            returncode=124,
            stdout="",
            stderr=f"trainer timed out after {timeout_seconds} seconds",
        )
    try:
        payload = result_queue.get(timeout=1)
    except queue.Empty:
        payload = {
            "returncode": process.exitcode or 1,
            "stdout": "",
            "stderr": "trainer process exited without emitting a result",
        }
    return _PythonRunResult(**payload)


def enqueue_job(
    db: Session,
    job_type: str,
    payload: dict[str, Any],
    *,
    dedupe_key: str | None = None,
    run_at: datetime | None = None,
    max_attempts: int | None = None,
) -> models.BackgroundJob:
    """Implements the enqueue job helper."""
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
        existing = (
            db.query(models.BackgroundJob)
            .filter(
                models.BackgroundJob.job_type == job_type,
                models.BackgroundJob.dedupe_key == dedupe_key,
                models.BackgroundJob.status.in_(["queued", "running"]),
            )
            .order_by(models.BackgroundJob.id.desc())
            .first()
        )
        if existing is None:
            raise
        setattr(existing, "_deduped", True)
        return existing
    db.refresh(job)
    log_event("job_enqueued", job_id=job.id, job_type=job.job_type)
    return job


def _now_utc() -> datetime:
    """Implements the now utc helper."""
    return datetime.now(timezone.utc)


def requeue_stale_jobs(db: Session, *, stale_after_seconds: int | None = None) -> int:
    """Implements the requeue stale jobs helper."""
    stale_after_seconds = stale_after_seconds or settings.task_queue_stale_after_seconds
    cutoff = _now_utc() - timedelta(seconds=stale_after_seconds)
    count = (
        db.query(models.BackgroundJob)
        .filter(
            models.BackgroundJob.status == "running",
            models.BackgroundJob.locked_at != None,
            models.BackgroundJob.locked_at < cutoff,
        )  # noqa: E711
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
    """Implements the claim next job helper."""
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
    """Implements the mark job succeeded helper."""
    job.status = "succeeded"
    job.finished_at = _now_utc()
    job.dedupe_key = None
    db.add(job)
    db.commit()
    log_event("job_succeeded", job_id=job.id, job_type=job.job_type, attempts=job.attempts)


def mark_job_failed(db: Session, job: models.BackgroundJob, error: str) -> None:
    """Implements the mark job failed helper."""
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
    job.dedupe_key = None
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


def _backend_root() -> Path:
    """Implements the backend root helper."""
    # backend/app/task_queue.py -> backend/
    return Path(__file__).resolve().parents[1]


def _apply_personalization_exclusions(
    query, *, hidden_tag_ids: set[int], blocked_organizer_ids: set[int]
):  # noqa: ANN001
    """Applies personalization exclusions to the target."""
    if blocked_organizer_ids:
        query = query.filter(~models.Event.owner_id.in_(sorted(blocked_organizer_ids)))
    if hidden_tag_ids:
        query = query.filter(~models.Event.tags.any(models.Tag.id.in_(sorted(hidden_tag_ids))))
    return query


def _run_recompute_recommendations_ml(*, payload: dict[str, Any]) -> None:
    """Runs the recompute recommendations ml helper path."""
    backend_root = _backend_root()
    script_path = backend_root / "scripts" / "recompute_recommendations_ml.py"
    if not script_path.exists():
        raise RuntimeError(f"Missing trainer script at {script_path}")

    proc = _execute_python_script(
        script_path=script_path,
        argv=_trainer_argv(script_path=script_path, payload=payload),
        cwd=backend_root,
        env_overrides=_trainer_env_overrides(payload),
        timeout_seconds=int(payload.get("timeout_seconds") or 60 * 30),
    )
    if proc.returncode != 0:
        combined = "\n".join([proc.stdout.strip(), proc.stderr.strip()]).strip()
        raise RuntimeError(f"trainer_failed exit_code={proc.returncode} output={combined[-4000:]}")


def _trainer_argv(*, script_path: Path, payload: dict[str, Any]) -> list[str]:
    """Implements the trainer argv helper."""
    argv = [str(script_path)]
    numeric_args = {
        "top_n": ("--top-n", int),
        "user_id": ("--user-id", int),
        "epochs": ("--epochs", int),
        "lr": ("--lr", float),
        "l2": ("--l2", float),
        "seed": ("--seed", int),
    }
    for key, (flag, caster) in numeric_args.items():
        value = payload.get(key)
        if value is not None:
            argv.extend([flag, str(caster(value))])
    if payload.get("skip_training"):
        argv.append("--skip-training")
    return argv


def _trainer_env_overrides(payload: dict[str, Any]) -> dict[str, str]:
    """Implements the trainer env overrides helper."""
    if not payload.get("model_version"):
        return {}
    return {"RECOMMENDER_MODEL_VERSION": str(payload["model_version"])}


def _send_weekly_digest(payload: dict[str, Any], *, db: Session) -> dict[str, int]:
    """Implements the send weekly digest helper."""
    return _send_weekly_digest_impl(
        db=db,
        payload=payload,
        enqueue_job_fn=enqueue_job,
        send_email_job_type=JOB_TYPE_SEND_EMAIL,
        load_personalization_exclusions_fn=_load_personalization_exclusions,
    )


def _send_filling_fast_alerts(payload: dict[str, Any], *, db: Session) -> dict[str, int]:
    """Implements the send filling fast alerts helper."""
    return _send_filling_fast_alerts_impl(
        db=db,
        payload=payload,
        enqueue_job_fn=enqueue_job,
        send_email_job_type=JOB_TYPE_SEND_EMAIL,
        load_personalization_exclusions_fn=_load_personalization_exclusions,
    )


def _evaluate_personalization_guardrails(payload: dict[str, Any], *, db: Session) -> dict[str, Any]:
    """Implements the evaluate personalization guardrails helper."""
    return _evaluate_personalization_guardrails_impl(
        db=db,
        payload=payload,
        enqueue_job_fn=enqueue_job,
        recompute_job_type=JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML,
    )


def _send_email_job(payload: dict[str, Any]) -> None:
    """Implements the send email job helper."""
    from .email_service import send_email_now  # noqa: PLC0415

    send_email_now(
        to_email=payload["to_email"],
        subject=payload["subject"],
        body_text=payload["body_text"],
        body_html=payload.get("body_html"),
        context=payload.get("context") or {},
    )


def _job_handlers(db: Session) -> dict[str, tuple[Any, str | None]]:
    """Implements the job handlers helper."""
    return {
        JOB_TYPE_SEND_EMAIL: (_send_email_job, None),
        JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML: (_run_recompute_recommendations_ml, None),
        JOB_TYPE_REFRESH_USER_RECOMMENDATIONS_ML: (_run_recompute_recommendations_ml, None),
        JOB_TYPE_SEND_WEEKLY_DIGEST: (
            functools.partial(_send_weekly_digest, db=db),
            "weekly_digest_enqueued",
        ),
        JOB_TYPE_SEND_FILLING_FAST_ALERTS: (
            functools.partial(_send_filling_fast_alerts, db=db),
            "filling_fast_alerts_enqueued",
        ),
        JOB_TYPE_EVALUATE_PERSONALIZATION_GUARDRAILS: (
            functools.partial(_evaluate_personalization_guardrails, db=db),
            "personalization_guardrails_evaluated",
        ),
    }


def process_job(db: Session, job: models.BackgroundJob) -> None:
    """Implements the process job helper."""
    payload = job.payload or {}
    handler_entry = _job_handlers(db).get(job.job_type)
    if handler_entry is None:
        mark_job_failed(db, job, error=f"Unknown job_type: {job.job_type}")
        return
    handler, success_event = handler_entry
    try:
        result = handler(payload)
        if success_event and isinstance(result, dict):
            log_event(success_event, **result)
        mark_job_succeeded(db, job)
    except Exception as exc:  # noqa: BLE001
        mark_job_failed(db, job, error=str(exc))


def idle_sleep() -> None:
    """Implements the idle sleep helper."""
    time.sleep(max(0.1, float(settings.task_queue_poll_interval_seconds)))
