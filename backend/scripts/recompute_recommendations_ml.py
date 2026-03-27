#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class _DeterministicRng:
    def __init__(self, seed: int) -> None:
        seed_value = int(seed) & ((1 << 64) - 1)
        self._state = seed_value or 0xA5A5A5A5A5A5A5A5

    def _next_u64(self) -> int:
        self._state = (6364136223846793005 * self._state + 1442695040888963407) & ((1 << 64) - 1)
        return self._state

    def randbelow(self, upper_bound: int) -> int:
        if upper_bound <= 0:
            raise ValueError("upper bound must be positive")
        return self._next_u64() % upper_bound

    def choice(self, items):
        if not items:
            raise IndexError("cannot choose from an empty sequence")
        return items[self.randbelow(len(items))]

    def shuffle(self, items) -> None:
        for index in range(len(items) - 1, 0, -1):
            swap_index = self.randbelow(index + 1)
            items[index], items[swap_index] = items[swap_index], items[index]


def _sigmoid(z: float) -> float:
    if z >= 0:
        exp_neg = math.exp(-z)
        return 1.0 / (1.0 + exp_neg)
    exp_pos = math.exp(z)
    return exp_pos / (1.0 + exp_pos)


def _dot(weights: list[float], features: list[float]) -> float:
    return sum(w * x for w, x in zip(weights, features, strict=False))


@dataclass(frozen=True)
class _EventFeatures:
    tags: set[str]
    category: str | None
    city: str | None
    owner_id: int
    start_time: datetime | None
    seats_taken: int
    max_seats: int | None
    status: str
    publish_at: datetime | None


@dataclass(frozen=True)
class _UserFeatures:
    city: str | None
    interest_tag_weights: dict[str, float]
    history_tags: set[str]
    history_categories: set[str]
    history_organizer_ids: set[int]
    category_weights: dict[str, float]
    city_weights: dict[str, float]


# Must match `_build_feature_vector` output order.
FEATURE_NAMES = [
    "bias",
    "overlap_interest_ratio",
    "overlap_history_ratio",
    "same_city",
    "category_match",
    "organizer_match",
    "popularity",
    "days_until",
]


def _normalize_tag(name: str) -> str:
    return (name or "").strip().lower()


def _normalize_city(name: str | None) -> str | None:
    if not name:
        return None
    name = name.strip()
    return name.lower() or None


def _normalize_category(name: str | None) -> str | None:
    if not name:
        return None
    name = name.strip()
    return name.lower() or None


def _coerce_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _build_feature_vector(
    *,
    user: _UserFeatures,
    event: _EventFeatures,
    now: datetime,
) -> list[float]:
    tags = event.tags
    tag_count = max(1, len(tags))

    overlap_interest = sum(float(user.interest_tag_weights.get(tag, 0.0)) for tag in tags)
    overlap_history = len(user.history_tags & tags)

    overlap_interest_ratio = overlap_interest / tag_count
    overlap_history_ratio = overlap_history / tag_count

    same_city = 0.0
    if user.city and event.city and user.city == event.city:
        same_city = 1.0
    elif event.city:
        same_city = float(user.city_weights.get(event.city, 0.0))

    category_match = 0.0
    if event.category and event.category in user.history_categories:
        category_match = 1.0
    elif event.category:
        category_match = float(user.category_weights.get(event.category, 0.0))

    organizer_match = 1.0 if event.owner_id in user.history_organizer_ids else 0.0

    popularity = min(math.log1p(event.seats_taken) / 5.0, 1.0)

    days_until = 0.0
    if event.start_time:
        delta_days = (event.start_time - now).total_seconds() / 86400.0
        days_until = max(0.0, min(delta_days / 180.0, 1.0))

    return [
        1.0,  # bias
        overlap_interest_ratio,
        overlap_history_ratio,
        same_city,
        category_match,
        organizer_match,
        popularity,
        days_until,
    ]


def _reason_for(*, user: _UserFeatures, event: _EventFeatures, lang: str) -> str:
    overlap: list[tuple[str, float]] = []
    for tag in event.tags:
        weight = float(user.interest_tag_weights.get(tag, 0.0))
        if weight > 0:
            overlap.append((tag, weight))
    overlap.sort(key=lambda item: (-item[1], item[0]))
    if overlap:
        top = ", ".join(tag for tag, _weight in overlap[:3])
        return f"Your interests: {top}" if lang == "en" else f"Interesele tale: {top}"
    if user.city and event.city and user.city == event.city:
        return "Near you" if lang == "en" else "În apropiere"
    if event.city and float(user.city_weights.get(event.city, 0.0)) >= 0.5:
        return "Near you" if lang == "en" else "În apropiere"
    return "Recommended for you" if lang == "en" else "Recomandat pentru tine"


def _train_log_regression_sgd(
    *,
    examples: list[tuple[list[float], int, float]],
    n_features: int,
    epochs: int,
    lr: float,
    l2: float,
    seed: int,
) -> list[float]:
    rng = _DeterministicRng(seed)
    weights = [0.0] * n_features
    eps = 1e-12

    for epoch in range(1, epochs + 1):
        rng.shuffle(examples)
        total_loss = 0.0
        for x, y, w in examples:
            z = _dot(weights, x)
            p = _sigmoid(z)
            total_loss += w * (-(y * math.log(p + eps) + (1 - y) * math.log(1 - p + eps)))

            err = (p - y) * w
            for i, xi in enumerate(x):
                weights[i] -= lr * (err * xi + l2 * weights[i])

        avg_loss = total_loss / max(1.0, float(len(examples)))
        print(f"[train] epoch={epoch} loss={avg_loss:.4f} examples={len(examples)}")

    return weights


def _impression_negative_weight(position: int | None) -> float:
    if position is None or position < 0:
        return 0.05
    if position <= 2:
        return 0.25
    if position <= 5:
        return 0.15
    if position <= 10:
        return 0.1
    return 0.05


def _sample_negative_event_ids(
    *,
    rng: _DeterministicRng,
    all_event_ids: list[int],
    positive_event_id: int,
    negatives_per_user: int,
) -> list[int]:
    negatives: list[int] = []
    while len(negatives) < negatives_per_user and len(negatives) < len(all_event_ids):
        candidate_event_id = rng.choice(all_event_ids)
        if candidate_event_id == positive_event_id:
            continue
        negatives.append(candidate_event_id)
    return negatives


def _score_candidate_event_ids(
    *,
    weights: list[float],
    user: _UserFeatures,
    events: dict[int, _EventFeatures],
    candidate_event_ids: list[int],
    now: datetime,
) -> list[tuple[float, int]]:
    scored: list[tuple[float, int]] = []
    for event_id in candidate_event_ids:
        event = events.get(event_id)
        if not event:
            continue
        features = _build_feature_vector(user=user, event=event, now=now)
        scored.append((_sigmoid(_dot(weights, features)), event_id))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


def _evaluate_hitrate_at_k(
    *,
    weights: list[float],
    users: dict[int, _UserFeatures],
    events: dict[int, _EventFeatures],
    positives_holdout: dict[int, int],
    all_event_ids: list[int],
    now: datetime,
    k: int,
    negatives_per_user: int,
    seed: int,
) -> float:
    rng = _DeterministicRng(seed)
    hits = 0
    total = 0

    for user_id, pos_event_id in positives_holdout.items():
        user = users.get(user_id)
        pos_event = events.get(pos_event_id)
        if not user or not pos_event:
            continue

        negatives = _sample_negative_event_ids(
            rng=rng,
            all_event_ids=all_event_ids,
            positive_event_id=pos_event_id,
            negatives_per_user=negatives_per_user,
        )
        scored = _score_candidate_event_ids(
            weights=weights,
            user=user,
            events=events,
            candidate_event_ids=[pos_event_id, *negatives],
            now=now,
        )
        top_k = {event_id for _score, event_id in scored[:k]}
        total += 1
        if pos_event_id in top_k:
            hits += 1

    return hits / max(1, total)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline ML v1: train and cache recommendations to user_recommendations.")
    parser.add_argument("--top-n", type=int, default=50, help="How many recommendations to store per user.")
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--lr", type=float, default=0.35)
    parser.add_argument("--l2", type=float, default=0.01)
    parser.add_argument("--negatives-per-positive", type=int, default=3)
    parser.add_argument("--eval-negatives", type=int, default=50)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--user-id", type=int, default=None, help="Only recompute recommendations for a single student user.")
    parser.add_argument(
        "--skip-training",
        action="store_true",
        help="Skip training and load weights from the persisted recommender_models table.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Train/eval but do not write to the DB.")
    return parser.parse_args()


def _bootstrap_script_environment() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    backend_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend_root))
    os.environ.setdefault("SECRET_KEY", "offline-ml-secret")
    os.environ.setdefault("EMAIL_ENABLED", "false")
    return repo_root


def _load_runtime_objects():
    from app import models  # noqa: PLC0415
    from app.config import settings  # noqa: PLC0415
    from app.database import SessionLocal  # noqa: PLC0415
    from sqlalchemy import func  # noqa: PLC0415

    return models, settings, SessionLocal, func


def _decayed_norm(
    *,
    score: float,
    last_seen_at: datetime | None,
    now: datetime,
    decay_lambda: float,
    max_score: float,
) -> float:
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
    if user_id is None:
        return query
    return query.filter(column == int(user_id))


def _load_students(*, db, models, user_id: int | None):
    students_query = db.query(models.User).filter(models.User.role == models.UserRole.student)
    students_query = _maybe_filter_user(students_query, user_id=user_id, column=models.User.id)
    return students_query.all()


def _load_event_features(*, db, models, func):
    tags_by_event_id: dict[int, set[str]] = {}
    events: dict[int, _EventFeatures] = {}
    all_events = db.query(models.Event).filter(models.Event.deleted_at.is_(None)).all()

    seats_rows = (
        db.query(models.Registration.event_id, func.count(models.Registration.id).label("seats_taken"))
        .filter(models.Registration.deleted_at.is_(None))
        .group_by(models.Registration.event_id)
        .all()
    )
    seats_taken_by_event = {int(event_id): int(seats_taken or 0) for event_id, seats_taken in seats_rows}

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


def _load_interest_tag_weights(*, db, models, user_id: int | None, now: datetime, decay_lambda: float, max_score: float):
    interest_tag_query = (
        db.query(models.user_interest_tags.c.user_id, models.Tag.name)
        .join(models.Tag, models.Tag.id == models.user_interest_tags.c.tag_id)
    )
    interest_tag_query = _maybe_filter_user(interest_tag_query, user_id=user_id, column=models.user_interest_tags.c.user_id)
    interest_tag_weights_by_user: dict[int, dict[str, float]] = {}
    for raw_user_id, tag_name in interest_tag_query.all():
        normalized = _normalize_tag(str(tag_name))
        if not normalized:
            continue
        interest_tag_weights_by_user.setdefault(int(raw_user_id), {})[normalized] = 1.0

    implicit_tag_query = (
        db.query(
            models.UserImplicitInterestTag.user_id,
            models.Tag.name,
            models.UserImplicitInterestTag.score,
            models.UserImplicitInterestTag.last_seen_at,
        )
        .join(models.Tag, models.Tag.id == models.UserImplicitInterestTag.tag_id)
    )
    implicit_tag_query = _maybe_filter_user(implicit_tag_query, user_id=user_id, column=models.UserImplicitInterestTag.user_id)
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


def _load_optional_implicit_weights(
    *,
    db,
    query_builder,
    user_id: int | None,
    user_column,
    normalizer,
    now: datetime,
    decay_lambda: float,
    max_score: float,
    warning_label: str,
    continuation_label: str,
) -> dict[int, dict[str, float]]:
    weights_by_user: dict[int, dict[str, float]] = {}
    try:
        query = query_builder()
        query = _maybe_filter_user(query, user_id=user_id, column=user_column)
        for raw_user_id, raw_key, score, last_seen_at in query.all():
            normalized = normalizer(str(raw_key))
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
            bucket = weights_by_user.setdefault(int(raw_user_id), {})
            bucket[normalized] = max(float(bucket.get(normalized, 0.0)), float(weight))
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] could not load {warning_label} ({exc}); continuing without {continuation_label}")
    return weights_by_user


def _load_registration_and_favorite_rows(*, db, models, user_id: int | None):
    reg_query = (
        db.query(models.Registration.user_id, models.Registration.event_id, models.Registration.attended)
        .filter(models.Registration.deleted_at.is_(None))
    )
    reg_query = _maybe_filter_user(reg_query, user_id=user_id, column=models.Registration.user_id)
    fav_query = db.query(models.FavoriteEvent.user_id, models.FavoriteEvent.event_id)
    fav_query = _maybe_filter_user(fav_query, user_id=user_id, column=models.FavoriteEvent.user_id)
    return reg_query.all(), fav_query.all()


def _build_registered_event_ids_by_user(registration_rows) -> dict[int, set[int]]:
    registered_event_ids_by_user: dict[int, set[int]] = {}
    for raw_user_id, event_id, _attended in registration_rows:
        registered_event_ids_by_user.setdefault(int(raw_user_id), set()).add(int(event_id))
    return registered_event_ids_by_user


def _build_positive_weights(registration_rows, favorite_rows) -> dict[tuple[int, int], float]:
    positive_weights: dict[tuple[int, int], float] = {}
    for raw_user_id, event_id, attended in registration_rows:
        weight = 1.0 + (0.5 if attended else 0.0)
        key = (int(raw_user_id), int(event_id))
        positive_weights[key] = max(positive_weights.get(key, 0.0), weight)
    for raw_user_id, event_id in favorite_rows:
        key = (int(raw_user_id), int(event_id))
        positive_weights[key] = max(positive_weights.get(key, 0.0), 1.2)
    return positive_weights


def _apply_search_filter_preferences(*, search_filter_rows, implicit_interest_tags_by_user, implicit_categories_by_user, implicit_city_by_user):
    for raw_user_id, _interaction_type, meta in search_filter_rows:
        user_id = int(raw_user_id)
        if not isinstance(meta, dict):
            continue
        tags_value = meta.get("tags")
        if isinstance(tags_value, list):
            for tag in tags_value:
                normalized = _normalize_tag(str(tag))
                if normalized:
                    implicit_interest_tags_by_user.setdefault(user_id, set()).add(normalized)

        category_value = meta.get("category")
        if isinstance(category_value, str) and category_value.strip():
            implicit_categories_by_user.setdefault(user_id, set()).add(_normalize_category(category_value))

        city_value = meta.get("city")
        if isinstance(city_value, str):
            normalized_city = _normalize_city(city_value)
            if normalized_city:
                implicit_city_by_user[user_id] = normalized_city


def _apply_event_interaction_feedback(
    *,
    interaction_rows,
    seen_by_user,
    impression_position_by_user_event,
    positive_weights,
    negative_weights,
) -> None:
    for raw_user_id, raw_event_id, interaction_type, meta in interaction_rows:
        user_id = int(raw_user_id)
        event_id = int(raw_event_id)
        normalized_type = str(interaction_type or "").strip().lower()
        if normalized_type == "impression":
            seen_by_user.setdefault(user_id, set()).add(event_id)
            position = None
            if isinstance(meta, dict):
                position_value = meta.get("position")
                if isinstance(position_value, (int, float)):
                    position = int(position_value)
            if position is not None:
                key = (user_id, event_id)
                existing = impression_position_by_user_event.get(key)
                if existing is None or position < existing:
                    impression_position_by_user_event[key] = position
            continue
        if normalized_type == "unregister":
            key = (user_id, event_id)
            negative_weights[key] = max(negative_weights.get(key, 0.0), 2.0)
            continue
        if normalized_type == "dwell":
            weight = 0.35
            if isinstance(meta, dict):
                seconds = meta.get("seconds")
                if isinstance(seconds, (int, float)) and seconds > 0:
                    weight = min(0.8, weight + (float(seconds) / 120.0) * 0.25)
        else:
            weight = {
                "click": 0.4,
                "view": 0.25,
                "share": 0.6,
                "favorite": 1.2,
                "register": 1.0,
            }[normalized_type]

        key = (user_id, event_id)
        positive_weights[key] = max(positive_weights.get(key, 0.0), weight)


def _load_interaction_signals(
    *,
    db,
    models,
    user_id: int | None,
    positive_weights,
) -> tuple[dict[tuple[int, int], float], dict[int, set[int]], dict[tuple[int, int], int], dict[int, set[str]], dict[int, set[str]], dict[int, str]]:
    negative_weights: dict[tuple[int, int], float] = {}
    seen_by_user: dict[int, set[int]] = {}
    impression_position_by_user_event: dict[tuple[int, int], int] = {}
    implicit_interest_tags_by_user: dict[int, set[str]] = {}
    implicit_categories_by_user: dict[int, set[str]] = {}
    implicit_city_by_user: dict[int, str] = {}

    try:
        search_filter_query = (
            db.query(
                models.EventInteraction.user_id,
                models.EventInteraction.interaction_type,
                models.EventInteraction.meta,
            )
            .filter(models.EventInteraction.user_id.isnot(None))
            .filter(models.EventInteraction.event_id.is_(None))
            .filter(models.EventInteraction.interaction_type.in_(["search", "filter"]))
        )
        search_filter_query = _maybe_filter_user(search_filter_query, user_id=user_id, column=models.EventInteraction.user_id)
        _apply_search_filter_preferences(
            search_filter_rows=search_filter_query.all(),
            implicit_interest_tags_by_user=implicit_interest_tags_by_user,
            implicit_categories_by_user=implicit_categories_by_user,
            implicit_city_by_user=implicit_city_by_user,
        )

        interaction_query = (
            db.query(
                models.EventInteraction.user_id,
                models.EventInteraction.event_id,
                models.EventInteraction.interaction_type,
                models.EventInteraction.meta,
            )
            .filter(models.EventInteraction.user_id.isnot(None))
            .filter(models.EventInteraction.event_id.isnot(None))
            .filter(
                models.EventInteraction.interaction_type.in_(
                    ["impression", "click", "view", "dwell", "share", "favorite", "register", "unregister"]
                )
            )
        )
        interaction_query = _maybe_filter_user(interaction_query, user_id=user_id, column=models.EventInteraction.user_id)
        _apply_event_interaction_feedback(
            interaction_rows=interaction_query.all(),
            seen_by_user=seen_by_user,
            impression_position_by_user_event=impression_position_by_user_event,
            positive_weights=positive_weights,
            negative_weights=negative_weights,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] could not load event_interactions ({exc}); continuing without interaction signals")

    return (
        negative_weights,
        seen_by_user,
        impression_position_by_user_event,
        implicit_interest_tags_by_user,
        implicit_categories_by_user,
        implicit_city_by_user,
    )


def _build_users_and_holdout(
    *,
    students,
    args,
    events,
    positives_by_user,
    implicit_categories_by_user,
    implicit_city_by_user,
    category_weights_by_user,
    city_weights_by_user,
    interest_tag_weights_by_user,
) -> tuple[dict[int, _UserFeatures], dict[int, str], dict[int, int]]:
    users: dict[int, _UserFeatures] = {}
    user_lang: dict[int, str] = {}
    holdout: dict[int, int] = {}
    rng = _DeterministicRng(args.seed)

    for student in students:
        user_id = int(student.id)
        city = _normalize_city(student.city) or implicit_city_by_user.get(user_id)
        if not city:
            city_preferences = city_weights_by_user.get(user_id, {})
            if city_preferences:
                city = max(city_preferences.items(), key=lambda item: item[1])[0]
        user_lang[user_id] = "en" if (student.language_preference or "system").strip().lower() == "en" else "ro"

        positive_event_ids = list(positives_by_user.get(user_id, {}).keys())
        if len(positive_event_ids) >= 2:
            holdout_event = rng.choice(positive_event_ids)
            holdout[user_id] = holdout_event
            positives_by_user[user_id].pop(holdout_event, None)

        history_tags: set[str] = set()
        history_categories: set[str] = set()
        history_organizers: set[int] = set()
        for event_id in positive_event_ids:
            event = events.get(event_id)
            if not event:
                continue
            history_tags |= event.tags
            if event.category:
                history_categories.add(event.category)
            history_organizers.add(event.owner_id)

        history_categories |= implicit_categories_by_user.get(user_id, set())
        users[user_id] = _UserFeatures(
            city=city,
            interest_tag_weights=interest_tag_weights_by_user.get(user_id, {}),
            history_tags=history_tags,
            history_categories=history_categories,
            history_organizer_ids=history_organizers,
            category_weights=category_weights_by_user.get(user_id, {}),
            city_weights=city_weights_by_user.get(user_id, {}),
        )

    return users, user_lang, holdout


def _load_persisted_model_state(*, db, models, requested_model_version: str | None) -> tuple[str | None, list[float] | None, int | None]:
    model_query = db.query(models.RecommenderModel)
    model_row = None
    if requested_model_version:
        model_row = model_query.filter(models.RecommenderModel.model_version == requested_model_version).first()
    if model_row is None:
        model_row = (
            model_query.filter(getattr(models.RecommenderModel, "is_active").is_(True))
            .order_by(models.RecommenderModel.id.desc())
            .first()
        )
    if model_row is None:
        model_row = model_query.order_by(models.RecommenderModel.id.desc()).first()

    if model_row is None:
        print("[warn] no persisted recommender model found; run the retraining job first")
        return None, None, 0

    feature_names = list(model_row.feature_names or [])
    weights = [float(weight) for weight in (model_row.weights or [])]
    if feature_names != FEATURE_NAMES:
        print(f"[error] persisted model feature_names mismatch: expected={FEATURE_NAMES} got={feature_names}")
        return None, None, 2
    if len(weights) != len(FEATURE_NAMES):
        print(f"[error] persisted model weights length mismatch: expected={len(FEATURE_NAMES)} got={len(weights)}")
        return None, None, 2

    model_version = str(model_row.model_version)
    print(f"[load] using persisted model_version={model_version}")
    return model_version, weights, None


def _build_training_examples(
    *,
    args,
    positives_by_user,
    users,
    holdout,
    seen_by_user,
    impression_position_by_user_event,
    implicit_interest_tags_by_user,
    implicit_categories_by_user,
    implicit_city_by_user,
    negative_weights,
    events,
    all_event_ids,
    now: datetime,
) -> list[tuple[list[float], int, float]]:
    examples: list[tuple[list[float], int, float]] = []
    rng = _DeterministicRng(args.seed)

    for user_id, positives in positives_by_user.items():
        user = users.get(user_id)
        if not user:
            continue
        user_positive_ids = set(positives.keys()) | ({holdout[user_id]} if user_id in holdout else set())
        impression_candidates = [
            (event_id, impression_position_by_user_event.get((user_id, event_id), 999))
            for event_id in (seen_by_user.get(user_id, set()) - user_positive_ids)
            if event_id in events
        ]
        impression_candidates.sort(key=lambda item: item[1])
        impression_negatives = [event_id for event_id, _position in impression_candidates[:50]]

        for event_id, weight in positives.items():
            event = events.get(event_id)
            if not event:
                continue
            examples.append((_build_feature_vector(user=user, event=event, now=now), 1, float(weight)))
            neg_added = 0
            while neg_added < args.negatives_per_positive and neg_added < len(all_event_ids):
                neg_weight = 1.0
                if impression_negatives:
                    neg_event_id = rng.choice(impression_negatives)
                    neg_weight = _impression_negative_weight(impression_position_by_user_event.get((user_id, neg_event_id)))
                else:
                    neg_event_id = rng.choice(all_event_ids)
                if neg_event_id in user_positive_ids:
                    continue
                examples.append((_build_feature_vector(user=user, event=events[neg_event_id], now=now), 0, float(neg_weight)))
                neg_added += 1

        weak_tags = implicit_interest_tags_by_user.get(user_id, set())
        weak_categories = implicit_categories_by_user.get(user_id, set())
        weak_city = implicit_city_by_user.get(user_id)
        if weak_tags or weak_categories or weak_city:
            added = 0
            attempts = 0
            while added < 3 and attempts < 200 and attempts < len(all_event_ids):
                attempts += 1
                candidate_id = rng.choice(all_event_ids)
                if candidate_id in user_positive_ids:
                    continue
                candidate_event = events[candidate_id]
                matches_city = bool(weak_city and candidate_event.city and _normalize_city(candidate_event.city) == weak_city)
                matches_category = bool(candidate_event.category and candidate_event.category in weak_categories)
                matches_tags = bool(weak_tags and (candidate_event.tags & weak_tags))
                if not (matches_city or matches_category or matches_tags):
                    continue
                examples.append((_build_feature_vector(user=user, event=candidate_event, now=now), 1, 0.15))
                user_positive_ids.add(candidate_id)
                added += 1

    for (user_id, event_id), weight in negative_weights.items():
        user = users.get(user_id)
        event = events.get(event_id)
        if not user or not event:
            continue
        examples.append((_build_feature_vector(user=user, event=event, now=now), 0, float(weight)))

    return examples


def _persist_model_state(*, db, models, model_version: str, weights: list[float], meta: dict) -> None:
    existing_model = (
        db.query(models.RecommenderModel)
        .filter(models.RecommenderModel.model_version == model_version)
        .first()
    )
    if existing_model is None:
        existing_model = models.RecommenderModel(
            model_version=model_version,
            feature_names=list(FEATURE_NAMES),
            weights=[float(weight) for weight in weights],
            meta=meta,
            is_active=True,
        )
        db.add(existing_model)
    else:
        existing_model.feature_names = list(FEATURE_NAMES)
        existing_model.weights = [float(weight) for weight in weights]
        existing_model.meta = meta
        setattr(existing_model, "is_active", True)

    db.query(models.RecommenderModel).filter(models.RecommenderModel.model_version != model_version).update(
        {"is_active": False},
        synchronize_session=False,
    )


def _eligible_event_ids(events: dict[int, _EventFeatures], now: datetime) -> list[int]:
    eligible: list[int] = []
    for event_id, event in events.items():
        if event.status != "published":
            continue
        if event.publish_at and event.publish_at > now:
            continue
        if event.start_time and event.start_time < now:
            continue
        if event.max_seats is not None and event.seats_taken >= event.max_seats:
            continue
        eligible.append(event_id)
    return eligible


def _build_recommendation_rows(
    *,
    user_ids: list[int],
    users,
    user_lang,
    registered_event_ids_by_user,
    eligible_event_ids: list[int],
    events,
    weights: list[float],
    args,
    model_version: str,
    now: datetime,
    models,
):
    inserts = []
    for user_id in user_ids:
        user = users[user_id]
        registered_ids = registered_event_ids_by_user.get(user_id, set())
        scored = [
            (_sigmoid(_dot(weights, _build_feature_vector(user=user, event=events[event_id], now=now))), event_id)
            for event_id in eligible_event_ids
            if event_id not in registered_ids
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        top = scored[: max(0, int(args.top_n))]
        student_lang = user_lang.get(user_id, "ro")
        inserts.extend(
            models.UserRecommendation(
                user_id=user_id,
                event_id=event_id,
                score=float(score),
                rank=rank,
                model_version=model_version,
                reason=_reason_for(user=user, event=events[event_id], lang=student_lang),
            )
            for rank, (score, event_id) in enumerate(top, start=1)
        )
    return inserts


def main() -> int:
    args = _parse_args()
    repo_root = _bootstrap_script_environment()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("Missing DATABASE_URL. Example:\n  DATABASE_URL=postgresql://... python backend/scripts/recompute_recommendations_ml.py")
        return 2

    models, settings, SessionLocal, func = _load_runtime_objects()
    now = datetime.now(timezone.utc)
    requested_model_version = os.environ.get("RECOMMENDER_MODEL_VERSION")
    half_life_hours = max(1, int(settings.recommendations_online_learning_decay_half_life_hours))
    decay_lambda = math.log(2.0) / (float(half_life_hours) * 3600.0)
    max_score = float(settings.recommendations_online_learning_max_score)

    with SessionLocal() as db:
        students = _load_students(db=db, models=models, user_id=args.user_id)
        if not students:
            print("No student users found; nothing to do.")
            return 0

        user_ids = [int(u.id) for u in students]
        events = _load_event_features(db=db, models=models, func=func)
        all_event_ids = list(events.keys())
        if not all_event_ids:
            print("No events found; nothing to do.")
            return 0

        interest_tag_weights_by_user = _load_interest_tag_weights(
            db=db,
            models=models,
            user_id=args.user_id,
            now=now,
            decay_lambda=decay_lambda,
            max_score=max_score,
        )
        category_weights_by_user = _load_optional_implicit_weights(
            db=db,
            query_builder=lambda: db.query(
                models.UserImplicitInterestCategory.user_id,
                models.UserImplicitInterestCategory.category,
                models.UserImplicitInterestCategory.score,
                models.UserImplicitInterestCategory.last_seen_at,
            ),
            user_id=args.user_id,
            user_column=models.UserImplicitInterestCategory.user_id,
            normalizer=_normalize_category,
            now=now,
            decay_lambda=decay_lambda,
            max_score=max_score,
            warning_label="user_implicit_interest_categories",
            continuation_label="category weights",
        )
        city_weights_by_user = _load_optional_implicit_weights(
            db=db,
            query_builder=lambda: db.query(
                models.UserImplicitInterestCity.user_id,
                models.UserImplicitInterestCity.city,
                models.UserImplicitInterestCity.score,
                models.UserImplicitInterestCity.last_seen_at,
            ),
            user_id=args.user_id,
            user_column=models.UserImplicitInterestCity.user_id,
            normalizer=_normalize_city,
            now=now,
            decay_lambda=decay_lambda,
            max_score=max_score,
            warning_label="user_implicit_interest_cities",
            continuation_label="city weights",
        )
        reg_rows, fav_rows = _load_registration_and_favorite_rows(db=db, models=models, user_id=args.user_id)
        registered_event_ids_by_user = _build_registered_event_ids_by_user(reg_rows)
        positive_weights = _build_positive_weights(reg_rows, fav_rows)
        (
            negative_weights,
            seen_by_user,
            impression_position_by_user_event,
            implicit_interest_tags_by_user,
            implicit_categories_by_user,
            implicit_city_by_user,
        ) = _load_interaction_signals(
            db=db,
            models=models,
            user_id=args.user_id,
            positive_weights=positive_weights,
        )

        for key in negative_weights:
            positive_weights.pop(key, None)

        positives_by_user: dict[int, dict[int, float]] = {}
        for (user_id, event_id), weight in positive_weights.items():
            positives_by_user.setdefault(user_id, {})[event_id] = weight

        users, user_lang, holdout = _build_users_and_holdout(
            students=students,
            args=args,
            events=events,
            positives_by_user=positives_by_user,
            implicit_categories_by_user=implicit_categories_by_user,
            implicit_city_by_user=implicit_city_by_user,
            category_weights_by_user=category_weights_by_user,
            city_weights_by_user=city_weights_by_user,
            interest_tag_weights_by_user=interest_tag_weights_by_user,
        )

        model_version: str | None
        weights: list[float] | None
        if args.skip_training:
            model_version, weights, exit_code = _load_persisted_model_state(
                db=db,
                models=models,
                requested_model_version=requested_model_version,
            )
            if exit_code is not None:
                return exit_code
        else:
            model_version = requested_model_version or f"ml-v1-{now.date().isoformat()}"
            examples = _build_training_examples(
                args=args,
                positives_by_user=positives_by_user,
                users=users,
                holdout=holdout,
                seen_by_user=seen_by_user,
                impression_position_by_user_event=impression_position_by_user_event,
                implicit_interest_tags_by_user=implicit_interest_tags_by_user,
                implicit_categories_by_user=implicit_categories_by_user,
                implicit_city_by_user=implicit_city_by_user,
                negative_weights=negative_weights,
                events=events,
                all_event_ids=all_event_ids,
                now=now,
            )
            if not examples:
                print("No training data found (no registrations/favorites/interactions); nothing to do.")
                return 0

            n_features = len(examples[0][0])
            if n_features != len(FEATURE_NAMES):
                print(f"[error] feature vector length mismatch: expected={len(FEATURE_NAMES)} got={n_features}")
                return 2

            weights = _train_log_regression_sgd(
                examples=examples,
                n_features=n_features,
                epochs=args.epochs,
                lr=args.lr,
                l2=args.l2,
                seed=args.seed,
            )

            hitrate = _evaluate_hitrate_at_k(
                weights=weights,
                users=users,
                events=events,
                positives_holdout=holdout,
                all_event_ids=all_event_ids,
                now=now,
                k=10,
                negatives_per_user=args.eval_negatives,
                seed=args.seed,
            )
            print(f"[eval] hitrate@10={hitrate:.3f} users={len(holdout)}")

            if args.dry_run:
                print("[write] dry-run enabled; skipping DB writes.")
                return 0

            meta = {
                "hitrate_at_10": float(hitrate),
                "trained_at": now.isoformat(),
                "examples": len(examples),
                "epochs": int(args.epochs),
                "lr": float(args.lr),
                "l2": float(args.l2),
                "negatives_per_positive": int(args.negatives_per_positive),
            }
            _persist_model_state(db=db, models=models, model_version=model_version, weights=weights, meta=meta)

        if args.dry_run:
            print("[write] dry-run enabled; skipping DB writes.")
            return 0

        if model_version is None or weights is None:
            return 0
        eligible_event_ids = _eligible_event_ids(events, now)
        db.query(models.UserRecommendation).filter(models.UserRecommendation.user_id.in_(user_ids)).delete(
            synchronize_session=False
        )
        inserts = _build_recommendation_rows(
            user_ids=user_ids,
            users=users,
            user_lang=user_lang,
            registered_event_ids_by_user=registered_event_ids_by_user,
            eligible_event_ids=eligible_event_ids,
            events=events,
            weights=weights,
            args=args,
            model_version=model_version,
            now=now,
            models=models,
        )
        db.add_all(inserts)
        db.commit()
        print(f"[write] stored {len(inserts)} recommendations (model_version={model_version})")

    print(f"Done. See docs/recommendations-ml.md for operational guidance (repo: {repo_root}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
