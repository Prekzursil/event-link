#!/usr/bin/env python3
"""Command-line helper: recompute recommendations ml."""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from recompute_ml_shared import (  # noqa: E402
    FEATURE_NAMES,
    _DeterministicRng,
    _EvaluationDependencies,
    _EvaluationState,
    _EventFeatures,
    _PreparedState,
    _UserFeatures,
    _build_feature_vector,
    _coerce_utc,
    _dot,
    _impression_negative_weight,
    _normalize_category,
    _normalize_city,
    _normalize_tag,
    _reason_for,
    _sigmoid,
    _train_log_regression_sgd,
    evaluate_hitrate_at_k_impl,
)
from recompute_ml_prepare_state import _prepare_state  # noqa: E402
from recompute_ml_state_helpers import (  # noqa: E402
    _RecommendationBuildState,
    _RecommendationDependencies,
    _eligible_event_ids,
    _feature_length_is_valid,
    _load_persisted_model_state as _load_persisted_model_state_impl,
    _persist_model_state,
    _selected_model_row,
    _training_meta,
    build_recommendation_rows_impl,
)

__all__ = (
    "FEATURE_NAMES",
    "_DeterministicRng",
    "_EventFeatures",
    "_PreparedState",
    "_UserFeatures",
    "_build_feature_vector",
    "_coerce_utc",
    "_dot",
    "_eligible_event_ids",
    "_evaluate_hitrate_at_k",
    "_impression_negative_weight",
    "_normalize_category",
    "_normalize_city",
    "_normalize_tag",
    "_prepare_state",
    "_reason_for",
    "_selected_model_row",
    "_sigmoid",
    "_train_log_regression_sgd",
    "main",
)


def _parse_args() -> argparse.Namespace:
    """Implements the parse args helper."""
    parser = argparse.ArgumentParser(
        description=(
            "Offline ML v1: train and cache recommendations to user_recommendations."
        )
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=50,
        help="How many recommendations to store per user.",
    )
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--lr", type=float, default=0.35)
    parser.add_argument("--l2", type=float, default=0.01)
    parser.add_argument("--negatives-per-positive", type=int, default=3)
    parser.add_argument("--eval-negatives", type=int, default=50)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument(
        "--user-id",
        type=int,
        default=None,
        help="Only recompute recommendations for a single student user.",
    )
    parser.add_argument(
        "--skip-training",
        action="store_true",
        help=(
            "Skip training and load weights from "
            "the persisted recommender_models table."
        ),
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Train/eval but do not write to the DB."
    )
    return parser.parse_args()


def _bootstrap_script_environment() -> Path:
    """Implements the bootstrap script environment helper."""
    repo_root = Path(__file__).resolve().parents[2]
    backend_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend_root))
    os.environ.setdefault("SECRET_KEY", "offline-ml-secret")
    os.environ.setdefault("EMAIL_ENABLED", "false")
    return repo_root


def _load_runtime_objects():
    """Loads the runtime objects resource."""
    from app import models  # noqa: PLC0415
    from app.config import settings  # noqa: PLC0415
    from app.database import SessionLocal  # noqa: PLC0415
    from sqlalchemy import func  # noqa: PLC0415

    return models, settings, SessionLocal, func


def _evaluate_hitrate_at_k(**kwargs) -> float:
    """Implements the evaluate hitrate at k helper."""
    return evaluate_hitrate_at_k_impl(
        state=_EvaluationState(**kwargs),
        deps=_EvaluationDependencies(
            rng_factory=_DeterministicRng,
            build_feature_vector=_build_feature_vector,
            sigmoid=_sigmoid,
            dot=_dot,
        ),
    )


def _load_persisted_model_state(
    *, db, models, requested_model_version: str | None
) -> tuple[str | None, list[float] | None, int | None]:
    """Loads the persisted model state resource."""
    return _load_persisted_model_state_impl(
        db=db,
        models=models,
        requested_model_version=requested_model_version,
    )


def _user_positive_ids(*, user_id: int, positives, holdout) -> set[int]:
    """Implements the user positive ids helper."""
    return set(positives.keys()) | ({holdout[user_id]} if user_id in holdout else set())


def _impression_negative_ids(
    *,
    user_id: int,
    user_positive_ids: set[int],
    seen_by_user,
    impression_position_by_user_event,
    events,
) -> list[int]:
    """Implements the impression negative ids helper."""
    impression_candidates = [
        (event_id, impression_position_by_user_event.get((user_id, event_id), 999))
        for event_id in (seen_by_user.get(user_id, set()) - user_positive_ids)
        if event_id in events
    ]
    impression_candidates.sort(key=lambda item: item[1])
    return [event_id for event_id, _position in impression_candidates[:50]]


def _append_example(
    *, examples, user, event, now: datetime, label: int, weight: float
) -> None:
    """Implements the append example helper."""
    examples.append(
        (_build_feature_vector(user=user, event=event, now=now), label, float(weight))
    )


def _sample_negative_example(
    *,
    rng,
    impression_negatives: list[int],
    impression_position_by_user_event,
    user_id: int,
    all_event_ids: list[int],
) -> tuple[int, float]:
    """Implements the sample negative example helper."""
    if impression_negatives:
        neg_event_id = rng.choice(impression_negatives)
        neg_weight = _impression_negative_weight(
            impression_position_by_user_event.get((user_id, neg_event_id))
        )
        return neg_event_id, neg_weight
    return rng.choice(all_event_ids), 1.0


def _append_positive_examples(**kwargs) -> None:
    """Implements the append positive examples helper."""
    for event_id, weight in kwargs["positives"].items():
        event = kwargs["events"].get(event_id)
        if not event:
            continue
        _append_example(
            examples=kwargs["examples"],
            user=kwargs["user"],
            event=event,
            now=kwargs["now"],
            label=1,
            weight=weight,
        )
        neg_added = 0
        max_attempts = len(kwargs["all_event_ids"])
        while (
            neg_added < int(kwargs["negatives_per_positive"])
            and neg_added < max_attempts
        ):
            neg_event_id, neg_weight = _sample_negative_example(
                rng=kwargs["rng"],
                impression_negatives=kwargs["impression_negatives"],
                impression_position_by_user_event=kwargs[
                    "impression_position_by_user_event"
                ],
                user_id=int(kwargs["user_id"]),
                all_event_ids=kwargs["all_event_ids"],
            )
            if neg_event_id in kwargs["user_positive_ids"]:
                continue
            _append_example(
                examples=kwargs["examples"],
                user=kwargs["user"],
                event=kwargs["events"][neg_event_id],
                now=kwargs["now"],
                label=0,
                weight=neg_weight,
            )
            neg_added += 1


def _matches_weak_signal(
    *,
    candidate_event: _EventFeatures,
    weak_tags: set[str],
    weak_categories: set[str],
    weak_city: str | None,
) -> bool:
    """Implements the matches weak signal helper."""
    matches_city = bool(
        weak_city
        and candidate_event.city
        and _normalize_city(candidate_event.city) == weak_city
    )
    matches_category = bool(
        candidate_event.category and candidate_event.category in weak_categories
    )
    matches_tags = bool(weak_tags and (candidate_event.tags & weak_tags))
    return matches_city or matches_category or matches_tags


def _next_weak_signal_candidate(
    *, kwargs, weak_tags: set[str], weak_categories: set[str], weak_city: str | None
):
    """Implements the next weak signal candidate helper."""
    candidate_id = kwargs["rng"].choice(kwargs["all_event_ids"])
    if candidate_id in kwargs["user_positive_ids"]:
        return None
    candidate_event = kwargs["events"][candidate_id]
    if not _matches_weak_signal(
        candidate_event=candidate_event,
        weak_tags=weak_tags,
        weak_categories=weak_categories,
        weak_city=weak_city,
    ):
        return None
    return candidate_event


def _event_id_for_features(
    events: dict[int, _EventFeatures], candidate_event: _EventFeatures
) -> int:
    """Implements the event id for features helper."""
    for event_id, event in events.items():
        if event is candidate_event:
            return event_id
    raise KeyError("candidate event not found")


def _append_weak_signal_examples(**kwargs) -> None:
    """Implements the append weak signal examples helper."""
    weak_tags = kwargs["weak_tags"]
    weak_categories = kwargs["weak_categories"]
    weak_city = kwargs["weak_city"]
    if not (weak_tags or weak_categories or weak_city):
        return
    added = 0
    attempts = 0
    while added < 3 and attempts < 200 and attempts < len(kwargs["all_event_ids"]):
        attempts += 1
        candidate_event = _next_weak_signal_candidate(
            kwargs=kwargs,
            weak_tags=weak_tags,
            weak_categories=weak_categories,
            weak_city=weak_city,
        )
        if candidate_event is None:
            continue
        _append_example(
            examples=kwargs["examples"],
            user=kwargs["user"],
            event=candidate_event,
            now=kwargs["now"],
            label=1,
            weight=0.15,
        )
        kwargs["user_positive_ids"].add(
            _event_id_for_features(kwargs["events"], candidate_event)
        )
        added += 1


def _append_negative_feedback_examples(
    *, examples, negative_weights, users, events, now: datetime
) -> None:
    """Implements the append negative feedback examples helper."""
    for (user_id, event_id), weight in negative_weights.items():
        user = users.get(user_id)
        event = events.get(event_id)
        if not user or not event:
            continue
        _append_example(
            examples=examples, user=user, event=event, now=now, label=0, weight=weight
        )


def _append_user_training_examples(*, kwargs, examples, rng) -> None:
    """Implements the append user training examples helper."""
    for user_id, positives in kwargs["positives_by_user"].items():
        user = kwargs["users"].get(user_id)
        if not user:
            continue
        user_positive_ids = _user_positive_ids(
            user_id=user_id, positives=positives, holdout=kwargs["holdout"]
        )
        impression_negatives = _impression_negative_ids(
            user_id=user_id,
            user_positive_ids=user_positive_ids,
            seen_by_user=kwargs["seen_by_user"],
            impression_position_by_user_event=kwargs[
                "impression_position_by_user_event"
            ],
            events=kwargs["events"],
        )
        _append_positive_examples(
            examples=examples,
            positives=positives,
            user=user,
            user_id=user_id,
            user_positive_ids=user_positive_ids,
            events=kwargs["events"],
            all_event_ids=kwargs["all_event_ids"],
            impression_negatives=impression_negatives,
            impression_position_by_user_event=kwargs[
                "impression_position_by_user_event"
            ],
            negatives_per_positive=kwargs["args"].negatives_per_positive,
            now=kwargs["now"],
            rng=rng,
        )
        _append_weak_signal_examples(
            examples=examples,
            user=user,
            user_positive_ids=user_positive_ids,
            weak_tags=kwargs["implicit_interest_tags_by_user"].get(user_id, set()),
            weak_categories=kwargs["implicit_categories_by_user"].get(user_id, set()),
            weak_city=kwargs["implicit_city_by_user"].get(user_id),
            events=kwargs["events"],
            all_event_ids=kwargs["all_event_ids"],
            now=kwargs["now"],
            rng=rng,
        )


def _build_training_examples(**kwargs) -> list[tuple[list[float], int, float]]:
    """Constructs a training examples structure."""
    examples: list[tuple[list[float], int, float]] = []
    rng = _DeterministicRng(int(kwargs["args"].seed))
    _append_user_training_examples(kwargs=kwargs, examples=examples, rng=rng)
    _append_negative_feedback_examples(
        examples=examples,
        negative_weights=kwargs["negative_weights"],
        users=kwargs["users"],
        events=kwargs["events"],
        now=kwargs["now"],
    )
    return examples


def _build_recommendation_rows(**kwargs):
    """Constructs a recommendation rows structure."""
    return build_recommendation_rows_impl(
        state=_RecommendationBuildState(**kwargs),
        deps=_RecommendationDependencies(
            build_feature_vector=_build_feature_vector,
            reason_for=_reason_for,
            sigmoid=_sigmoid,
            dot=_dot,
        ),
    )


def _train_model_state(
    *,
    db,
    models,
    args,
    requested_model_version: str | None,
    state: _PreparedState,
    now: datetime,
) -> tuple[str | None, list[float] | None, int | None]:
    """Implements the train model state helper."""
    model_version = requested_model_version or f"ml-v1-{now.date().isoformat()}"
    examples = _build_training_examples(
        args=args,
        positives_by_user=state.positives_by_user,
        users=state.users,
        holdout=state.holdout,
        seen_by_user=state.seen_by_user,
        impression_position_by_user_event=state.impression_position_by_user_event,
        implicit_interest_tags_by_user=state.implicit_interest_tags_by_user,
        implicit_categories_by_user=state.implicit_categories_by_user,
        implicit_city_by_user=state.implicit_city_by_user,
        negative_weights=state.negative_weights,
        events=state.events,
        all_event_ids=state.all_event_ids,
        now=now,
    )
    if not examples:
        print(
            "No training data found (no registrations/favorites/interactions); "
            "nothing to do."
        )
        return None, None, 0

    n_features, exit_code = _feature_length_is_valid(examples)
    if exit_code is not None:
        return None, None, exit_code

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
        users=state.users,
        events=state.events,
        positives_holdout=state.holdout,
        all_event_ids=state.all_event_ids,
        now=now,
        k=10,
        negatives_per_user=args.eval_negatives,
        seed=args.seed,
    )
    print(f"[eval] hitrate@10={hitrate:.3f} users={len(state.holdout)}")
    meta = _training_meta(args=args, now=now, examples=examples, hitrate=hitrate)
    if not args.dry_run:
        _persist_model_state(
            db=db,
            models=models,
            model_version=model_version,
            weights=weights,
            meta=meta,
        )
    return model_version, weights, None


def _resolve_model_state(
    *,
    db,
    models,
    args,
    requested_model_version: str | None,
    state: _PreparedState,
    now: datetime,
) -> tuple[str | None, list[float] | None, int | None]:
    """Implements the resolve model state helper."""
    if args.skip_training:
        return _load_persisted_model_state(
            db=db,
            models=models,
            requested_model_version=requested_model_version,
        )
    return _train_model_state(
        db=db,
        models=models,
        args=args,
        requested_model_version=requested_model_version,
        state=state,
        now=now,
    )


def _store_recommendations(
    *,
    db,
    models,
    args,
    state: _PreparedState,
    model_version: str | None,
    weights: list[float] | None,
    now: datetime,
) -> int | None:
    """Implements the store recommendations helper."""
    if args.dry_run:
        print("[write] dry-run enabled; skipping DB writes.")
        return 0
    if model_version is None or weights is None:
        return 0

    eligible_event_ids = _eligible_event_ids(state.events, now)
    db.query(models.UserRecommendation).filter(
        models.UserRecommendation.user_id.in_(state.user_ids)
    ).delete(synchronize_session=False)
    inserts = _build_recommendation_rows(
        user_ids=state.user_ids,
        users=state.users,
        user_lang=state.user_lang,
        registered_event_ids_by_user=state.registered_event_ids_by_user,
        eligible_event_ids=eligible_event_ids,
        events=state.events,
        weights=weights,
        args=args,
        model_version=model_version,
        now=now,
        models=models,
    )
    db.add_all(inserts)
    db.commit()
    print(
        f"[write] stored {len(inserts)} recommendations (model_version={model_version})"
    )
    return None


def main() -> int:
    """Implements the main helper."""
    args = _parse_args()
    repo_root = _bootstrap_script_environment()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "Missing DATABASE_URL. Example:\n"
            "  DATABASE_URL=postgresql://... "
            "python backend/scripts/recompute_recommendations_ml.py"
        )
        return 2

    models, settings, session_local_factory, func = _load_runtime_objects()
    now = datetime.now(timezone.utc)
    requested_model_version = os.environ.get("RECOMMENDER_MODEL_VERSION")
    half_life_hours = max(
        1, int(settings.recommendations_online_learning_decay_half_life_hours)
    )
    decay_lambda = math.log(2.0) / (float(half_life_hours) * 3600.0)
    max_score = float(settings.recommendations_online_learning_max_score)

    with session_local_factory() as db:
        state = _prepare_state(
            db=db,
            models=models,
            func=func,
            args=args,
            now=now,
            decay_lambda=decay_lambda,
            max_score=max_score,
        )
        if state is None:
            return 0

        model_version, weights, exit_code = _resolve_model_state(
            db=db,
            models=models,
            args=args,
            requested_model_version=requested_model_version,
            state=state,
            now=now,
        )
        if exit_code is not None:
            return exit_code

        store_exit = _store_recommendations(
            db=db,
            models=models,
            args=args,
            state=state,
            model_version=model_version,
            weights=weights,
            now=now,
        )
        if store_exit is not None:
            return store_exit

    print(
        "Done. See docs/recommendations-ml.md for operational guidance "
        f"(repo: {repo_root})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
