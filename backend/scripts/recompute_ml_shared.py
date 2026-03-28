#!/usr/bin/env python3
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone


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


@dataclass(frozen=True)
class _PreparedState:
    user_ids: list[int]
    events: dict[int, _EventFeatures]
    all_event_ids: list[int]
    registered_event_ids_by_user: dict[int, set[int]]
    positives_by_user: dict[int, dict[int, float]]
    negative_weights: dict[tuple[int, int], float]
    seen_by_user: dict[int, set[int]]
    impression_position_by_user_event: dict[tuple[int, int], int]
    implicit_interest_tags_by_user: dict[int, set[str]]
    implicit_categories_by_user: dict[int, set[str]]
    implicit_city_by_user: dict[int, str]
    users: dict[int, _UserFeatures]
    user_lang: dict[int, str]
    holdout: dict[int, int]


@dataclass(frozen=True)
class _EvaluationState:
    weights: list[float]
    users: dict[int, _UserFeatures]
    events: dict[int, _EventFeatures]
    positives_holdout: dict[int, int]
    all_event_ids: list[int]
    now: datetime
    k: int
    negatives_per_user: int
    seed: int


@dataclass(frozen=True)
class _EvaluationDependencies:
    rng_factory: object
    build_feature_vector: object
    sigmoid: object
    dot: object


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


def _tag_overlap_ratios(*, user: _UserFeatures, event: _EventFeatures) -> tuple[float, float]:
    tags = event.tags
    tag_count = max(1, len(tags))
    overlap_interest = sum(float(user.interest_tag_weights.get(tag, 0.0)) for tag in tags)
    overlap_history = len(user.history_tags & tags)
    return overlap_interest / tag_count, overlap_history / tag_count


def _same_city_score(*, user: _UserFeatures, event: _EventFeatures) -> float:
    if user.city and event.city and user.city == event.city:
        return 1.0
    if event.city:
        return float(user.city_weights.get(event.city, 0.0))
    return 0.0


def _category_match_score(*, user: _UserFeatures, event: _EventFeatures) -> float:
    if event.category and event.category in user.history_categories:
        return 1.0
    if event.category:
        return float(user.category_weights.get(event.category, 0.0))
    return 0.0


def _days_until_score(*, event: _EventFeatures, now: datetime) -> float:
    if not event.start_time:
        return 0.0
    delta_days = (event.start_time - now).total_seconds() / 86400.0
    return max(0.0, min(delta_days / 180.0, 1.0))


def _build_feature_vector(*, user: _UserFeatures, event: _EventFeatures, now: datetime) -> list[float]:
    overlap_interest_ratio, overlap_history_ratio = _tag_overlap_ratios(user=user, event=event)
    same_city = _same_city_score(user=user, event=event)
    category_match = _category_match_score(user=user, event=event)
    organizer_match = 1.0 if event.owner_id in user.history_organizer_ids else 0.0
    popularity = min(math.log1p(event.seats_taken) / 5.0, 1.0)
    days_until = _days_until_score(event=event, now=now)
    return [
        1.0,
        overlap_interest_ratio,
        overlap_history_ratio,
        same_city,
        category_match,
        organizer_match,
        popularity,
        days_until,
    ]


def _weighted_overlap_tags(*, user: _UserFeatures, event: _EventFeatures) -> list[tuple[str, float]]:
    overlap: list[tuple[str, float]] = []
    for tag in event.tags:
        weight = float(user.interest_tag_weights.get(tag, 0.0))
        if weight > 0:
            overlap.append((tag, weight))
    overlap.sort(key=lambda item: (-item[1], item[0]))
    return overlap


def _interest_reason(*, overlap: list[tuple[str, float]], lang: str) -> str:
    top = ", ".join(tag for tag, _weight in overlap[:3])
    return f"Your interests: {top}" if lang == "en" else f"Interesele tale: {top}"


def _event_is_local_for_user(*, user: _UserFeatures, event: _EventFeatures) -> bool:
    return bool(user.city and event.city and user.city == event.city)


def _reason_for(*, user: _UserFeatures, event: _EventFeatures, lang: str) -> str:
    overlap = _weighted_overlap_tags(user=user, event=event)
    if overlap:
        return _interest_reason(overlap=overlap, lang=lang)
    if _event_is_local_for_user(user=user, event=event):
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
            for index, xi in enumerate(x):
                weights[index] -= lr * (err * xi + l2 * weights[index])

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
    rng,
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
    build_feature_vector,
    sigmoid,
    dot,
) -> list[tuple[float, int]]:
    scored: list[tuple[float, int]] = []
    for event_id in candidate_event_ids:
        event = events.get(event_id)
        if not event:
            continue
        features = build_feature_vector(user=user, event=event, now=now)
        scored.append((sigmoid(dot(weights, features)), event_id))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


def evaluate_hitrate_at_k_impl(*, state: _EvaluationState, deps: _EvaluationDependencies) -> float:
    rng = deps.rng_factory(int(state.seed))
    hits = 0
    total = 0

    for user_id, pos_event_id in state.positives_holdout.items():
        user = state.users.get(user_id)
        pos_event = state.events.get(pos_event_id)
        if not user or not pos_event:
            continue

        negatives = _sample_negative_event_ids(
            rng=rng,
            all_event_ids=state.all_event_ids,
            positive_event_id=pos_event_id,
            negatives_per_user=int(state.negatives_per_user),
        )
        scored = _score_candidate_event_ids(
            weights=state.weights,
            user=user,
            events=state.events,
            candidate_event_ids=[pos_event_id, *negatives],
            now=state.now,
            build_feature_vector=deps.build_feature_vector,
            sigmoid=deps.sigmoid,
            dot=deps.dot,
        )
        top_k = {event_id for _score, event_id in scored[: int(state.k)]}
        total += 1
        if pos_event_id in top_k:
            hits += 1

    return hits / max(1, total)
