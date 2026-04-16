#!/usr/bin/env python3
"""Command-line helper: recompute ml loading."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from recompute_ml_shared import (
    _EventFeatures,
    _coerce_utc,
    _normalize_category,
    _normalize_city,
    _normalize_tag,
)


def _decayed_norm(
    *,
    score: float,
    last_seen_at: datetime | None,
    now: datetime,
    decay_lambda: float,
    max_score: float,
) -> float:
    """Implements the decayed norm helper."""
    if max_score <= 0:
        return 0.0
    last_seen = last_seen_at or now
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    delta_seconds = (now - last_seen).total_seconds()
    if delta_seconds > 0:
        score = float(score) * math.exp(-decay_lambda * float(delta_seconds))
    score = max(0.0, min(max_score, float(score)))
    return score / max_score


def _maybe_filter_user(query, *, user_id: int | None, column):
    """Implements the maybe filter user helper."""
    if user_id is None:
        return query
    return query.filter(column == int(user_id))


def _load_students(*, db, models, user_id: int | None):
    """Loads the students resource."""
    students_query = db.query(models.User).filter(
        models.User.role == models.UserRole.student
    )
    students_query = _maybe_filter_user(
        students_query, user_id=user_id, column=models.User.id
    )
    return students_query.all()


def _load_event_features(*, db, models, func):
    """Loads the event features resource."""
    tags_by_event_id: dict[int, set[str]] = {}
    events: dict[int, _EventFeatures] = {}
    all_events = db.query(models.Event).filter(models.Event.deleted_at.is_(None)).all()

    seats_rows = (
        db.query(
            models.Registration.event_id,
            func.count(models.Registration.id).label("seats_taken"),
        )
        .filter(models.Registration.deleted_at.is_(None))
        .group_by(models.Registration.event_id)
        .all()
    )
    seats_taken_by_event = {
        int(event_id): int(seats_taken or 0) for event_id, seats_taken in seats_rows
    }

    event_tag_rows = (
        db.query(models.event_tags.c.event_id, models.Tag.name)
        .join(models.Tag, models.Tag.id == models.event_tags.c.tag_id)
        .all()
    )
    for event_id, tag_name in event_tag_rows:
        normalized = _normalize_tag(str(tag_name))
        if normalized:
            tags_by_event_id.setdefault(int(event_id), set()).add(normalized)

    for event in all_events:
        event_id = int(event.id)
        events[event_id] = _EventFeatures(
            tags=tags_by_event_id.get(event_id, set()),
            category=_normalize_category(event.category),
            city=_normalize_city(event.city),
            owner_id=int(event.owner_id),
            start_time=_coerce_utc(event.start_time),
            seats_taken=int(seats_taken_by_event.get(event_id, 0)),
            max_seats=event.max_seats,
            status=str(event.status or "published"),
            publish_at=_coerce_utc(event.publish_at),
        )

    return events


# pylint: disable-next=too-many-arguments,too-many-locals
def _load_interest_tag_weights(
    *,
    db,
    models,
    user_id: int | None,
    now: datetime,
    decay_lambda: float,
    max_score: float,
):
    """Loads the interest tag weights resource."""
    interest_tag_query = db.query(
        models.user_interest_tags.c.user_id, models.Tag.name
    ).join(models.Tag, models.Tag.id == models.user_interest_tags.c.tag_id)
    interest_tag_query = _maybe_filter_user(
        interest_tag_query, user_id=user_id, column=models.user_interest_tags.c.user_id
    )
    interest_tag_weights_by_user: dict[int, dict[str, float]] = {}
    for raw_user_id, tag_name in interest_tag_query.all():
        normalized = _normalize_tag(str(tag_name))
        if not normalized:
            continue
        interest_tag_weights_by_user.setdefault(int(raw_user_id), {})[normalized] = 1.0

    implicit_tag_query = db.query(
        models.UserImplicitInterestTag.user_id,
        models.Tag.name,
        models.UserImplicitInterestTag.score,
        models.UserImplicitInterestTag.last_seen_at,
    ).join(models.Tag, models.Tag.id == models.UserImplicitInterestTag.tag_id)
    implicit_tag_query = _maybe_filter_user(
        implicit_tag_query,
        user_id=user_id,
        column=models.UserImplicitInterestTag.user_id,
    )
    for raw_user_id, tag_name, score, last_seen_at in implicit_tag_query.all():
        normalized = _normalize_tag(str(tag_name))
        if not normalized:
            continue
        weight = _decayed_norm(
            score=float(score or 0.0),
            last_seen_at=last_seen_at,
            now=now,
            decay_lambda=decay_lambda,
            max_score=max_score,
        )
        if weight <= 0:
            continue
        bucket = interest_tag_weights_by_user.setdefault(int(raw_user_id), {})
        bucket[normalized] = max(float(bucket.get(normalized, 0.0)), float(weight))

    return interest_tag_weights_by_user


def _load_optional_implicit_weights(**kwargs) -> dict[int, dict[str, float]]:
    """Loads the optional implicit weights resource."""
    weights_by_user: dict[int, dict[str, float]] = {}
    try:
        query = kwargs["query_builder"]()
        query = _maybe_filter_user(
            query, user_id=kwargs.get("user_id"), column=kwargs["user_column"]
        )
        for raw_user_id, raw_key, score, last_seen_at in query.all():
            normalized = kwargs["normalizer"](str(raw_key))
            if not normalized:
                continue
            weight = _decayed_norm(
                score=float(score or 0.0),
                last_seen_at=last_seen_at,
                now=kwargs["now"],
                decay_lambda=float(kwargs["decay_lambda"]),
                max_score=float(kwargs["max_score"]),
            )
            if weight <= 0:
                continue
            bucket = weights_by_user.setdefault(int(raw_user_id), {})
            bucket[normalized] = max(float(bucket.get(normalized, 0.0)), float(weight))
    except Exception as exc:  # noqa: BLE001
        warning_label = kwargs["warning_label"]
        continuation_label = kwargs["continuation_label"]
        print(
            f"[warn] could not load {warning_label} ({exc}); "
            f"continuing without {continuation_label}"
        )
    return weights_by_user


def _load_registration_and_favorite_rows(*, db, models, user_id: int | None):
    """Loads the registration and favorite rows resource."""
    reg_query = db.query(
        models.Registration.user_id,
        models.Registration.event_id,
        models.Registration.attended,
    ).filter(models.Registration.deleted_at.is_(None))
    reg_query = _maybe_filter_user(
        reg_query, user_id=user_id, column=models.Registration.user_id
    )
    fav_query = db.query(models.FavoriteEvent.user_id, models.FavoriteEvent.event_id)
    fav_query = _maybe_filter_user(
        fav_query, user_id=user_id, column=models.FavoriteEvent.user_id
    )
    return reg_query.all(), fav_query.all()


def _build_registered_event_ids_by_user(registration_rows) -> dict[int, set[int]]:
    """Constructs a registered event ids by user structure."""
    registered_event_ids_by_user: dict[int, set[int]] = {}
    for raw_user_id, event_id, _attended in registration_rows:
        registered_event_ids_by_user.setdefault(int(raw_user_id), set()).add(
            int(event_id)
        )
    return registered_event_ids_by_user


def _build_positive_weights(
    registration_rows, favorite_rows
) -> dict[tuple[int, int], float]:
    """Constructs a positive weights structure."""
    positive_weights: dict[tuple[int, int], float] = {}
    for raw_user_id, event_id, attended in registration_rows:
        weight = 1.0 + (0.5 if attended else 0.0)
        key = (int(raw_user_id), int(event_id))
        positive_weights[key] = max(positive_weights.get(key, 0.0), weight)
    for raw_user_id, event_id in favorite_rows:
        key = (int(raw_user_id), int(event_id))
        positive_weights[key] = max(positive_weights.get(key, 0.0), 1.2)
    return positive_weights
