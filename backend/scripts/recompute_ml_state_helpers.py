#!/usr/bin/env python3
"""Command-line helper: recompute ml state helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from recompute_ml_interactions import _load_interaction_signals
from recompute_ml_loading import (
    _build_positive_weights,
    _build_registered_event_ids_by_user,
    _load_event_features,
    _load_interest_tag_weights,
    _load_optional_implicit_weights,
    _load_registration_and_favorite_rows,
    _load_students,
)
from recompute_ml_shared import (
    FEATURE_NAMES,
    _EventFeatures,
    _PreparedState,
    _UserFeatures,
    _normalize_category,
    _normalize_city,
)


def _resolved_user_city(
    *, student, user_id: int, implicit_city_by_user, city_weights_by_user
) -> str | None:
    """Implements the resolved user city helper."""
    city = _normalize_city(student.city) or implicit_city_by_user.get(user_id)
    if city:
        return city
    city_preferences = city_weights_by_user.get(user_id, {})
    if not city_preferences:
        return None
    return max(city_preferences.items(), key=lambda item: item[1])[0]


def _preferred_lang(language_preference: str | None) -> str:
    """Implements the preferred lang helper."""
    return "en" if (language_preference or "system").strip().lower() == "en" else "ro"


def _holdout_positive_event_ids(*, user_id: int, positives, holdout, rng) -> list[int]:
    """Implements the holdout positive event ids helper."""
    positive_event_ids = list(positives.keys())
    if len(positive_event_ids) < 2:
        return positive_event_ids
    holdout_event = rng.choice(positive_event_ids)
    holdout[user_id] = holdout_event
    positives.pop(holdout_event, None)
    return positive_event_ids


def _history_from_positive_events(
    *, positive_event_ids: list[int], events, implicit_categories: set[str]
) -> tuple[set[str], set[str], set[int]]:
    """Implements the history from positive events helper."""
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
    history_categories |= implicit_categories
    return history_tags, history_categories, history_organizers


def _selected_model_row(*, db, models, requested_model_version: str | None):
    """Implements the selected model row helper."""
    model_query = db.query(models.RecommenderModel)
    if requested_model_version:
        model_row = model_query.filter(
            models.RecommenderModel.model_version == requested_model_version
        ).first()
        if model_row is not None:
            return model_row
    is_active_attr = "is_active"
    model_row = (
        model_query.filter(getattr(models.RecommenderModel, is_active_attr).is_(True))
        .order_by(models.RecommenderModel.id.desc())
        .first()
    )
    if model_row is not None:
        return model_row
    return model_query.order_by(models.RecommenderModel.id.desc()).first()


def _validated_persisted_model(
    model_row,
) -> tuple[str | None, list[float] | None, int | None]:
    """Implements the validated persisted model helper."""
    if model_row is None:
        print(
            "[warn] no persisted recommender model found; run the retraining job first"
        )
        return None, None, 0
    feature_names = list(model_row.feature_names or [])
    weights = [float(weight) for weight in (model_row.weights or [])]
    if feature_names != FEATURE_NAMES:
        print(
            "[error] persisted model feature_names mismatch: "
            f"expected={FEATURE_NAMES} got={feature_names}"
        )
        return None, None, 2
    if len(weights) != len(FEATURE_NAMES):
        print(
            "[error] persisted model weights length mismatch: "
            f"expected={len(FEATURE_NAMES)} got={len(weights)}"
        )
        return None, None, 2
    return str(model_row.model_version), weights, None


def _load_persisted_model_state(
    *, db, models, requested_model_version: str | None
) -> tuple[str | None, list[float] | None, int | None]:
    """Loads the persisted model state resource."""
    model_row = _selected_model_row(
        db=db, models=models, requested_model_version=requested_model_version
    )
    model_version, weights, exit_code = _validated_persisted_model(model_row)
    if exit_code is not None:
        return model_version, weights, exit_code
    print(f"[load] using persisted model_version={model_version}")
    return model_version, weights, None


def _positive_weights_by_user(positive_weights) -> dict[int, dict[int, float]]:
    """Implements the positive weights by user helper."""
    positives_by_user: dict[int, dict[int, float]] = {}
    for (user_id, event_id), weight in positive_weights.items():
        positives_by_user.setdefault(user_id, {})[event_id] = weight
    return positives_by_user


# pylint: disable-next=too-many-arguments
def _load_decay_weight_buckets(
    *, db, models, args, now: datetime, decay_lambda: float, max_score: float
):
    """Loads the decay weight buckets resource."""
    interest_tag_weights_by_user = _load_interest_tag_weights(
        db=db,
        models=models,
        user_id=args.user_id,
        now=now,
        decay_lambda=decay_lambda,
        max_score=max_score,
    )
    category_weights_by_user = _load_optional_implicit_weights(
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
    return interest_tag_weights_by_user, category_weights_by_user, city_weights_by_user


def _interaction_training_state(*, db, models, args):
    """Implements the interaction training state helper."""
    reg_rows, fav_rows = _load_registration_and_favorite_rows(
        db=db, models=models, user_id=args.user_id
    )
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
    return (
        registered_event_ids_by_user,
        positive_weights,
        negative_weights,
        seen_by_user,
        impression_position_by_user_event,
        implicit_interest_tags_by_user,
        implicit_categories_by_user,
        implicit_city_by_user,
    )


def _prepared_state_from_loaded_data(**kwargs) -> _PreparedState:
    """Implements the prepared state from loaded data helper."""
    positives_by_user = _positive_weights_by_user(kwargs["positive_weights"])
    return _PreparedState(
        user_ids=kwargs["user_ids"],
        events=kwargs["events"],
        all_event_ids=kwargs["all_event_ids"],
        registered_event_ids_by_user=kwargs["registered_event_ids_by_user"],
        positives_by_user=positives_by_user,
        negative_weights=kwargs["negative_weights"],
        seen_by_user=kwargs["seen_by_user"],
        impression_position_by_user_event=kwargs["impression_position_by_user_event"],
        implicit_interest_tags_by_user=kwargs["implicit_interest_tags_by_user"],
        implicit_categories_by_user=kwargs["implicit_categories_by_user"],
        implicit_city_by_user=kwargs["implicit_city_by_user"],
        users=kwargs["users"],
        user_lang=kwargs["user_lang"],
        holdout=kwargs["holdout"],
    )


def _student_event_state(*, db, models, func, args):
    """Implements the student event state helper."""
    students = _load_students(db=db, models=models, user_id=args.user_id)
    if not students:
        print("No student users found; nothing to do.")
        return None, None, None
    events = _load_event_features(db=db, models=models, func=func)
    all_event_ids = list(events.keys())
    if not all_event_ids:
        print("No events found; nothing to do.")
        return None, None, None
    return students, events, all_event_ids


def _training_meta(
    *,
    args,
    now: datetime,
    examples: list[tuple[list[float], int, float]],
    hitrate: float,
) -> dict[str, float | int | str]:
    """Implements the training meta helper."""
    return {
        "hitrate_at_10": float(hitrate),
        "trained_at": now.isoformat(),
        "examples": len(examples),
        "epochs": int(args.epochs),
        "lr": float(args.lr),
        "l2": float(args.l2),
        "negatives_per_positive": int(args.negatives_per_positive),
    }


def _feature_length_is_valid(
    examples: list[tuple[list[float], int, float]],
) -> tuple[int, int | None]:
    """Implements the feature length is valid helper."""
    n_features = len(examples[0][0])
    if n_features == len(FEATURE_NAMES):
        return n_features, None
    print(
        "[error] feature vector length mismatch: "
        f"expected={len(FEATURE_NAMES)} got={n_features}"
    )
    return n_features, 2


def _persist_model_state(
    *, db, models, model_version: str, weights: list[float], meta: dict
) -> None:
    """Implements the persist model state helper."""
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
        existing_model.is_active = True

    db.query(models.RecommenderModel).filter(
        models.RecommenderModel.model_version != model_version
    ).update(
        {"is_active": False},
        synchronize_session=False,
    )


def _event_is_eligible(*, event: _EventFeatures, now: datetime) -> bool:
    """Implements the event is eligible helper."""
    if event.status != "published":
        return False
    if event.publish_at and event.publish_at > now:
        return False
    if event.start_time and event.start_time < now:
        return False
    if event.max_seats is not None and event.seats_taken >= event.max_seats:
        return False
    return True


def _eligible_event_ids(events: dict[int, _EventFeatures], now: datetime) -> list[int]:
    """Implements the eligible event ids helper."""
    return [
        event_id
        for event_id, event in events.items()
        if _event_is_eligible(event=event, now=now)
    ]


@dataclass(frozen=True)
class _RecommendationBuildState:
    """Recommendation Build State value object used in the surrounding module."""

    user_ids: list[int]
    users: dict[int, _UserFeatures]
    user_lang: dict[int, str]
    registered_event_ids_by_user: dict[int, set[int]]
    eligible_event_ids: list[int]
    events: dict[int, _EventFeatures]
    weights: list[float]
    args: object
    model_version: str
    now: datetime
    models: object


@dataclass(frozen=True)
class _RecommendationDependencies:
    """Recommendation Dependencies value object used in the surrounding module."""

    build_feature_vector: Callable[..., list[float]]
    reason_for: Callable[..., str]
    sigmoid: Callable[[float], float]
    dot: Callable[[list[float], list[float]], float]


def build_recommendation_rows_impl(
    *, state: _RecommendationBuildState, deps: _RecommendationDependencies
):
    """Constructs a recommendation rows impl structure."""
    inserts = []
    for user_id in state.user_ids:
        user = state.users[user_id]
        registered_ids = state.registered_event_ids_by_user.get(user_id, set())
        scored = [
            (
                deps.sigmoid(
                    deps.dot(
                        state.weights,
                        deps.build_feature_vector(
                            user=user, event=state.events[event_id], now=state.now
                        ),
                    )
                ),
                event_id,
            )
            for event_id in state.eligible_event_ids
            if event_id not in registered_ids
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        top = scored[: max(0, int(state.args.top_n))]
        student_lang = state.user_lang.get(user_id, "ro")
        inserts.extend(
            state.models.UserRecommendation(
                user_id=user_id,
                event_id=event_id,
                score=float(score),
                rank=rank,
                model_version=state.model_version,
                reason=deps.reason_for(
                    user=user, event=state.events[event_id], lang=student_lang
                ),
            )
            for rank, (score, event_id) in enumerate(top, start=1)
        )
    return inserts
