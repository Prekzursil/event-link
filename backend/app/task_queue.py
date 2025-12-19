from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .logging_utils import log_event, log_warning


JOB_TYPE_SEND_EMAIL = "send_email"
JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML = "recompute_recommendations_ml"
JOB_TYPE_REFRESH_USER_RECOMMENDATIONS_ML = "refresh_user_recommendations_ml"
JOB_TYPE_EVALUATE_PERSONALIZATION_GUARDRAILS = "evaluate_personalization_guardrails"
JOB_TYPE_SEND_WEEKLY_DIGEST = "send_weekly_digest"
JOB_TYPE_SEND_FILLING_FAST_ALERTS = "send_filling_fast_alerts"


def enqueue_job(
    db: Session,
    job_type: str,
    payload: dict[str, Any],
    *,
    dedupe_key: str | None = None,
    run_at: datetime | None = None,
    max_attempts: int | None = None,
) -> models.BackgroundJob:
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
    job.dedupe_key = None
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
    # backend/app/task_queue.py -> backend/
    return Path(__file__).resolve().parents[1]


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}
    return bool(value)


def _load_personalization_exclusions(*, db: Session, user_id: int) -> tuple[set[int], set[int]]:
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


def _apply_personalization_exclusions(query, *, hidden_tag_ids: set[int], blocked_organizer_ids: set[int]):  # noqa: ANN001
    if blocked_organizer_ids:
        query = query.filter(~models.Event.owner_id.in_(sorted(blocked_organizer_ids)))
    if hidden_tag_ids:
        query = query.filter(~models.Event.tags.any(models.Tag.id.in_(sorted(hidden_tag_ids))))
    return query


def _run_recompute_recommendations_ml(*, payload: dict[str, Any]) -> None:
    backend_root = _backend_root()
    script_path = backend_root / "scripts" / "recompute_recommendations_ml.py"
    if not script_path.exists():
        raise RuntimeError(f"Missing trainer script at {script_path}")

    cmd = [sys.executable, str(script_path)]
    if payload.get("top_n") is not None:
        cmd.extend(["--top-n", str(int(payload["top_n"]))])
    if payload.get("user_id") is not None:
        cmd.extend(["--user-id", str(int(payload["user_id"]))])
    if payload.get("skip_training"):
        cmd.append("--skip-training")
    if payload.get("epochs") is not None:
        cmd.extend(["--epochs", str(int(payload["epochs"]))])
    if payload.get("lr") is not None:
        cmd.extend(["--lr", str(float(payload["lr"]))])
    if payload.get("l2") is not None:
        cmd.extend(["--l2", str(float(payload["l2"]))])
    if payload.get("seed") is not None:
        cmd.extend(["--seed", str(int(payload["seed"]))])

    env = os.environ.copy()
    if payload.get("model_version"):
        env["RECOMMENDER_MODEL_VERSION"] = str(payload["model_version"])

    proc = subprocess.run(
        cmd,
        cwd=str(backend_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=int(payload.get("timeout_seconds") or 60 * 30),
        check=False,
    )
    if proc.returncode != 0:
        combined = "\n".join([proc.stdout.strip(), proc.stderr.strip()]).strip()
        raise RuntimeError(f"trainer_failed exit_code={proc.returncode} output={combined[-4000:]}")


def _send_weekly_digest(*, db: Session, payload: dict[str, Any]) -> dict[str, int]:
    from .email_templates import render_weekly_digest_email  # noqa: PLC0415

    now = datetime.now(timezone.utc)
    iso = now.isocalendar()
    week_key = f"{iso.year}-W{iso.week:02d}"

    top_n = int(payload.get("top_n") or 8)
    total_users = 0
    enqueued_emails = 0

    users = db.query(models.User).filter(models.User.role == models.UserRole.student).all()
    for user in users:
        if not _coerce_bool(getattr(user, "is_active", True)):
            continue
        if not _coerce_bool(getattr(user, "email_digest_enabled", False)):
            continue
        total_users += 1
        dedupe_key = f"digest:{user.id}:{week_key}"
        already_sent = (
            db.query(models.NotificationDelivery.id)
            .filter(models.NotificationDelivery.dedupe_key == dedupe_key)
            .first()
            is not None
        )
        if already_sent:
            continue

        hidden_tag_ids, blocked_organizer_ids = _load_personalization_exclusions(db=db, user_id=int(user.id))
        rec = models.UserRecommendation
        query = (
            db.query(models.Event)
            .join(rec, (rec.event_id == models.Event.id) & (rec.user_id == user.id))
            .filter(rec.user_id == user.id)
            .filter(models.Event.deleted_at.is_(None))
            .filter(models.Event.start_time >= now)
            .filter(models.Event.status == "published")
            .filter((models.Event.publish_at == None) | (models.Event.publish_at <= now))  # noqa: E711
        )
        query = _apply_personalization_exclusions(
            query,
            hidden_tag_ids=hidden_tag_ids,
            blocked_organizer_ids=blocked_organizer_ids,
        )
        query = query.order_by(rec.rank.asc()).limit(max(1, top_n))
        events = query.all()
        if not events:
            continue

        lang = user.language_preference
        if not lang or lang == "system":
            lang = "ro"
        subject, body_text, body_html = render_weekly_digest_email(user, events, lang=lang)

        db.add(
            models.NotificationDelivery(
                dedupe_key=dedupe_key,
                notification_type="weekly_digest",
                user_id=int(user.id),
                event_id=None,
                meta={"week": week_key, "count": len(events)},
            )
        )

        enqueue_job(
            db,
            JOB_TYPE_SEND_EMAIL,
            {
                "to_email": user.email,
                "subject": subject,
                "body_text": body_text,
                "body_html": body_html,
                "context": {"notification": "weekly_digest", "user_id": int(user.id), "week": week_key},
            },
        )
        enqueued_emails += 1

    return {"users": total_users, "emails": enqueued_emails}


def _send_filling_fast_alerts(*, db: Session, payload: dict[str, Any]) -> dict[str, int]:
    from sqlalchemy import func  # noqa: PLC0415

    from .email_templates import render_filling_fast_email  # noqa: PLC0415

    now = datetime.now(timezone.utc)
    threshold_abs = int(payload.get("threshold_abs") or 5)
    threshold_ratio = float(payload.get("threshold_ratio") or 0.2)
    max_per_user = int(payload.get("max_per_user") or 3)

    seats_subquery = (
        db.query(models.Registration.event_id, func.count(models.Registration.id).label("seats_taken"))
        .filter(models.Registration.deleted_at.is_(None))
        .group_by(models.Registration.event_id)
        .subquery()
    )

    rows = (
        db.query(
            models.User,
            models.Event,
            func.coalesce(seats_subquery.c.seats_taken, 0).label("seats_taken"),
        )
        .select_from(models.FavoriteEvent)
        .join(models.User, models.User.id == models.FavoriteEvent.user_id)
        .join(models.Event, models.Event.id == models.FavoriteEvent.event_id)
        .outerjoin(seats_subquery, models.Event.id == seats_subquery.c.event_id)
        .filter(
            models.User.role == models.UserRole.student,
            models.Event.deleted_at.is_(None),
            models.Event.start_time >= now,
            models.Event.status == "published",
            (models.Event.publish_at == None) | (models.Event.publish_at <= now),  # noqa: E711
            models.Event.max_seats.isnot(None),
        )
        .order_by(models.User.id.asc(), models.Event.start_time.asc())
        .all()
    )

    total_pairs = 0
    enqueued_emails = 0
    sent_by_user: dict[int, int] = {}
    for user, event, seats_taken in rows:
        if not _coerce_bool(getattr(user, "is_active", True)):
            continue
        if not _coerce_bool(getattr(user, "email_filling_fast_enabled", False)):
            continue
        user_id = int(user.id)
        event_id = int(event.id)
        total_pairs += 1

        if sent_by_user.get(user_id, 0) >= max_per_user:
            continue

        hidden_tag_ids, blocked_organizer_ids = _load_personalization_exclusions(db=db, user_id=user_id)
        if blocked_organizer_ids and int(event.owner_id) in blocked_organizer_ids:
            continue
        if hidden_tag_ids and any(int(tag.id) in hidden_tag_ids for tag in (event.tags or [])):
            continue

        if event.max_seats is None:
            continue
        available = int(event.max_seats) - int(seats_taken or 0)
        if available <= 0:
            continue
        if available > threshold_abs and (available / max(1.0, float(event.max_seats))) > threshold_ratio:
            continue

        dedupe_key = f"filling_fast:{user_id}:{event_id}"
        already_sent = (
            db.query(models.NotificationDelivery.id)
            .filter(models.NotificationDelivery.dedupe_key == dedupe_key)
            .first()
            is not None
        )
        if already_sent:
            continue

        lang = user.language_preference
        if not lang or lang == "system":
            lang = "ro"
        subject, body_text, body_html = render_filling_fast_email(
            user,
            event,
            available_seats=available,
            lang=lang,
        )

        db.add(
            models.NotificationDelivery(
                dedupe_key=dedupe_key,
                notification_type="filling_fast",
                user_id=user_id,
                event_id=event_id,
                meta={"available_seats": available, "max_seats": int(event.max_seats)},
            )
        )
        enqueue_job(
            db,
            JOB_TYPE_SEND_EMAIL,
            {
                "to_email": user.email,
                "subject": subject,
                "body_text": body_text,
                "body_html": body_html,
                "context": {"notification": "filling_fast", "user_id": user_id, "event_id": event_id},
            },
        )
        enqueued_emails += 1
        sent_by_user[user_id] = sent_by_user.get(user_id, 0) + 1

    return {"pairs": total_pairs, "emails": enqueued_emails}


def _evaluate_personalization_guardrails(*, db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    if not settings.personalization_guardrails_enabled:
        return {"enabled": False}

    days = int(payload.get("days") or settings.personalization_guardrails_days)
    if days < 1 or days > 365:
        days = int(settings.personalization_guardrails_days)

    min_impressions = int(payload.get("min_impressions") or settings.personalization_guardrails_min_impressions)
    ctr_drop_ratio = float(payload.get("ctr_drop_ratio") or settings.personalization_guardrails_ctr_drop_ratio)
    conversion_drop_ratio = float(
        payload.get("conversion_drop_ratio") or settings.personalization_guardrails_conversion_drop_ratio
    )
    click_to_register_hours = int(
        payload.get("click_to_register_window_hours") or settings.personalization_guardrails_click_to_register_window_hours
    )
    click_to_register_window = timedelta(hours=max(1, click_to_register_hours))

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    def _meta_value(meta: object, key: str) -> str | None:
        if isinstance(meta, dict):
            value = meta.get(key)
            if value is None:
                return None
            return str(value)
        return None

    impressions: dict[str, int] = {"recommended": 0, "time": 0}
    clicks: dict[str, int] = {"recommended": 0, "time": 0}
    conversions: dict[str, int] = {"recommended": 0, "time": 0}

    click_by_user_event: dict[tuple[int, int], tuple[str, datetime]] = {}

    impression_rows = (
        db.query(
            models.EventInteraction.user_id,
            models.EventInteraction.event_id,
            models.EventInteraction.occurred_at,
            models.EventInteraction.meta,
        )
        .filter(models.EventInteraction.occurred_at >= start)
        .filter(models.EventInteraction.user_id.isnot(None))
        .filter(models.EventInteraction.event_id.isnot(None))
        .filter(models.EventInteraction.interaction_type == "impression")
        .all()
    )
    for user_id, event_id, occurred_at, meta in impression_rows:
        source = (_meta_value(meta, "source") or "").strip().lower()
        sort = (_meta_value(meta, "sort") or "").strip().lower()
        if source != "events_list":
            continue
        if sort not in impressions:
            continue
        impressions[sort] += 1

    click_rows = (
        db.query(
            models.EventInteraction.user_id,
            models.EventInteraction.event_id,
            models.EventInteraction.occurred_at,
            models.EventInteraction.meta,
        )
        .filter(models.EventInteraction.occurred_at >= start)
        .filter(models.EventInteraction.user_id.isnot(None))
        .filter(models.EventInteraction.event_id.isnot(None))
        .filter(models.EventInteraction.interaction_type == "click")
        .all()
    )
    for user_id, event_id, occurred_at, meta in click_rows:
        source = (_meta_value(meta, "source") or "").strip().lower()
        sort = (_meta_value(meta, "sort") or "").strip().lower()
        if source != "events_list":
            continue
        if sort not in clicks:
            continue
        clicks[sort] += 1
        key = (int(user_id), int(event_id))
        prev = click_by_user_event.get(key)
        if prev is None or occurred_at > prev[1]:
            click_by_user_event[key] = (sort, occurred_at)

    register_rows = (
        db.query(
            models.EventInteraction.user_id,
            models.EventInteraction.event_id,
            models.EventInteraction.occurred_at,
        )
        .filter(models.EventInteraction.occurred_at >= start)
        .filter(models.EventInteraction.user_id.isnot(None))
        .filter(models.EventInteraction.event_id.isnot(None))
        .filter(models.EventInteraction.interaction_type == "register")
        .all()
    )
    for user_id, event_id, occurred_at in register_rows:
        key = (int(user_id), int(event_id))
        click = click_by_user_event.get(key)
        if not click:
            continue
        sort, click_time = click
        if occurred_at < click_time or occurred_at > (click_time + click_to_register_window):
            continue
        if sort in conversions:
            conversions[sort] += 1

    def _safe_ratio(num: int, den: int) -> float:
        return float(num) / float(den) if den else 0.0

    ctr = {key: _safe_ratio(clicks[key], impressions[key]) for key in impressions}
    conversion = {key: _safe_ratio(conversions[key], clicks[key]) for key in clicks}

    result: dict[str, Any] = {
        "enabled": True,
        "days": days,
        "impressions": impressions,
        "clicks": clicks,
        "conversions": conversions,
        "ctr": ctr,
        "conversion": conversion,
    }

    if impressions["recommended"] < min_impressions or impressions["time"] < min_impressions:
        log_event("personalization_guardrails_skip_low_volume", **result)
        result["action"] = "skip_low_volume"
        return result

    recommended_ctr = ctr["recommended"]
    time_ctr = ctr["time"]
    recommended_conv = conversion["recommended"]
    time_conv = conversion["time"]

    ctr_ok = True if time_ctr == 0 else (recommended_ctr >= time_ctr * (1.0 - ctr_drop_ratio))
    conv_ok = True if time_conv == 0 else (recommended_conv >= time_conv * (1.0 - conversion_drop_ratio))
    result["ctr_ok"] = ctr_ok
    result["conversion_ok"] = conv_ok

    if ctr_ok and conv_ok:
        log_event("personalization_guardrails_ok", **result)
        result["action"] = "ok"
        return result

    active = (
        db.query(models.RecommenderModel)
        .filter(models.RecommenderModel.is_active.is_(True))
        .order_by(models.RecommenderModel.id.desc())
        .first()
    )
    if not active:
        log_warning("personalization_guardrails_no_active_model", **result)
        result["action"] = "no_active_model"
        return result

    previous = (
        db.query(models.RecommenderModel)
        .filter(models.RecommenderModel.id < active.id)
        .order_by(models.RecommenderModel.id.desc())
        .first()
    )
    if not previous:
        log_warning("personalization_guardrails_no_previous_model", active_model_version=active.model_version, **result)
        result["action"] = "no_previous_model"
        return result

    active.is_active = False
    previous.is_active = True
    db.add_all([active, previous])
    db.commit()
    log_warning(
        "personalization_guardrails_rollback",
        from_model_version=active.model_version,
        to_model_version=previous.model_version,
        **result,
    )

    enqueue_job(
        db,
        JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML,
        {"top_n": int(settings.recommendations_realtime_refresh_top_n), "skip_training": True},
        dedupe_key="global",
    )
    result["action"] = "rollback"
    result["rolled_back_from"] = str(active.model_version)
    result["rolled_back_to"] = str(previous.model_version)
    return result


def process_job(db: Session, job: models.BackgroundJob) -> None:
    payload = job.payload or {}
    try:
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

        if job.job_type == JOB_TYPE_RECOMPUTE_RECOMMENDATIONS_ML:
            _run_recompute_recommendations_ml(payload=payload)
            mark_job_succeeded(db, job)
            return

        if job.job_type == JOB_TYPE_REFRESH_USER_RECOMMENDATIONS_ML:
            _run_recompute_recommendations_ml(payload=payload)
            mark_job_succeeded(db, job)
            return

        if job.job_type == JOB_TYPE_SEND_WEEKLY_DIGEST:
            result = _send_weekly_digest(db=db, payload=payload)
            log_event("weekly_digest_enqueued", **result)
            mark_job_succeeded(db, job)
            return

        if job.job_type == JOB_TYPE_SEND_FILLING_FAST_ALERTS:
            result = _send_filling_fast_alerts(db=db, payload=payload)
            log_event("filling_fast_alerts_enqueued", **result)
            mark_job_succeeded(db, job)
            return

        if job.job_type == JOB_TYPE_EVALUATE_PERSONALIZATION_GUARDRAILS:
            result = _evaluate_personalization_guardrails(db=db, payload=payload)
            log_event("personalization_guardrails_evaluated", **(result or {}))
            mark_job_succeeded(db, job)
            return

        mark_job_failed(db, job, error=f"Unknown job_type: {job.job_type}")
    except Exception as exc:  # noqa: BLE001
        mark_job_failed(db, job, error=str(exc))


def idle_sleep() -> None:
    time.sleep(max(0.1, float(settings.task_queue_poll_interval_seconds)))
