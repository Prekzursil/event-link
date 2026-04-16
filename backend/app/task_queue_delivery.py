"""Support module: task queue delivery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models
from .task_queue_shared import (
    _coerce_bool,
    _notification_exists,
    _preferred_lang,
    _send_email_payload,
)

__all__ = [
    "evaluate_personalization_guardrails",
    "send_filling_fast_alerts",
    "send_weekly_digest",
]


@dataclass(frozen=True)
class FillingFastSettings:
    """Filling Fast Settings value object used in the surrounding module."""

    threshold_abs: int
    threshold_ratio: float
    max_per_user: int


def _weekly_digest_window(now: datetime) -> tuple[datetime, datetime, str]:
    """Implements the weekly digest window helper."""
    iso = now.isocalendar()
    week_key = f"{iso.year}-W{iso.week:02d}"
    weekday = now.isoweekday()
    week_start = datetime(
        now.year, now.month, now.day, tzinfo=timezone.utc
    ) - timedelta(days=weekday - 1)
    week_end = week_start + timedelta(days=7)
    return week_start, week_end, week_key


def _eligible_weekly_digest_users(db: Session) -> list[models.User]:
    """Implements the eligible weekly digest users helper."""
    return (
        db.query(models.User)
        .filter(
            models.User.role == models.UserRole.student,
            models.User.email_digest_enabled.is_(True),
        )
        .all()
    )


def _weekly_digest_events(
    *,
    db: Session,
    user_id: int,
    now: datetime,
    top_n: int,
    load_personalization_exclusions_fn: Callable[..., tuple[set[int], set[int]]],
) -> list[models.Event]:
    """Implements the weekly digest events helper."""
    query = (
        db.query(models.Event)
        .join(
            models.UserRecommendation,
            models.UserRecommendation.event_id == models.Event.id,
        )
        .filter(
            models.UserRecommendation.user_id == user_id,
            models.Event.deleted_at.is_(None),
            models.Event.start_time >= now,
            models.Event.status == "published",
            models.Event.publish_at.is_(None) | (models.Event.publish_at <= now),
        )
        .order_by(
            models.UserRecommendation.rank.asc(),
            models.Event.start_time.asc(),
            models.Event.id.asc(),
        )
    )
    hidden_tag_ids, blocked_organizer_ids = load_personalization_exclusions_fn(
        db=db, user_id=user_id
    )
    if blocked_organizer_ids:
        query = query.filter(~models.Event.owner_id.in_(sorted(blocked_organizer_ids)))
    if hidden_tag_ids:
        query = query.filter(
            ~models.Event.tags.any(models.Tag.id.in_(sorted(hidden_tag_ids)))
        )
    return query.limit(max(1, top_n)).all()


def _enqueue_weekly_digest_email(
    *,
    db: Session,
    enqueue_job_fn: Callable[..., Any],
    send_email_job_type: str,
    user: models.User,
    events: list[models.Event],
    week_key: str,
) -> None:
    """Implements the enqueue weekly digest email helper."""
    from .email_templates import render_weekly_digest_email  # noqa: PLC0415

    subject, body_text, body_html = render_weekly_digest_email(
        user,
        events,
        lang=_preferred_lang(user.language_preference),
    )
    dedupe_key = f"digest:{int(user.id)}:{week_key}"
    db.add(
        models.NotificationDelivery(
            dedupe_key=dedupe_key,
            notification_type="weekly_digest",
            user_id=int(user.id),
            event_id=None,
            meta={"week": week_key, "count": len(events)},
        )
    )
    enqueue_job_fn(
        db,
        send_email_job_type,
        _send_email_payload(
            to_email=user.email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            context={
                "notification": "weekly_digest",
                "user_id": int(user.id),
                "week": week_key,
            },
        ),
    )


def send_weekly_digest(
    *,
    db: Session,
    payload: dict[str, Any],
    enqueue_job_fn: Callable[..., Any],
    send_email_job_type: str,
    load_personalization_exclusions_fn: Callable[..., tuple[set[int], set[int]]],
) -> dict[str, int]:
    """Implements the send weekly digest helper."""
    now = datetime.now(timezone.utc)
    _week_start, _week_end, week_key = _weekly_digest_window(now)
    top_n = max(1, int(payload.get("top_n") or 5))
    total_users = 0
    enqueued_emails = 0

    for user in _eligible_weekly_digest_users(db):
        if not _coerce_bool(getattr(user, "is_active", True)):
            continue
        total_users += 1
        dedupe_key = f"digest:{int(user.id)}:{week_key}"
        if _notification_exists(db=db, dedupe_key=dedupe_key):
            continue
        events = _weekly_digest_events(
            db=db,
            user_id=int(user.id),
            now=now,
            top_n=top_n,
            load_personalization_exclusions_fn=load_personalization_exclusions_fn,
        )
        if not events:
            continue
        _enqueue_weekly_digest_email(
            db=db,
            enqueue_job_fn=enqueue_job_fn,
            send_email_job_type=send_email_job_type,
            user=user,
            events=events,
            week_key=week_key,
        )
        enqueued_emails += 1

    return {"users": total_users, "emails": enqueued_emails}


def _filling_fast_rows(
    db: Session, now: datetime
) -> list[tuple[models.User, models.Event, int]]:
    """Implements the filling fast rows helper."""
    seats_subquery = (
        db.query(
            models.Registration.event_id,
            func.count(models.Registration.id).label("seats_taken"),
        )
        .filter(models.Registration.deleted_at.is_(None))
        .group_by(models.Registration.event_id)
        .subquery()
    )
    return (
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
            models.Event.publish_at.is_(None) | (models.Event.publish_at <= now),
            models.Event.max_seats.isnot(None),
        )
        .order_by(models.User.id.asc(), models.Event.start_time.asc())
        .all()
    )


def _skip_filling_fast_user(user: models.User) -> bool:
    """Implements the skip filling fast user helper."""
    return not _coerce_bool(getattr(user, "is_active", True)) or not _coerce_bool(
        getattr(user, "email_filling_fast_enabled", False)
    )


def _passes_filling_fast_personalization(
    *,
    event: models.Event,
    hidden_tag_ids: set[int],
    blocked_organizer_ids: set[int],
) -> bool:
    """Implements the passes filling fast personalization helper."""
    if blocked_organizer_ids and int(event.owner_id) in blocked_organizer_ids:
        return False
    if hidden_tag_ids and any(
        int(tag.id) in hidden_tag_ids for tag in (event.tags or [])
    ):
        return False
    return True


def _available_seats_within_threshold(
    *,
    event: models.Event,
    seats_taken: int,
    threshold_abs: int,
    threshold_ratio: float,
) -> int | None:
    """Implements the available seats within threshold helper."""
    if event.max_seats is None:
        return None
    available = int(event.max_seats) - int(seats_taken or 0)
    if available <= 0:
        return None
    ratio = available / max(1.0, float(event.max_seats))
    if available > threshold_abs and ratio > threshold_ratio:
        return None
    return available


def _enqueue_filling_fast_email(
    *,
    db: Session,
    enqueue_job_fn: Callable[..., Any],
    send_email_job_type: str,
    user: models.User,
    event: models.Event,
    available: int,
) -> None:
    """Implements the enqueue filling fast email helper."""
    from .email_templates import render_filling_fast_email  # noqa: PLC0415

    subject, body_text, body_html = render_filling_fast_email(
        user,
        event,
        available_seats=available,
        lang=_preferred_lang(user.language_preference),
    )
    user_id = int(user.id)
    event_id = int(event.id)
    db.add(
        models.NotificationDelivery(
            dedupe_key=f"filling_fast:{user_id}:{event_id}",
            notification_type="filling_fast",
            user_id=user_id,
            event_id=event_id,
            meta={"available_seats": available, "max_seats": int(event.max_seats)},
        )
    )
    enqueue_job_fn(
        db,
        send_email_job_type,
        _send_email_payload(
            to_email=user.email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            context={
                "notification": "filling_fast",
                "user_id": user_id,
                "event_id": event_id,
            },
        ),
    )


def _filling_fast_settings(payload: dict[str, Any]) -> FillingFastSettings:
    """Implements the filling fast settings helper."""
    return FillingFastSettings(
        threshold_abs=int(payload.get("threshold_abs") or 5),
        threshold_ratio=float(payload.get("threshold_ratio") or 0.2),
        max_per_user=int(payload.get("max_per_user") or 3),
    )


def _user_reached_filling_fast_limit(
    *,
    sent_by_user: dict[int, int],
    user_id: int,
    max_per_user: int,
) -> bool:
    """Implements the user reached filling fast limit helper."""
    return sent_by_user.get(user_id, 0) >= max_per_user


def _process_filling_fast_row(
    *,
    db: Session,
    enqueue_job_fn: Callable[..., Any],
    send_email_job_type: str,
    user: models.User,
    event: models.Event,
    seats_taken: int,
    settings: FillingFastSettings,
    load_personalization_exclusions_fn: Callable[..., tuple[set[int], set[int]]],
) -> bool:
    """Implements the process filling fast row helper."""
    user_id = int(user.id)
    event_id = int(event.id)
    hidden_tag_ids, blocked_organizer_ids = load_personalization_exclusions_fn(
        db=db, user_id=user_id
    )
    if not _passes_filling_fast_personalization(
        event=event,
        hidden_tag_ids=hidden_tag_ids,
        blocked_organizer_ids=blocked_organizer_ids,
    ):
        return False
    available = _available_seats_within_threshold(
        event=event,
        seats_taken=seats_taken,
        threshold_abs=settings.threshold_abs,
        threshold_ratio=settings.threshold_ratio,
    )
    if available is None:
        return False
    if _notification_exists(db=db, dedupe_key=f"filling_fast:{user_id}:{event_id}"):
        return False
    _enqueue_filling_fast_email(
        db=db,
        enqueue_job_fn=enqueue_job_fn,
        send_email_job_type=send_email_job_type,
        user=user,
        event=event,
        available=available,
    )
    return True


def send_filling_fast_alerts(
    *,
    db: Session,
    payload: dict[str, Any],
    enqueue_job_fn: Callable[..., Any],
    send_email_job_type: str,
    load_personalization_exclusions_fn: Callable[..., tuple[set[int], set[int]]],
) -> dict[str, int]:
    """Implements the send filling fast alerts helper."""
    now = datetime.now(timezone.utc)
    settings = _filling_fast_settings(payload)
    total_pairs = 0
    enqueued_emails = 0
    sent_by_user: dict[int, int] = {}

    for user, event, seats_taken in _filling_fast_rows(db, now):
        if _skip_filling_fast_user(user):
            continue
        user_id = int(user.id)
        total_pairs += 1
        if _user_reached_filling_fast_limit(
            sent_by_user=sent_by_user,
            user_id=user_id,
            max_per_user=settings.max_per_user,
        ):
            continue
        if not _process_filling_fast_row(
            db=db,
            enqueue_job_fn=enqueue_job_fn,
            send_email_job_type=send_email_job_type,
            user=user,
            event=event,
            seats_taken=int(seats_taken or 0),
            settings=settings,
            load_personalization_exclusions_fn=load_personalization_exclusions_fn,
        ):
            continue
        enqueued_emails += 1
        sent_by_user[user_id] = sent_by_user.get(user_id, 0) + 1

    return {"pairs": total_pairs, "emails": enqueued_emails}
